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
    ) -> Optional[Dict[str, Any]]:
        """
        Build MSTR viewFilter from query parameters.
        
        Args:
            filter_mappings: Dict of param_name -> mstr_filter_key
            query_params: Query parameters from request
        
        Returns:
            viewFilter payload or None if no filters
        """
        # Group params by MSTR filter ID (for date ranges)
        filter_groups: Dict[str, Dict[str, str]] = {}
        
        for param_name, param_value in query_params.items():
            # Skip pagination params
            if param_name in ['page', 'per_page']:
                continue
            
            if param_name not in filter_mappings:
                logger.warning(f"No MSTR filter mapping for param: {param_name}")
                continue
            
            filter_id = filter_mappings[param_name]
            if filter_id not in filter_groups:
                filter_groups[filter_id] = {}
            filter_groups[filter_id][param_name] = param_value
        
        if not filter_groups:
            return None
        
        # Build operands
        operands = []
        
        for filter_id, param_values in filter_groups.items():
            # Detect if this is a date range (has _start and _end params)
            start_param = next((k for k in param_values if k.endswith('_start')), None)
            end_param = next((k for k in param_values if k.endswith('_end')), None)
            
            if start_param and end_param:
                # Date range filter
                operands.append({
                    "operator": "Between",
                    "operands": [
                        {"type": "filter", "id": filter_id},
                        {
                            "type": "constants",
                            "dataType": "Date",
                            "values": [
                                param_values[start_param],
                                param_values[end_param]
                            ]
                        }
                    ]
                })
            else:
                # Single/multi-value filter
                for param_name, param_value in param_values.items():
                    values = [v.strip() for v in param_value.split(',')]
                    
                    if len(values) == 1:
                        operator = "Equals"
                        elements = [{"id": f"h{values[0]}"}]
                    else:
                        operator = "In"
                        elements = [{"id": f"h{v}"} for v in values]
                    
                    operands.append({
                        "operator": operator,
                        "operands": [
                            {"type": "filter", "id": filter_id},
                            {"type": "elements", "elements": elements}
                        ]
                    })
        
        return {"operands": operands} if operands else None
    
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
            response = self.client.get_report_data(
                dossier_id=dossier_id,
                viz_key=viz_key,
                view_filter=view_filter,
                limit=limit,
                offset=offset
            )
            
            # Parse CSV response (v1-compatible)
            df = pd.read_csv(StringIO(response.content.decode("utf-16")))
            total_records = len(df)
            
            return {
                'data': df.to_dict('records'),
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
