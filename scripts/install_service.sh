#!/bin/bash
# Install Venus v2 as systemd service

set -e

echo "Installing Venus v2 systemd service..."

# Create service file
sudo tee /etc/systemd/system/venus_v2.service > /dev/null <<EOF
[Unit]
Description=Venus v2 MSTR Herald API
After=network.target

[Service]
Type=notify
User=administrator
Group=administrator
WorkingDirectory=/home/administrator/venus/src
Environment="PATH=/home/administrator/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/administrator/venv/bin/gunicorn \\
    --workers 3 \\
    --bind 127.0.0.1:9102 \\
    --timeout=300 \\
    --access-logfile /home/administrator/venus/logs/access.log \\
    --error-logfile /home/administrator/venus/logs/error.log \\
    --log-level info \\
    app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create logs directory if it doesn't exist
mkdir -p /home/administrator/venus/logs
chown administrator:administrator /home/administrator/venus/logs

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable venus_v2

# Start service
sudo systemctl start venus_v2

# Show status
sudo systemctl status venus_v2

echo ""
echo "✅ Venus v2 service installed and started!"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status venus_v2    - Check status"
echo "  sudo systemctl restart venus_v2   - Restart service"
echo "  sudo systemctl stop venus_v2      - Stop service"
echo "  sudo journalctl -u venus_v2 -f    - Follow logs"
echo "  tail -f /home/administrator/venus/logs/error.log - App error log"
