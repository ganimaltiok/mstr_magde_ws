from __future__ import annotations

from flask import Flask
from flask_cors import CORS
from services.settings import get_settings
import logging
from pathlib import Path


def create_app() -> Flask:
    """Create and configure Flask application."""
    settings = get_settings()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = settings.SECRET_KEY
    
    # Disable ASCII encoding to return UTF-8 Turkish characters directly
    app.config['JSON_AS_ASCII'] = False
    
    # Enable CORS
    CORS(app)
    
    # Set template folder
    template_dir = Path(__file__).parent / 'templates'
    app.template_folder = str(template_dir)
    
    # Register blueprints
    from web.blueprints import register_blueprints
    register_blueprints(app)
    
    # Log startup info
    logger = logging.getLogger(__name__)
    
    # Setup request logging
    from web.request_logger import setup_request_logging
    setup_request_logging(app)
    
    logger.info(f"MSTR Herald API starting on port {settings.PORT}")
    logger.info(f"Environment: {settings.FLASK_ENV}")
    
    return app

