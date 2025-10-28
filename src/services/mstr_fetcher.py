import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from io import StringIO
from mstr_herald.mstr_client import get_mstr_client
from services.endpoint_config import EndpointConfig
import logging

logger = logging.getLogger(__name__)


class MstrFetcher:
    """Fetch data from MicroStrategy with full filter support."""
    
    def __init__(self):
        self.client = get_mstr_client()
    
    def _build_filter_payload(
        self,
        filter_mappings: Dict[str, str],
        query_params: Dict[str, str]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Build MSTR filters array (v1-compatible format).
        
        Args:
            filter_mappings: Dict of param_name -> mstr_filter_key
            query_params: Query parameters from request
        
        Returns:
            List of filter objects or None if no filters
            Format: [{"key": filter_key, "selections": [{"name": value}]}]
        """
        applied_filters = []
        
        for param_name, param_value in query_params.items():
            # Skip pagination params
            if param_name in ['page', 'per_page']:
                continue
            
            if param_name not in filter_mappings:
                logger.warning(f"No MSTR filter mapping for param: {param_name}")
                continue
            
            filter_key = filter_mappings[param_name]
            
            # Build selections (v1 format)
            applied_filters.append({
                "key": filter_key,
                "selections": [{"name": str(param_value)}]
            })
        
        if applied_filters:
            logger.info(f"Applying {len(applied_filters)} MSTR filters")
        
        return applied_filters if applied_filters else None
    
    def fetch(
        self,
        endpoint_config: EndpointConfig,
        query_params: Dict[str, str],
        info_type: str = 'summary',
        page: int = 1,
        per_page: int = 100
    ) -> Dict[str, Any]:
        """
        Fetch data from MSTR report.
        
        For cachemstr behavior: Fetch full dataset (ignore page/per_page)
        For livemstr behavior: Use pagination
        
        Returns:
            {
                'data': List[Dict],
                'total_records': int,
                'columns': List[str]
            }
        """
        try:
            dossier_id = endpoint_config.mstr.get('dossier_id')
            viz_keys = endpoint_config.mstr.get('viz_keys', {})
            viz_key = viz_keys.get(info_type)
            filter_mappings = endpoint_config.mstr.get('filter_mappings', {})
            
            if not dossier_id or not viz_key:
                raise ValueError(f"Missing dossier_id or viz_key for {info_type}")
            
            # Build filter payload
            view_filter = self._build_filter_payload(filter_mappings, query_params)
            
            # For cached behavior, fetch all data (no limit/offset)
            if endpoint_config.behavior == 'cachemstr':
                limit = 0  # MSTR: 0 means all records
                offset = 0
            else:
                # For live behavior, use pagination
                limit = per_page
                offset = (page - 1) * per_page
            
            # Fetch from MSTR
            import sys
            print(f">>> Fetching from MSTR: dossier={dossier_id}, viz={viz_key}", file=sys.stderr, flush=True)
            logger.info(f">>> Fetching from MSTR: dossier={dossier_id}, viz={viz_key}, filters={view_filter}")
            response = self.client.get_report_data(
                dossier_id=dossier_id,
                viz_key=viz_key,
                view_filter=view_filter,
                limit=limit,
                offset=offset
            )
            print(f">>> MSTR response received OK", file=sys.stderr, flush=True)
            logger.info(f">>> MSTR response received: {type(response)}, status={response.status_code if hasattr(response, 'status_code') else 'N/A'}")
            
            # Parse CSV response with encoding detection
            # Try UTF-16 first (MSTR standard), then UTF-8, then Latin-1
            df = None
            last_error = None
            
            print(f">>> About to check content length", file=sys.stderr, flush=True)
            logger.info(f"Response content length: {len(response.content)} bytes")
            logger.info(f"Response headers: {response.headers.get('Content-Type', 'unknown')}")
            
            for encoding in ['utf-16', 'utf-8', 'latin-1', 'utf-16-le', 'utf-16-be', 'iso-8859-1']:
                try:
                    content = response.content.decode(encoding)
                    df = pd.read_csv(StringIO(content))
                    logger.info(f"✓ Successfully decoded CSV with {encoding}, rows: {len(df)}")
                    break
                except UnicodeDecodeError as e:
                    last_error = f"{encoding}: UnicodeDecodeError at position {e.start}"
                    logger.debug(f"✗ {last_error}")
                    continue
                except pd.errors.ParserError as e:
                    last_error = f"{encoding}: ParserError - {str(e)[:100]}"
                    logger.debug(f"✗ {last_error}")
                    continue
                except Exception as e:
                    last_error = f"{encoding}: {type(e).__name__} - {str(e)[:100]}"
                    logger.warning(f"✗ {last_error}")
                    continue
            
            if df is None:
                error_msg = f"Failed to decode CSV response. Last error: {last_error}. Tried: utf-16, utf-8, latin-1, utf-16-le, utf-16-be, iso-8859-1"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Replace NaN with None for JSON serialization
            df = df.where(pd.notnull(df), None)
            
            # Filter out aggregate rows (Total, Grand Total, etc.)
            # These rows typically have null/None values in key identifier columns
            if 'acente_kodu' in df.columns:
                # Remove rows where acente_kodu is null (aggregate rows)
                df = df[df['acente_kodu'].notna()]
            elif 'Agency Desc' in df.columns:
                # Remove rows that start with "Total" or "Grand Total"
                df = df[~df['Agency Desc'].astype(str).str.startswith('Total', na=False)]
            
            total_records = len(df)
            
            # Convert to dict with NaN as None
            data_records = df.to_dict('records')
            
            # Ensure NaN values are converted to None in the output
            import math
            for record in data_records:
                for key, value in record.items():
                    if isinstance(value, float) and math.isnan(value):
                        record[key] = None
            
            return {
                'data': data_records,
                'total_records': total_records,
                'columns': df.columns.tolist()
            }
        
        except Exception as e:
            logger.error(f"Error fetching from MSTR dossier {endpoint_config.mstr.get('dossier_id')}: {e}")
            raise
    
    def test_connection(self) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Test MicroStrategy connection.
        
        Returns:
            (success, error_message, response_time_ms)
        """
        import time
        
        try:
            start = time.time()
            self.client.ensure_authenticated()
            elapsed_ms = (time.time() - start) * 1000
            return True, None, elapsed_ms
        
        except Exception as e:
            return False, str(e), None


# Singleton instance
_mstr_fetcher: Optional[MstrFetcher] = None


def get_mstr_fetcher() -> MstrFetcher:
    """Get MSTR fetcher singleton."""
    global _mstr_fetcher
    if _mstr_fetcher is None:
        _mstr_fetcher = MstrFetcher()
    return _mstr_fetcher
