import os
import pickle
import logging
import redis
from typing import Dict
from mstr_herald.utils import load_config, _to_camel_no_tr
from mstr_herald.connection import create_connection
from mstr_herald.fetcher_v2 import fetch_report_csv
import pandas as pd

logger = logging.getLogger(__name__)
import warnings
warnings.filterwarnings("ignore", message="Warning: For given format of date*")

BASE_DIR = os.path.dirname(__file__)
LOG_FILE = os.path.join(BASE_DIR, "refresh_logs", "refresh_cache.log")

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    decode_responses=False
)

def normalize_agency_code_columns(df):
    """Convert acente-related numeric columns to string to avoid float artifacts like 100100.0."""
    for col in df.columns:
        col_lower = col.lower()
        if "acente" in col_lower or "agency" in col_lower:
            if df[col].dtype.kind in {"i", "f"}:
                df[col] = df[col].apply(lambda x: str(int(x)) if not pd.isna(x) else x)
    return df

def refresh_full_reports() -> None:
    config = load_config()
    reports: Dict[str, Dict] = {
        name: cfg for name, cfg in config.items() if cfg.get("is_csv_cached") == 3
    }
    if not reports:
        logger.info("No reports with caching flag 3 found")
        return

    conn = None
    try:
        conn = create_connection()
        for report_name, cfg in reports.items():
            try:
                info_types = [
                    info_type
                    for info_type in cfg.get("viz_keys", {})
                    if cfg["viz_keys"].get(info_type) is not None
                ]

                for info_type in info_types:
                    try:
                        df = fetch_report_csv(conn, report_name, filters={}, info_type=info_type)
                        df.columns = [_to_camel_no_tr(c) for c in df.columns]
                        df = normalize_agency_code_columns(df)
                        cache_key = f"{report_name}:all:{info_type}"
                        redis_client.set(cache_key, pickle.dumps(df))
                        logger.info(f"Cached {info_type} data for {report_name} ({len(df)} rows)")
                    except Exception as e:
                        logger.error(f"Failed to cache {report_name} ({info_type}): {e}")
            except Exception as e:
                logger.error(f"Failed to refresh {report_name}: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

if __name__ == "__main__":
    import pandas as pd  # 💡 normalize fonksiyonu için gerekli
    logging.basicConfig(level=logging.INFO)
    refresh_full_reports()
