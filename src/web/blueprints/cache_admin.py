from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify

from cache_refresher.cache_refresher import refresh_daily_caches
from cache_refresher.full_report_refresher import get_report_cache_meta

cache_bp = Blueprint("cache_admin", __name__)


def _normalise(value: str | None) -> str:
    return (value or "").strip()


@cache_bp.route("/refresh", methods=["GET", "POST"])
def refresh_all():
    summary = refresh_daily_caches()
    status = 200 if summary.get("refreshed") else 202
    return jsonify(summary), status


@cache_bp.route("/refresh/<report_name>", methods=["GET", "POST"])
def refresh_single(report_name: str):
    report_name = _normalise(report_name)
    if not report_name:
        return jsonify({"error": "Report name is required."}), 400

    summary = refresh_daily_caches([report_name])
    refreshed: Dict[str, Any] = summary.get("refreshed", {})
    errors: Dict[str, Any] = summary.get("errors", {})
    skipped: Dict[str, Any] = summary.get("skipped", {})

    if report_name in refreshed:
        return jsonify(
            {
                "status": "refreshed",
                "report": report_name,
                "meta": refreshed[report_name],
            }
        )

    if report_name in errors:
        return (
            jsonify(
                {
                    "status": "error",
                    "report": report_name,
                    "errors": errors[report_name],
                    "meta": get_report_cache_meta(report_name),
                }
            ),
            400,
        )

    if report_name in skipped:
        return (
            jsonify(
                {
                    "status": "skipped",
                    "report": report_name,
                    "reason": skipped[report_name],
                    "meta": get_report_cache_meta(report_name),
                }
            ),
            409,
        )

    return (
        jsonify(
            {
                "status": "noop",
                "report": report_name,
                "meta": get_report_cache_meta(report_name),
            }
        ),
        404,
    )


@cache_bp.route("/refresh/meta/<report_name>", methods=["GET"])
def cache_meta(report_name: str):
    report_name = _normalise(report_name)
    if not report_name:
        return jsonify({"error": "Report name is required."}), 400

    meta = get_report_cache_meta(report_name)
    if meta is None:
        return jsonify({"report": report_name, "meta": None}), 404
    return jsonify({"report": report_name, "meta": meta})


__all__ = ["cache_bp"]

