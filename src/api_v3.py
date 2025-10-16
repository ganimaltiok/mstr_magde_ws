from flask import Blueprint, request, jsonify, Response
import redis
import pickle
import pandas as pd
import json
import logging
import os
import re
from mstr_herald.utils import (
    load_config,
    replace_turkish_characters,
    _to_camel_no_tr,
    is_lower_camel_case,
    _stringify_dataframe,
    resolve_cache_policy,
    CACHE_POLICY_DAILY,
)
from mstr_herald.fetcher_v2 import fetch_report_csv
from mstr_herald.connection import create_connection
from mstr_herald.filter_utils import apply_filters

logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    decode_responses=False,
)

api_v3 = Blueprint("api_v3", __name__, url_prefix="/api/v3")


def filter_df_by_agency(df: pd.DataFrame, agency_code: str) -> pd.DataFrame:
    normalized_target_cols = [
        "agencycode", "agency", "agencyid",
        "acentekodu", "acente", "acenteid"
    ]

    for col in df.columns:
        norm_col = re.sub(r"[^a-z]", "", col.lower())
        if norm_col in normalized_target_cols:
            return df[df[col].astype(str) == str(agency_code)]

    # fallback: no matching column
    return df

def safe_json_serialize(df: pd.DataFrame) -> str:
    df2 = df.copy()
    df2.columns = [
        _to_camel_no_tr(c) if not is_lower_camel_case(c) else c
        for c in df2.columns
    ]
    for col in df2.select_dtypes(include=["datetime", "datetimetz"]).columns:
        df2[col] = df2[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    df2 = _stringify_dataframe(df2)
    return json.dumps(df2.to_dict(orient="records"), ensure_ascii=False, indent=2)

def filter_df_by_agency(df: pd.DataFrame, agency_code: str) -> pd.DataFrame:
    possible_cols = ["acente_kodu", "acenteKodu", "agency_code", "agencyCode", "acente", "agency"]
    for col in df.columns:
        if col in possible_cols or col.lower() in possible_cols:
            return df[df[col].astype(str) == str(agency_code)]
    return df

def get_cached_data(cache_key: str) -> pd.DataFrame:
    try:
        raw = redis_client.get(cache_key)
        if raw:
            return pickle.loads(raw)
    except Exception as e:
        logger.warning(f"Cache deserialization failed for {cache_key}: {e}")
    return None

def fetch_fresh_data(conn, report_name: str, filters: dict, info_type: str) -> pd.DataFrame:
    try:
        df = fetch_report_csv(conn, report_name, filters, info_type)
        logger.info(f"Fetched report '{report_name}' ({info_type}) from MSTR.")
        return df
    except Exception as e:
        logger.error(f"Error fetching report from MSTR: {e}")
        raise

def process_dataframe(df: pd.DataFrame, filters: dict) -> tuple:
    df.columns = [replace_turkish_characters(col) for col in df.columns]
    df.columns = [
        _to_camel_no_tr(c) if not is_lower_camel_case(c) else c
        for c in df.columns
    ]
    cube_time = None
    if "datarefreshtime" in df.columns:
        cube_time = df["datarefreshtime"].iloc[0] if not df.empty else None
        df = df.drop(columns=["datarefreshtime"])
    remaining_filters = {k: v for k, v in filters.items() if k != "agency_name"}
    if remaining_filters:
        df = apply_filters(df, remaining_filters)
    return df, cube_time

def paginate_data(df: pd.DataFrame, page: int, page_size: int) -> tuple:
    total_rows = len(df)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = df.iloc[start:end]
    total_pages = (total_rows + page_size - 1) // page_size
    return paginated, total_rows, total_pages

@api_v3.route("/report/<report_name>/agency/<agency_code>", methods=["GET"])
def get_cached_report(report_name, agency_code):
    try:
        config = load_config()
        cfg = config.get(report_name, {})
        if not cfg:
            return jsonify({"error": f"Report '{report_name}' not found in configuration"}), 404

        filters = request.args.to_dict()
        info_type = filters.pop("info_type", "summary").lower()
        page = int(filters.pop("page", 1))
        page_size = int(filters.pop("page_size", 50))

        if info_type not in cfg.get("viz_keys", {}):
            return jsonify({"error": f"Visualization type '{info_type}' is not defined for this report."}), 400

        cache_policy = resolve_cache_policy(cfg)
        use_cache = cache_policy == CACHE_POLICY_DAILY
        cache_key = f"{report_name}:all:{info_type}" if use_cache else None
        cache_hit = False
        df = None

        logger.info(
            f"Fetching report '{report_name}' ({info_type}) for agency '{agency_code}' "
            f"- cache policy: {cache_policy}"
        )

        if use_cache and cache_key:
            df = get_cached_data(cache_key)
            if df is not None:
                cache_hit = True
                logger.info(f"Loaded {cache_key} from cache.")
                df = filter_df_by_agency(df, agency_code)
                filters["agency_name"] = agency_code
            else:
                logger.info(f"[CACHE MISS] {cache_key} not found in Redis.")

        if df is None:
            try:
                conn = create_connection()
            except Exception as e:
                logger.error(f"Failed to create MSTR connection: {e}")
                return jsonify({"error": "MicroStrategy connection not available"}), 503
            try:
                filters["agency_name"] = agency_code
                df = fetch_fresh_data(conn, report_name, filters, info_type)
            except Exception as e:
                return jsonify({"error": f"Failed to fetch report: {str(e)}"}), 500
            finally:
                try:
                    conn.close()
                except:
                    pass

        df, cube_time = process_dataframe(df, filters)

        if df.empty:
            return jsonify({
                "data": [],
                "report": report_name,
                "agency": agency_code,
                "info_type": info_type,
                "page": page,
                "page_size": page_size,
                "total_rows": 0,
                "data_refresh_time": cube_time,
                "message": "No data found for the given criteria"
            })

        paginated, total_rows, total_pages = paginate_data(df, page, page_size)

        payload = {
            "data": json.loads(safe_json_serialize(paginated)),
            "report": report_name,
            "agency": agency_code,
            "info_type": info_type,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "data_refresh_time": cube_time,
            "is_cached": use_cache,
            "cache_hit": cache_hit,
            "cache_policy": cache_policy,
        }

        return Response(json.dumps(payload, ensure_ascii=False, indent=2), content_type="application/json")

    except Exception as e:
        logger.error(f"Unexpected error in get_cached_report: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@api_v3.route("/report/<report_name>", methods=["GET"])
def get_report_without_agency(report_name):
    try:
        config = load_config()
        cfg = config.get(report_name, {})
        if not cfg:
            return jsonify({"error": f"Report '{report_name}' not found in configuration"}), 404

        if "agency_name" in cfg.get("filters", {}):
            return jsonify({
                "error": f"Report '{report_name}' requires agency_code parameter",
                "usage": f"Use /api/v3/report/{report_name}/agency/<agency_code>"
            }), 400

        filters = request.args.to_dict()
        info_type = filters.pop("info_type", "summary").lower()
        page = int(filters.pop("page", 1))
        page_size = int(filters.pop("page_size", 50))

        if info_type not in cfg.get("viz_keys", {}):
            return jsonify({"error": f"Visualization type '{info_type}' is not defined for this report."}), 400

        cache_policy = resolve_cache_policy(cfg)
        use_cache = cache_policy == CACHE_POLICY_DAILY
        cache_key = f"{report_name}:all:{info_type}" if use_cache else None
        cache_hit = False
        df = None

        logger.info(
            f"Fetching report '{report_name}' without agency filter "
            f"- cache policy: {cache_policy}"
        )

        if use_cache and cache_key:
            df = get_cached_data(cache_key)
            if df is not None:
                cache_hit = True
                logger.info(f"Loaded {cache_key} from cache.")
            else:
                logger.info(f"[CACHE MISS] {cache_key} not found in Redis.")

        if df is None:
            try:
                conn = create_connection()
            except Exception as e:
                logger.error(f"Failed to create MSTR connection: {e}")
                return jsonify({"error": "MicroStrategy connection not available"}), 503
            try:
                df = fetch_report_csv(conn, report_name, filters, info_type)
            except Exception as e:
                logger.error(f"Error fetching report '{report_name}': {e}")
                return jsonify({"error": f"Failed to fetch report: {str(e)}"}), 500
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        df, cube_time = process_dataframe(df, filters)
        paginated, total_rows, total_pages = paginate_data(df, page, page_size)

        payload = {
            "data": json.loads(safe_json_serialize(paginated)),
            "report": report_name,
            "info_type": info_type,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "data_refresh_time": cube_time,
            "is_cached": use_cache,
            "cache_hit": cache_hit,
            "cache_policy": cache_policy,
        }

        return Response(json.dumps(payload, ensure_ascii=False, indent=2), content_type="application/json")

    except Exception as e:
        logger.error(f"Unexpected error in get_report_without_agency: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@api_v3.route("/reports", methods=["GET"])
def list_reports():
    try:
        config = load_config()
        reports = []

        for report_name, cfg in config.items():
            policy = resolve_cache_policy(cfg)
            reports.append({
                "name": report_name,
                "cache_policy": policy,
                "is_cached": policy == CACHE_POLICY_DAILY,
                "requires_agency": "agency_name" in cfg.get("filters", {}),
                "available_filters": list(cfg.get("filters", {}).keys())
            })

        return jsonify({
            "reports": reports,
            "total_count": len(reports),
            "cached_count": sum(1 for r in reports if r["is_cached"]),
            "non_cached_count": sum(1 for r in reports if not r["is_cached"])
        })

    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        return jsonify({"error": f"Failed to list reports: {str(e)}"}), 500
