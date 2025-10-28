#!/bin/bash

# Fix nginx cache permissions for administrator user
# This allows the Flask app to manage cache without sudo

echo "Fixing nginx cache directory permissions..."

# Create cache directories if they don't exist
sudo mkdir -p /var/cache/nginx/shortcache
sudo mkdir -p /var/cache/nginx/dailycache

# Change ownership to administrator:www-data (administrator can write, nginx can read)
sudo chown -R administrator:www-data /var/cache/nginx/shortcache
sudo chown -R administrator:www-data /var/cache/nginx/dailycache

# Set permissions: owner (administrator) has full access, group (www-data/nginx) can read
sudo chmod -R 755 /var/cache/nginx/shortcache
sudo chmod -R 755 /var/cache/nginx/dailycache

echo "Cache permissions fixed!"
echo "Administrator user can now manage cache directories"
echo ""
echo "Verifying permissions:"
ls -la /var/cache/nginx/
