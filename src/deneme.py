from mstrio.connection import Connection
import os
from dotenv import load_dotenv


load_dotenv()

conn = Connection(
    os.getenv("MSTR_URL_API"),
    os.getenv("MSTR_USERNAME"),
    os.getenv("MSTR_PASSWORD"),
    login_mode=1,
    project_name=os.getenv("MSTR_PROJECT")
)

dossier_id = "6D1B67F64A2D55FA78863EA2F9F5A042"
viz_key = "K52"

# Instance başlat, dönen JSON’u ekrana yaz
resp = conn.post(
    f"{conn.base_url}/api/dossiers/{dossier_id}/instances",
    json={"filters": []}
)
resp.raise_for_status()
instance_json = resp.json()

print("Instance JSON response:")
for k, v in instance_json.items():
    print(f"{k}: {v}")

import time

inst = conn.post(
    f"{conn.base_url}/api/dossiers/{dossier_id}/instances",
    json={"filters": []}
).json()
mid = inst["mid"]
status = inst["status"]

while status == 0:
    print(f"Bekleniyor... Instance {mid}, status={status}")
    time.sleep(1)
    # Tekrar status kontrolü (aynı endpointle yapılmaz, /status endpointi kapalıysa tekrar instance başlatılmaz!)
    # En pratik yöntem: CSV endpointini deneyerek polling yapmaktır.

print(f"Instance {mid} status={status} (hazır!)")
