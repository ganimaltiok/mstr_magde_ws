import unicodedata
import re
import json
import pandas as pd
from mstrio.project_objects import OlapCube
from datetime import datetime
import os
import yaml

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config", "dossiers.yaml")

CACHE_POLICY_NONE = "none"
CACHE_POLICY_DAILY = "daily"


def load_config():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(base_dir, "config", "dossiers.yaml")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict) -> None:
    import os, yaml
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(base_dir, "config", "dossiers.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, default_flow_style=False)


def resolve_cache_policy(cfg: dict) -> str:
    """
    Determine the cache policy for a given report configuration.

    Accepts legacy integer-based ``is_csv_cached`` flags and maps them to the
    simplified ``none`` / ``daily`` options while prioritising the explicit
    ``cache_policy`` field when present.
    """
    if not cfg:
        return CACHE_POLICY_NONE

    policy = (cfg.get("cache_policy") or "").strip().lower()
    if policy in {CACHE_POLICY_NONE, CACHE_POLICY_DAILY}:
        return policy

    legacy_flag = cfg.get("is_csv_cached")
    try:
        legacy_flag = int(legacy_flag)
    except (TypeError, ValueError):
        legacy_flag = 0

    if legacy_flag > 0:
        return CACHE_POLICY_DAILY
    return CACHE_POLICY_NONE


def try_parse_date(s):
    from dateutil.parser import parse
    try:
        return parse(s)
    except:
        return s


def is_lower_camel_case(s: str) -> bool:
    """Check if a string is in lowerCamelCase format."""
    return s[0].islower() and any(c.isupper() for c in s[1:])


def replace_turkish_characters(text: str) -> str:
    replacements = {
        "ç": "c", "Ç": "C",
        "ğ": "g", "Ğ": "G",
        "ı": "i", "I": "I",
        "i": "i", "İ": "I",
        "ö": "o", "Ö": "O",
        "ş": "s", "Ş": "S",
        "ü": "u", "Ü": "U"
    }
    for turkish, ascii in replacements.items():
        text = text.replace(turkish, ascii)
    return text

def _to_camel_no_tr(s: str) -> str:
    """Convert string to ASCII-only camelCase."""
    s_norm = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    parts = re.sub(r"[^0-9a-zA-Z]+", " ", s_norm).strip().split()
    return parts[0].lower() + ''.join(p.title() for p in parts[1:]) if parts else ""

def _stringify_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Convert all DataFrame values to strings and replace missing values with 'NULL'."""
    return df.applymap(lambda value: "NULL" if pd.isna(value) else str(value))


def dataframe_to_pretty_json(df: pd.DataFrame) -> str:
    """Convert DataFrame to pretty JSON with camelCase keys and missing→'NULL' and datetime→str."""
    df2 = df.copy()
    df2.columns = [_to_camel_no_tr(c) for c in df2.columns]
    
    for col in df2.select_dtypes(include=["datetime", "datetimetz"]).columns:
        df2[col] = df2[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    df2 = _stringify_dataframe(df2)
    return json.dumps(df2.to_dict(orient="records"), ensure_ascii=False, indent=2)


def save_dataframe_to_json_file(df: pd.DataFrame, file_path: str) -> None:
    """Save DataFrame as pretty JSON file."""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(dataframe_to_pretty_json(df))

def get_cube_last_update_time(conn, cube_id: str) -> str:
    """
    OlapCube üzerinden zaman bilgisini alır, datetime objesine dönüştürür
    ve 'YYYY-MM-DD HH:MM:SS' formatında döner.
    """
    if not cube_id:
        return "NULL"
    
    cube = OlapCube(connection=conn, id=cube_id)
    t = cube.last_update_time

    # Eğer zaten datetime objesi değilse, ISO string’i parse et
    if not isinstance(t, datetime):
        t = datetime.fromisoformat(t)
    return t.strftime("%Y-%m-%d %H:%M:%S")

def safe_json_serialize(df: pd.DataFrame) -> str:
    """Safely convert DataFrame to JSON without renaming columns. Handles missing values and datetime."""
    df2 = df.copy()

    # Convert datetime columns to string
    for col in df2.select_dtypes(include=["datetime", "datetimetz"]).columns:
        df2[col] = df2[col].dt.strftime("%Y-%m-%d %H:%M:%S")

    df2 = _stringify_dataframe(df2)
    return json.dumps(df2.to_dict(orient="records"), ensure_ascii=False, indent=2)
