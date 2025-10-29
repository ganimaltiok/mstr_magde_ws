#!/bin/bash
# Setup nginx cache directories with proper permissions
# Run this script with sudo on the production server

set -e

echo "=== Setting up nginx cache directory permissions ==="
echo ""

# Step 1: Configure nginx systemd service to use umask 022
echo "Step 1: Configuring nginx systemd service umask..."
sudo mkdir -p /etc/systemd/system/nginx.service.d/
sudo tee /etc/systemd/system/nginx.service.d/override.conf > /dev/null <<EOF
[Service]
# Set umask to 022 so nginx creates cache directories with mode 755 instead of 700
UMask=0022
EOF

# Step 2: Reload systemd and restart nginx
echo "Step 2: Reloading systemd and restarting nginx..."
sudo systemctl daemon-reload
sudo systemctl restart nginx

# Step 3: Create cache directories if they don't exist
echo "Step 3: Creating cache directories..."
sudo mkdir -p /var/cache/nginx/shortcache
sudo mkdir -p /var/cache/nginx/dailycache

# Step 4: Set ownership to www-data (nginx user)
echo "Step 4: Setting ownership to www-data:www-data..."
sudo chown -R www-data:www-data /var/cache/nginx/shortcache
sudo chown -R www-data:www-data /var/cache/nginx/dailycache

# Step 5: Set permissions to allow group read access
echo "Step 5: Setting directory permissions to 755..."
sudo chmod -R 755 /var/cache/nginx/shortcache
sudo chmod -R 755 /var/cache/nginx/dailycache

# Step 6: Add administrator to www-data group
echo "Step 6: Adding administrator user to www-data group..."
if groups administrator | grep -q '\bwww-data\b'; then
    echo "  - administrator is already in www-data group"
else
    sudo usermod -a -G www-data administrator
    echo "  - administrator added to www-data group"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Summary:"
echo "  - nginx umask set to 022 (creates dirs with 755)"
echo "  - Cache directories: 755 (rwxr-xr-x)"
echo "  - Owner: www-data:www-data"
echo "  - User 'administrator' in www-data group"
echo ""
echo "Current cache directory permissions:"
ls -la /var/cache/nginx/
echo ""
echo "IMPORTANT: User 'administrator' needs to log out and back in"
echo "for group changes to take effect, or run: newgrp www-data"

