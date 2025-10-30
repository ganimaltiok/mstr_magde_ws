#!/bin/bash
# Update Gunicorn timeout to 30 minutes
# This script helps update the Supervisor configuration on the server

echo "=== Gunicorn Timeout Update Script ==="
echo ""
echo "This will update the venus Supervisor configuration to use 30-minute timeout"
echo ""

# Check if running on server
if [ ! -f /etc/supervisor/conf.d/venus.conf ]; then
    echo "❌ Error: /etc/supervisor/conf.d/venus.conf not found"
    echo "This script should be run on the server, not locally"
    exit 1
fi

echo "Current Supervisor configuration:"
grep "command=" /etc/supervisor/conf.d/venus.conf
echo ""

echo "Recommended configuration:"
echo "command=/home/administrator/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:9102 --timeout=1800 app:app"
echo ""

read -p "Do you want to update the Supervisor configuration? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

# Backup existing configuration
sudo cp /etc/supervisor/conf.d/venus.conf /etc/supervisor/conf.d/venus.conf.backup_$(date +%Y%m%d_%H%M%S)
echo "✓ Backed up Supervisor configuration"

# Create new configuration
sudo tee /etc/supervisor/conf.d/venus.conf > /dev/null << 'EOF'
[program:venus]
directory=/home/administrator/venus/src
command=/home/administrator/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:9102 --timeout=1800 app:app
autostart=true
autorestart=true
stopsignal=TERM
stopasgroup=true
killasgroup=true
stdout_logfile=/var/log/venus/access.log
stderr_logfile=/var/log/venus/error.log
user=administrator
environment=PATH="/home/administrator/venv/bin",PYTHONUNBUFFERED="1"
EOF

echo "✓ Updated Supervisor configuration"

# Reload Supervisor
sudo supervisorctl reread
echo "✓ Supervisor reread configuration"

sudo supervisorctl update venus
echo "✓ Supervisor updated venus program"

# Restart service
echo ""
read -p "Restart venus service now? (yes/no): " restart

if [ "$restart" = "yes" ]; then
    sudo supervisorctl restart venus
    echo "✓ Restarted venus service"
    
    sleep 2
    
    echo ""
    echo "Service status:"
    sudo supervisorctl status venus
    
    echo ""
    echo "Verify timeout in process:"
    ps aux | grep gunicorn | grep -v grep | head -1
else
    echo "⚠️  Remember to restart the service later: sudo supervisorctl restart venus"
fi

echo ""
echo "=== Update Complete ==="
echo ""
echo "Timeout settings:"
echo "  Gunicorn: 1800s (30 minutes)"
echo "  Nginx:    1800s (30 minutes)"
echo ""
echo "To verify:"
echo "  ps aux | grep gunicorn | grep timeout"
