from __future__ import annotations

import logging
from typing import Dict

from flask import Blueprint, Response, jsonify, request

from services.report_service import (
    ReportNotFoundError,
    UnsupportedInfoTypeError,
    get_report_payload,
    list_reports_summary,
)

logger = logging.getLogger(__name__)

reports_bp = Blueprint("reports_v3", __name__)


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_filters() -> Dict[str, str]:
    filters = request.args.to_dict()
    filters.pop("page", None)
    filters.pop("page_size", None)
    return filters


@reports_bp.route("/report/<report_name>/agency/<agency_code>", methods=["GET"])
def fetch_report_for_agency(report_name: str, agency_code: str) -> Response:
    filters = _extract_filters()
    info_type = (filters.pop("info_type", "summary") or "summary").lower()
    page = _parse_int(request.args.get("page"), 1)
    page_size = _parse_int(request.args.get("page_size"), 50)
    filters["agency_name"] = agency_code

    try:
        payload = get_report_payload(
            report_name=report_name,
            filters=filters,
            info_type=info_type,
            page=page,
            page_size=page_size,
            agency_code=agency_code,
        )
    except ReportNotFoundError:
        return jsonify({"error": f"Report '{report_name}' not found in configuration."}), 404
    except UnsupportedInfoTypeError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover - defensive catch
        logger.exception("Unexpected error while fetching report %s: %s", report_name, exc)
        return jsonify({"error": "Internal server error"}), 500

    return jsonify(payload)


@reports_bp.route("/report/<report_name>", methods=["GET"])
def fetch_report(report_name: str) -> Response:
    filters = _extract_filters()
    info_type = (filters.pop("info_type", "summary") or "summary").lower()
    page = _parse_int(request.args.get("page"), 1)
    page_size = _parse_int(request.args.get("page_size"), 50)

    try:
        payload = get_report_payload(
            report_name=report_name,
            filters=filters,
            info_type=info_type,
            page=page,
            page_size=page_size,
        )
    except ReportNotFoundError:
        return jsonify({"error": f"Report '{report_name}' not found in configuration."}), 404
    except UnsupportedInfoTypeError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover - defensive catch
        logger.exception("Unexpected error while fetching report %s: %s", report_name, exc)
        return jsonify({"error": "Internal server error"}), 500

    return jsonify(payload)


@reports_bp.route("/reports", methods=["GET"])
def list_reports() -> Response:
    try:
        payload = list_reports_summary()
        return jsonify(payload)
    except Exception as exc:  # pragma: no cover - defensive catch
        logger.exception("Failed to list reports: %s", exc)
        return jsonify({"error": "Failed to list reports"}), 500


__all__ = ["reports_bp"]

