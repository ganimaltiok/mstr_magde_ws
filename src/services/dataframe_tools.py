from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Iterable, Optional, Sequence

import pandas as pd

_TURKISH_REPLACEMENTS = {
    "ç": "c",
    "Ç": "C",
    "ğ": "g",
    "Ğ": "G",
    "ı": "i",
    "I": "I",
    "i": "i",
    "İ": "I",
    "ö": "o",
    "Ö": "O",
    "ş": "s",
    "Ş": "S",
    "ü": "u",
    "Ü": "U",
}

_AGENCY_COLUMN_HINTS = {"agency", "agencycode", "agencyid", "acentekodu", "acente", "acenteid"}


def replace_turkish_characters(value: str) -> str:
    for src, dst in _TURKISH_REPLACEMENTS.items():
        value = value.replace(src, dst)
    return value


def is_lower_camel_case(value: str) -> bool:
    return bool(value) and value[0].islower() and any(ch.isupper() for ch in value[1:])


def to_ascii_camel(value: str) -> str:
    value = replace_turkish_characters(value)
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    parts = re.sub(r"[^0-9a-zA-Z]+", " ", normalized).strip().split()
    if not parts:
        return ""
    head, *tail = parts
    head = head.lower()
    camel_tail = "".join(fragment.title() for fragment in tail)
    candidate = f"{head}{camel_tail}"
    return candidate if candidate else value


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [
        col if is_lower_camel_case(str(col)) else to_ascii_camel(str(col))
        for col in out.columns
    ]
    return out


def normalise_agency_code_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert numeric agency columns to string to preserve leading zeros.
    """
    out = df.copy()
    for column in out.columns:
        simplified = re.sub(r"[^a-z]", "", column.lower())
        if simplified in _AGENCY_COLUMN_HINTS or simplified.startswith(("agency", "acente")):
            if pd.api.types.is_numeric_dtype(out[column]):
                out[column] = out[column].apply(
                    lambda value: str(int(value)) if not pd.isna(value) else value
                )
            else:
                out[column] = out[column].astype(str)
    return out


def coerce_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in out.select_dtypes(include=["datetime", "datetimetz"]).columns:
        out[column] = out[column].dt.strftime("%Y-%m-%d %H:%M:%S")
    return out


def stringify_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    def _stringify(value: Any) -> str:
        if pd.isna(value):
            return "NULL"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        return str(value)

    return df.applymap(_stringify)


def extract_cube_time(df: pd.DataFrame) -> tuple[pd.DataFrame, Optional[Any]]:
    """
    Identify a refresh timestamp column and remove it from the dataframe.
    """
    out = df.copy()
    cube_time = None
    for column in list(out.columns):
        simplified = re.sub(r"[^a-z]", "", column.lower())
        if simplified == "datarefreshtime":
            cube_time = out[column].iloc[0] if not out.empty else None
            out = out.drop(columns=[column])
            break
    return out, cube_time


def filter_by_agency(df: pd.DataFrame, agency_code: str | None) -> pd.DataFrame:
    if agency_code is None:
        return df

    target = str(agency_code)
    for column in df.columns:
        simplified = re.sub(r"[^a-z]", "", column.lower())
        if simplified in _AGENCY_COLUMN_HINTS or any(hint in simplified for hint in _AGENCY_COLUMN_HINTS):
            try:
                mask = df[column].astype(str) == target
                return df[mask]
            except Exception:
                continue
    return df


def apply_filters(df: pd.DataFrame, filters: dict[str, str]) -> pd.DataFrame:
    """
    Apply filters to dataframe in-memory.
    Used for Redis cached data where full dataset is stored.
    
    Args:
        df: DataFrame to filter
        filters: Dict of column_name -> value
    
    Returns:
        Filtered DataFrame
    """
    if not filters or df.empty:
        return df
    
    result = df.copy()
    
    for filter_key, filter_value in filters.items():
        if not filter_value:
            continue
        
        # Find matching column (case-insensitive)
        matching_cols = [col for col in result.columns if col.lower() == filter_key.lower()]
        
        if not matching_cols:
            continue
        
        column = matching_cols[0]
        
        try:
            # String comparison (handles dates, numbers as strings)
            mask = result[column].astype(str).str.lower() == str(filter_value).lower()
            result = result[mask]
        except Exception as e:
            # If filtering fails, skip this filter
            continue
    
    return result


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    processed = coerce_datetime_columns(df)
    processed = stringify_dataframe(processed)
    return processed.to_dict(orient="records")


def dataframe_to_pretty_json(df: pd.DataFrame) -> str:
    return json.dumps(dataframe_to_records(df), ensure_ascii=False, indent=2)


__all__ = [
    "apply_filters",
    "dataframe_to_pretty_json",
    "dataframe_to_records",
    "extract_cube_time",
    "filter_by_agency",
    "is_lower_camel_case",
    "normalise_columns",
    "normalise_agency_code_columns",
    "replace_turkish_characters",
    "stringify_dataframe",
    "to_ascii_camel",
]
