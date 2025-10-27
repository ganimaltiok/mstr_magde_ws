# -*- coding: utf-8 -*-
from flask import Flask
from flask_caching import Cache
from dotenv import load_dotenv
import os
import logging
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

from mstr_herald.connection import create_connection
from mstr_herald.error_handlers import register_error_handlers
from api_v1 import register_v1_blueprint
from api_v2 import register_v2_blueprint
from api_v3 import api_v3  # v3 zaten blueprint olarak geliyor
from admin import admin
from configurator import configure_bp
from cache_routes import cache_bp

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("py.warnings").setLevel(logging.ERROR)

# Load environment variables
load_dotenv()

cache = Cache()

SENTRY_DSN = os.getenv(
    "SENTRY_DSN",
    "https://a2edc7bea5dcb3c53628a115ab8f4712@o4510260666105856.ingest.de.sentry.io/4510260725022800",
)


if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FlaskIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        environment=os.getenv("FLASK_ENV", "production"),
    )


def create_app():
    app = Flask(__name__)

    # Configure cache
    app.config.update({
        "CACHE_TYPE": os.getenv("CACHE_TYPE", "SimpleCache"),
        "CACHE_DEFAULT_TIMEOUT": int(os.getenv("CACHE_TIMEOUT", 60))
    })

    # Register error handlers
    register_error_handlers(app)

    # Create MicroStrategy connection
    try:
        mstr_conn = create_connection()
        logger.info("Successfully connected to MicroStrategy")
    except Exception as e:
        logger.error(f"Failed to connect to MicroStrategy: {e}")
        mstr_conn = None

    # Initialise caching
    cache.init_app(app)

    # Register blueprints
    register_v1_blueprint(app, cache, mstr_conn)
    register_v2_blueprint(app, mstr_conn)
    app.register_blueprint(api_v3, url_prefix="/api/v3")
    app.register_blueprint(admin)
    app.register_blueprint(configure_bp)
    app.register_blueprint(cache_bp)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=True)
