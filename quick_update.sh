#!/bin/bash
# Quick update script - pulls code and restarts gunicorn
# Run as: ./quick_update.sh (no sudo needed)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

DEPLOY_DIR="/home/administrator/venus"

echo -e "${GREEN}Quick Update - Venus v2${NC}"
echo ""

echo "[1/4] Pulling latest code..."
cd "$DEPLOY_DIR"
git pull origin venus_v2
echo "✓ Code updated"

echo ""
echo "[2/4] Stopping old gunicorn processes..."
pkill -f "gunicorn.*9102" || echo "  (no processes running)"
sleep 1
echo "✓ Processes stopped"

echo ""
echo "[3/4] Starting gunicorn..."
cd "$DEPLOY_DIR/src"
/home/administrator/venv/bin/gunicorn \
  --workers 3 \
  --bind 127.0.0.1:9102 \
  --timeout=300 \
  --daemon \
  --access-logfile "$DEPLOY_DIR/logs/access.log" \
  --error-logfile "$DEPLOY_DIR/logs/error.log" \
  app:app
sleep 2
echo "✓ Gunicorn started"

echo ""
echo "[4/4] Checking status..."
ps aux | grep "gunicorn.*9102" | grep -v grep || echo "⚠ WARNING: No gunicorn processes found!"

echo ""
echo -e "${GREEN}Update complete!${NC}"
echo ""
echo "Test endpoints:"
echo "  curl http://localhost:9102/ping"
echo "  curl http://localhost:9101/admin/dashboard"
echo ""
echo "Check logs:"
echo "  tail -f $DEPLOY_DIR/logs/error.log"

