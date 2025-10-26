from __future__ import annotations

import logging

from flask import Flask, Response, jsonify

from services.settings import get_settings
from web.blueprints import register_blueprints
from web.errors import register_error_handlers
from web.health import render_health_page
from mstr_herald.connection import create_connection

logger = logging.getLogger(__name__)


def _eager_connection_check() -> None:
    try:
        conn = create_connection()
    except Exception as exc:
        logger.warning("Failed to establish MicroStrategy connection on startup: %s", exc)
        return

    try:
        conn.close()
    except Exception:
        pass
    logger.info("Successfully validated MicroStrategy connectivity.")


def create_app() -> Flask:
    settings = get_settings()
    app = Flask(__name__)
    app.config.update(
        {
            "CACHE_TYPE": settings.cache_type,
            "CACHE_DEFAULT_TIMEOUT": settings.cache_default_timeout,
        }
    )

    register_error_handlers(app)
    register_blueprints(app)
    _eager_connection_check()

    @app.get("/ping")
    def ping():
        return jsonify({"status": "ok"})

    @app.get("/health")
    def health_page() -> Response:
        return Response(render_health_page(), content_type="text/html; charset=utf-8")

    return app


__all__ = ["create_app"]
