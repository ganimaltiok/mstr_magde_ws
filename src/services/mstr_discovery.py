from typing import Dict, List, Any, Optional
from mstr_herald.mstr_client import get_mstr_client
import logging
import re

logger = logging.getLogger(__name__)


class MstrDiscoveryService:
    """Auto-discover MicroStrategy dossier metadata."""
    
    def __init__(self):
        self.client = get_mstr_client()
    
    def discover_dossier_info(self, dossier_id: str) -> Dict[str, Any]:
        """
        Auto-discover dossier configuration.
        
        Returns:
            {
                'dossier_name': str,
                'cube_id': str,
                'viz_keys': {'summary': str, 'detail': str},
                'filters': [
                    {
                        'key': str,
                        'name': str,
                        'suggested_param_name': str
                    }
                ]
            }
        """
        try:
            logger.info(f"Fetching dossier definition for: {dossier_id}")
            definition = self.client.get_dossier_definition(dossier_id)
            logger.info(f"Retrieved definition with keys: {list(definition.keys())}")
            
            # Extract dossier name
            dossier_name = definition.get('name', 'Unknown Dossier')
            logger.info(f"Extracted dossier_name: {dossier_name}")
            
            # Extract cube ID
            cube_id = self._extract_cube_id(definition)
            logger.info(f"Extracted cube_id: {cube_id}")
            
            # Extract visualization keys
            viz_keys = self._extract_viz_keys(definition)
            logger.info(f"Extracted viz_keys: {viz_keys}")
            
            # Extract filters
            filters = self._extract_filters(definition)
            logger.info(f"Extracted {len(filters)} filters: {[f['name'] for f in filters]}")
            
            return {
                'dossier_name': dossier_name,
                'cube_id': cube_id,
                'viz_keys': viz_keys,
                'filters': filters
            }
        except Exception as e:
            logger.error(f"Discovery failed for dossier {dossier_id}: {e}", exc_info=True)
            raise
    
    def _extract_cube_id(self, definition: Dict[str, Any]) -> Optional[str]:
        """Extract cube ID from dossier definition."""
        try:
            # Check if we need to unwrap 'definition' key
            if 'definition' in definition:
                definition = definition['definition']
            
            # Try datasets first (some dossiers have this)
            datasets = definition.get('datasets', [])
            if datasets and len(datasets) > 0:
                cube_id = datasets[0].get('id')
                if cube_id:
                    return cube_id
            
            # Fallback: some dossiers might have cube info elsewhere
            # For now, return None if not in datasets
            logger.warning("No datasets found in definition, cube_id might need manual entry")
        except Exception as e:
            logger.error(f"Could not extract cube_id: {e}", exc_info=True)
        return None
    
    def _extract_viz_keys(self, definition: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract visualization keys from chapters.
        
        Heuristic:
        - First visualization -> 'summary' (usually K52 or similar)
        - Additional visualizations could be 'detail' but usually there's only one
        """
        viz_keys = {}
        
        try:
            # Check if we need to unwrap 'definition' key
            if 'definition' in definition:
                definition = definition['definition']
            
            chapters = definition.get('chapters', [])
            all_vizs = []
            
            for chapter in chapters:
                pages = chapter.get('pages', [])
                for page in pages:
                    visualizations = page.get('visualizations', [])
                    for viz in visualizations:
                        viz_key = viz.get('key')
                        viz_name = viz.get('name', '')
                        if viz_key:
                            all_vizs.append({
                                'key': viz_key,
                                'name': viz_name
                            })
            
            # Assign to summary/detail
            if len(all_vizs) > 0:
                viz_keys['summary'] = all_vizs[0]['key']
            if len(all_vizs) > 1:
                viz_keys['detail'] = all_vizs[1]['key']
            
            logger.info(f"Found {len(all_vizs)} visualizations")
        
        except Exception as e:
            logger.error(f"Could not extract viz_keys: {e}", exc_info=True)
        
        return viz_keys
    
    def _extract_filters(self, definition: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract available filters from dossier.
        
        Returns list of filters with suggested parameter names.
        """
        filters = []
        
        try:
            # Check if we need to unwrap 'definition' key
            if 'definition' in definition:
                definition = definition['definition']
            
            # Filters are inside chapters
            chapters = definition.get('chapters', [])
            
            for chapter in chapters:
                chapter_filters = chapter.get('filters', [])
                
                for filter_def in chapter_filters:
                    filter_key = filter_def.get('key')
                    filter_name = filter_def.get('name', '')
                    
                    if not filter_key:
                        continue
                    
                    # Suggest parameter name from filter name
                    suggested_param = self._suggest_param_name(filter_name)
                    
                    filters.append({
                        'key': filter_key,
                        'name': filter_name,
                        'suggested_param_name': suggested_param
                    })
            
            logger.info(f"Extracted {len(filters)} filters from {len(chapters)} chapters")
        
        except Exception as e:
            logger.error(f"Could not extract filters: {e}", exc_info=True)
        
        return filters
    
    def _suggest_param_name(self, filter_name: str) -> str:
        """
        Convert filter display name to snake_case parameter name.
        
        Examples:
        - 'Agency Code' -> 'agency_code'
        - 'Start Date' -> 'start_date'
        - 'Product Category' -> 'product_category'
        """
        # Remove special characters, convert to lowercase
        param = re.sub(r'[^\w\s]', '', filter_name.lower())
        # Replace spaces with underscores
        param = re.sub(r'\s+', '_', param.strip())
        return param


# Singleton instance
_discovery_service: Optional[MstrDiscoveryService] = None


def get_discovery_service() -> MstrDiscoveryService:
    """Get discovery service singleton."""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = MstrDiscoveryService()
    return _discovery_service
