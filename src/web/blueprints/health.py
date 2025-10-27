from flask import Blueprint, jsonify, render_template_string
from services.health_checker import get_health_checker

health_bp = Blueprint('health', __name__)


@health_bp.route('/ping', methods=['GET'])
def ping():
    """Simple ping endpoint."""
    return jsonify({"status": "ok"})


@health_bp.route('/health', methods=['GET'])
def health():
    """Detailed health check with HTML output."""
    checker = get_health_checker()
    health_status = checker.check_all()
    
    # Simple HTML template
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MSTR Herald Health Check</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .status { padding: 20px; margin: 10px 0; border-radius: 5px; }
            .ok { background-color: #d4edda; border: 1px solid #c3e6cb; }
            .error { background-color: #f8d7da; border: 1px solid #f5c6cb; }
            .not_configured { background-color: #fff3cd; border: 1px solid #ffeaa7; }
            h1 { color: #333; }
            h2 { color: #666; margin-top: 20px; }
            .response-time { color: #28a745; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>MSTR Herald Health Status</h1>
        
        <h2>MSSQL</h2>
        <div class="status {{ health_status.mssql.status }}">
            <strong>Status:</strong> {{ health_status.mssql.status }}<br>
            {% if health_status.mssql.response_time_ms %}
            <strong>Response Time:</strong> <span class="response-time">{{ "%.1f"|format(health_status.mssql.response_time_ms) }} ms</span><br>
            {% endif %}
            {% if health_status.mssql.error %}
            <strong>Error:</strong> {{ health_status.mssql.error }}
            {% endif %}
        </div>
        
        <h2>PostgreSQL</h2>
        <div class="status {{ health_status.postgresql.status }}">
            <strong>Status:</strong> {{ health_status.postgresql.status }}<br>
            {% if health_status.postgresql.response_time_ms %}
            <strong>Response Time:</strong> <span class="response-time">{{ "%.1f"|format(health_status.postgresql.response_time_ms) }} ms</span><br>
            {% endif %}
            {% if health_status.postgresql.error %}
            <strong>Error:</strong> {{ health_status.postgresql.error }}
            {% endif %}
        </div>
        
        <h2>MicroStrategy</h2>
        <div class="status {{ health_status.microstrategy.status }}">
            <strong>Status:</strong> {{ health_status.microstrategy.status }}<br>
            {% if health_status.microstrategy.response_time_ms %}
            <strong>Response Time:</strong> <span class="response-time">{{ "%.1f"|format(health_status.microstrategy.response_time_ms) }} ms</span><br>
            {% endif %}
            {% if health_status.microstrategy.error %}
            <strong>Error:</strong> {{ health_status.microstrategy.error }}
            {% endif %}
        </div>
        
        <h2>Nginx Cache</h2>
        <div class="status {{ health_status.nginx_cache.status }}">
            <strong>Status:</strong> {{ health_status.nginx_cache.status }}<br>
            {% if health_status.nginx_cache.total_size %}
            <strong>Cache Size:</strong> {{ (health_status.nginx_cache.total_size / 1024 / 1024) | round(2) }} MB<br>
            <strong>Total Files:</strong> {{ health_status.nginx_cache.total_files }}<br>
            {% endif %}
            {% if health_status.nginx_cache.error %}
            <strong>Error:</strong> {{ health_status.nginx_cache.error }}
            {% endif %}
        </div>
    </body>
    </html>
    """
    
    return render_template_string(html, health_status=health_status)
