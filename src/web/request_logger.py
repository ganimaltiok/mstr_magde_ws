from flask import Flask, request, g
from services.access_logger import get_access_logger
import time
import logging

logger = logging.getLogger(__name__)


def setup_request_logging(app: Flask):
    """Setup request logging middleware."""
    
    @app.before_request
    def before_request():
        """Start request timer."""
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        """Log completed requests."""
        # Only log v3 API requests
        if not request.path.startswith('/api/v3/'):
            return response
        
        # Calculate response time
        response_time_ms = (time.time() - g.start_time) * 1000
        
        # Extract endpoint name from path
        # Path format: /api/v3/report/<endpoint_name> or /api/v3/report/<endpoint_name>/agency/<code>
        path_parts = request.path.split('/')
        # path_parts = ['', 'api', 'v3', 'report', 'endpoint_name', ...]
        endpoint_name = path_parts[4] if len(path_parts) > 4 else 'unknown'
        
        # Check if response was from cache
        cache_hit = response.headers.get('X-Cache-Status') == 'HIT'
        
        # Log to access logger
        access_logger = get_access_logger()
        access_logger.log_request(
            endpoint_name=endpoint_name,
            method=request.method,
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            cache_hit=cache_hit,
            query_params=dict(request.args)
        )
        
        # Add response time header
        response.headers['X-Response-Time'] = f"{response_time_ms:.2f}ms"
        
        return response
