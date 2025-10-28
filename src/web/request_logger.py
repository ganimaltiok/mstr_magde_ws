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
        logger.info(f"after_request hook called for {request.path}")
        
        # TEMPORARILY DISABLE FOR DEBUGGING
        logger.info("after_request: returning response unmodified (debugging)")
        return response
        
        # Only log v3 API requests
        if not request.path.startswith('/api/v3/'):
            logger.info(f"Skipping logging for non-v3 path: {request.path}")
            return response
        
        logger.info(f"Processing v3 API request: {request.path}")
        
        # Calculate response time
        response_time_ms = (time.time() - g.start_time) * 1000
        logger.info(f"Response time calculated: {response_time_ms}ms")
        
        # Extract endpoint name from path
        path_parts = request.path.split('/')
        endpoint_name = path_parts[3] if len(path_parts) > 3 else 'unknown'
        logger.info(f"Endpoint name: {endpoint_name}")
        
        # Check if response was from cache
        cache_hit = response.headers.get('X-Cache-Status') == 'HIT'
        logger.info(f"Cache hit: {cache_hit}")
        
        # Log to access logger
        logger.info(f"Calling access_logger.log_request...")
        access_logger = get_access_logger()
        access_logger.log_request(
            endpoint_name=endpoint_name,
            method=request.method,
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            cache_hit=cache_hit,
            query_params=dict(request.args)
        )
        logger.info(f"Access logger completed")
        
        # Add response time header
        response.headers['X-Response-Time'] = f"{response_time_ms:.2f}ms"
        logger.info(f"Added X-Response-Time header, returning response")
        
        return response
