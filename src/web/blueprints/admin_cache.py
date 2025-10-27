from flask import Blueprint, render_template, request, jsonify
from services.cache_manager import get_cache_manager
from services.endpoint_config import get_config_store
import logging

logger = logging.getLogger(__name__)

admin_cache_bp = Blueprint('admin_cache', __name__, url_prefix='/admin/cache')


@admin_cache_bp.route('/')
def cache_page():
    """Cache management page."""
    cache_manager = get_cache_manager()
    cache_stats = cache_manager.get_cache_stats()
    
    config_store = get_config_store()
    endpoints = config_store.list_names()
    
    return render_template('admin_cache.html',
                         cache_stats=cache_stats,
                         endpoints=endpoints)


@admin_cache_bp.route('/purge', methods=['POST'])
def purge_cache():
    """
    Purge cache endpoint.
    
    JSON payload:
    {
        "target": "all" | "endpoint",
        "endpoint_name": "..." (required if target="endpoint")
    }
    """
    try:
        data = request.get_json()
        target = data.get('target')
        
        cache_manager = get_cache_manager()
        
        if target == 'all':
            result = cache_manager.purge_all()
        elif target == 'endpoint':
            endpoint_name = data.get('endpoint_name')
            if not endpoint_name:
                return jsonify({'error': 'endpoint_name required'}), 400
            result = cache_manager.purge_endpoint(endpoint_name)
        else:
            return jsonify({'error': 'Invalid target'}), 400
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Cache purge failed: {e}")
        return jsonify({'error': str(e)}), 500


@admin_cache_bp.route('/stats')
def cache_stats_api():
    """Get cache statistics (API endpoint for auto-refresh)."""
    cache_manager = get_cache_manager()
    stats = cache_manager.get_cache_stats()
    return jsonify(stats)
