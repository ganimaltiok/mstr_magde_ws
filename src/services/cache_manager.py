import shutil
import subprocess
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from services.settings import get_settings
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Manage nginx cache via filesystem operations."""
    
    def __init__(self):
        self.settings = get_settings()
        # Unified cache path (10-minute cache for all endpoints)
        self.cache_paths = [
            Path('/var/cache/nginx/apicache')
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
                
                logger.info(f"Processing cache directory: {cache_path}")
                
                try:
                    # Check if directory is empty
                    items = list(cache_path.iterdir())
                    
                    if not items:
                        logger.info(f"Cache directory is empty, nothing to clear: {cache_path}")
                        cleared_paths.append(str(cache_path))  # Still count as success
                        continue
                    
                    # Remove all files and subdirectories inside
                    items_cleared = 0
                    for item in items:
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
                    # Try sudo fallback (configured with NOPASSWD on production)
                    logger.warning(f"Permission denied for {cache_path}, attempting sudo fallback...")
                    
                    try:
                        # Use absolute path to sudo to avoid PATH issues
                        sudo_cmd = '/usr/bin/sudo'
                        
                        # First check if directory is empty using sudo
                        check_result = subprocess.run(
                            [sudo_cmd, 'find', str(cache_path), '-mindepth', '1', '-maxdepth', '1', '-print', '-quit'],
                            capture_output=True,
                            text=True,
                            timeout=5,
                            check=False
                        )
                        
                        if check_result.returncode == 0 and not check_result.stdout.strip():
                            logger.info(f"Directory is empty (checked with sudo): {cache_path}")
                            cleared_paths.append(str(cache_path))
                            continue
                        
                        # Clear the cache directory
                        result = subprocess.run(
                            [sudo_cmd, 'find', str(cache_path), '-mindepth', '1', '-delete'],
                            capture_output=True,
                            text=True,
                            timeout=30,
                            check=False
                        )
                        
                        if result.returncode == 0:
                            logger.info(f"Successfully cleared {cache_path} using sudo")
                            cleared_paths.append(str(cache_path))
                        else:
                            error_msg = f"Sudo command failed for {cache_path}: {result.stderr or result.stdout}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                    
                    except FileNotFoundError:
                        # sudo command not found or not available
                        error_msg = f"Permission denied for {cache_path}. Sudo not available (development environment). Deploy to production server for cache clearing."
                        logger.warning(error_msg)
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
        Get cache statistics for unified cache.
        
        Returns:
            {
                'total_size': int,
                'cache_size': int,
                'total_files': int,
                'error': str or None
            }
        """
        stats = {
            'total_size': 0,
            'cache_size': 0,
            'total_files': 0,
            'error': None
        }
        
        try:
            cache_path = self.cache_paths[0]  # Unified cache
            if cache_path.exists():
                try:
                    cache_size = self._get_directory_size(cache_path)
                    cache_files = self._count_files(cache_path)
                    stats['cache_size'] = cache_size
                    stats['total_size'] = cache_size
                    stats['total_files'] = cache_files
                except PermissionError:
                    # Try with sudo
                    size, files = self._get_cache_stats_with_sudo(cache_path)
                    if size is not None:
                        stats['cache_size'] = size
                        stats['total_size'] = size
                        stats['total_files'] = files
                    else:
                        stats['error'] = 'Permission denied reading cache'
        
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}", exc_info=True)
            stats['error'] = str(e)
        
        return stats
    
    def _get_directory_size(self, path: Path) -> int:
        """Get total size of directory in bytes."""
        total = 0
        accessible_items = 0
        permission_errors = 0
        
        try:
            # Walk the directory tree manually to catch permission errors
            for root, dirs, files in os.walk(path):
                try:
                    for file in files:
                        try:
                            file_path = Path(root) / file
                            total += file_path.stat().st_size
                            accessible_items += 1
                        except (PermissionError, OSError) as e:
                            permission_errors += 1
                            logger.debug(f"Permission denied accessing {file_path}: {e}")
                except PermissionError as e:
                    permission_errors += 1
                    logger.debug(f"Permission denied accessing directory {root}: {e}")
            
            # If we found permission errors but no accessible items, we need sudo
            if permission_errors > 0 and accessible_items == 0:
                logger.info(f"No accessible items found in {path}, triggering sudo fallback")
                raise PermissionError(f"Cannot access cache files in {path}")
                
        except PermissionError:
            raise
            
        return total
    
    def _count_files(self, path: Path) -> int:
        """Count total files in directory."""
        count = 0
        permission_errors = 0
        
        try:
            for root, dirs, files in os.walk(path):
                try:
                    for file in files:
                        try:
                            # Just checking if we can access it
                            file_path = Path(root) / file
                            file_path.stat()
                            count += 1
                        except (PermissionError, OSError):
                            permission_errors += 1
                except PermissionError:
                    permission_errors += 1
            
            # If we found permission errors but no accessible files, we need sudo
            if permission_errors > 0 and count == 0:
                logger.info(f"No accessible files found in {path}, triggering sudo fallback")
                raise PermissionError(f"Cannot access cache files in {path}")
                
        except PermissionError:
            raise
            
        return count
    
    def _get_cache_stats_with_sudo(self, path: Path) -> tuple:
        """
        Get cache stats using sudo when permission denied.
        
        Returns:
            (size_in_bytes, file_count) or (None, 0) if failed
        """
        try:
            # Get total size in bytes
            size_result = subprocess.run(
                ['/usr/bin/sudo', 'du', '-sb', str(path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            
            size_bytes = 0
            if size_result.returncode == 0:
                # Output format: "123456\t/path/to/dir"
                size_str = size_result.stdout.strip().split('\t')[0]
                size_bytes = int(size_str)
            else:
                logger.warning(f"Failed to get size with sudo: {size_result.stderr}")
                return (None, 0)
            
            # Get file count
            count_result = subprocess.run(
                ['/usr/bin/sudo', 'find', str(path), '-type', 'f'],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            
            file_count = 0
            if count_result.returncode == 0:
                # Count non-empty lines
                file_count = len([line for line in count_result.stdout.strip().split('\n') if line])
            else:
                logger.warning(f"Failed to count files with sudo: {count_result.stderr}")
            
            return (size_bytes, file_count)
        
        except FileNotFoundError:
            logger.warning("Sudo not available")
            return (None, 0)
        except subprocess.TimeoutExpired:
            logger.warning(f"Sudo command timed out for {path}")
            return (None, 0)
        except Exception as e:
            logger.warning(f"Failed to get stats with sudo: {e}")
            return (None, 0)
    
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
