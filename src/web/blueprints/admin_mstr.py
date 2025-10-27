from flask import Blueprint, request, jsonify
from services.mstr_discovery import get_discovery_service
import logging

logger = logging.getLogger(__name__)

admin_mstr_bp = Blueprint('admin_mstr', __name__, url_prefix='/api/admin/mstr')


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
        
        discovery_service = get_discovery_service()
        result = discovery_service.discover_dossier_info(dossier_id)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Dossier discovery failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
