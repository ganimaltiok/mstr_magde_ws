from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import logging
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    refresh_log_path: Path
    config_path: Path
    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str

    # Flask
    FLASK_ENV: str
    PORT: int
    SECRET_KEY: str

    # MSSQL
    MSSQL_HOST: str
    MSSQL_PORT: int
    MSSQL_DATABASE: str
    MSSQL_USER: str
    MSSQL_PASSWORD: str
    MSSQL_DRIVER: str

    # MicroStrategy
    MSTR_URL_API: str
    MSTR_USERNAME: str
    MSTR_PASSWORD: str
    MSTR_PROJECT: str

    # Nginx Cache
    NGINX_CACHE_SHORT: Path
    NGINX_CACHE_DAILY: Path

    # Redis Cache
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_TTL: int  # seconds (default 12 hours)

    # Logging
    LOG_LEVEL: str
    LOG_FILE: str

    # Sentry
    SENTRY_DSN: str
    SENTRY_ENVIRONMENT: str

    @property
    def mssql_connection_string(self) -> str:
        """Build MSSQL connection string from components."""
        return (
            f"DRIVER={{{self.MSSQL_DRIVER}}};"
            f"SERVER={self.MSSQL_HOST},{self.MSSQL_PORT};"
            f"DATABASE={self.MSSQL_DATABASE};"
            f"UID={self.MSSQL_USER};"
            f"PWD={self.MSSQL_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )


def _resolve_path(env_value: str | None, default: Path) -> Path:
    if env_value:
        return Path(env_value).expanduser()
    return default


def _parse_int(raw_value: str | None, fallback: int, env_key: str) -> int:
    if raw_value is None:
        return fallback

    # Support inline comments such as "60  # seconds"
    cleaned = raw_value.split("#", 1)[0].strip()
    if not cleaned:
        return fallback

    try:
        return int(cleaned)
    except ValueError:
        logger.warning(
            "Environment variable %s='%s' is not a valid integer. Using fallback %d.",
            env_key,
            raw_value,
            fallback,
        )
        return fallback


@lru_cache()
def get_settings() -> Settings:
    """
    Return immutable application settings derived from environment variables.
    """
    base_dir = Path(__file__).resolve().parents[1]
    refresh_log_default = base_dir / "refresh_cache.log"
    config_default = base_dir / "config" / "dossiers.yaml"

    return Settings(
        base_dir=base_dir,
        refresh_log_path=_resolve_path(os.getenv("REFRESH_LOG_PATH"), refresh_log_default),
        config_path=_resolve_path(os.getenv("MSTR_CONFIG_PATH"), config_default),
        pg_host=os.getenv("PG_HOST", "localhost"),
        pg_port=_parse_int(os.getenv("PG_PORT"), 5432, "PG_PORT"),
        pg_database=os.getenv("PG_DATABASE", ""),
        pg_user=os.getenv("PG_USER", ""),
        pg_password=os.getenv("PG_PASSWORD", ""),
        # Flask
        FLASK_ENV=os.getenv('FLASK_ENV', 'production'),
        PORT=int(os.getenv('PORT', 9101)),
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),

        # MSSQL
        MSSQL_HOST=os.getenv('MSSQL_HOST'),
        MSSQL_PORT=int(os.getenv('MSSQL_PORT', 1433)),
        MSSQL_DATABASE=os.getenv('MSSQL_DATABASE'),
        MSSQL_USER=os.getenv('MSSQL_USER'),
        MSSQL_PASSWORD=os.getenv('MSSQL_PASSWORD'),
        MSSQL_DRIVER=os.getenv('MSSQL_DRIVER', 'ODBC Driver 18 for SQL Server'),

        # MicroStrategy
        MSTR_URL_API=os.getenv('MSTR_URL_API'),
        MSTR_USERNAME=os.getenv('MSTR_USERNAME'),
        MSTR_PASSWORD=os.getenv('MSTR_PASSWORD'),
        MSTR_PROJECT=os.getenv('MSTR_PROJECT'),

        # Nginx Cache
        NGINX_CACHE_SHORT=_resolve_path(os.getenv('NGINX_CACHE_SHORT', '/var/cache/nginx/shortcache'), base_dir / 'shortcache'),
        NGINX_CACHE_DAILY=_resolve_path(os.getenv('NGINX_CACHE_DAILY', '/var/cache/nginx/dailycache'), base_dir / 'dailycache'),

        # Redis Cache
        REDIS_HOST=os.getenv('REDIS_HOST', 'localhost'),
        REDIS_PORT=_parse_int(os.getenv('REDIS_PORT'), 6379, 'REDIS_PORT'),
        REDIS_DB=_parse_int(os.getenv('REDIS_DB'), 0, 'REDIS_DB'),
        REDIS_TTL=_parse_int(os.getenv('REDIS_TTL'), 43200, 'REDIS_TTL'),  # 12 hours

        # Logging
        LOG_LEVEL=os.getenv('LOG_LEVEL', 'INFO'),
        LOG_FILE=os.getenv('LOG_FILE', '/var/log/mstr_herald/app.log'),

        # Sentry
        SENTRY_DSN=os.getenv('SENTRY_DSN'),
        SENTRY_ENVIRONMENT=os.getenv('SENTRY_ENVIRONMENT', 'dev'),
    )


__all__ = ["Settings", "get_settings"]
