from flask import Blueprint, request, jsonify
from services.mstr_discovery import get_discovery_service
import logging

logger = logging.getLogger(__name__)

admin_mstr_bp = Blueprint('admin_mstr', __name__, url_prefix='/api/admin/mstr')


@admin_mstr_bp.route('/definition/<dossier_id>', methods=['GET'])
def get_raw_definition(dossier_id: str):
    """
    Get raw dossier definition from MSTR (for debugging).
    
    Returns the complete JSON structure from MSTR API.
    """
    try:
        from mstr_herald.mstr_client import get_mstr_client
        
        logger.info(f"Fetching raw definition for dossier: {dossier_id}")
        client = get_mstr_client()
        definition = client.get_dossier_definition(dossier_id)
        
        return jsonify({
            'dossier_id': dossier_id,
            'definition': definition
        })
    
    except Exception as e:
        logger.error(f"Failed to get dossier definition: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'error_type': type(e).__name__
        }), 500


@admin_mstr_bp.route('/discover', methods=['POST'])
def discover_dossier():
    """
    Auto-discover MicroStrategy dossier metadata.
    
    JSON payload:
    {
        "dossier_id": "ABC123DEF456..."
    }
    
    Returns:
    {
        "cube_id": "...",
        "viz_keys": {
            "summary": "K52",
            "detail": "W8D67A24C..."
        },
        "filters": [
            {
                "key": "W7B89C12D...",
                "name": "Agency Code",
                "suggested_param_name": "agency_code"
            }
        ]
    }
    """
    try:
        data = request.get_json()
        dossier_id = data.get('dossier_id')
        
        if not dossier_id:
            return jsonify({'error': 'dossier_id required'}), 400
        
        logger.info(f"Discovering dossier: {dossier_id}")
        
        discovery_service = get_discovery_service()
        result = discovery_service.discover_dossier_info(dossier_id)
        
        logger.info(f"Discovery result: cube_id={result.get('cube_id')}, "
                   f"viz_keys={result.get('viz_keys')}, "
                   f"filters={len(result.get('filters', []))} found")
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Dossier discovery failed for {dossier_id}: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'error_type': type(e).__name__
        }), 500
