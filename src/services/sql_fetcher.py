import pyodbc
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from services.settings import get_settings
import logging

logger = logging.getLogger(__name__)


class SQLFetcher:
    """Fetch data from MSSQL with server-side filtering and pagination."""
    
    def __init__(self):
        self.settings = get_settings()
        self._connection_pool: Optional[pyodbc.Connection] = None
    
    def _get_connection(self) -> pyodbc.Connection:
        """Get database connection."""
        conn_str = self.settings.mssql_connection_string
        if not conn_str:
            raise ValueError("MSSQL connection not configured")
        
        return pyodbc.connect(conn_str, timeout=30)
    
    def _get_table_columns(self, schema: str, table: str) -> List[str]:
        """Get list of columns for validation."""
        query = """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
        """
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (schema, table))
            return [row[0] for row in cursor.fetchall()]
    
    def _build_where_clause(
        self,
        query_params: Dict[str, str],
        table_columns: List[str]
    ) -> Tuple[str, List[Any]]:
        """
        Build WHERE clause from query parameters.
        
        Supported operators (suffix in param name):
        - _eq / no suffix: = (default)
        - _ne: !=
        - _gt: >
        - _gte: >=
        - _lt: <
        - _lte: <=
        - _like: LIKE
        - _in: IN (comma-separated values)
        """
        conditions = []
        params = []
        
        for param_name, param_value in query_params.items():
            # Skip pagination params
            if param_name in ['page', 'per_page']:
                continue
            
            # Parse operator
            if param_name.endswith('_gte'):
                column = param_name[:-4]
                operator = '>='
            elif param_name.endswith('_lte'):
                column = param_name[:-4]
                operator = '<='
            elif param_name.endswith('_gt'):
                column = param_name[:-3]
                operator = '>'
            elif param_name.endswith('_lt'):
                column = param_name[:-3]
                operator = '<'
            elif param_name.endswith('_ne'):
                column = param_name[:-3]
                operator = '!='
            elif param_name.endswith('_like'):
                column = param_name[:-5]
                operator = 'LIKE'
            elif param_name.endswith('_in'):
                column = param_name[:-3]
                operator = 'IN'
            else:
                column = param_name
                operator = '='
            
            # Validate column exists
            if column not in table_columns:
                logger.warning(f"Ignoring unknown column filter: {column}")
                continue
            
            # Build condition
            if operator == 'IN':
                values = param_value.split(',')
                placeholders = ','.join(['?' for _ in values])
                conditions.append(f"[{column}] IN ({placeholders})")
                params.extend(values)
            elif operator == 'LIKE':
                conditions.append(f"[{column}] LIKE ?")
                params.append(f"%{param_value}%")
            else:
                conditions.append(f"[{column}] {operator} ?")
                params.append(param_value)
        
        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        return where_clause, params
    
    def fetch(
        self,
        schema: str,
        table: str,
        query_params: Dict[str, str],
        page: int = 1,
        per_page: int = 100
    ) -> Dict[str, Any]:
        """
        Fetch data with server-side filtering and pagination.
        
        Returns:
            {
                'data': List[Dict],
                'total_records': int,
                'columns': List[str]
            }
        """
        try:
            # Get table columns for validation
            columns = self._get_table_columns(schema, table)
            
            # Build WHERE clause
            where_clause, params = self._build_where_clause(query_params, columns)
            
            # Count total records
            count_sql = f"SELECT COUNT(*) FROM [{schema}].[{table}] WHERE {where_clause}"
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(count_sql, params)
                total_records = cursor.fetchone()[0]
                
                # Fetch data with pagination
                offset = (page - 1) * per_page
                data_sql = f"""
                    SELECT * FROM [{schema}].[{table}]
                    WHERE {where_clause}
                    ORDER BY (SELECT NULL)
                    OFFSET ? ROWS
                    FETCH NEXT ? ROWS ONLY
                """
                
                params_with_pagination = params + [offset, per_page]
                df = pd.read_sql(data_sql, conn, params=params_with_pagination)
            
            return {
                'data': df.to_dict('records'),
                'total_records': total_records,
                'columns': df.columns.tolist()
            }
        
        except Exception as e:
            logger.error(f"Error fetching from MSSQL {schema}.{table}: {e}")
            raise
    
    def test_connection(self) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Test database connection.
        
        Returns:
            (success, error_message, response_time_ms)
        """
        import time
        
        try:
            start = time.time()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            elapsed_ms = (time.time() - start) * 1000
            return True, None, elapsed_ms
        
        except Exception as e:
            return False, str(e), None


# Singleton instance
_sql_fetcher: Optional[SQLFetcher] = None


def get_sql_fetcher() -> SQLFetcher:
    """Get SQL fetcher singleton."""
    global _sql_fetcher
    if _sql_fetcher is None:
        _sql_fetcher = SQLFetcher()
    return _sql_fetcher
