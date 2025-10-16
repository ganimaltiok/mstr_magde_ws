# src/api_v2.py
from flask import Blueprint, jsonify, request, Response
import json
import logging
from mstr_herald.fetcher_v2 import fetch_report_csv
from mstr_herald.utils import dataframe_to_pretty_json

logger = logging.getLogger(__name__)
api_v2 = Blueprint("api_v2", __name__)

def register_v2_blueprint(app, mstr_conn):
    @api_v2.route("/report/<report_name>")
    def get_report_v2(report_name):
        info_type = request.args.get("info_type", "summary")
        page = int(request.args.get("page", 1)) 
        page_size = int(request.args.get("page_size", 100))
        offset = (page - 1) * page_size

        filters = dict(request.args)
        filters.pop("info_type", None)
        filters.pop("page", None)
        filters.pop("page_size", None)

        logger.info(f"[v2] report: {report_name}, filters: {filters}")

        try:
            if not mstr_conn:
                return jsonify({"error": "MicroStrategy connection not available"}), 503

            df = fetch_report_csv(mstr_conn, report_name, filters, info_type)

            cube_time = None
            if "dataRefreshTime" in df.columns:
                cube_time = df["dataRefreshTime"].iloc[0]
                df = df.drop(columns=["dataRefreshTime"])

            total_records = len(df)
            total_pages = (total_records + page_size - 1) // page_size
            start_idx = offset
            end_idx = offset + page_size

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
            logger.error(f"[v2] error fetching report '{report_name}': {e}")
            return jsonify({"error": str(e)}), 400

    app.register_blueprint(api_v2, url_prefix="/api/v2")
