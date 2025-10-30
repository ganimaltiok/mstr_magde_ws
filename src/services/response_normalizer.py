"""
Response format normalizer to ensure consistency with legacy API format.
Converts data types to match the old API's string-based format.
"""
import math
from typing import Any, Dict, List


def normalize_value(value: Any) -> Any:
    """
    Normalize a single value to match old API format:
    - null/NaN → "NULL"
    - Keep numbers as numbers (not strings)
    - Keep strings as strings
    """
    # Handle None/null
    if value is None:
        return "NULL"
    
    # Handle NaN (float)
    if isinstance(value, float) and math.isnan(value):
        return "NULL"
    
    # Keep everything else as-is
    return value


def normalize_data_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize a list of data records to match old API format.
    Converts null/NaN values to "NULL" string.
    """
    normalized = []
    for record in records:
        normalized_record = {}
        for key, value in record.items():
            normalized_record[key] = normalize_value(value)
        normalized.append(normalized_record)
    return normalized


__all__ = ['normalize_value', 'normalize_data_records']
