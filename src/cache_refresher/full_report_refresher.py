import json
import logging
import os
import pickle
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

import pandas as pd
import redis

from mstr_herald.connection import create_connection
from mstr_herald.fetcher_v2 import fetch_report_csv
from mstr_herald.utils import (
    CACHE_POLICY_DAILY,
    _to_camel_no_tr,
    load_config,
    resolve_cache_policy,
)

logger = logging.getLogger(__name__)

import warnings

warnings.filterwarnings("ignore", message="Warning: For given format of date*")

BASE_DIR = os.path.dirname(__file__)
LOG_FILE = os.path.join(BASE_DIR, "refresh_logs", "refresh_cache.log")

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    decode_responses=False,
)

META_SUFFIX = ":meta"


def normalize_agency_code_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert acente-related numeric columns to strings to avoid float suffixes like 100100.0."""
    for col in df.columns:
        col_lower = col.lower()
        if ("acente" in col_lower or "agency" in col_lower) and df[col].dtype.kind in {"i", "f"}:
            df[col] = df[col].apply(lambda x: str(int(x)) if not pd.isna(x) else x)
    return df


def _meta_key(report_name: str) -> str:
    return f"{report_name}{META_SUFFIX}"


def get_report_cache_meta(report_name: str) -> Optional[Dict[str, Any]]:
    """Return cached metadata for a report, if available."""
    raw = redis_client.get(_meta_key(report_name))
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Failed to decode cache metadata for %s: %s", report_name, exc)
        return None


def refresh_full_reports(report_names: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """
    Refresh Redis snapshots for reports configured with the ``daily`` cache policy.

    Args:
        report_names: Optional iterable of report names to refresh. When omitted,
            every report with ``cache_policy = daily`` is refreshed.

    Returns:
        A dictionary containing refreshed metadata, skipped entries, and errors.
    """
    config = load_config()
    daily_reports: Dict[str, Dict[str, Any]] = {
        name: cfg
        for name, cfg in config.items()
        if resolve_cache_policy(cfg) == CACHE_POLICY_DAILY
    }

    requested = list(report_names) if report_names is not None else list(daily_reports.keys())
    result: Dict[str, Any] = {
        "requested": requested,
        "refreshed": {},
        "skipped": {},
        "errors": {},
    }

    if report_names is not None:
        to_process: Dict[str, Dict[str, Any]] = {}
        for name in report_names:
            if name not in config:
                result["errors"].setdefault(name, []).append("Report not defined in configuration.")
                continue
            policy = resolve_cache_policy(config[name])
            if policy != CACHE_POLICY_DAILY:
                result["skipped"][name] = f"cache_policy is '{policy}', refresh ignored."
                continue
            to_process[name] = config[name]
    else:
        to_process = daily_reports

    if not to_process:
        logger.info("No eligible reports found for cache refresh.")
        return result

    try:
        conn = create_connection()
    except Exception as exc:
        logger.error("Failed to create MicroStrategy connection: %s", exc)
        for name in to_process:
            result["errors"].setdefault(name, []).append("MicroStrategy connection unavailable.")
        return result

    try:
        for report_name, cfg in to_process.items():
            info_types = [
                info_type
                for info_type, viz_key in (cfg.get("viz_keys") or {}).items()
                if viz_key
            ]

            if not info_types:
                logger.info("%s: No visualization keys configured; skipping.", report_name)
                result["skipped"][report_name] = "No viz_keys defined for caching."
                continue

            refreshed_meta = {
                "report": report_name,
                "refreshed_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "info_types": {},
                "cache_policy": CACHE_POLICY_DAILY,
            }
            errors_for_report: list[str] = []

            for info_type in info_types:
                cache_key = f"{report_name}:all:{info_type}"
                try:
                    df = fetch_report_csv(conn, report_name, filters={}, info_type=info_type)
                    df.columns = [_to_camel_no_tr(c) for c in df.columns]
                    df = normalize_agency_code_columns(df)
                    redis_client.set(cache_key, pickle.dumps(df))
                    refreshed_meta["info_types"][info_type] = {
                        "rows": int(len(df)),
                        "columns": list(df.columns),
                        "cache_key": cache_key,
                    }
                    logger.info(
                        "%s: Cached %s data (%d rows, %d columns)",
                        report_name,
                        info_type,
                        len(df),
                        len(df.columns),
                    )
                except Exception as exc:
                    logger.error(
                        "%s: Failed to cache info_type '%s': %s",
                        report_name,
                        info_type,
                        exc,
                    )
                    errors_for_report.append(f"{info_type}: {exc}")

            if refreshed_meta["info_types"]:
                refreshed_meta["partial"] = bool(errors_for_report)
                redis_client.set(_meta_key(report_name), json.dumps(refreshed_meta))
                result["refreshed"][report_name] = refreshed_meta
            else:
                result["skipped"][report_name] = "All info types failed to refresh."

            if errors_for_report:
                result["errors"][report_name] = errors_for_report

    finally:
        try:
            conn.close()
        except Exception:
            pass

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    summary = refresh_full_reports()
    logger.info("Refreshed %d report caches.", len(summary.get("refreshed", {})))
