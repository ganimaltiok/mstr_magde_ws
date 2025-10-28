import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from services.settings import get_settings
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Manage nginx cache via filesystem operations."""
    
    def __init__(self):
        self.settings = get_settings()
        self.cache_paths = [
            self.settings.NGINX_CACHE_SHORT,
            self.settings.NGINX_CACHE_DAILY
        ]
    
    def purge_all(self) -> Dict[str, Any]:
        """
        Purge all nginx cache by clearing directory contents (not the directory itself).
        
        Returns:
            {'status': 'success', 'message': str, 'purged_bytes': int}
        """
        total_bytes = 0
        cleared_paths = []
        errors = []
        
        logger.info("Starting cache purge operation...")
        
        try:
            # First try to get size (may fail due to permissions)
            for cache_path in self.cache_paths:
                if cache_path.exists():
                    try:
                        size = self._get_directory_size(cache_path)
                        total_bytes += size
                        logger.info(f"Cache path {cache_path}: {self._format_bytes(size)}")
                    except PermissionError:
                        logger.warning(f"Cannot read cache size for {cache_path} (permission denied)")
                else:
                    logger.info(f"Cache path does not exist: {cache_path}")
            
            # Clear cache directory contents (not the directory itself)
            for cache_path in self.cache_paths:
                if not cache_path.exists():
                    logger.info(f"Skipping non-existent cache path: {cache_path}")
                    continue
                
                logger.info(f"Attempting to clear cache: {cache_path}")
                
                try:
                    # Remove all files and subdirectories inside
                    items_cleared = 0
                    for item in cache_path.iterdir():
                        if item.is_file():
                            item.unlink()
                            items_cleared += 1
                            logger.debug(f"Deleted file: {item}")
                        elif item.is_dir():
                            shutil.rmtree(item)
                            items_cleared += 1
                            logger.debug(f"Deleted directory: {item}")
                    
                    logger.info(f"Successfully cleared {items_cleared} items from {cache_path}")
                    cleared_paths.append(str(cache_path))
                    
                except PermissionError as pe:
                    # Try sudo fallback only on Linux (where sudo is configured with NOPASSWD)
                    logger.warning(f"Permission denied for {cache_path}, attempting sudo fallback...")
                    
                    try:
                        result = subprocess.run(
                            ['sudo', 'find', str(cache_path), '-mindepth', '1', '-delete'],
                            capture_output=True,
                            text=True,
                            timeout=10,
                            check=False
                        )
                        
                        if result.returncode == 0:
                            logger.info(f"Successfully cleared {cache_path} using sudo")
                            cleared_paths.append(str(cache_path))
                        else:
                            error_msg = f"Sudo command failed for {cache_path}: {result.stderr}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                    
                    except FileNotFoundError:
                        # sudo command not found or not available
                        error_msg = f"Permission denied and sudo not available for {cache_path}. Run on production server or fix permissions manually."
                        logger.error(error_msg)
                        errors.append(error_msg)
                    
                    except subprocess.TimeoutExpired:
                        error_msg = f"Sudo command timed out for {cache_path}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                    
                    except Exception as e:
                        error_msg = f"Sudo fallback failed for {cache_path}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
            
            # Build response
            if cleared_paths and not errors:
                message = f"Successfully cleared {len(cleared_paths)} cache directories"
                if total_bytes:
                    message += f" ({self._format_bytes(total_bytes)} freed)"
                logger.info(message)
                return {
                    'status': 'success',
                    'message': message,
                    'purged_bytes': total_bytes,
                    'cleared_paths': cleared_paths
                }
            
            elif cleared_paths and errors:
                message = f"Partially cleared {len(cleared_paths)} of {len(self.cache_paths)} caches. Errors: {'; '.join(errors)}"
                logger.warning(message)
                return {
                    'status': 'warning',
                    'message': message,
                    'purged_bytes': total_bytes,
                    'cleared_paths': cleared_paths,
                    'errors': errors
                }
            
            else:
                message = f"Failed to clear any caches. Errors: {'; '.join(errors)}"
                logger.error(message)
                return {
                    'status': 'error',
                    'message': message,
                    'purged_bytes': 0,
                    'errors': errors
                }
        
        except Exception as e:
            error_msg = f"Unexpected error during cache purge: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'message': error_msg,
                'purged_bytes': 0
            }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            {
                'total_size': int,
                'short_cache_size': int,
                'daily_cache_size': int,
                'total_files': int,
                'error': str or None
            }
        """
        stats = {
            'total_size': 0,
            'short_cache_size': 0,
            'daily_cache_size': 0,
            'total_files': 0,
            'error': None
        }
        
        try:
            if self.settings.NGINX_CACHE_SHORT.exists():
                try:
                    short_size = self._get_directory_size(self.settings.NGINX_CACHE_SHORT)
                    short_files = self._count_files(self.settings.NGINX_CACHE_SHORT)
                    stats['short_cache_size'] = short_size
                    stats['total_size'] += short_size
                    stats['total_files'] += short_files
                except PermissionError:
                    stats['error'] = 'Permission denied - cache directories owned by nginx/www-data'
            
            if self.settings.NGINX_CACHE_DAILY.exists():
                try:
                    daily_size = self._get_directory_size(self.settings.NGINX_CACHE_DAILY)
                    daily_files = self._count_files(self.settings.NGINX_CACHE_DAILY)
                    stats['daily_cache_size'] = daily_size
                    stats['total_size'] += daily_size
                    stats['total_files'] += daily_files
                except PermissionError:
                    if not stats['error']:
                        stats['error'] = 'Permission denied - cache directories owned by nginx/www-data'
        
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            stats['error'] = str(e)
        
        return stats
    
    def _get_directory_size(self, path: Path) -> int:
        """Get total size of directory in bytes."""
        total = 0
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total
    
    def _count_files(self, path: Path) -> int:
        """Count total files in directory."""
        return sum(1 for item in path.rglob("*") if item.is_file())
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes to human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f} TB"


# Singleton instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get cache manager singleton."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
