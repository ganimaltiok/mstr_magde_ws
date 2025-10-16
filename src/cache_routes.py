from __future__ import annotations

import logging
from typing import Any, Dict

from flask import Blueprint, jsonify

from cache_refresher.cache_refresher import refresh_daily_caches
from cache_refresher.full_report_refresher import get_report_cache_meta

logger = logging.getLogger(__name__)

cache_bp = Blueprint("cache_admin", __name__)


def _normalise_report_arg(name: str) -> str:
    return (name or "").strip()


@cache_bp.route("/refresh", methods=["GET", "POST"])
def refresh_all_caches():
    """
    Refresh cache entries for every report flagged with ``cache_policy = daily``.
    """
    summary = refresh_daily_caches()
    status = 200 if summary.get("refreshed") else 202
    return jsonify(summary), status


@cache_bp.route("/refresh/<report_name>", methods=["GET", "POST"])
def refresh_single_cache(report_name: str):
    """
    Refresh cache entries for a single report.
    """
    report_name = _normalise_report_arg(report_name)
    if not report_name:
        return jsonify({"error": "Report name is required."}), 400

    summary = refresh_daily_caches([report_name])
    refreshed: Dict[str, Any] = summary.get("refreshed", {})
    errors: Dict[str, Any] = summary.get("errors", {})
    skipped: Dict[str, Any] = summary.get("skipped", {})

    if report_name in refreshed:
        payload = {
            "status": "refreshed",
            "report": report_name,
            "meta": refreshed[report_name],
        }
        return jsonify(payload)

    if report_name in errors:
        payload = {
            "status": "error",
            "report": report_name,
            "errors": errors[report_name],
            "meta": get_report_cache_meta(report_name),
        }
        return jsonify(payload), 400

    if report_name in skipped:
        payload = {
            "status": "skipped",
            "report": report_name,
            "reason": skipped[report_name],
            "meta": get_report_cache_meta(report_name),
        }
        return jsonify(payload), 409

    # Fall back to returning existing metadata if nothing was done
    payload = {
        "status": "noop",
        "report": report_name,
        "meta": get_report_cache_meta(report_name),
    }
    return jsonify(payload), 404


@cache_bp.route("/refresh/meta/<report_name>", methods=["GET"])
def fetch_cache_meta(report_name: str):
    """
    Return the cached metadata for a report without triggering a refresh.
    """
    report_name = _normalise_report_arg(report_name)
    if not report_name:
        return jsonify({"error": "Report name is required."}), 400

    meta = get_report_cache_meta(report_name)
    if meta is None:
        return jsonify({"report": report_name, "meta": None}), 404
    return jsonify({"report": report_name, "meta": meta})
