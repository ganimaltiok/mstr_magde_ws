#!/bin/bash

echo "========================================="
echo "Port & Service Analysis"
echo "========================================="
echo ""

echo "=== 1. All Gunicorn processes with full command ==="
ps aux | grep gunicorn | grep -v grep
echo ""

echo "=== 2. Which process is listening on which port? ==="
echo "Port 9101:"
ss -tlnp | grep 9101 || echo "Not listening"
echo ""
echo "Port 8001:"
ss -tlnp | grep 8001 || echo "Not listening"
echo ""
echo "Port 8000:"
ss -tlnp | grep 8000 || echo "Not listening"
echo ""

echo "=== 3. Nginx configuration files ==="
echo "Looking for nginx configs mentioning venus or mstr..."
sudo grep -r "9101\|8001\|venus\|mstr" /etc/nginx/sites-available/ 2>/dev/null || echo "No matches in sites-available"
echo ""
sudo grep -r "9101\|8001\|venus\|mstr" /etc/nginx/sites-enabled/ 2>/dev/null || echo "No matches in sites-enabled"
echo ""

echo "=== 4. Check which working directory each Gunicorn uses ==="
for pid in $(pgrep -f "gunicorn.*app:app"); do
    echo "PID $pid working directory:"
    pwdx $pid 2>/dev/null || readlink -f /proc/$pid/cwd 2>/dev/null
done
echo ""

echo "=== 5. Application .env file (if readable) ==="
if [ -f /home/administrator/venus/.env ]; then
    echo "PORT setting from .env:"
    grep -i "^PORT=" /home/administrator/venus/.env 2>/dev/null || echo "No PORT variable found"
else
    echo ".env not found or not readable"
fi
echo ""

echo "=== 6. Test connections ==="
echo "Testing localhost:9101..."
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:9101/ping 2>/dev/null || echo "Connection failed"
echo ""
echo "Testing localhost:8001..."
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8001/ping 2>/dev/null || echo "Connection failed"
echo ""
echo "Testing localhost:8000..."
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8000/ping 2>/dev/null || echo "Connection failed"
echo ""

echo "========================================="
echo "Analysis complete!"
echo "========================================="
