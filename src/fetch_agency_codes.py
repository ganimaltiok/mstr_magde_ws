import pandas as pd
from mstr_herald.connection import create_connection
from mstr_herald.fetcher_v2 import fetch_report_csv
import logging
import os

BASE_DIR = os.path.dirname(__file__)
LOG_FILE = os.path.join(BASE_DIR, "refresh_cache.log")
# --- Setup Logging ---
logging.basicConfig(
    filename=LOG_FILE,
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Python warnings modülünden gelen loglari bastir
logging.getLogger("py.warnings").setLevel(logging.ERROR)

def fetch_agency_codes() -> list[str]:
    """
    'agency_master_list' raporundan acente kodlarini çeker.
    'acente_kodu' sütunu varsayimi ile çalişir, gerekirse alan adlari uyarlanabilir.
    """
    conn = create_connection()
    try:
        df = fetch_report_csv(conn, "agency_master_list", filters={})
        if "acente_kodu" not in df.columns:
            raise KeyError("Beklenen 'acente_kodu' sutunu bulunamadi.")
        codes = df["acente_kodu"].dropna().astype(str).unique().tolist()
        return codes
    except Exception as e:
        logging.info(f"Acente listesi alinamadi: {e}")
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass