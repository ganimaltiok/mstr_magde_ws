#!/bin/bash
# Safe Update Script - Preserves local endpoints.yaml changes

set -e

echo "=== Safe Update - Venus v2 ==="
echo ""

# Change to venus directory
cd ~/venus

echo "[1/6] Backing up current endpoints.yaml..."
cp src/config/endpoints.yaml src/config/endpoints.yaml.backup
echo "✓ Backup saved to src/config/endpoints.yaml.backup"
echo ""

echo "[2/6] Stashing local changes..."
git stash push -m "Auto-stash before update $(date +%Y%m%d_%H%M%S)"
echo "✓ Local changes stashed"
echo ""

echo "[3/6] Pulling latest code..."
git pull origin venus_v2
echo "✓ Code updated"
echo ""

echo "[4/6] Restoring endpoints.yaml from backup..."
cp src/config/endpoints.yaml.backup src/config/endpoints.yaml
echo "✓ Your endpoint configurations preserved"
echo ""

echo "[5/6] Restarting Gunicorn..."
pkill -f "gunicorn.*9102" 2>/dev/null || echo "  (No existing process found)"
sleep 2

cd src
nohup /home/administrator/venv/bin/gunicorn \
  --workers 3 \
  --bind 127.0.0.1:9102 \
  --timeout=300 \
  --daemon \
  app:app

sleep 3
echo "✓ Gunicorn restarted"
echo ""

echo "[6/6] Verifying service..."
if pgrep -f "gunicorn.*9102" > /dev/null; then
    echo "✓ Service is running (PID: $(pgrep -f 'gunicorn.*9102' | head -1))"
    echo ""
    echo "✅ Update complete!"
    echo ""
    echo "📋 Your endpoints.yaml was preserved from backup"
    echo "💾 Git stash saved as: Auto-stash before update $(date +%Y%m%d_%H%M%S)"
    echo "🔍 To see stashed changes: git stash list"
else
    echo "❌ Service failed to start!"
    echo "Check logs: tail -f nohup.out"
    exit 1
fi
