from __future__ import annotations

import logging
import traceback

from flask import Flask, jsonify

logger = logging.getLogger(__name__)


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad Request", "message": str(error)}), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not Found", "message": "The requested resource was not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal server error: %s\n%s", error, traceback.format_exc())
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred"}), 500

    @app.errorhandler(Exception)
    def unhandled_exception(error):
        logger.error("Unhandled exception: %s\n%s", error, traceback.format_exc())
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred"}), 500


__all__ = ["register_error_handlers"]

