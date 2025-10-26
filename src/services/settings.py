from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import logging

from dotenv import load_dotenv

# Ensure environment variables from a local .env file are available everywhere,
# including background jobs that import this module directly.
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    cache_type: str
    cache_default_timeout: int
    redis_host: str
    redis_port: int
    redis_db: int
    refresh_log_path: Path
    config_path: Path


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
        cache_type=os.getenv("CACHE_TYPE", "SimpleCache"),
        cache_default_timeout=_parse_int(os.getenv("CACHE_TIMEOUT"), 60, "CACHE_TIMEOUT"),
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=_parse_int(os.getenv("REDIS_PORT"), 6379, "REDIS_PORT"),
        redis_db=_parse_int(os.getenv("REDIS_DB"), 0, "REDIS_DB"),
        refresh_log_path=_resolve_path(os.getenv("REFRESH_LOG_PATH"), refresh_log_default),
        config_path=_resolve_path(os.getenv("MSTR_CONFIG_PATH"), config_default),
    )


__all__ = ["Settings", "get_settings"]
