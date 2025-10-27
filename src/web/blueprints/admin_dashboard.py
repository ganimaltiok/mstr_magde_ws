from flask import Blueprint, render_template, jsonify
from services.health_checker import get_health_checker
from services.endpoint_config import get_config_store
from services.access_logger import get_access_logger
from services.cache_manager import get_cache_manager

admin_dashboard_bp = Blueprint('admin_dashboard', __name__, url_prefix='/admin')


@admin_dashboard_bp.route('/')
@admin_dashboard_bp.route('/dashboard')
def dashboard():
    """Main admin dashboard."""
    # Get health status
    health_checker = get_health_checker()
    health_status = health_checker.check_all()
    
    # Get all endpoints
    config_store = get_config_store()
    endpoints = config_store.get_all()
    
    # Get access statistics
    access_logger = get_access_logger()
    access_stats = access_logger.get_all_stats()
    
    # Get cache statistics
    cache_manager = get_cache_manager()
    cache_stats = cache_manager.get_cache_stats()
    
    # Build endpoint table data
    endpoint_data = []
    for name, config in endpoints.items():
        stats = access_stats.get(name, {})
        
        endpoint_data.append({
            'name': name,
            'behavior': config.behavior,
            'description': config.description,
            'last_request': stats.get('last_request'),
            'total_requests': stats.get('total_requests', 0),
            'avg_response_time_ms': stats.get('avg_response_time_ms', 0),
            'cache_hit_rate': stats.get('cache_hit_rate', 0),
            'is_cached': config.is_cached,
            'cache_zone': config.cache_zone
        })
    
    return render_template('admin_dashboard.html',
                         health_status=health_status,
                         endpoints=endpoint_data,
                         cache_stats=cache_stats)


@admin_dashboard_bp.route('/api/dashboard/stats')
def dashboard_stats_api():
    """API endpoint for dashboard statistics (for auto-refresh)."""
    health_checker = get_health_checker()
    health_status = health_checker.check_all()
    
    access_logger = get_access_logger()
    access_stats = access_logger.get_all_stats()
    
    cache_manager = get_cache_manager()
    cache_stats = cache_manager.get_cache_stats()
    
    return jsonify({
        'health': health_status,
        'access': access_stats,
        'cache': cache_stats
    })
