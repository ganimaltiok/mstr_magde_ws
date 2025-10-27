from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from services import cache_service
from services.config_store import (
    CACHE_POLICY_DAILY,
    DATA_POLICY_MICROSTRATEGY,
    DATA_POLICY_POSTGRESQL,
    load_config,
    resolve_cache_policy,
    resolve_data_policy,
)
from services.dataframe_tools import (
    dataframe_to_records,
    extract_cube_time,
    filter_by_agency,
    normalise_agency_code_columns,
    normalise_columns,
)
from services.postgres_service import fetch_table_dataframe, parse_table_reference
from mstr_herald.connection import create_connection
from mstr_herald.filter_utils import apply_filters
from mstr_herald.reports import fetch_report_dataframe

logger = logging.getLogger(__name__)


class ReportNotFoundError(KeyError):
    pass


class UnsupportedInfoTypeError(ValueError):
    pass


@dataclass(frozen=True)
class ReportMeta:
    report_name: str
    info_type: str
    cache_policy: str
    cache_hit: bool
    cache_key: Optional[str]
    data_refresh_time: Optional[str]
    total_rows: int
    total_pages: int
    page: int
    page_size: int


def _paginate(df: pd.DataFrame, page: int, page_size: int) -> Tuple[pd.DataFrame, int, int]:
    total_rows = len(df)
    if page_size <= 0:
        page_size = max(total_rows, 1)
    if page <= 0:
        page = 1

    start = (page - 1) * page_size
    end = start + page_size
    sliced = df.iloc[start:end]
    total_pages = (total_rows + page_size - 1) // page_size if page_size else 1
    return sliced, total_rows, total_pages


def _prepare_dataframe(df: pd.DataFrame, filters: Dict[str, Any], agency_code: Optional[str]) -> Tuple[pd.DataFrame, Optional[str]]:
    working = normalise_columns(df)
    working = normalise_agency_code_columns(working)
    working = filter_by_agency(working, agency_code)
    working, cube_time = extract_cube_time(working)

    non_agency_filters = {
        k: v
        for k, v in (filters or {}).items()
        if k.lower() != "agency_name" and v not in (None, "")
    }

    if non_agency_filters:
        try:
            working = apply_filters(working, non_agency_filters)
        except Exception as exc:
            logger.warning("Failed to apply filters %s: %s", non_agency_filters, exc)
    return working.reset_index(drop=True), cube_time


def _fetch_remote(report_name: str, cfg: Dict[str, Any], info_type: str, filters: Dict[str, Any]) -> pd.DataFrame:
    data_policy = resolve_data_policy(cfg)
    if data_policy == DATA_POLICY_POSTGRESQL:
        pg_ref = parse_table_reference(cfg.get("postgres_table"))
        if not pg_ref:
            raise ValueError(f"postgres_table must be defined for Postgres-backed report '{report_name}'.")
        logger.info("%s: Fetching data from Postgres table %s", report_name, cfg.get("postgres_table"))
        return fetch_table_dataframe(pg_ref)

    conn = create_connection()
    try:
        return fetch_report_dataframe(conn, report_name, cfg, filters, info_type)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _validate_info_type(cfg: Dict[str, Any], info_type: str) -> None:
    if resolve_data_policy(cfg) == DATA_POLICY_POSTGRESQL:
        if info_type != "summary":
            raise UnsupportedInfoTypeError("Postgres-backed reports only support info_type='summary'.")
        return
    viz_keys = cfg.get("viz_keys") or {}
    if info_type not in viz_keys or not viz_keys[info_type]:
        raise UnsupportedInfoTypeError(f"Visualization type '{info_type}' is not configured.")


def _format_cube_time(value: Any) -> Optional[str]:
    if value is None or value == "NULL":
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def get_report_payload(
    report_name: str,
    filters: Dict[str, Any],
    info_type: str,
    page: int,
    page_size: int,
    agency_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch a report dataset, optionally using cached data, and return a serialisable payload.
    """
    config = load_config()
    cfg = config.get(report_name)
    if not cfg:
        raise ReportNotFoundError(report_name)

    _validate_info_type(cfg, info_type)

    cache_policy = resolve_cache_policy(cfg)
    data_policy = resolve_data_policy(cfg)
    use_cache = cache_policy == CACHE_POLICY_DAILY
    # Postgres-backed reports always cache under summary key
    cache_key_info_type = info_type if data_policy == DATA_POLICY_MICROSTRATEGY else "summary"
    cache_key = cache_service.build_cache_key(report_name, cache_key_info_type) if use_cache else None

    df = None
    cache_hit = False

    if use_cache and cache_key:
        df = cache_service.get_dataframe(cache_key)
        if df is not None and df.empty:
            logger.info(
                "%s (%s): Cached dataframe is empty; falling back to live fetch.",
                report_name,
                info_type,
            )
            df = None
        cache_hit = df is not None

    if df is None:
        df = _fetch_remote(report_name, cfg, info_type, filters)

    processed_df, cube_time = _prepare_dataframe(df, filters, agency_code)
    paged_df, total_rows, total_pages = _paginate(processed_df, page, page_size)
    records = dataframe_to_records(paged_df)

    response = {
        "data": records,
        "report": report_name,
        "info_type": info_type,
        "page": page,
        "page_size": page_size,
        "total_rows": total_rows,
        "total_pages": total_pages,
        "data_refresh_time": _format_cube_time(cube_time),
        "cache_policy": cache_policy,
        "data_policy": data_policy,
        "is_cached": use_cache,
        "cache_hit": cache_hit,
    }

    if agency_code is not None:
        response["agency"] = str(agency_code)

    return response


def list_reports_summary() -> Dict[str, Any]:
    config = load_config()
    summaries = []

    for report_name, cfg in config.items():
        policy = resolve_cache_policy(cfg)
        data_policy = resolve_data_policy(cfg)
        summaries.append(
            {
                "name": report_name,
                "cache_policy": policy,
                "is_cached": policy == CACHE_POLICY_DAILY,
                "data_policy": data_policy,
                "requires_agency": "agency_name" in (cfg.get("filters") or {}),
                "available_filters": sorted((cfg.get("filters") or {}).keys()),
                "postgres_table": cfg.get("postgres_table"),
            }
        )

    return {
        "reports": summaries,
        "total_count": len(summaries),
        "cached_count": sum(1 for item in summaries if item["is_cached"]),
        "non_cached_count": sum(1 for item in summaries if not item["is_cached"]),
    }


__all__ = [
    "ReportNotFoundError",
    "UnsupportedInfoTypeError",
    "get_report_payload",
    "list_reports_summary",
]
