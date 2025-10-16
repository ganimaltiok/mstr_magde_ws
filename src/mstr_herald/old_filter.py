import pandas as pd
from datetime import datetime
from typing import Optional

def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.strptime(date_str, "%m/%d/%Y") if date_str else None
    except ValueError:
        return None

def _filter_exact(df: pd.DataFrame, column: str, value) -> pd.DataFrame:
    if column not in df.columns:
        return df

    col_dtype = df[column].dtype
    try:
        if pd.api.types.is_numeric_dtype(col_dtype):
            value = float(value)
        elif pd.api.types.is_datetime64_any_dtype(col_dtype):
            value = _parse_date(value)
        return df[df[column] == value]
    except Exception:
        return df
    return df

def _filter_date_range(df: pd.DataFrame, column: str, start_date: Optional[str], end_date: Optional[str]) -> pd.DataFrame:
    if column not in df.columns:
        return df

    dt_series = pd.to_datetime(df[column], errors='coerce')
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    mask = pd.Series([True] * len(df), index=df.index)
    if start:
        mask &= dt_series >= start
    if end:
        mask &= dt_series <= end

    return df[mask]

def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    df_result = df.copy()
    filters = {k.lower(): v for k, v in filters.items()}

    # Önceden tanımlı filtreler (key: input param, value: dataframe column)
    key_map = {
        "start_date": "start_date",
        "end_date": "end_date",
        "urunanabransno": "urunAnaBransNo",
        "urunno": "urunNo",
        "musteritcknvkn": "musteriTcknVkn",
        "sigortalitcknvkn": "sigortaliTcknVkn",
    }

    # Özel tarih aralığı filtresi (sabit kolon adı ile)
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    df_result = _filter_date_range(df_result, "policeOnayTarih", start_date, end_date)

    # Harita üzerinden eşleşen filtreleri uygula
    for raw_key, col_name in key_map.items():
        if raw_key in filters and col_name in df_result.columns:
            df_result = _filter_exact(df_result, col_name, filters[raw_key])

    # Diğer her şeyi: filtre adı kolon adıyla birebir eşleşiyorsa uygula
    excluded_keys = set(["start_date", "end_date"]) | set(key_map.keys())
    for key, value in filters.items():
        if key in excluded_keys:
            continue
        for col in df_result.columns:
            if col.lower() == key:  # case-insensitive eşleşme
                df_result = _filter_exact(df_result, col, value)

    return df_result
