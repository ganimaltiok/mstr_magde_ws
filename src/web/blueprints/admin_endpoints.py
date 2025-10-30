from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from services.endpoint_config import get_config_store
import logging

logger = logging.getLogger(__name__)

admin_endpoints_bp = Blueprint('admin_endpoints', __name__, url_prefix='/admin/endpoints')


@admin_endpoints_bp.route('/')
def list_endpoints():
    """List all endpoints with edit/delete actions."""
    config_store = get_config_store()
    endpoints = config_store.get_all()
    
    return render_template('admin_endpoints_list.html', endpoints=endpoints)


@admin_endpoints_bp.route('/create', methods=['GET', 'POST'])
def create_endpoint():
    """Create new endpoint."""
    if request.method == 'GET':
        return render_template('admin_endpoints_form.html', 
                             endpoint=None, 
                             mode='create')
    
    try:
        data = request.form.to_dict()
        
        # Build config based on behavior
        config = _build_config_from_form(data)
        
        config_store = get_config_store()
        config_store.create(data['endpoint_name'], config)
        
        return redirect(url_for('admin_endpoints.list_endpoints'))
    
    except Exception as e:
        logger.error(f"Failed to create endpoint: {e}")
        return jsonify({'error': str(e)}), 400


@admin_endpoints_bp.route('/edit/<endpoint_name>', methods=['GET', 'POST'])
def edit_endpoint(endpoint_name: str):
    """Edit existing endpoint."""
    config_store = get_config_store()
    
    if request.method == 'GET':
        endpoint = config_store.get(endpoint_name)
        if not endpoint:
            return "Endpoint not found", 404
        
        return render_template('admin_endpoints_form.html',
                             endpoint=endpoint,
                             mode='edit')
    
    try:
        data = request.form.to_dict()
        config = _build_config_from_form(data)
        
        config_store.update(endpoint_name, config)
        
        return redirect(url_for('admin_endpoints.list_endpoints'))
    
    except Exception as e:
        logger.error(f"Failed to update endpoint: {e}")
        return jsonify({'error': str(e)}), 400


@admin_endpoints_bp.route('/delete/<endpoint_name>', methods=['POST'])
def delete_endpoint(endpoint_name: str):
    """Delete endpoint."""
    try:
        config_store = get_config_store()
        config_store.delete(endpoint_name)
        
        return jsonify({'status': 'success'})
    
    except Exception as e:
        logger.error(f"Failed to delete endpoint: {e}")
        return jsonify({'error': str(e)}), 400


def _build_config_from_form(data: dict) -> dict:
    """Build endpoint config dictionary from form data."""
    source = data.get('source')
    description = data.get('description', '')
    
    config = {
        'source': source,
        'description': description,
        'pagination': {
            'per_page': int(data.get('per_page', 100))
        }
    }
    
    # SQL-specific config
    if source == 'mssql':
        schema = data.get('mssql_schema')
        table = data.get('mssql_table')
        database = data.get('mssql_database')
        
        config['mssql'] = {
            'schema': schema,
            'table': table
        }
        
        # Add database if provided
        if database:
            config['mssql']['database'] = database
        
        # Auto-update description if not provided
        if not description and schema and table:
            if database:
                config['description'] = f"{database}.{schema}.{table}"
            else:
                config['description'] = f"{schema}.{table}"
    
    # PostgreSQL-specific config
    elif source == 'postgresql':
        schema = data.get('pg_schema')
        table = data.get('pg_table')
        config['postgresql'] = {
            'schema': schema,
            'table': table
        }
        # Auto-update description if not provided
        if not description and schema and table:
            config['description'] = f"{schema}.{table}"
    
    # MSTR-specific config
    elif source == 'microstrategy':
        config['mstr'] = {
            'dossier_id': data.get('dossier_id'),
            'viz_keys': {
                'summary': data.get('summary_viz_key'),
                'detail': data.get('detail_viz_key', '')
            },
            'filter_mappings': {}
        }
        
        # Optional cube_id
        if data.get('cube_id'):
            config['mstr']['cube_id'] = data.get('cube_id')
        
        # Parse filter mappings from form arrays
        filter_params = request.form.getlist('filter_param[]')
        filter_keys = request.form.getlist('filter_key[]')
        
        for param, key in zip(filter_params, filter_keys):
            if param and key:
                config['mstr']['filter_mappings'][param] = key
    
    return config
