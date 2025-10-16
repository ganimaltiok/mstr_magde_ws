# fetcher_v2.py
import yaml
from pathlib import Path
from mstrio.connection import Connection
import pandas as pd
from io import StringIO
from mstrio.connection import Connection
from mstr_herald.utils import get_cube_last_update_time
from mstr_herald.utils import dataframe_to_pretty_json
import logging
import time

CONFIG_PATH = Path(__file__).parent.parent / "config" / "dossiers.yaml"

def _get_cfg(report_name: str) -> dict:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if report_name not in cfg:
        raise KeyError(f"Report '{report_name}' not found in config.")
    return cfg[report_name]

def fetch_report_csv(conn, report_name: str, filters: dict, info_type: str = "summary") -> pd.DataFrame:
    cfg = _get_cfg(report_name)
    dossier_id = cfg["dossier_id"]
    viz_key = cfg["viz_keys"][info_type]
    cube_id = cfg["cube_id"]

    applied_filters = []
    agency_key = cfg["filters"].get("agency_name")
    agency_val = filters.get("agency_name")

    if agency_key and agency_val is not None:
        applied_filters.append({"key": agency_key, "selections": [{"name": agency_val}]})

    if applied_filters:
        logging.info(
            "Applying %d REST filters for report '%s'", len(applied_filters), report_name
        )
    else:
        logging.info("Fetching report '%s' without REST filters", report_name)

    inst = conn.post(
        f"{conn.base_url}/api/dossiers/{dossier_id}/instances",
        json={"filters": applied_filters}
    ).json()
    mid = inst["mid"]

    csv_url = f"{conn.base_url}/api/documents/{dossier_id}/instances/{mid}/visualizations/{viz_key}/csv"
    timeout = 90  # saniye, istersen parametreleştir
    poll_interval = 0.5  # saniye

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

    res = conn.post(
        f"{conn.base_url}/api/documents/{dossier_id}/instances/{mid}/visualizations/{viz_key}/csv"
    )
    res.raise_for_status()
    df = pd.read_csv(StringIO(res.content.decode("utf-16")))
    df["datarefreshtime"] = get_cube_last_update_time(conn, cube_id)
    return df