from flask import Blueprint, jsonify, request, make_response, after_this_request
from services.endpoint_config import get_config_store
from services.data_fetcher import get_data_fetcher
from datetime import datetime
import pytz
import logging

logger = logging.getLogger(__name__)

v3_bp = Blueprint('v3_api', __name__, url_prefix='/api/v3')


@v3_bp.route('/test', methods=['GET'])
def test_endpoint():
    """Simple test endpoint to verify JSON responses work."""
    return jsonify({
        "status": "ok",
        "message": "Test endpoint working",
        "data": [{"id": 1, "name": "test"}]
    })


@v3_bp.route('/report/<report_name>', methods=['GET'])
@v3_bp.route('/report/<report_name>/agency/<agency_code>', methods=['GET'])
def get_report(report_name: str, agency_code: str = None):
    """
    Get report data (v3 API - backward compatible).
    
    URL patterns:
    - /api/v3/report/<report_name>
    - /api/v3/report/<report_name>/agency/<agency_code>
    
    Query params:
    - page: Page number (default 1)
    - per_page: Items per page (default from config)
    - info_type: 'summary' or 'detail' (default 'summary', MSTR only)
    - Any other params: Used for filtering (server-side)
    
    Response format (unchanged):
    {
        "data": [...],
        "pagination": {...},
        "info": {
            "report_name": str,
            "info_type": str,
            "cache_hit": bool,
            "refreshed_at": str,
            "data_source": str,
            "error": {...}  // only if error occurred
        }
    }
    """
    try:
        # Get endpoint configuration
        config_store = get_config_store()
        endpoint_config = config_store.get(report_name)
        
        if not endpoint_config:
            return jsonify({
                "error": f"Report '{report_name}' not found"
            }), 404
        
        # Parse query parameters
        query_params = dict(request.args)
        page = int(query_params.pop('page', 1))
        per_page = query_params.pop('per_page', None)
        if per_page:
            per_page = int(per_page)
        info_type = query_params.pop('info_type', 'summary')
        
        # Add agency_code to query params if provided in URL
        if agency_code:
            query_params['agency_code'] = agency_code
        
        # Fetch data
        data_fetcher = get_data_fetcher()
        result = data_fetcher.fetch(
            endpoint_config=endpoint_config,
            query_params=query_params,
            info_type=info_type,
            page=page,
            per_page=per_page
        )
        
        logger.info(f"v3_api: Fetched {len(result.data)} records for {report_name}, total={result.total_records}, pagination={result.pagination}")
        
        # Determine data source
        if endpoint_config.is_mstr:
            data_source = 'microstrategy'
        elif endpoint_config.is_sql:
            data_source = 'mssql'
        else:
            data_source = 'postgresql'
        
        # Build response
        istanbul_tz = pytz.timezone('Europe/Istanbul')
        response_data = {
            "data": result.data,
            "pagination": result.pagination,
            "info": {
                "report_name": report_name,
                "info_type": info_type,
                "cache_hit": False,  # Will be set by nginx
                "refreshed_at": datetime.now(istanbul_tz).isoformat(),
                "data_source": data_source
            }
        }
        
        # Add error if present
        if result.has_error:
            response_data['info']['error'] = result.error
        
        logger.info(f"Building JSON response with {len(response_data['data'])} records...")
        
        # Set cache headers based on behavior
        cache_control = None
        if endpoint_config.cache_zone:
            if endpoint_config.behavior in ['cachesql', 'cachepg']:
                # 10 minute cache
                cache_control = 'public, max-age=600'
            elif endpoint_config.behavior == 'cachemstr':
                # Cache until 7 AM Istanbul
                next_7am = get_next_7am_istanbul()
                now = datetime.now(istanbul_tz)
                max_age = int((next_7am - now).total_seconds())
                cache_control = f'public, max-age={max_age}'
        else:
            # No cache for live behaviors
            cache_control = 'no-store'
        
        logger.info(f"Returning response with Cache-Control: {cache_control}")
        
        # Add logging AFTER response is sent
        @after_this_request
        def log_after_send(response):
            logger.info("!!! after_this_request: Response was sent to client")
            return response
        
        # Use make_response to ensure proper response object
        response = make_response(jsonify(response_data))
        if cache_control:
            response.headers['Cache-Control'] = cache_control
        if endpoint_config.cache_zone:
            response.headers['X-Cache-Zone'] = endpoint_config.cache_zone
        
        logger.info(f"Response object created, type: {type(response)}, status: {response.status}")
        return response
    
    except Exception as e:
        logger.error(f"Unexpected error in v3 API: {e}", exc_info=True)
        
        # Safely convert exception to string (handle binary data)
        try:
            error_message = str(e)
        except UnicodeDecodeError:
            error_message = repr(e)
        
        return jsonify({
            "data": [],
            "pagination": {
                "page": 1,
                "per_page": 100,
                "total_pages": 0,
                "total_records": 0
            },
            "info": {
                "report_name": report_name,
                "info_type": "summary",
                "cache_hit": False,
                "refreshed_at": None,
                "error": {
                    "type": "InternalServerError",
                    "message": error_message,
                    "timestamp": datetime.now(pytz.timezone('Europe/Istanbul')).isoformat()
                }
            }
        }), 500


def get_next_7am_istanbul():
    """Calculate next 7 AM Istanbul time."""
    from datetime import timedelta
    istanbul_tz = pytz.timezone('Europe/Istanbul')
    now = datetime.now(istanbul_tz)
    
    # Today at 7 AM
    today_7am = now.replace(hour=7, minute=0, second=0, microsecond=0)
    
    # If current time is past 7 AM, use tomorrow
    if now >= today_7am:
        next_7am = today_7am + timedelta(days=1)
    else:
        next_7am = today_7am
    
    return next_7am
