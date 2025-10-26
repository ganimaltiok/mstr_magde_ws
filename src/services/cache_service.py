from __future__ import annotations

import json
import logging
import pickle
from functools import lru_cache
from typing import Any, Dict, Optional

import pandas as pd
import redis

from services.settings import get_settings

logger = logging.getLogger(__name__)

_META_SUFFIX = ":meta"


@lru_cache()
def _get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=False,
    )


def get_redis_client() -> redis.Redis:
    """
    Return a cached Redis client instance.
    """
    return _get_redis_client()


def build_cache_key(report_name: str, info_type: str, scope: str = "all") -> str:
    return f"{report_name}:{scope}:{info_type}"


def get_dataframe(cache_key: str) -> Optional[pd.DataFrame]:
    raw = _get_redis_client().get(cache_key)
    if not raw:
        return None
    try:
        return pickle.loads(raw)
    except Exception as exc:  # pragma: no cover - defensive catch for corrupted data
        logger.warning("Failed to deserialize cache entry %s: %s", cache_key, exc)
        return None


def set_dataframe(cache_key: str, df: pd.DataFrame) -> None:
    _get_redis_client().set(cache_key, pickle.dumps(df))


def _meta_key(report_name: str) -> str:
    return f"{report_name}{_META_SUFFIX}"


def get_metadata(report_name: str) -> Optional[Dict[str, Any]]:
    raw = _get_redis_client().get(_meta_key(report_name))
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Failed to decode cache metadata for %s: %s", report_name, exc)
        return None


def set_metadata(report_name: str, meta: Dict[str, Any]) -> None:
    payload = json.dumps(meta, ensure_ascii=False)
    _get_redis_client().set(_meta_key(report_name), payload.encode("utf-8"))


__all__ = [
    "build_cache_key",
    "get_dataframe",
    "get_metadata",
    "get_redis_client",
    "set_dataframe",
    "set_metadata",
]
