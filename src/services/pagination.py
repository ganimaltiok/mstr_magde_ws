import pandas as pd
from typing import Dict, Any, Tuple
import math


def paginate_dataframe(
    df: pd.DataFrame,
    page: int = 1,
    per_page: int = 100
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Paginate a DataFrame.
    
    Args:
        df: DataFrame to paginate
        page: Page number (1-indexed)
        per_page: Items per page
    
    Returns:
        (paginated_df, pagination_info)
        
        pagination_info = {
            'page': int,
            'per_page': int,
            'total_pages': int,
            'total_records': int
        }
    """
    total_records = len(df)
    total_pages = math.ceil(total_records / per_page) if per_page > 0 else 1
    
    # Clamp page to valid range
    page = max(1, min(page, total_pages if total_pages > 0 else 1))
    
    # Calculate slice
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    paginated_df = df.iloc[start_idx:end_idx]
    
    pagination_info = {
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'total_records': total_records
    }
    
    return paginated_df, pagination_info
