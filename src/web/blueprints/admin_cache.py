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
    Purge all cache.
    
    JSON payload:
    {
        "target": "all"
    }
    """
    try:
        data = request.get_json()
        target = data.get('target')
        
        if target != 'all':
            return jsonify({'error': 'Only "all" target is supported'}), 400
        
        cache_manager = get_cache_manager()
        result = cache_manager.purge_all()
        
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
