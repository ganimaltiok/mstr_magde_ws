#!/bin/bash
# Quick update script - just pulls code and restarts service
# Run as: sudo bash quick_update.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

DEPLOY_DIR="/home/administrator/venus"

echo -e "${GREEN}Quick Update - Venus v2${NC}"
echo ""

echo "[1/3] Pulling latest code..."
cd "$DEPLOY_DIR"
sudo -u administrator git pull origin venus_v2
echo "✓ Code updated"

echo ""
echo "[2/3] Restarting venus service..."
supervisorctl restart venus
sleep 2
echo "✓ Service restarted"

echo ""
echo "[3/3] Checking status..."
supervisorctl status venus

echo ""
echo -e "${GREEN}Update complete!${NC}"
echo ""
echo "Test: curl http://localhost:9101/ping"
