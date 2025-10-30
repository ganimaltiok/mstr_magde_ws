from flask import Blueprint, render_template, jsonify
from services.health_checker import get_health_checker
from services.endpoint_config import get_config_store
from services.redis_cache_service import get_redis_cache_service

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
    
    # Get Redis cache service
    redis_cache = get_redis_cache_service()
    
    # Build endpoint table data
    endpoint_data = []
    for name, config in endpoints.items():
        # Get Redis metadata if enabled
        redis_metadata = None
        if config.redis_cache:
            redis_metadata = redis_cache.get_cache_metadata(name)
        
        endpoint_data.append({
            'name': name,
            'source': config.source,
            'description': config.description,
            'is_cached': config.is_cached,
            'cache_zone': config.cache_zone,
            'redis_cache': config.redis_cache,
            'redis_metadata': redis_metadata
        })
    
    return render_template('admin_dashboard.html',
                         health_status=health_status,
                         endpoints=endpoint_data)


@admin_dashboard_bp.route('/api/dashboard/stats')
def dashboard_stats_api():
    """API endpoint for dashboard statistics (for auto-refresh)."""
    health_checker = get_health_checker()
    health_status = health_checker.check_all()
    
    return jsonify({
        'health': health_status
    })
