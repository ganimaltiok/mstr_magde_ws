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

echo "[1/5] Pulling latest code..."
cd "$DEPLOY_DIR"

# Stash local changes to endpoints.yaml if they exist
if git diff --quiet src/config/endpoints.yaml; then
    echo "No local changes to endpoints.yaml"
else
    echo "Stashing local endpoints.yaml changes..."
    git stash push -m "Auto-stash endpoints.yaml before update" src/config/endpoints.yaml
    STASHED=1
fi

git pull origin venus_v2

# Restore stashed endpoints.yaml if we stashed it
if [ "$STASHED" = "1" ]; then
    echo "Restoring local endpoints.yaml..."
    git stash pop
fi

echo "✓ Code updated"

echo ""
echo "[2/5] Testing nginx configuration..."
if sudo nginx -t 2>&1 | grep -q "successful"; then
    echo "✓ Nginx config valid"
    echo ""
    echo "[3/5] Reloading nginx..."
    sudo systemctl reload nginx
    echo "✓ Nginx reloaded"
else
    echo "✗ Nginx config test failed!"
    sudo nginx -t
    exit 1
fi

echo ""
echo "[4/5] Restarting via supervisor..."
sudo supervisorctl restart venus
sleep 2
echo "✓ Service restarted"

echo ""
echo "[5/5] Checking status..."
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

