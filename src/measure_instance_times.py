import os
import time
import yaml
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from mstrio.connection import Connection

load_dotenv()

CONFIG_PATH = Path(__file__).parent / "config" / "dossiers.yaml"
EXCEL_OUT = Path(__file__).parent / "instance_times.xlsx"

def create_connection() -> Connection:
    base_url = os.getenv("MSTR_URL_API")
    username = os.getenv("MSTR_USERNAME")
    password = os.getenv("MSTR_PASSWORD")
    project = os.getenv("MSTR_PROJECT")
    return Connection(base_url, username, password, login_mode=1, project_name=project)

def load_dossiers_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def measure_instance_time_csv_polling(conn, dossier_id, viz_key, poll_interval=0.5, timeout=900):
    # Instance başlat
    inst = conn.post(
        f"{conn.base_url}/api/dossiers/{dossier_id}/instances",
        json={"filters": []}
    ).json()
    mid = inst["mid"]

    csv_url = f"{conn.base_url}/api/documents/{dossier_id}/instances/{mid}/visualizations/{viz_key}/csv"
    start_time = time.time()
    while True:
        try:
            res = conn.post(csv_url)
            res.raise_for_status()
            elapsed = time.time() - start_time
            return elapsed, mid
        except Exception as e:
            # Hata kodu 404 veya 409 ise (instance henüz hazır değil) tekrar dene
            if time.time() - start_time > timeout:
                return None, mid
            time.sleep(poll_interval)

def main():
    conn = create_connection()
    dossiers = load_dossiers_config()
    results = []

    for report_name, report in dossiers.items():
        
        dossier_id = report["dossier_id"]
        viz_key = report["viz_keys"]["summary"]  # Sadece summary key kullanılacak
        #if dossier_id != 'FDC1B21D494DFD70BC4F6F943E77F448':
        #    continue 
        print(f"{report_name} ({dossier_id}, {viz_key}): instance+csv hazırlanma süresi ölçülüyor...")
        try:
            elapsed, mid = measure_instance_time_csv_polling(conn, dossier_id, viz_key)
            if elapsed is not None:
                print(f"  -> {elapsed:.2f} saniye")
            else:
                print("  -> Zaman aşımı/timeout")
            results.append({
                "report_name": report_name,
                "dossier_id": dossier_id,
                "viz_key": viz_key,
                "instance_id": mid,
                "elapsed_seconds": elapsed
            })
        except Exception as e:
            print(f"  -> HATA: {e}")
            results.append({
                "report_name": report_name,
                "dossier_id": dossier_id,
                "viz_key": viz_key,
                "instance_id": None,
                "elapsed_seconds": None,
                "error": str(e)
            })

    df = pd.DataFrame(results)
    df.to_excel(EXCEL_OUT, index=False)
    print(f"\nSonuçlar: {EXCEL_OUT} dosyasına kaydedildi.")

if __name__ == "__main__":
    main()
