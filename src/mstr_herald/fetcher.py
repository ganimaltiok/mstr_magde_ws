import yaml
from pathlib import Path
import pandas as pd
from io import StringIO
from mstrio.connection import Connection
from mstr_herald.utils import get_cube_last_update_time
from mstr_herald.utils import dataframe_to_pretty_json
import time

CONFIG_PATH = Path(__file__).parent.parent / "config" / "dossiers.yaml"

def get_report_config(report_name: str) -> dict:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if report_name not in cfg:
        raise KeyError(f"Rapor '{report_name}' config dosyasında bulunamadı.")
    return cfg[report_name]

def fetch_report_df(conn: Connection,
                    report_name: str,
                    agency_code: str,
                    info_type: str = "summary") -> pd.DataFrame:
    """
    1. YAML’den config oku
    2. Filtreli instance yarat
    3. CSV export et -> DataFrame
    """
    cfg = get_report_config(report_name)
    dossier_id = cfg["dossier_id"]
    filter_key = cfg["filters"]["agency_name"]
    viz_key = cfg["viz_keys"].get(info_type)
    cube_id = cfg["cube_id"]
    if not viz_key:
        raise ValueError(f"Widget '{info_type}' tanımlı değil.")

    # Filtreli instance yarat
    inst = conn.post(
        f"{conn.base_url}/api/dossiers/{dossier_id}/instances",
        json={"filters":[{"key": filter_key, "selections":[{"name": agency_code}]}]}
    ).json()
    mid = inst.get("mid")

    csv_url = f"{conn.base_url}/api/documents/{dossier_id}/instances/{mid}/visualizations/{viz_key}/csv"
    timeout = 90 # saniye, istersen parametreleştir
    poll_interval = 1  # saniye

    start_time = time.time()
    while True:
        try:
            res = conn.post(csv_url)
            res.raise_for_status()
            # Başarılıysa döngüden çık
            break
        except Exception as e:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"CSV polling süresi aşıldı. Hata: {e}")
            time.sleep(poll_interval)
    
    # CSV export
    res = conn.post(
        f"{conn.base_url}/api/documents/{dossier_id}/instances/{mid}/visualizations/{viz_key}/csv"
    )
    res.raise_for_status()
    result_df = pd.read_csv(StringIO(res.content.decode("utf-16")))
    result_df["datarefreshtime"] = get_cube_last_update_time(conn, cube_id)
    return result_df 