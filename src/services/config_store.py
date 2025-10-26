from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from services.settings import get_settings

CACHE_POLICY_NONE = "none"
CACHE_POLICY_DAILY = "daily"
_LEGACY_CACHE_FLAG_KEY = "is_csv_cached"


def get_config_path() -> Path:
    """
    Determine the path to the dossiers configuration file.
    """
    settings = get_settings()
    return settings.config_path


def load_config() -> Dict[str, Any]:
    """
    Load dossier configuration from YAML.
    """
    path = get_config_path()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found at {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid dossier configuration structure in {path}")
    return data


def save_config(config: Dict[str, Any]) -> None:
    """
    Persist dossier configuration to YAML.
    """
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, allow_unicode=True, default_flow_style=False)


def resolve_cache_policy(cfg: Dict[str, Any] | None) -> str:
    """
    Determine the desired cache policy for a report configuration.
    """
    if not cfg:
        return CACHE_POLICY_NONE

    policy = (cfg.get("cache_policy") or "").strip().lower()
    if policy in {CACHE_POLICY_NONE, CACHE_POLICY_DAILY}:
        return policy

    # Backwards compatibility for earlier configurations.
    legacy_flag = cfg.get(_LEGACY_CACHE_FLAG_KEY)
    try:
        legacy_flag = int(legacy_flag)
    except (TypeError, ValueError):
        legacy_flag = 0

    return CACHE_POLICY_DAILY if legacy_flag > 0 else CACHE_POLICY_NONE


__all__ = ["CACHE_POLICY_NONE", "CACHE_POLICY_DAILY", "get_config_path", "load_config", "save_config", "resolve_cache_policy"]

