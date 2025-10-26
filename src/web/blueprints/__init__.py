from __future__ import annotations

from flask import Flask

from web.blueprints.cache_admin import cache_bp
from web.blueprints.config_admin import config_bp
from web.blueprints.logs import logs_bp
from web.blueprints.reports import reports_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(reports_bp, url_prefix="/api/v3")
    app.register_blueprint(cache_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(logs_bp)


__all__ = ["register_blueprints"]

