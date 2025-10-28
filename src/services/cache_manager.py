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
        
        try:
            # First try to get size (may fail due to permissions)
            for cache_path in self.cache_paths:
                if cache_path.exists():
                    try:
                        total_bytes += self._get_directory_size(cache_path)
                    except PermissionError:
                        logger.warning(f"Cannot read cache size for {cache_path}")
            
            # Clear cache directory contents (not the directory itself)
            for cache_path in self.cache_paths:
                if cache_path.exists():
                    try:
                        # Remove all files and subdirectories inside
                        for item in cache_path.iterdir():
                            if item.is_file():
                                item.unlink()
                            elif item.is_dir():
                                shutil.rmtree(item)
                        logger.info(f"Cleared cache directory contents: {cache_path}")
                    except PermissionError:
                        # Fall back to sudo to remove contents
                        logger.info(f"Using sudo to clear {cache_path}")
                        result = subprocess.run(
                            ['sudo', 'find', str(cache_path), '-mindepth', '1', '-delete'],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if result.returncode == 0:
                            logger.info(f"Cleared cache directory with sudo: {cache_path}")
                        else:
                            raise Exception(f"Failed to clear with sudo: {result.stderr}")
            
            return {
                'status': 'success',
                'message': f'All caches cleared ({self._format_bytes(total_bytes) if total_bytes else "size unknown"})',
                'purged_bytes': total_bytes
            }
        
        except Exception as e:
            logger.error(f"Failed to purge all cache: {e}")
            return {
                'status': 'error',
                'message': str(e),
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
