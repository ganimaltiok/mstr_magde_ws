from typing import Dict, Any, Optional
from services.sql_fetcher import get_sql_fetcher
from services.pg_fetcher import get_pg_fetcher
from services.mstr_fetcher import get_mstr_fetcher
from services.cache_manager import get_cache_manager
from services.settings import get_settings
import logging

logger = logging.getLogger(__name__)


class HealthChecker:
    """Check health of all system connections."""
    
    def __init__(self):
        self.settings = get_settings()
    
    def check_all(self) -> Dict[str, Any]:
        """
        Check all connections and return status.
        
        Returns:
            {
                'mssql': {'status': 'ok'|'error', 'response_time_ms': float, 'error': str},
                'postgresql': {...},
                'microstrategy': {...},
                'nginx_cache': {...}
            }
        """
        return {
            'mssql': self._check_mssql(),
            'postgresql': self._check_postgresql(),
            'microstrategy': self._check_mstr(),
            'nginx_cache': self._check_nginx_cache()
        }
    
    def _check_mssql(self) -> Dict[str, Any]:
        """Check MSSQL connection."""
        if not self.settings.MSSQL_HOST or not self.settings.MSSQL_DATABASE:
            return {
                'status': 'not_configured',
                'response_time_ms': None,
                'error': 'MSSQL credentials not configured'
            }
        
        try:
            fetcher = get_sql_fetcher()
            success, error, response_time = fetcher.test_connection()
            
            if success:
                return {
                    'status': 'ok',
                    'response_time_ms': response_time,
                    'error': None
                }
            else:
                return {
                    'status': 'error',
                    'response_time_ms': None,
                    'error': error
                }
        except Exception as e:
            logger.error(f"MSSQL health check failed: {e}")
            return {
                'status': 'error',
                'response_time_ms': None,
                'error': str(e)
            }
    
    def _check_postgresql(self) -> Dict[str, Any]:
        """Check PostgreSQL connection."""
        if not self.settings.pg_host or not self.settings.pg_database:
            return {
                'status': 'not_configured',
                'response_time_ms': None,
                'error': 'PostgreSQL credentials not configured'
            }
        
        try:
            fetcher = get_pg_fetcher()
            success, error, response_time = fetcher.test_connection()
            
            if success:
                return {
                    'status': 'ok',
                    'response_time_ms': response_time,
                    'error': None
                }
            else:
                return {
                    'status': 'error',
                    'response_time_ms': None,
                    'error': error
                }
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return {
                'status': 'error',
                'response_time_ms': None,
                'error': str(e)
            }
    
    def _check_mstr(self) -> Dict[str, Any]:
        """Check MicroStrategy connection."""
        if not self.settings.MSTR_URL_API:
            return {
                'status': 'not_configured',
                'response_time_ms': None,
                'error': 'MicroStrategy credentials not configured'
            }
        
        try:
            fetcher = get_mstr_fetcher()
            success, error, response_time = fetcher.test_connection()
            
            if success:
                return {
                    'status': 'ok',
                    'response_time_ms': response_time,
                    'error': None
                }
            else:
                return {
                    'status': 'error',
                    'response_time_ms': None,
                    'error': error
                }
        except Exception as e:
            logger.error(f"MicroStrategy health check failed: {e}")
            return {
                'status': 'error',
                'response_time_ms': None,
                'error': str(e)
            }
    
    def _check_nginx_cache(self) -> Dict[str, Any]:
        """Check nginx cache accessibility."""
        try:
            manager = get_cache_manager()
            stats = manager.get_cache_stats()
            
            # Check if there's a permission error (cache owned by nginx/www-data)
            if stats.get('error'):
                # Permission denied is a warning, not a critical error
                # Cache purge still works via nginx, we just can't read stats
                return {
                    'status': 'warning',
                    'total_size': 0,
                    'total_files': 0,
                    'error': stats['error']
                }
            
            # Check if cache directories exist
            accessible = all([
                self.settings.NGINX_CACHE_SHORT.exists(),
                self.settings.NGINX_CACHE_DAILY.exists()
            ])
            
            if accessible:
                return {
                    'status': 'ok',
                    'total_size': stats['total_size'],
                    'total_files': stats['total_files'],
                    'error': None
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Cache directories not accessible'
                }
        except Exception as e:
            logger.error(f"Nginx cache health check failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }


# Singleton instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get health checker singleton."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker
