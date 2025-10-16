# -*- coding: utf-8 -*-
from flask import Flask, jsonify
import logging
import traceback

def register_error_handlers(app: Flask):
    """Register error handlers for the Flask app"""
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad Request", "message": str(error)}), 400
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not Found", "message": "The requested resource was not found"}), 404
    
    @app.errorhandler(500)
    def server_error(error):
        logger.error(f"Internal server error: {error}\n{traceback.format_exc()}")
        return jsonify({
            "error": "Internal Server Error", 
            "message": "An unexpected error occurred"
        }), 500
    
    @app.errorhandler(Exception)
    def unhandled_exception(error):
        logger.error(f"Unhandled exception: {error}\n{traceback.format_exc()}")
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred"
        }), 500