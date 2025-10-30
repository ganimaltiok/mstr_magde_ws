"""
Admin API for Redis cache management.

Routes:
- GET /api/admin/redis/stats - Redis server statistics
- POST /api/admin/redis/refresh-all - Refresh all endpoints with redis_cache=true
- POST /api/admin/redis/refresh/:endpoint - Refresh single endpoint
"""

from flask import Blueprint, jsonify, request
from services.redis_cache_service import get_redis_cache_service
from services.endpoint_config import get_config_store
import logging

logger = logging.getLogger(__name__)

admin_redis_bp = Blueprint('admin_redis', __name__, url_prefix='/api/admin/redis')


@admin_redis_bp.route('/stats', methods=['GET'])
def get_redis_stats():
    """
    Get Redis server statistics.
    
    Returns:
        {
            "status": "success",
            "data": {
                "connected": true,
                "version": "7.4.4",
                "uptime_days": 3,
                "used_memory": "750M",
                "total_keys": 42,
                "v3_cache_keys": 5
            }
        }
    """
    try:
        redis_cache = get_redis_cache_service()
        stats = redis_cache.get_redis_stats()
        
        return jsonify({
            'status': 'success',
            'data': stats
        })
    
    except Exception as e:
        logger.error(f"Error getting Redis stats: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@admin_redis_bp.route('/refresh-all', methods=['POST'])
def refresh_all_caches():
    """
    Refresh all endpoints with redis_cache=true.
    Clears Redis cache; next request will fetch fresh data.
    
    Returns:
        {
            "status": "success",
            "message": "Refreshed 5/8 endpoints",
            "endpoints_processed": 8,
            "success_count": 5,
            "results": [...]
        }
    """
    try:
        redis_cache = get_redis_cache_service()
        result = redis_cache.refresh_all_caches()
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error refreshing all caches: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@admin_redis_bp.route('/refresh/<endpoint_name>', methods=['POST'])
def refresh_endpoint_cache(endpoint_name: str):
    """
    Refresh single endpoint cache.
    Clears Redis cache; next request will fetch fresh data.
    
    Args:
        endpoint_name: Name of the endpoint
    
    Returns:
        {
            "status": "success",
            "message": "Cache cleared for 'sales_summary'",
            "endpoint": "sales_summary",
            "cache_deleted": true
        }
    """
    try:
        redis_cache = get_redis_cache_service()
        result = redis_cache.refresh_endpoint_cache(endpoint_name)
        
        if result['status'] == 'error':
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error refreshing cache for {endpoint_name}: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e),
            'endpoint': endpoint_name
        }), 500


@admin_redis_bp.route('/cached-endpoints', methods=['GET'])
def get_cached_endpoints():
    """
    Get list of all endpoints currently in Redis cache with metadata.
    
    Returns:
        {
            "status": "success",
            "data": {
                "total": 3,
                "endpoints": [
                    {
                        "name": "sales_summary",
                        "last_updated": "2025-01-24T10:30:45",
                        "record_count": 1500,
                        "source": "mssql",
                        "fetch_duration_ms": 234,
                        "cache_size_bytes": 458900,
                        "ttl_remaining": 39600
                    }
                ]
            }
        }
    """
    try:
        redis_cache = get_redis_cache_service()
        endpoint_names = redis_cache.get_all_cached_endpoints()
        
        endpoints = []
        for name in endpoint_names:
            metadata = redis_cache.get_cache_metadata(name)
            if metadata:
                metadata['name'] = name
                endpoints.append(metadata)
        
        return jsonify({
            'status': 'success',
            'data': {
                'total': len(endpoints),
                'endpoints': endpoints
            }
        })
    
    except Exception as e:
        logger.error(f"Error getting cached endpoints: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@admin_redis_bp.route('/metadata/<endpoint_name>', methods=['GET'])
def get_endpoint_metadata(endpoint_name: str):
    """
    Get cache metadata for specific endpoint.
    
    Args:
        endpoint_name: Name of the endpoint
    
    Returns:
        {
            "status": "success",
            "data": {
                "last_updated": "2025-01-24T10:30:45",
                "record_count": 1500,
                "source": "mssql",
                "fetch_duration_ms": 234,
                "cache_size_bytes": 458900,
                "ttl_remaining": 39600
            }
        }
    """
    try:
        redis_cache = get_redis_cache_service()
        metadata = redis_cache.get_cache_metadata(endpoint_name)
        
        if metadata is None:
            return jsonify({
                'status': 'error',
                'message': f'No cache metadata found for endpoint "{endpoint_name}"'
            }), 404
        
        return jsonify({
            'status': 'success',
            'data': metadata
        })
    
    except Exception as e:
        logger.error(f"Error getting metadata for {endpoint_name}: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e),
            'endpoint': endpoint_name
        }), 500


__all__ = ['admin_redis_bp']
