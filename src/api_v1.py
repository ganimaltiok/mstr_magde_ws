# src/api_v1.py
from flask import Blueprint, jsonify, request, Response
import json
import logging
from mstr_herald.fetcher import fetch_report_df
from mstr_herald.utils import dataframe_to_pretty_json

logger = logging.getLogger(__name__)
api_v1 = Blueprint("api_v1", __name__)

def register_v1_blueprint(app, cache, mstr_conn):
    @api_v1.route("/report/<report_name>/agency/<agency_code>")
    @cache.cached(
        timeout=60,
        key_prefix=lambda: f"{request.path}?{request.query_string.decode()}"
    )
    def get_report(report_name: str, agency_code: str):
        info_type = request.args.get("info_type", "summary")
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 100))

        logger.info(f"[v1] report: {report_name}, agency: {agency_code}, type: {info_type}")

        try:
            if not mstr_conn:
                return jsonify({"error": "MicroStrategy connection not available"}), 503

            df = fetch_report_df(mstr_conn, report_name, agency_code, info_type)

            cube_time = None
            if "datarefreshtime" in df.columns:
                cube_time = df["datarefreshtime"].iloc[0]
                df = df.drop(columns=["datarefreshtime"])

            total_records = len(df)
            total_pages = (total_records + page_size - 1) // page_size
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            page_df = df.iloc[start_idx:end_idx]
            records = json.loads(dataframe_to_pretty_json(page_df))

            return Response(json.dumps({
                "data": records,
                "meta": {
                    "page": page,
                    "page_size": page_size,
                    "total_records": total_records,
                    "total_pages": total_pages,
                    "data_refresh_time": cube_time
                }
            }, ensure_ascii=False, indent=2), mimetype="application/json")

        except Exception as e:
            logger.error(f"[v1] error fetching report '{report_name}': {e}")
            return jsonify({"error": str(e)}), 400

    @api_v1.route("/ping")
    def ping():
        return {"status": "ok", "mstr_connection": "ok" if mstr_conn else "error"}

    app.register_blueprint(api_v1, url_prefix="/api/v1")
