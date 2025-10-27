import psycopg2
import psycopg2.pool
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from services.settings import get_settings
import logging

logger = logging.getLogger(__name__)


class PGFetcher:
    """Fetch data from PostgreSQL with server-side filtering and pagination."""
    
    def __init__(self):
        self.settings = get_settings()
        self._connection_pool: Optional[psycopg2.pool.SimpleConnectionPool] = None
    
    def _get_pool(self) -> psycopg2.pool.SimpleConnectionPool:
        """Get connection pool (lazy initialization)."""
        if self._connection_pool is None:
            params = self.settings.pg_connection_params
            if not params:
                raise ValueError("PostgreSQL connection not configured")
            
            self._connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                **params
            )
        return self._connection_pool
    
    def _get_connection(self):
        """Get connection from pool."""
        return self._get_pool().getconn()
    
    def _return_connection(self, conn):
        """Return connection to pool."""
        self._get_pool().putconn(conn)
    
    def _get_table_columns(self, schema: str, table: str) -> List[str]:
        """Get list of columns for validation."""
        query = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (schema, table))
            return [row[0] for row in cursor.fetchall()]
        finally:
            self._return_connection(conn)
    
    def _build_where_clause(
        self,
        query_params: Dict[str, str],
        table_columns: List[str]
    ) -> Tuple[str, List[Any]]:
        """Build WHERE clause from query parameters (same logic as SQL fetcher)."""
        conditions = []
        params = []
        param_counter = 1
        
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
                operator = 'ILIKE'  # Case-insensitive LIKE for PostgreSQL
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
                placeholders = ','.join([f'%s' for _ in values])
                conditions.append(f'"{column}" IN ({placeholders})')
                params.extend(values)
            elif operator == 'ILIKE':
                conditions.append(f'"{column}" ILIKE %s')
                params.append(f"%{param_value}%")
            else:
                conditions.append(f'"{column}" {operator} %s')
                params.append(param_value)
        
        where_clause = ' AND '.join(conditions) if conditions else 'TRUE'
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
            
            conn = self._get_connection()
            try:
                # Count total records
                count_sql = f'SELECT COUNT(*) FROM "{schema}"."{table}" WHERE {where_clause}'
                cursor = conn.cursor()
                cursor.execute(count_sql, params)
                total_records = cursor.fetchone()[0]
                
                # Fetch data with pagination
                offset = (page - 1) * per_page
                data_sql = f"""
                    SELECT * FROM "{schema}"."{table}"
                    WHERE {where_clause}
                    ORDER BY 1
                    LIMIT %s OFFSET %s
                """
                
                params_with_pagination = params + [per_page, offset]
                df = pd.read_sql(data_sql, conn, params=params_with_pagination)
                
                return {
                    'data': df.to_dict('records'),
                    'total_records': total_records,
                    'columns': df.columns.tolist()
                }
            finally:
                self._return_connection(conn)
        
        except Exception as e:
            logger.error(f"Error fetching from PostgreSQL {schema}.{table}: {e}")
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
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            finally:
                self._return_connection(conn)
            elapsed_ms = (time.time() - start) * 1000
            return True, None, elapsed_ms
        
        except Exception as e:
            return False, str(e), None


# Singleton instance
_pg_fetcher: Optional[PGFetcher] = None


def get_pg_fetcher() -> PGFetcher:
    """Get PG fetcher singleton."""
    global _pg_fetcher
    if _pg_fetcher is None:
        _pg_fetcher = PGFetcher()
    return _pg_fetcher
