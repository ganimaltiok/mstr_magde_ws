import shutil
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
        Purge all nginx cache.
        
        Returns:
            {'status': 'success', 'message': str, 'purged_bytes': int}
        """
        total_bytes = 0
        
        try:
            for cache_path in self.cache_paths:
                if cache_path.exists():
                    # Calculate size before deletion
                    total_bytes += self._get_directory_size(cache_path)
                    
                    # Remove and recreate
                    shutil.rmtree(cache_path)
                    cache_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Purged cache directory: {cache_path}")
            
            return {
                'status': 'success',
                'message': f'All caches purged ({self._format_bytes(total_bytes)})',
                'purged_bytes': total_bytes
            }
        
        except Exception as e:
            logger.error(f"Failed to purge all cache: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'purged_bytes': 0
            }
    
    def purge_endpoint(self, endpoint_name: str) -> Dict[str, Any]:
        """
        Purge cache for specific endpoint.
        
        Nginx cache files are hashed, so we scan and match by cache key.
        Cache key format: {endpoint_name}:{query_params_hash}
        
        Returns:
            {'status': 'success', 'purged_files': int, 'purged_bytes': int}
        """
        purged_files = 0
        purged_bytes = 0
        
        try:
            for cache_path in self.cache_paths:
                if not cache_path.exists():
                    continue
                
                # Recursively scan cache files
                for cache_file in cache_path.rglob("*"):
                    if not cache_file.is_file():
                        continue
                    
                    # Try to read cache key from file header
                    try:
                        with open(cache_file, 'rb') as f:
                            # Read first 2KB (nginx cache metadata is at beginning)
                            header = f.read(2048).decode('utf-8', errors='ignore')
                            
                            # Look for our cache key pattern
                            # Nginx stores "KEY: <cache_key>" in metadata
                            if f'KEY: /api/v3/report/{endpoint_name}' in header:
                                file_size = cache_file.stat().st_size
                                cache_file.unlink()
                                purged_files += 1
                                purged_bytes += file_size
                                logger.debug(f"Purged cache file: {cache_file.name}")
                    except Exception as e:
                        logger.debug(f"Could not read cache file {cache_file}: {e}")
                        continue
            
            return {
                'status': 'success',
                'purged_files': purged_files,
                'purged_bytes': purged_bytes,
                'message': f'Purged {purged_files} files ({self._format_bytes(purged_bytes)})'
            }
        
        except Exception as e:
            logger.error(f"Failed to purge endpoint cache for '{endpoint_name}': {e}")
            return {
                'status': 'error',
                'purged_files': 0,
                'purged_bytes': 0,
                'message': str(e)
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
