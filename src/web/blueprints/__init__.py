from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask):
    """Register all blueprints."""
    
    # v3 API (backward compatible)
    from web.blueprints.v3_api import v3_bp
    app.register_blueprint(v3_bp)
    
    # Admin interface
    from web.blueprints.admin_dashboard import admin_dashboard_bp
    app.register_blueprint(admin_dashboard_bp)
    
    from web.blueprints.admin_endpoints import admin_endpoints_bp
    app.register_blueprint(admin_endpoints_bp)
    
    from web.blueprints.admin_cache import admin_cache_bp
    app.register_blueprint(admin_cache_bp)
    
    from web.blueprints.admin_mstr import admin_mstr_bp
    app.register_blueprint(admin_mstr_bp)
    
    from web.blueprints.admin_redis import admin_redis_bp
    app.register_blueprint(admin_redis_bp)
    
    # Health checks
    from web.blueprints.health import health_bp
    app.register_blueprint(health_bp)

