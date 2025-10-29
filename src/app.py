import logging
import os

import sentry_sdk
from dotenv import load_dotenv
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from web import create_app
from services.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
_SENTRY_INITIALIZED = False


def _init_sentry() -> None:
    global _SENTRY_INITIALIZED
    if _SENTRY_INITIALIZED:
        return
    
    dsn = (os.getenv("SENTRY_DSN") or "https://a2edc7bea5dcb3c53628a115ab8f4712@o4510260666105856.ingest.de.sentry.io/4510260725022800").strip()
    if not dsn:
        logger.info("Sentry DSN not provided; skipping Sentry setup.")
        return

    sentry_kwargs = {
        "dsn": dsn,
        "integrations": [
            FlaskIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        "send_default_pii": False,
    }

    environment = os.getenv("SENTRY_ENVIRONMENT")
    if environment:
        sentry_kwargs["environment"] = environment

    sample_rate_raw = os.getenv("SENTRY_TRACES_SAMPLE_RATE")
    if sample_rate_raw:
        try:
            sentry_kwargs["traces_sample_rate"] = float(sample_rate_raw)
        except ValueError:
            logger.warning(
                "Invalid SENTRY_TRACES_SAMPLE_RATE '%s'; ignoring trace sampling configuration.",
                sample_rate_raw,
            )

    sentry_sdk.init(**sentry_kwargs)
    _SENTRY_INITIALIZED = True
    logger.info("Sentry SDK initialized.")


load_dotenv()
_init_sentry()

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    app.run(
        host="0.0.0.0",
        port=settings.PORT,
        debug=settings.is_development,
    )
