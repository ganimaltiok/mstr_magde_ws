from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from urllib.parse import quote_plus
import pandas as pd
import warnings
from typing import Dict, List, Tuple, Optional, Any
from services.settings import get_settings
import logging

logger = logging.getLogger(__name__)


class PGFetcher:
    """Fetch data from PostgreSQL with server-side filtering and pagination."""
    
    def __init__(self):
        self.settings = get_settings()
        self._engine = None
    
    def _get_engine(self):
        """Get SQLAlchemy engine (lazy initialization)."""
        if self._engine is None:
            # Build connection params from settings
            if not self.settings.pg_database:
                raise ValueError("PostgreSQL connection not configured (missing PG_DATABASE)")
            
            # Ensure we have a valid host (not empty, not just whitespace)
            host = (self.settings.pg_host or '').strip()
            if not host:
                raise ValueError("PostgreSQL PG_HOST is empty or not configured")
            
            port = self.settings.pg_port if self.settings.pg_port else 5432
            user = quote_plus(self.settings.pg_user or 'postgres')
            password = quote_plus(self.settings.pg_password or '')
            database = self.settings.pg_database
            
            # Build SQLAlchemy connection string with URL-encoded credentials
            connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
            
            logger.info(f"Creating PostgreSQL engine for {host}:{port}/{database}")
            
            # Use NullPool to avoid connection pooling issues
            # echo=False disables SQLAlchemy query logging (we log queries manually)
            self._engine = create_engine(
                connection_string,
                poolclass=NullPool,
                echo=False
            )
        return self._engine
    
    def _get_table_columns(self, schema: str, table: str) -> List[str]:
        """Get list of columns for validation."""
        query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            ORDER BY ordinal_position
        """)
        
        engine = self._get_engine()
        with engine.connect() as conn:
            result = conn.execute(query, {"schema": schema, "table": table})
            return [row[0] for row in result]
    
    def _build_where_clause(
        self,
        query_params: Dict[str, str],
        table_columns: List[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """Build WHERE clause from query parameters (same logic as SQL fetcher)."""
        conditions = []
        params = {}
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
                placeholders = ','.join([f':p{i}' for i in range(param_counter, param_counter + len(values))])
                conditions.append(f'"{column}" IN ({placeholders})')
                for val in values:
                    params[f'p{param_counter}'] = val
                    param_counter += 1
            elif operator == 'ILIKE':
                param_key = f'p{param_counter}'
                conditions.append(f'"{column}" ILIKE :{param_key}')
                params[param_key] = f"%{param_value}%"
                param_counter += 1
            else:
                param_key = f'p{param_counter}'
                conditions.append(f'"{column}" {operator} :{param_key}')
                params[param_key] = param_value
                param_counter += 1
        
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
            
            engine = self._get_engine()
            
            # Count total records
            count_sql = text(f'SELECT COUNT(*) FROM "{schema}"."{table}" WHERE {where_clause}')
            logger.info(f"PostgreSQL COUNT query: {count_sql} | Params: {params}")
            with engine.connect() as conn:
                result = conn.execute(count_sql, params)
                total_records = result.scalar()
            
            # Fetch data with pagination
            offset = (page - 1) * per_page
            data_sql = f"""
                SELECT * FROM "{schema}"."{table}"
                WHERE {where_clause}
                ORDER BY 1
                LIMIT :limit OFFSET :offset
            """
            
            params_with_pagination = {**params, 'limit': per_page, 'offset': offset}
            logger.info(f"PostgreSQL SELECT query: {data_sql} | Params: {params_with_pagination}")
            df = pd.read_sql(text(data_sql), engine, params=params_with_pagination)
            
            # Build executable query (replace parameters and remove double quotes)
            executable_query = data_sql
            for param_name, param_value in params_with_pagination.items():
                # Format value for SQL
                if isinstance(param_value, str):
                    formatted_value = f"'{param_value}'"
                elif param_value is None:
                    formatted_value = "NULL"
                else:
                    formatted_value = str(param_value)
                executable_query = executable_query.replace(f':{param_name}', formatted_value)
            
            # Remove double quotes from table/column names
            executable_query = executable_query.replace('"', '')
            
            # Remove line breaks and extra whitespace
            executable_query = ' '.join(executable_query.split())
            
            # Convert datetime/timestamp columns to ISO format strings (like MSTR) BEFORE to_dict()
            for col in df.columns:
                # Try to convert object columns to datetime
                if df[col].dtype == 'object':
                    # Try to infer datetime, but check if conversion actually worked
                    try:
                        # Suppress UserWarning about date format inference
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", UserWarning)
                            converted = pd.to_datetime(df[col], errors='coerce')
                        # Only keep conversion if at least one value was successfully parsed
                        if converted.notna().any():
                            df[col] = converted
                    except Exception:
                        pass
                
                # Now check if it's a datetime type and convert to ISO string
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    logger.info(f"Converting datetime column: {col}")
                    df[col] = df[col].apply(
                        lambda x: x.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + '+03:00' 
                        if pd.notna(x) else "NULL"
                    )
            
            # Convert DataFrame to records with NULL string for None values
            import math
            data_records = df.to_dict('records')
            normalized_records = []
            for record in data_records:
                normalized = {}
                for key, value in record.items():
                    # Convert None/NaN to "NULL" string
                    if value is None or (isinstance(value, float) and math.isnan(value)):
                        value = "NULL"
                    normalized[key] = value
                normalized_records.append(normalized)
            
            return {
                'data': normalized_records,
                'total_records': total_records,
                'columns': df.columns.tolist(),
                'query': executable_query.strip()
            }
        
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
            engine = self._get_engine()
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.scalar()
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
