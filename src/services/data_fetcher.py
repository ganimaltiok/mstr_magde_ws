import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime
import pytz
from services.endpoint_config import EndpointConfig
from services.sql_fetcher import get_sql_fetcher
from services.pg_fetcher import get_pg_fetcher
from services.mstr_fetcher import get_mstr_fetcher
from services.pagination import paginate_dataframe
import logging
import math

logger = logging.getLogger(__name__)


class DataFetchResult:
    """Result of data fetching operation."""
    
    def __init__(
        self,
        data: list,
        total_records: int,
        pagination: Dict[str, int],
        columns: list,
        error: Optional[Dict[str, Any]] = None,
        query: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ):
        self.data = data
        self.total_records = total_records
        self.pagination = pagination
        self.columns = columns
        self.error = error
        self.query = query
        self.params = params
    
    @property
    def has_error(self) -> bool:
        return self.error is not None


class DataFetcher:
    """Orchestrate data fetching based on endpoint behavior."""
    
    def __init__(self):
        self.sql_fetcher = get_sql_fetcher()
        self.pg_fetcher = get_pg_fetcher()
        self.mstr_fetcher = get_mstr_fetcher()
    
    def fetch(
        self,
        endpoint_config: EndpointConfig,
        query_params: Dict[str, str],
        info_type: str = 'summary',
        page: int = 1,
        per_page: Optional[int] = None
    ) -> DataFetchResult:
        """
        Fetch data based on endpoint behavior.
        
        Args:
            endpoint_config: Endpoint configuration
            query_params: Query parameters from request
            info_type: 'summary' or 'detail' (for MSTR)
            page: Page number
            per_page: Items per page (overrides config default)
        
        Returns:
            DataFetchResult with data and metadata
        """
        if per_page is None:
            per_page = endpoint_config.per_page
        
        try:
            # Route to appropriate fetcher
            if endpoint_config.is_sql:
                return self._fetch_sql(endpoint_config, query_params, page, per_page)
            elif endpoint_config.is_pg:
                return self._fetch_pg(endpoint_config, query_params, page, per_page)
            elif endpoint_config.is_mstr:
                return self._fetch_mstr(endpoint_config, query_params, info_type, page, per_page)
            else:
                raise ValueError(f"Unknown behavior: {endpoint_config.behavior}")
        
        except Exception as e:
            logger.error(f"Error fetching data for {endpoint_config.name}: {e}", exc_info=True)
            return self._error_result(endpoint_config, str(e), type(e).__name__)
    
    def _fetch_sql(
        self,
        config: EndpointConfig,
        query_params: Dict[str, str],
        page: int,
        per_page: int
    ) -> DataFetchResult:
        """Fetch from MSSQL."""
        schema = config.mssql.get('schema')
        table = config.mssql.get('table')
        
        if not schema or not table:
            raise ValueError("MSSQL schema and table required")
        
        result = self.sql_fetcher.fetch(schema, table, query_params, page, per_page)
        
        total_pages = math.ceil(result['total_records'] / per_page) if per_page > 0 else 1
        
        return DataFetchResult(
            data=result['data'],
            total_records=result['total_records'],
            pagination={
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'total_records': result['total_records']
            },
            columns=result['columns']
        )
    
    def _fetch_pg(
        self,
        config: EndpointConfig,
        query_params: Dict[str, str],
        page: int,
        per_page: int
    ) -> DataFetchResult:
        """Fetch from PostgreSQL."""
        schema = config.postgresql.get('schema')
        table = config.postgresql.get('table')
        
        if not schema or not table:
            raise ValueError("PostgreSQL schema and table required")
        
        result = self.pg_fetcher.fetch(schema, table, query_params, page, per_page)
        
        total_pages = math.ceil(result['total_records'] / per_page) if per_page > 0 else 1
        
        return DataFetchResult(
            data=result['data'],
            total_records=result['total_records'],
            pagination={
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'total_records': result['total_records']
            },
            columns=result['columns'],
            query=result.get('query'),
            params=result.get('params')
        )
    
    def _fetch_mstr(
        self,
        config: EndpointConfig,
        query_params: Dict[str, str],
        info_type: str,
        page: int,
        per_page: int
    ) -> DataFetchResult:
        """Fetch from MicroStrategy."""
        result = self.mstr_fetcher.fetch(
            endpoint_config=config,
            query_params=query_params,
            info_type=info_type,
            page=page,
            per_page=per_page
        )
        
        # For cachemstr, data is fetched in full - paginate in memory
        if config.behavior == 'cachemstr':
            df = pd.DataFrame(result['data'])
            
            paginated_df, pagination_info = paginate_dataframe(df, page, per_page)
            
            paginated_records = paginated_df.to_dict('records')
            
            return DataFetchResult(
                data=paginated_records,
                total_records=result['total_records'],
                pagination=pagination_info,
                columns=result['columns']
            )
        else:
            # For livemstr, pagination already done server-side
            total_pages = math.ceil(result['total_records'] / per_page) if per_page > 0 else 1
            
            return DataFetchResult(
                data=result['data'],
                total_records=result['total_records'],
                pagination={
                    'page': page,
                    'per_page': per_page,
                    'total_pages': total_pages,
                    'total_records': result['total_records']
                },
                columns=result['columns']
            )
    
    def _error_result(
        self,
        config: EndpointConfig,
        error_message: str,
        error_type: str
    ) -> DataFetchResult:
        """Create error result."""
        istanbul_tz = pytz.timezone('Europe/Istanbul')
        
        return DataFetchResult(
            data=[],
            total_records=0,
            pagination={
                'page': 1,
                'per_page': config.per_page,
                'total_pages': 0,
                'total_records': 0
            },
            columns=[],
            error={
                'type': error_type,
                'message': error_message,
                'timestamp': datetime.now(istanbul_tz).isoformat()
            }
        )


# Singleton instance
_data_fetcher: Optional[DataFetcher] = None


def get_data_fetcher() -> DataFetcher:
    """Get data fetcher singleton."""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = DataFetcher()
    return _data_fetcher
