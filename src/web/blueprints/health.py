from flask import Blueprint, jsonify, render_template
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
    return render_template('health.html', health_status=health_status)
