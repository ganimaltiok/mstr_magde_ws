import pandas as pd
from datetime import datetime
from typing import Optional

# Tarih aralığı filtresi uygulanacak kolonlar
DATE_COLUMN_LIST = [
    "policeOnayTarih", "policeBaslangicTarihi", "policeBitisTarihi",
    "teklifGecerlilikBitisTarih", "policeVadeBaslangic", "policeVadeBitis",
    "ihbarTarihi", "hasarTarihi", "acenteKurulusTarihi", "confirmDate", 
    "polBegDate", "polEndDate", "begDate", "endDate", "propValidBegDate", 
    "propValidEndDate", "policeTanzimTarihi", "girisTarihi", "sonKullanmaTarihi",
    "vadeTarihi", "kapanisTarihi", "enSonMuallakTarihi", "policeBaslangic",
    "policeBitis"
]

def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.strptime(date_str, "%m/%d/%Y") if date_str else None
    except ValueError:
        try:
            return pd.to_datetime(date_str, errors='coerce')
        except Exception:
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

    # 1. DATE_COLUMN_LIST için [_beg_date, _end_date] kontrol et
    for col in DATE_COLUMN_LIST:
        col_lower = col.lower()
        beg_key = f"{col_lower}_beg_date"
        end_key = f"{col_lower}_end_date"
        beg_val = filters.get(beg_key)
        end_val = filters.get(end_key)
        if beg_val or end_val:
            if col in df_result.columns:
                df_result = _filter_date_range(df_result, col, beg_val, end_val)

    # Diğer filtreleri doğrudan kolon adı eşleşmesiyle uygula
    excluded_keys = {f"{col.lower()}_beg_date" for col in DATE_COLUMN_LIST}
    excluded_keys |= {f"{col.lower()}_end_date" for col in DATE_COLUMN_LIST}

    for key, value in filters.items():
        if key in excluded_keys:
            continue
        for col in df_result.columns:
            if col.lower() == key:
                df_result = _filter_exact(df_result, col, value)

    return df_result