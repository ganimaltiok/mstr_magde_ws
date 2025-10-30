"""
Redis caching service for MSTR Herald v3.

Provides endpoint-level caching of full datasets with metadata tracking.
When enabled, stores complete datasets in Redis and applies filters/pagination
in-memory on cached data.
"""

import json
import logging
import redis
from typing import Optional, Dict, Any, List
from datetime import datetime
from functools import lru_cache
from services.settings import get_settings
from services.endpoint_config import get_config_store

logger = logging.getLogger(__name__)


@lru_cache()
def _get_redis_client() -> redis.Redis:
    """Get cached Redis client instance."""
    settings = get_settings()
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=False,
        socket_connect_timeout=1800,  # 30 minutes
        socket_timeout=1800  # 30 minutes
    )


def get_redis_client() -> redis.Redis:
    """Return a cached Redis client instance."""
    return _get_redis_client()


def _cache_key(endpoint_name: str) -> str:
    """Build cache key for endpoint data."""
    return f"v3:data:{endpoint_name}"


def _meta_key(endpoint_name: str) -> str:
    """Build cache key for endpoint metadata."""
    return f"v3:meta:{endpoint_name}"


class RedisCacheService:
    """Service for managing Redis-based endpoint caching."""
    
    def __init__(self):
        self.client = get_redis_client()
        self.settings = get_settings()
    
    def get_cached_data(self, endpoint_name: str) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve cached data for an endpoint.
        
        Args:
            endpoint_name: Name of the endpoint
            
        Returns:
            List of records or None if not cached
        """
        try:
            key = _cache_key(endpoint_name)
            raw_data = self.client.get(key)
            
            if not raw_data:
                logger.debug(f"Cache MISS for endpoint: {endpoint_name}")
                return None
            
            data = json.loads(raw_data.decode('utf-8'))
            logger.info(f"Cache HIT for endpoint: {endpoint_name} ({len(data)} records)")
            return data
            
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to decode cached data for {endpoint_name}: {e}")
            # Delete corrupted cache
            self.delete_cache(endpoint_name)
            return None
            
        except redis.RedisError as e:
            logger.error(f"Redis error retrieving {endpoint_name}: {e}")
            return None
    
    def set_cached_data(
        self, 
        endpoint_name: str, 
        data: List[Dict[str, Any]], 
        source: str,
        fetch_duration_ms: Optional[int] = None
    ) -> bool:
        """
        Store data in cache with metadata.
        
        Args:
            endpoint_name: Name of the endpoint
            data: List of records to cache
            source: Data source (mssql, postgresql, microstrategy)
            fetch_duration_ms: Time taken to fetch data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Store data
            data_key = _cache_key(endpoint_name)
            data_json = json.dumps(data, ensure_ascii=False)
            
            # Set with TTL
            self.client.setex(
                data_key,
                self.settings.REDIS_TTL,
                data_json.encode('utf-8')
            )
            
            # Store metadata
            metadata = {
                'last_updated': datetime.now().isoformat(),
                'record_count': len(data),
                'source': source,
                'fetch_duration_ms': fetch_duration_ms,
                'cache_size_bytes': len(data_json)
            }
            
            meta_key = _meta_key(endpoint_name)
            meta_json = json.dumps(metadata, ensure_ascii=False)
            self.client.setex(
                meta_key,
                self.settings.REDIS_TTL,
                meta_json.encode('utf-8')
            )
            
            logger.info(
                f"Cached {len(data)} records for {endpoint_name} "
                f"(size: {len(data_json)} bytes, TTL: {self.settings.REDIS_TTL}s)"
            )
            return True
            
        except redis.RedisError as e:
            logger.error(f"Failed to cache data for {endpoint_name}: {e}")
            return False
    
    def delete_cache(self, endpoint_name: str) -> bool:
        """
        Delete cached data and metadata for an endpoint.
        
        Args:
            endpoint_name: Name of the endpoint
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            data_key = _cache_key(endpoint_name)
            meta_key = _meta_key(endpoint_name)
            
            deleted = self.client.delete(data_key, meta_key)
            
            if deleted > 0:
                logger.info(f"Deleted cache for {endpoint_name}")
                return True
            else:
                logger.debug(f"No cache to delete for {endpoint_name}")
                return False
                
        except redis.RedisError as e:
            logger.error(f"Failed to delete cache for {endpoint_name}: {e}")
            return False
    
    def get_cache_metadata(self, endpoint_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve metadata for cached endpoint.
        
        Args:
            endpoint_name: Name of the endpoint
            
        Returns:
            Metadata dict or None if not cached
        """
        try:
            meta_key = _meta_key(endpoint_name)
            raw_meta = self.client.get(meta_key)
            
            if not raw_meta:
                return None
            
            metadata = json.loads(raw_meta.decode('utf-8'))
            
            # Add TTL info
            data_key = _cache_key(endpoint_name)
            ttl = self.client.ttl(data_key)
            metadata['ttl_remaining'] = ttl if ttl > 0 else 0
            
            return metadata
            
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to decode metadata for {endpoint_name}: {e}")
            return None
            
        except redis.RedisError as e:
            logger.error(f"Redis error retrieving metadata for {endpoint_name}: {e}")
            return None
    
    def get_all_cached_endpoints(self) -> List[str]:
        """
        Get list of all endpoints currently in cache.
        
        Returns:
            List of endpoint names
        """
        try:
            pattern = "v3:data:*"
            keys = self.client.keys(pattern)
            
            # Extract endpoint names from keys
            endpoints = []
            for key in keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                # v3:data:endpoint_name -> endpoint_name
                endpoint_name = key_str.replace('v3:data:', '')
                endpoints.append(endpoint_name)
            
            return endpoints
            
        except redis.RedisError as e:
            logger.error(f"Failed to list cached endpoints: {e}")
            return []
    
    def get_redis_stats(self) -> Dict[str, Any]:
        """
        Get Redis server statistics.
        
        Returns:
            Dict with Redis stats
        """
        try:
            info = self.client.info()
            memory_info = self.client.info('memory')
            
            return {
                'connected': True,
                'version': info.get('redis_version', 'unknown'),
                'uptime_days': info.get('uptime_in_days', 0),
                'used_memory': memory_info.get('used_memory_human', 'unknown'),
                'total_keys': self.client.dbsize(),
                'v3_cache_keys': len(self.get_all_cached_endpoints())
            }
            
        except redis.RedisError as e:
            logger.error(f"Failed to get Redis stats: {e}")
            return {
                'connected': False,
                'error': str(e)
            }
    
    def refresh_endpoint_cache(self, endpoint_name: str) -> Dict[str, Any]:
        """
        Refresh cache for a single endpoint by deleting existing cache.
        Next request will fetch fresh data.
        
        Args:
            endpoint_name: Name of the endpoint
            
        Returns:
            Result dict with status and message
        """
        try:
            # Check if endpoint has redis_cache enabled
            config_store = get_config_store()
            config = config_store.get(endpoint_name)
            
            if not config:
                return {
                    'status': 'error',
                    'message': f'Endpoint "{endpoint_name}" not found'
                }
            
            if not config.redis_cache:
                return {
                    'status': 'error',
                    'message': f'Endpoint "{endpoint_name}" does not have Redis cache enabled'
                }
            
            # Delete cache
            deleted = self.delete_cache(endpoint_name)
            
            return {
                'status': 'success',
                'message': f'Cache cleared for "{endpoint_name}". Next request will fetch fresh data.',
                'endpoint': endpoint_name,
                'cache_deleted': deleted
            }
            
        except Exception as e:
            logger.error(f"Error refreshing cache for {endpoint_name}: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e),
                'endpoint': endpoint_name
            }
    
    def refresh_all_caches(self) -> Dict[str, Any]:
        """
        Refresh caches for all endpoints with redis_cache=true.
        Deletes existing caches; next requests will fetch fresh data.
        
        Returns:
            Summary of refresh operation
        """
        try:
            config_store = get_config_store()
            all_endpoints = config_store.get_all()
            
            # Filter endpoints with redis_cache enabled
            redis_endpoints = [
                name for name, config in all_endpoints.items()
                if config.redis_cache
            ]
            
            if not redis_endpoints:
                return {
                    'status': 'success',
                    'message': 'No endpoints have Redis cache enabled',
                    'endpoints_processed': 0,
                    'results': []
                }
            
            results = []
            success_count = 0
            
            for endpoint_name in redis_endpoints:
                result = self.refresh_endpoint_cache(endpoint_name)
                results.append(result)
                
                if result['status'] == 'success':
                    success_count += 1
            
            return {
                'status': 'success',
                'message': f'Refreshed {success_count}/{len(redis_endpoints)} endpoints',
                'endpoints_processed': len(redis_endpoints),
                'success_count': success_count,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error refreshing all caches: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }


# Singleton instance
_redis_cache_service: Optional[RedisCacheService] = None


def get_redis_cache_service() -> RedisCacheService:
    """Get Redis cache service singleton."""
    global _redis_cache_service
    if _redis_cache_service is None:
        _redis_cache_service = RedisCacheService()
    return _redis_cache_service


__all__ = [
    'RedisCacheService',
    'get_redis_cache_service',
    'get_redis_client'
]
