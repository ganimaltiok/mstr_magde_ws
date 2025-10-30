# MSTR Herald API Migration Guide

## Latest: Redis Cache Enhancement (v3.1)
See [REDIS_CACHE_IMPLEMENTATION.md](REDIS_CACHE_IMPLEMENTATION.md) for details on the optional Redis caching layer.

## MSTR Herald API v2 → v3 Migration Guide

## Overview

v2 represents a complete architectural rebuild with the following major changes:

### What Changed

| Component | v1 | v2 |
|-----------|----|----|
| **Cache Backend** | Redis (pickled DataFrames) | Nginx proxy cache |
| **Data Sources** | MSTR + PostgreSQL (dual policy) | 6 explicit behaviors (livesql, cachesql, livepg, cachepg, livemstr, cachemstr) |
| **Configuration** | `dossiers.yaml` | `endpoints.yaml` |
| **Filtering** | In-memory (post-fetch) | Server-side (MSTR API + SQL WHERE) |
| **Admin UI** | `/admin/configure`, `/admin/edit` | `/admin/dashboard`, `/admin/endpoints` |
| **Cache Refresh** | CLI + HTTP endpoints | Nginx automatic + HTTP purge API |
| **Pagination** | In-memory only | Database-level + in-memory |
| **Access Logs** | In-memory circular buffer | Persistent access logger service |

### What Stayed the Same

✅ **v3 REST API is 100% backward compatible**  
✅ URL structure unchanged: `/api/v3/report/<name>/agency/<code>`  
✅ Response JSON format identical  
✅ Query parameter filtering still supported  
✅ MicroStrategy Library API integration  

## Pre-Migration Checklist

- [ ] Backup current production database
- [ ] Export current `src/config/dossiers.yaml`
- [ ] Document all active v3 endpoints in use
- [ ] Note current cache refresh schedule (cron jobs)
- [ ] Verify Redis data export (if needed for analysis)
- [ ] Test all endpoints return expected data

## Migration Steps

### 1. Backup Current System

```bash
# Backup configuration
cp src/config/dossiers.yaml /tmp/dossiers.yaml.backup

# Backup current code (create v1 branch)
cd /home/administrator/venus
git checkout -b v1-backup
git add -A
git commit -m "Backup v1 before migration to v2"

# Export Redis data (optional, for records)
redis-cli --rdb /tmp/venus_redis_backup.rdb
```

### 2. Install v2 Code

```bash
# Pull v2 code
git checkout main  # or your v2 branch
git pull origin main

# Install new dependencies
source /home/administrator/venv/bin/activate
pip install -r requirements.txt

# pyodbc and psycopg2-binary are new requirements
# Ensure ODBC drivers are installed for MSSQL
```

### 3. Migrate Configuration

```bash
# Run migration script
cd /home/administrator/venus
python scripts/migrate_dossiers.py \
    /tmp/dossiers.yaml.backup \
    src/config/endpoints.yaml

# Review generated endpoints.yaml
cat src/config/endpoints.yaml

# Manual adjustments needed:
# - Verify behavior assignments (default: cachemstr for MSTR, cachepg for PG)
# - Add SQL/PG table mappings for new data sources
# - Configure filter_mappings for MSTR reports
```

### 4. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env with production credentials
vim .env

# Required new variables:
# - MSSQL_* (if using SQL behaviors)
# - PG_* (existing, verify values)
# - NGINX_CACHE_SHORT=/var/cache/nginx/shortcache
# - NGINX_CACHE_DAILY=/var/cache/nginx/dailycache

# Remove Redis variables (no longer needed):
# - REDIS_HOST
# - REDIS_PORT
# - REDIS_DB
```

### 5. Setup Nginx Cache

```bash
# Create cache directories
sudo mkdir -p /var/cache/nginx/shortcache
sudo mkdir -p /var/cache/nginx/dailycache

# Set ownership (Flask app needs write access for purge)
sudo chown -R administrator:administrator /var/cache/nginx/

# Copy nginx config
sudo cp nginx/mstr_herald.conf /etc/nginx/sites-available/mstr_herald.conf

# Enable site
sudo ln -sf /etc/nginx/sites-available/mstr_herald.conf /etc/nginx/sites-enabled/

# Test config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 6. Update Gunicorn

```bash
# Stop old Gunicorn
pkill -f "gunicorn.*app:app"

# Start new Gunicorn (v2 uses port 9101)
cd /home/administrator/venus/src
/home/administrator/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:9101 \
    --timeout=300 \
    app:app &

# Verify it's running
curl http://localhost:9101/ping
# Expected: {"status": "ok"}
```

### 7. Update Nginx Upstream

Edit `/etc/nginx/sites-available/mstr_herald.conf`:

```nginx
upstream flask_backend {
    server 127.0.0.1:9101;  # Changed from 8001
}
```

Reload nginx:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 8. Remove Deprecated Files

```bash
# Run cleanup script
chmod +x scripts/cleanup_old_files.sh
./scripts/cleanup_old_files.sh

# Verify structure
python scripts/verify_v2_structure.py
```

### 9. Update Cron Jobs

**Old cron (remove these):**
```cron
# v1 cache refresh jobs
0 7 * * * cd /home/administrator/venus/src && python -m cache_refresher.cache_refresher
```

**New approach:**
- No cron jobs needed for cache refresh
- Nginx handles automatic cache expiry
- Use `/admin/cache` UI for manual purge

**Optional: Daily cache pre-warming (for cachemstr endpoints):**
```cron
# Warm cache at 6:30 AM (before 7 AM expiry)
30 6 * * * curl -X POST http://localhost:8000/admin/cache/purge
```

### 10. Test All Endpoints

Create a test script:

```bash
# filepath: /tmp/test_v2_endpoints.sh
#!/bin/bash

ENDPOINTS=(
    "sales_summary"
    "inventory"
    "customer_master"
    # ... add all your endpoints
)

for endpoint in "${ENDPOINTS[@]}"; do
    echo "Testing: $endpoint"
    curl -s "http://localhost:8000/api/v3/report/$endpoint/agency/100100?page=1&per_page=10" \
        | jq '.info.report_name, .pagination.total_records'
done
```

Run tests:
```bash
chmod +x /tmp/test_v2_endpoints.sh
/tmp/test_v2_endpoints.sh
```

### 11. Monitor Initial Production Run

```bash
# Watch Gunicorn logs
tail -f /var/log/mstr_herald/app.log

# Watch Nginx access logs
sudo tail -f /var/log/nginx/access.log | grep mstrws

# Monitor cache growth
watch -n 5 'du -sh /var/cache/nginx/*'
```

### 12. Verify Functionality

Check these in order:

1. **Health checks:**
   ```bash
   curl http://localhost:8000/health
   # Should show all green statuses
   ```

2. **Admin dashboard:**
   - Navigate to `http://mstrws.magdeburger.local:8000/admin/dashboard`
   - Verify all endpoints listed
   - Check health panel shows connections OK

3. **Cache behavior:**
   ```bash
   # First request (cache MISS)
   curl -I "http://localhost:8000/api/v3/report/sales_summary/agency/100100"
   # Look for: X-Cache-Status: MISS
   
   # Second request (cache HIT)
   curl -I "http://localhost:8000/api/v3/report/sales_summary/agency/100100"
   # Look for: X-Cache-Status: HIT
   ```

4. **Cache purge:**
   - Go to `/admin/cache`
   - Click "Clear All Cache"
   - Verify cache directories are recreated empty

5. **MSTR auto-discovery:**
   - Go to `/admin/endpoints/create`
   - Select behavior: `cachemstr`
   - Enter dossier ID
   - Click "Gather Info"
   - Verify viz keys and filters auto-populate

## Rollback Plan

If issues arise, rollback to v1:

```bash
# Stop v2 Gunicorn
pkill -f "gunicorn.*app:app"

# Restore v1 code
cd /home/administrator/venus
git checkout v1-backup

# Restore v1 config
cp /tmp/dossiers.yaml.backup src/config/dossiers.yaml

# Start v1 Gunicorn (port 8001)
cd src
/home/administrator/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8001 \
    --timeout=300 \
    app:app &

# Update nginx upstream back to 8001
sudo vim /etc/nginx/sites-available/mstr_herald.conf
# Change: server 127.0.0.1:8001;

# Reload nginx
sudo systemctl reload nginx

# Restart Redis (if stopped)
docker start venus_redis
```

## Post-Migration Tasks

- [ ] Update documentation with new admin URLs
- [ ] Train users on new admin interface
- [ ] Remove v1 backup branch after 1 week stable
- [ ] Setup monitoring for nginx cache disk usage
- [ ] Configure log rotation for `/var/log/mstr_herald/`
- [ ] Update deployment scripts/runbooks

## Troubleshooting

### "Endpoint not found" errors

**Cause:** Configuration not migrated correctly.

**Fix:**
```bash
# Check endpoints.yaml exists and is valid
cat src/config/endpoints.yaml | python -m yaml

# Verify endpoint names match exactly
curl http://localhost:8000/admin/api/dashboard/stats | jq '.endpoints'
```

### Cache not working (always MISS)

**Cause:** Nginx cache directories not writable or X-Cache-Zone header not set.

**Fix:**
```bash
# Check permissions
ls -la /var/cache/nginx/

# Check Flask response headers
curl -I "http://localhost:9101/api/v3/report/sales_summary/agency/100100"
# Should see: X-Cache-Zone: dailycache (or shortcache)

# Check nginx config syntax
sudo nginx -t
```

### MSSQL/PostgreSQL connection errors

**Cause:** Missing ODBC drivers or incorrect credentials.

**Fix:**
```bash
# Test MSSQL connection
python -c "
from services.sql_fetcher import get_sql_fetcher
success, error, time = get_sql_fetcher().test_connection()
print(f'Success: {success}, Error: {error}')
"

# Test PostgreSQL connection
python -c "
from services.pg_fetcher import get_pg_fetcher
success, error, time = get_pg_fetcher().test_connection()
print(f'Success: {success}, Error: {error}')
"
```

### Performance slower than v1

**Cause:** Database-level pagination may be slower than in-memory (but more scalable).

**Solutions:**
- Add indexes to filtered columns in MSSQL/PostgreSQL
- Use cached behaviors (cachesql, cachepg, cachemstr) for frequently accessed data
- Increase nginx cache size in `mstr_herald.conf`

## FAQ

**Q: Can I still use Redis for caching?**  
A: No, v2 uses nginx exclusively. Redis dependency has been removed.

**Q: What happens to old Redis cache data?**  
A: It's no longer used. You can safely delete the Redis container after verifying v2 works.

**Q: Do I need to change client applications?**  
A: No, v3 API is 100% backward compatible.

**Q: How do I add a new endpoint now?**  
A: Use the admin UI at `/admin/endpoints/create` or manually edit `endpoints.yaml`.

**Q: Where are cache refresh logs now?**  
A: Check `/var/log/nginx/access.log` for cache activity. Application logs in `/var/log/mstr_herald/app.log`.

**Q: Can I mix v1 and v2 endpoints?**  
A: No, it's all-or-nothing migration. v2 uses completely different configuration format.

## Support

For issues during migration:
- Check `/var/log/mstr_herald/app.log` for application errors
- Check `/var/log/nginx/error.log` for nginx errors
- Review health dashboard: `http://mstrws.magdeburger.local:8000/health`
- Contact: [Your Support Contact]
