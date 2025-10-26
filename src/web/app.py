from __future__ import annotations

import logging

from flask import Flask, Response, jsonify, g, request

from services.settings import get_settings
from web.blueprints import register_blueprints
from web.errors import register_error_handlers
from web.health import render_health_page
from web import logbook
from mstr_herald.connection import create_connection
from datetime import datetime
import time

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

    @app.before_request
    def _start_timer():
        g._request_start_time = time.perf_counter()

    @app.after_request
    def _record_request(response):
        try:
            duration_ms = int((time.perf_counter() - getattr(g, "_request_start_time", time.perf_counter())) * 1000)
            payload = None
            response_size = 0
            if response.direct_passthrough is False:
                raw_body = response.get_data()
                response_size = len(raw_body)
                if response.mimetype and response.mimetype.startswith("application/json"):
                    text = raw_body.decode(response.charset or "utf-8", errors="replace")
                    payload = text if len(text) <= 20000 else text[:20000] + "... (truncated)"
            entry = logbook.RequestLogEntry(
                timestamp=datetime.utcnow(),
                method=request.method,
                url=request.url,
                status=response.status_code,
                duration_ms=duration_ms,
                remote_addr=request.remote_addr or "-",
                response_size=response_size,
                response_json=payload,
            )
            logbook.add_entry(entry)
        except Exception:  # pragma: no cover - logging should never break responses
            logger.exception("Failed to record request log entry.")
        return response

    @app.get("/ping")
    def ping():
        return jsonify({"status": "ok"})

    @app.get("/health")
    def health_page() -> Response:
        return Response(render_health_page(), content_type="text/html; charset=utf-8")

    return app


__all__ = ["create_app"]
