#!/bin/bash
# Deployment Configuration Gatherer for MSTR Herald API
# Run this on your server and paste the output back

echo "========================================="
echo "MSTR Herald API - Deployment Configuration"
echo "========================================="
echo ""

echo "=== 1. System Information ==="
echo "Hostname: $(hostname)"
echo "OS: $(uname -s) $(uname -r)"
echo "Date: $(date)"
echo ""

echo "=== 2. Application Directory ==="
if [ -d "/opt/mstr_magde_ws" ]; then
    echo "Found: /opt/mstr_magde_ws"
    ls -la /opt/mstr_magde_ws/ 2>/dev/null | head -20
elif [ -d "/var/www/mstr_magde_ws" ]; then
    echo "Found: /var/www/mstr_magde_ws"
    ls -la /var/www/mstr_magde_ws/ 2>/dev/null | head -20
else
    echo "App directory: $(pwd)"
    ls -la 2>/dev/null | head -20
fi
echo ""

echo "=== 3. Supervisor Configuration ==="
if [ -f "/etc/supervisor/conf.d/mstr_magde_ws.conf" ]; then
    echo "File: /etc/supervisor/conf.d/mstr_magde_ws.conf"
    cat /etc/supervisor/conf.d/mstr_magde_ws.conf
elif [ -f "/etc/supervisor/supervisord.conf" ]; then
    echo "Checking main supervisord.conf for inline config..."
    grep -A 20 "mstr" /etc/supervisor/supervisord.conf 2>/dev/null || echo "No mstr program found"
else
    echo "Supervisor config not found in standard locations"
    find /etc -name "*supervisor*.conf" 2>/dev/null | head -5
fi
echo ""

echo "=== 4. Systemd Service (if used instead of Supervisor) ==="
if [ -f "/etc/systemd/system/mstr_magde_ws.service" ]; then
    echo "File: /etc/systemd/system/mstr_magde_ws.service"
    cat /etc/systemd/system/mstr_magde_ws.service
elif [ -f "/lib/systemd/system/mstr_magde_ws.service" ]; then
    echo "File: /lib/systemd/system/mstr_magde_ws.service"
    cat /lib/systemd/system/mstr_magde_ws.service
else
    echo "No systemd service found for mstr_magde_ws"
fi
echo ""

echo "=== 5. Nginx Configuration ==="
if [ -f "/etc/nginx/sites-available/mstr_magde_ws" ]; then
    echo "File: /etc/nginx/sites-available/mstr_magde_ws"
    cat /etc/nginx/sites-available/mstr_magde_ws
elif [ -f "/etc/nginx/conf.d/mstr_magde_ws.conf" ]; then
    echo "File: /etc/nginx/conf.d/mstr_magde_ws.conf"
    cat /etc/nginx/conf.d/mstr_magde_ws.conf
else
    echo "Nginx config not found in standard locations"
    echo "Available sites:"
    ls -1 /etc/nginx/sites-available/ 2>/dev/null || echo "Directory not found"
    echo ""
    echo "Enabled sites:"
    ls -1 /etc/nginx/sites-enabled/ 2>/dev/null || echo "Directory not found"
fi
echo ""

echo "=== 6. Gunicorn Process Info ==="
ps aux | grep gunicorn | grep -v grep || echo "No gunicorn process found"
echo ""

echo "=== 7. Socket Files ==="
if [ -d "/run/gunicorn" ]; then
    ls -la /run/gunicorn/
elif [ -S "/tmp/mstr_magde_ws.sock" ]; then
    ls -la /tmp/mstr_magde_ws.sock
else
    echo "Socket directory not found in standard locations"
    find /run /tmp -name "*mstr*.sock" 2>/dev/null
fi
echo ""

echo "=== 8. Environment Variables (from process) ==="
GUNICORN_PID=$(pgrep -f "gunicorn.*mstr_magde_ws" | head -1)
if [ -n "$GUNICORN_PID" ]; then
    echo "Gunicorn PID: $GUNICORN_PID"
    echo "Environment (sensitive values masked):"
    cat /proc/$GUNICORN_PID/environ 2>/dev/null | tr '\0' '\n' | grep -E '^(REDIS|MSTR|PORT|SENTRY|PG)' | sed 's/PASSWORD=.*/PASSWORD=***MASKED***/g' | sed 's/DSN=.*/DSN=***MASKED***/g'
else
    echo "No running gunicorn process found"
fi
echo ""

echo "=== 9. Redis Connection ==="
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
echo "Testing connection to Redis at $REDIS_HOST:$REDIS_PORT"
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" PING 2>&1 || echo "Redis connection failed or redis-cli not installed"
echo ""

echo "=== 10. Log Files ==="
echo "Checking for log files..."
find /var/log -name "*mstr*" -o -name "*gunicorn*" 2>/dev/null | while read logfile; do
    echo "Found: $logfile (size: $(du -h "$logfile" 2>/dev/null | cut -f1))"
done
echo ""

echo "=== 11. Python/Virtualenv Info ==="
if [ -d "/opt/mstr_magde_ws/venv" ]; then
    echo "Virtualenv: /opt/mstr_magde_ws/venv"
    /opt/mstr_magde_ws/venv/bin/python --version
elif [ -d "/var/www/mstr_magde_ws/venv" ]; then
    echo "Virtualenv: /var/www/mstr_magde_ws/venv"
    /var/www/mstr_magde_ws/venv/bin/python --version
else
    echo "System Python: $(which python3)"
    python3 --version
fi
echo ""

echo "=== 12. Listening Ports ==="
echo "Checking what's listening..."
netstat -tlnp 2>/dev/null | grep -E ':(80|443|8000|5000|6379)' || ss -tlnp 2>/dev/null | grep -E ':(80|443|8000|5000|6379)'
echo ""

echo "========================================="
echo "Configuration gathering complete!"
echo "========================================="
echo ""
echo "Please copy all output above and paste it back."
echo "If any sensitive info (passwords, keys) appears, mask it before sharing."
