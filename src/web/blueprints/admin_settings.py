from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from pathlib import Path
from typing import Dict, Any
import os
import logging

logger = logging.getLogger(__name__)

admin_settings_bp = Blueprint('admin_settings', __name__, url_prefix='/admin')


def get_env_file_path() -> Path:
    """Get path to .env file."""
    return Path(__file__).parent.parent.parent.parent / '.env'


def read_env_file() -> Dict[str, str]:
    """Read .env file and return as dictionary."""
    env_path = get_env_file_path()
    env_vars = {}
    
    if not env_path.exists():
        logger.warning(f".env file not found at {env_path}")
        return env_vars
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip().strip('"').strip("'")
                    env_vars[key.strip()] = value
    
    except Exception as e:
        logger.error(f"Error reading .env file: {e}")
    
    return env_vars


def write_env_file(env_vars: Dict[str, str]) -> bool:
    """Write dictionary to .env file."""
    env_path = get_env_file_path()
    
    try:
        # Read original file to preserve comments and order
        original_lines = []
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                original_lines = f.readlines()
        
        # Build new content
        new_lines = []
        updated_keys = set()
        
        for line in original_lines:
            stripped = line.strip()
            
            # Keep comments and empty lines
            if not stripped or stripped.startswith('#'):
                new_lines.append(line)
                continue
            
            # Update existing key
            if '=' in stripped:
                key = stripped.split('=', 1)[0].strip()
                if key in env_vars:
                    new_lines.append(f'{key}={env_vars[key]}\n')
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        # Add any new keys that weren't in original file
        for key, value in env_vars.items():
            if key not in updated_keys:
                new_lines.append(f'{key}={value}\n')
        
        # Write to file
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        return True
    
    except Exception as e:
        logger.error(f"Error writing .env file: {e}")
        return False


@admin_settings_bp.route('/settings', methods=['GET'])
def settings():
    """Display settings page."""
    env_vars = read_env_file()
    
    # Organize settings into groups
    settings_groups = {
        'Flask': ['FLASK_ENV', 'PORT', 'SECRET_KEY'],
        'MSSQL Database': ['MSSQL_HOST', 'MSSQL_PORT', 'MSSQL_DATABASE', 'MSSQL_USER', 'MSSQL_PASSWORD', 'MSSQL_DRIVER'],
        'PostgreSQL': ['PG_HOST', 'PG_PORT', 'PG_DATABASE', 'PG_USER', 'PG_PASSWORD'],
        'MicroStrategy': ['MSTR_URL_API', 'MSTR_USERNAME', 'MSTR_PASSWORD', 'MSTR_PROJECT'],
        'Nginx Cache': ['NGINX_CACHE_SHORT', 'NGINX_CACHE_DAILY'],
        'Logging': ['LOG_LEVEL', 'LOG_FILE'],
        'Sentry': ['SENTRY_DSN', 'SENTRY_ENVIRONMENT']
    }
    
    # Sensitive fields to mask
    sensitive_fields = ['PASSWORD', 'SECRET_KEY', 'DSN']
    
    return render_template(
        'admin_settings.html',
        env_vars=env_vars,
        settings_groups=settings_groups,
        sensitive_fields=sensitive_fields
    )


@admin_settings_bp.route('/settings/save', methods=['POST'])
def save_settings():
    """Save settings to .env file."""
    try:
        # Get form data
        form_data = request.form.to_dict()
        
        # Remove CSRF token if present
        form_data.pop('csrf_token', None)
        
        # Write to .env file
        if write_env_file(form_data):
            return jsonify({
                'status': 'success',
                'message': 'Settings saved successfully. Please restart the application for changes to take effect.'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to save settings to .env file'
            }), 500
    
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@admin_settings_bp.route('/settings/restart', methods=['POST'])
def restart_application():
    """Restart the application (requires supervisor)."""
    try:
        import subprocess
        
        # Try to restart via supervisor
        result = subprocess.run(
            ['sudo', 'supervisorctl', 'restart', 'venus'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return jsonify({
                'status': 'success',
                'message': 'Application restarted successfully',
                'output': result.stdout
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Failed to restart: {result.stderr}',
                'output': result.stderr
            }), 500
    
    except subprocess.TimeoutExpired:
        return jsonify({
            'status': 'error',
            'message': 'Restart command timed out'
        }), 500
    except Exception as e:
        logger.error(f"Error restarting application: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
