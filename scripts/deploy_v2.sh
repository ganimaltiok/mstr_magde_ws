#!/bin/bash

################################################################################
# MSTR Herald v2 Deployment Script
#
# This script deploys the v2 application alongside the existing production
# without disrupting the current 8000 port service.
#
# Architecture:
# - Port 8000 (Nginx) → 127.0.0.1:8001 (portal_prod - existing production)
# - Port 9101 (Nginx + Gunicorn) → venus v2 (new deployment)
#
# Note: Both nginx and gunicorn use port 9101 for v2
# Gunicorn binds to 0.0.0.0:9101, nginx proxies to 127.0.0.1:9101
#
# Run as root: sudo bash scripts/deploy_v2.sh
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEPLOY_USER="administrator"
DEPLOY_DIR="/home/administrator/venus"
VENV_DIR="/home/administrator/venv"
GITHUB_REPO="https://github.com/ganimaltiok/mstr_magde_ws"
GITHUB_BRANCH="venus_v2"
NGINX_PORT=9101  # External port for v2 (8000 is for production)
GUNICORN_PORT=9101  # Keep same internal port
SUPERVISOR_CONF="/etc/supervisor/conf.d/venus.conf"
NGINX_CONF="/etc/nginx/sites-available/venus_v2.conf"
NGINX_ENABLED="/etc/nginx/sites-enabled/venus_v2.conf"
BACKUP_DIR="/tmp/venus_v1_backup_$(date +%Y%m%d_%H%M%S)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}MSTR Herald v2 Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Usage: sudo bash scripts/deploy_v2.sh"
    exit 1
fi

# Confirmation prompt
echo -e "${YELLOW}This will deploy v2 to:${NC}"
echo "  - Directory: $DEPLOY_DIR"
echo "  - External Port: $NGINX_PORT"
echo "  - Gunicorn: 0.0.0.0:$GUNICORN_PORT (bound to all interfaces)"
echo "  - Production (port 8000) will NOT be affected"
echo ""
read -p "Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo -e "${GREEN}[1/12] Creating backup of current deployment...${NC}"
mkdir -p "$BACKUP_DIR"
if [ -d "$DEPLOY_DIR" ]; then
    cp -r "$DEPLOY_DIR" "$BACKUP_DIR/"
    echo "Backup created at: $BACKUP_DIR"
else
    echo "No existing deployment found (first time deployment)"
fi

echo ""
echo -e "${GREEN}[2/12] Stopping venus supervisor service...${NC}"
supervisorctl stop venus || true
sleep 2

echo ""
echo -e "${GREEN}[3/12] Clearing deployment directory...${NC}"
if [ -d "$DEPLOY_DIR" ]; then
    # Keep .env file if it exists
    if [ -f "$DEPLOY_DIR/.env" ]; then
        cp "$DEPLOY_DIR/.env" "/tmp/venus_env_backup"
        echo "Saved .env file"
    fi
    
    rm -rf "$DEPLOY_DIR"/*
    rm -rf "$DEPLOY_DIR"/.git
    rm -rf "$DEPLOY_DIR"/.github
    echo "Deployment directory cleared"
fi

mkdir -p "$DEPLOY_DIR"
chown -R $DEPLOY_USER:$DEPLOY_USER "$DEPLOY_DIR"

echo ""
echo -e "${GREEN}[4/12] Cloning v2 code from GitHub...${NC}"
cd "$DEPLOY_DIR"
sudo -u $DEPLOY_USER git clone --branch "$GITHUB_BRANCH" "$GITHUB_REPO" temp_clone
sudo -u $DEPLOY_USER mv temp_clone/* .
sudo -u $DEPLOY_USER mv temp_clone/.* . 2>/dev/null || true
rm -rf temp_clone
echo "Code cloned from branch: $GITHUB_BRANCH"

echo ""
echo -e "${GREEN}[5/12] Cleaning up deprecated v1 files...${NC}"
# Remove v1-specific files
rm -f src/web/logbook.py
rm -f src/web/blueprints/config_admin.py
rm -f src/web/blueprints/cache_admin.py
rm -f src/web/blueprints/logs.py
rm -f src/services/cache_service.py
rm -f src/services/postgres_service.py
rm -f src/services/report_service.py
rm -f src/mstr_herald/reports.py
rm -f src/web/health.py  # OLD v1 health check with Redis
rm -f src/web/app.py     # OLD v1 app.py (replaced by web/__init__.py)
rm -rf src/cache_refresher/
rm -f src/web/templates/configure.html
rm -f src/web/templates/edit_dossier.html
echo "Deprecated files removed"

echo ""
echo -e "${GREEN}[6/12] Restoring/creating .env file...${NC}"
if [ -f "/tmp/venus_env_backup" ]; then
    cp "/tmp/venus_env_backup" "$DEPLOY_DIR/.env"
    echo "Restored existing .env file"
else
    # Create new .env from example
    if [ -f "$DEPLOY_DIR/.env.example" ]; then
        cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"
        echo -e "${YELLOW}Created .env from template - YOU MUST EDIT THIS FILE WITH CREDENTIALS!${NC}"
    else
        echo -e "${RED}Warning: No .env file found. You must create one manually.${NC}"
    fi
fi

# Add/update v2-specific env variables
if [ -f "$DEPLOY_DIR/.env" ]; then
    # Add nginx cache paths if not present
    if ! grep -q "NGINX_CACHE_SHORT" "$DEPLOY_DIR/.env"; then
        echo "" >> "$DEPLOY_DIR/.env"
        echo "# Nginx Cache (v2)" >> "$DEPLOY_DIR/.env"
        echo "NGINX_CACHE_SHORT=/var/cache/nginx/shortcache" >> "$DEPLOY_DIR/.env"
        echo "NGINX_CACHE_DAILY=/var/cache/nginx/dailycache" >> "$DEPLOY_DIR/.env"
    fi
    
    # Update port if needed
    sed -i 's/^PORT=.*/PORT=9101/' "$DEPLOY_DIR/.env"
fi

chown $DEPLOY_USER:$DEPLOY_USER "$DEPLOY_DIR/.env"
chmod 600 "$DEPLOY_DIR/.env"

echo ""
echo -e "${GREEN}[7/12] Installing system dependencies...${NC}"
# Install PostgreSQL client libraries and ODBC drivers needed for Python packages
apt-get update -qq
apt-get install -y -qq \
    libpq-dev \
    python3-dev \
    build-essential \
    unixodbc-dev \
    > /dev/null 2>&1
echo "System dependencies installed"

echo ""
echo -e "${GREEN}[8/12] Installing Python dependencies...${NC}"
cd "$DEPLOY_DIR"
# Ensure pip cache ownership is correct
chown -R $DEPLOY_USER:$DEPLOY_USER /home/$DEPLOY_USER/.cache 2>/dev/null || true
# Install with no cache to avoid permission issues
sudo -u $DEPLOY_USER $VENV_DIR/bin/pip install --no-cache-dir -r requirements.txt --quiet
echo "Python dependencies installed"

echo ""
echo -e "${GREEN}[9/12] Migrating dossiers.yaml to endpoints.yaml...${NC}"
if [ -f "$BACKUP_DIR/venus/src/config/dossiers.yaml" ]; then
    echo "Running migration script..."
    sudo -u $DEPLOY_USER $VENV_DIR/bin/python scripts/migrate_dossiers.py \
        "$BACKUP_DIR/venus/src/config/dossiers.yaml" \
        "$DEPLOY_DIR/src/config/endpoints.yaml"
    echo "Migration completed"
elif [ -f "src/config/dossiers.yaml" ]; then
    echo "Running migration script..."
    sudo -u $DEPLOY_USER $VENV_DIR/bin/python scripts/migrate_dossiers.py \
        "src/config/dossiers.yaml" \
        "src/config/endpoints.yaml"
    mv src/config/dossiers.yaml src/config/dossiers.yaml.v1.backup
    echo "Migration completed"
else
    echo "No dossiers.yaml found - creating empty endpoints.yaml"
    mkdir -p "$DEPLOY_DIR/src/config"
    echo "endpoints: {}" > "$DEPLOY_DIR/src/config/endpoints.yaml"
fi

chown $DEPLOY_USER:$DEPLOY_USER "$DEPLOY_DIR/src/config/endpoints.yaml"

echo ""
echo -e "${GREEN}[10/12] Setting up nginx cache directories...${NC}"
mkdir -p /var/cache/nginx/shortcache
mkdir -p /var/cache/nginx/dailycache
chown -R $DEPLOY_USER:$DEPLOY_USER /var/cache/nginx/shortcache
chown -R $DEPLOY_USER:$DEPLOY_USER /var/cache/nginx/dailycache
chmod -R 755 /var/cache/nginx/shortcache
chmod -R 755 /var/cache/nginx/dailycache
echo "Cache directories created"

echo ""
echo -e "${GREEN}[11/12] Creating nginx configuration...${NC}"
cat > "$NGINX_CONF" << 'EOF'
# MSTR Herald v2 - Nginx Configuration
# External Port: 9101
# Direct pass-through to Gunicorn on 0.0.0.0:9101

# Cache zones
proxy_cache_path /var/cache/nginx/shortcache 
    levels=1:2 
    keys_zone=shortcache:10m 
    max_size=500m 
    inactive=10m
    use_temp_path=off;

proxy_cache_path /var/cache/nginx/dailycache 
    levels=1:2 
    keys_zone=dailycache:50m 
    max_size=2g 
    inactive=24h
    use_temp_path=off;

# Map for cacheable methods
map $request_method $is_cacheable {
    GET     1;
    HEAD    1;
    default 0;
}

upstream venus_v2_backend {
    server 127.0.0.1:9101;
}

server {
    listen 9101;
    server_name _;
    
    client_max_body_size 10M;
    
    # Admin routes - bypass cache
    location /admin {
        proxy_pass http://venus_v2_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_no_cache 1;
        proxy_cache_bypass 1;
        add_header X-Cache-Status "BYPASS" always;
    }
    
    location /api/admin {
        proxy_pass http://venus_v2_backend;
        proxy_set_header Host $host;
        proxy_no_cache 1;
        proxy_cache_bypass 1;
        add_header X-Cache-Status "BYPASS" always;
    }
    
    # Health checks - bypass cache
    location ~ ^/(ping|health) {
        proxy_pass http://venus_v2_backend;
        proxy_no_cache 1;
        proxy_cache_bypass 1;
        add_header X-Cache-Status "BYPASS" always;
    }
    
    # v3 API - conditional caching based on Flask headers
    location /api/v3 {
        proxy_pass http://venus_v2_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # Cache key includes full request URI
        proxy_cache_key "$request_uri";
        
        # Cache zone determined by X-Cache-Zone header from Flask
        proxy_cache $upstream_http_x_cache_zone;
        
        # Respect Cache-Control from backend
        proxy_cache_valid 200 10m;
        
        # Only cache GET/HEAD
        proxy_no_cache $is_cacheable = 0;
        proxy_cache_bypass $is_cacheable = 0;
        
        # Add cache status to response
        add_header X-Cache-Status $upstream_cache_status always;
        add_header X-Cache-Zone $upstream_http_x_cache_zone always;
        
        # Timeouts for long-running queries
        proxy_read_timeout 300s;
        proxy_connect_timeout 10s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 16k;
        proxy_buffers 8 16k;
    }
    
    # All other routes
    location / {
        proxy_pass http://venus_v2_backend;
        proxy_set_header Host $host;
        proxy_no_cache 1;
        proxy_cache_bypass 1;
    }
}
EOF

# Enable site
ln -sf "$NGINX_CONF" "$NGINX_ENABLED"
echo "Nginx configuration created at: $NGINX_CONF"
echo "Listening on port: $NGINX_PORT"

# Test nginx config
echo "Testing nginx configuration..."
nginx -t
if [ $? -ne 0 ]; then
    echo -e "${RED}Nginx configuration test failed!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}[12/12] Updating supervisor configuration...${NC}"
# Update existing venus.conf to use v2
cat > "$SUPERVISOR_CONF" << EOF
[program:venus]
directory=$DEPLOY_DIR/src
command=$VENV_DIR/bin/gunicorn --workers 3 --bind 0.0.0.0:9101 --timeout=300 app:app
autostart=true
autorestart=true
stopsignal=TERM
stopasgroup=true
killasgroup=true
stdout_logfile=/var/log/venus/access.log
stderr_logfile=/var/log/venus/error.log
user=$DEPLOY_USER
environment=PATH="$VENV_DIR/bin",PYTHONUNBUFFERED="1"
EOF

# Create log directory
mkdir -p /var/log/venus
chown -R $DEPLOY_USER:$DEPLOY_USER /var/log/venus

echo "Supervisor configuration updated"

# Reload supervisor
supervisorctl reread
supervisorctl update

echo ""
echo -e "${GREEN}[12/12] Starting services...${NC}"
# Start venus
supervisorctl start venus
sleep 3

# Check if venus is running
if supervisorctl status venus | grep -q RUNNING; then
    echo -e "${GREEN}✓ Venus v2 service started successfully${NC}"
else
    echo -e "${RED}✗ Venus v2 service failed to start${NC}"
    echo "Check logs: tail -f /var/log/venus/error.log"
    exit 1
fi

# Reload nginx
systemctl reload nginx
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Nginx reloaded successfully${NC}"
else
    echo -e "${RED}✗ Nginx reload failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Service Status:${NC}"
supervisorctl status
echo ""
echo -e "${BLUE}Listening Ports:${NC}"
netstat -tulpn | grep -E ":(8000|8001|9101)" | grep LISTEN
echo ""
echo -e "${BLUE}Testing Endpoints:${NC}"
echo ""

# Test health endpoint
echo -n "Testing /ping on port $NGINX_PORT... "
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$NGINX_PORT/ping" | grep -q "200"; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
fi

echo -n "Testing /health on port $NGINX_PORT... "
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$NGINX_PORT/health" | grep -q "200"; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
fi

echo -n "Testing /admin/dashboard on port $NGINX_PORT... "
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$NGINX_PORT/admin/dashboard" | grep -q "200"; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
fi

echo ""
echo -e "${BLUE}Access URLs:${NC}"
echo "  - Health Check:    http://$(hostname -I | awk '{print $1}'):$NGINX_PORT/health"
echo "  - Admin Dashboard: http://$(hostname -I | awk '{print $1}'):$NGINX_PORT/admin/dashboard"
echo "  - API Ping:        http://$(hostname -I | awk '{print $1}'):$NGINX_PORT/ping"
echo ""
echo -e "${BLUE}v3 API Example:${NC}"
echo "  curl http://localhost:$NGINX_PORT/api/v3/report/p1_anlik_uretim/agency/100100"
echo ""
echo -e "${BLUE}Production Status (unchanged):${NC}"
echo "  - Port 8000 → 127.0.0.1:8001 (portal_prod) - ${GREEN}ACTIVE${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Review admin dashboard: http://localhost:$NGINX_PORT/admin/dashboard"
echo "  2. Create/verify endpoints in: $DEPLOY_DIR/src/config/endpoints.yaml"
echo "  3. Test v3 API endpoints"
echo "  4. Configure .env file if needed: $DEPLOY_DIR/.env"
echo "  5. Monitor logs: tail -f /var/log/venus/error.log"
echo ""
echo -e "${YELLOW}Rollback Instructions:${NC}"
echo "  If you need to rollback to v1:"
echo "    1. sudo supervisorctl stop venus"
echo "    2. sudo rm -rf $DEPLOY_DIR/*"
echo "    3. sudo cp -r $BACKUP_DIR/venus/* $DEPLOY_DIR/"
echo "    4. sudo supervisorctl start venus"
echo "    5. sudo rm $NGINX_ENABLED"
echo "    6. sudo systemctl reload nginx"
echo ""
echo -e "${GREEN}Deployment script completed successfully!${NC}"
