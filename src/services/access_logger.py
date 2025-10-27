from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import threading


class AccessLog:
    """Track endpoint access for analytics."""
    
    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self._logs: List[Dict] = []
        self._lock = threading.Lock()
        
        # Statistics cache
        self._stats_cache: Dict[str, Dict] = {}
        self._cache_timestamp: Optional[datetime] = None
    
    def log_request(
        self,
        endpoint_name: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        cache_hit: bool = False,
        query_params: Optional[Dict] = None
    ):
        """Log an API request."""
        entry = {
            'timestamp': datetime.now(),
            'endpoint_name': endpoint_name,
            'method': method,
            'status_code': status_code,
            'response_time_ms': response_time_ms,
            'cache_hit': cache_hit,
            'query_params': query_params or {}
        }
        
        with self._lock:
            self._logs.append(entry)
            
            # Trim to max size (circular buffer)
            if len(self._logs) > self.max_entries:
                self._logs = self._logs[-self.max_entries:]
            
            # Invalidate stats cache
            self._cache_timestamp = None
    
    def get_endpoint_stats(self, endpoint_name: str) -> Dict:
        """
        Get statistics for an endpoint.
        
        Returns:
            {
                'total_requests': int,
                'last_request': datetime,
                'avg_response_time_ms': float,
                'cache_hit_rate': float,
                'requests_by_hour': Dict[str, int]
            }
        """
        with self._lock:
            endpoint_logs = [log for log in self._logs if log['endpoint_name'] == endpoint_name]
            
            if not endpoint_logs:
                return {
                    'total_requests': 0,
                    'last_request': None,
                    'avg_response_time_ms': 0,
                    'cache_hit_rate': 0,
                    'requests_by_hour': {}
                }
            
            total_requests = len(endpoint_logs)
            last_request = max(log['timestamp'] for log in endpoint_logs)
            avg_response_time = sum(log['response_time_ms'] for log in endpoint_logs) / total_requests
            cache_hits = sum(1 for log in endpoint_logs if log.get('cache_hit'))
            cache_hit_rate = (cache_hits / total_requests) * 100 if total_requests > 0 else 0
            
            # Group by hour for sparkline
            requests_by_hour = defaultdict(int)
            for log in endpoint_logs:
                hour_key = log['timestamp'].strftime('%Y-%m-%d %H:00')
                requests_by_hour[hour_key] += 1
            
            return {
                'total_requests': total_requests,
                'last_request': last_request,
                'avg_response_time_ms': round(avg_response_time, 2),
                'cache_hit_rate': round(cache_hit_rate, 2),
                'requests_by_hour': dict(requests_by_hour)
            }
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Get statistics for all endpoints."""
        # Check cache (1 minute TTL)
        if self._cache_timestamp and (datetime.now() - self._cache_timestamp).seconds < 60:
            return self._stats_cache
        
        with self._lock:
            # Get unique endpoint names
            endpoint_names = set(log['endpoint_name'] for log in self._logs)
            
            stats = {}
            for name in endpoint_names:
                stats[name] = self.get_endpoint_stats(name)
            
            self._stats_cache = stats
            self._cache_timestamp = datetime.now()
            
            return stats
    
    def get_recent_requests(self, limit: int = 100) -> List[Dict]:
        """Get most recent requests across all endpoints."""
        with self._lock:
            return list(reversed(self._logs[-limit:]))


# Singleton instance
_access_logger: Optional[AccessLog] = None


def get_access_logger() -> AccessLog:
    """Get access logger singleton."""
    global _access_logger
    if _access_logger is None:
        _access_logger = AccessLog()
    return _access_logger
