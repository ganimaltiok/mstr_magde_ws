import logging
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

from services import cache_service
from services.config_store import CACHE_POLICY_DAILY, load_config, resolve_cache_policy
from services.dataframe_tools import normalise_agency_code_columns, normalise_columns
from services.postgres_service import fetch_table_dataframe, parse_table_reference
from mstr_herald.connection import create_connection
from mstr_herald.reports import fetch_report_dataframe

logger = logging.getLogger(__name__)


def get_report_cache_meta(report_name: str) -> Optional[Dict[str, Any]]:
    """Return cached metadata for a report, if available."""
    return cache_service.get_metadata(report_name)


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

    conn = None

    try:
        for report_name, cfg in to_process.items():
            try:
                pg_ref = parse_table_reference(cfg.get("postgres_table"))
            except ValueError as exc:
                result["errors"].setdefault(report_name, []).append(str(exc))
                continue
            if pg_ref:
                info_types = ["summary"]
            else:
                if conn is None:
                    try:
                        conn = create_connection()
                    except Exception as exc:
                        logger.error("Failed to create MicroStrategy connection: %s", exc)
                        result["errors"].setdefault(report_name, []).append("MicroStrategy connection unavailable.")
                        continue
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
                cache_key = cache_service.build_cache_key(report_name, info_type)
                try:
                    if pg_ref:
                        df = fetch_table_dataframe(pg_ref)
                    else:
                        df = fetch_report_dataframe(conn, report_name, cfg, filters={}, info_type=info_type)
                    df = normalise_columns(df)
                    df = normalise_agency_code_columns(df)
                    cache_service.set_dataframe(cache_key, df)
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
                cache_service.set_metadata(report_name, refreshed_meta)
                result["refreshed"][report_name] = refreshed_meta
            else:
                result["skipped"][report_name] = "All info types failed to refresh."

            if errors_for_report:
                result["errors"][report_name] = errors_for_report

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    summary = refresh_full_reports()
    logger.info("Refreshed %d report caches.", len(summary.get("refreshed", {})))
