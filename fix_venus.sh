#!/bin/bash
# Quick fix script for Venus v2 on server
# Run as: sudo bash fix_venus.sh

set -e

echo "=========================================="
echo "Fixing Venus v2 Deployment"
echo "=========================================="
echo ""

echo "[1/4] Pulling latest code from GitHub..."
cd /home/administrator/venus
sudo -u administrator git pull origin venus_v2
echo "✓ Code updated"

echo ""
echo "[2/4] Testing app import..."
cd /home/administrator/venus/src
if sudo -u administrator /home/administrator/venv/bin/python -c "from app import app; print('OK')" 2>&1 | grep -q "OK"; then
    echo "✓ App imports successfully"
else
    echo "✗ App import failed - check output above"
    exit 1
fi

echo ""
echo "[3/4] Restarting venus service..."
supervisorctl restart venus
sleep 3

echo ""
echo "[4/4] Testing endpoints..."
if curl -s http://localhost:9101/ping | grep -q "pong"; then
    echo "✓ /ping OK"
else
    echo "✗ /ping FAILED"
fi

if curl -s -o /dev/null -w "%{http_code}" http://localhost:9101/health | grep -q "200"; then
    echo "✓ /health OK"
else
    echo "✗ /health FAILED"
fi

echo ""
echo "=========================================="
echo "Venus Status:"
supervisorctl status venus
echo ""
echo "Access URLs:"
echo "  - http://172.30.4.1:9101/ping"
echo "  - http://172.30.4.1:9101/health"
echo "  - http://172.30.4.1:9101/admin/dashboard"
echo ""
echo "If still failing, check logs:"
echo "  sudo tail -f /var/log/venus/error.log"
echo "=========================================="
