from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Ensure environment variables from a local .env file are available everywhere,
# including background jobs that import this module directly.
load_dotenv()


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
        cache_default_timeout=int(os.getenv("CACHE_TIMEOUT", "60")),
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_db=int(os.getenv("REDIS_DB", "0")),
        refresh_log_path=_resolve_path(os.getenv("REFRESH_LOG_PATH"), refresh_log_default),
        config_path=_resolve_path(os.getenv("MSTR_CONFIG_PATH"), config_default),
    )


__all__ = ["Settings", "get_settings"]

