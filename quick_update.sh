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
echo "[2/4] Restarting via supervisor..."
sudo supervisorctl restart venus
sleep 2
echo "✓ Service restarted"

echo ""
echo "[3/4] Checking status..."
sudo supervisorctl status venus

echo ""
echo -e "${GREEN}Update complete!${NC}"
echo ""
echo "Test endpoints:"
echo "  curl http://localhost:9102/ping"
echo "  curl http://localhost:9101/admin/dashboard"
echo ""
echo "Check logs:"
echo "  sudo tail -f /var/log/venus/error.log"

