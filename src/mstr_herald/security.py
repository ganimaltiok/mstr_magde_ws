# -*- coding: utf-8 -*-
from flask import request, jsonify
from functools import wraps
import os
import secrets
import logging
import time

logger = logging.getLogger(__name__)

# Function to generate a new API key (use during setup)
def generate_api_key():
    return secrets.token_urlsafe(32)

# Check if API key is required and valid
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get configured API keys
        api_keys_str = os.getenv('API_KEYS', '')
        
        # If no API keys are set, authentication is disabled
        if not api_keys_str:
            return f(*args, **kwargs)
        
        # Split comma-separated API keys
        valid_api_keys = set(key.strip() for key in api_keys_str.split(',') if key.strip())
        
        # Get API key from request
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        
        if not api_key:
            logger.warning(f"API request missing authentication: {request.path}")
            return jsonify({"error": "API key is required"}), 401
        
        if api_key not in valid_api_keys:
            logger.warning(f"Invalid API key used: {request.path}")
            return jsonify({"error": "Invalid API key"}), 403
        
        # If we get here, the API key is valid
        return f(*args, **kwargs)
    
    return decorated_function

# Rate limiting decorator (simple implementation)
def rate_limit(limit=100, per=60):
    # Simple in-memory storage for request counts
    # In production, use Redis or another shared storage
    requests = {}
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client IP
            client_ip = request.remote_addr
            
            # Get current timestamp
            now = time.time()
            
            # Clean up old entries
            requests_by_ip = requests.setdefault(client_ip, [])
            requests_by_ip = [timestamp for timestamp in requests_by_ip if timestamp > now - per]
            requests[client_ip] = requests_by_ip
            
            # Check if rate limit is exceeded
            if len(requests_by_ip) >= limit:
                logger.warning(f"Rate limit exceeded for {client_ip}: {request.path}")
                return jsonify({
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {limit} requests per {per} seconds"
                }), 429
            
            # Add current request timestamp
            requests_by_ip.append(now)
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator