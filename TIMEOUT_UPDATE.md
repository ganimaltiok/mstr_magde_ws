# Timeout Configuration Update

## Summary
Increased timeout settings from 5 minutes to **30 minutes (1800 seconds)** for both Nginx and Gunicorn to support long-running queries, particularly for:
- Large MSTR dossiers
- Complex cross-database SQL queries  
- Redis cache initial population (full dataset fetches)
- Report exports with large datasets

## Changes Made

### 1. Nginx Configuration (`nginx/venus_v2.conf`)
**Updated timeout directives in `/api/v3` location block:**

```nginx
# Before (5 minutes)
proxy_read_timeout 300s;
proxy_connect_timeout 10s;

# After (30 minutes)
proxy_read_timeout 1800s;
proxy_connect_timeout 30s;
proxy_send_timeout 1800s;
```

**Timeout Directives:**
- `proxy_read_timeout`: How long nginx waits for backend response (1800s = 30 min)
- `proxy_connect_timeout`: Connection establishment timeout (30s)
- `proxy_send_timeout`: How long nginx waits to transmit request to backend (1800s = 30 min)

### 2. Gunicorn Configuration
**Updated worker timeout setting:**

```bash
# Before (5 minutes)
--timeout=300

# After (30 minutes)
--timeout=1800
```

This needs to be updated in:
- Supervisor configuration: `/etc/supervisor/conf.d/venus.conf`
- Deployment script: `scripts/deploy_v2.sh`
- Manual startup commands
- Documentation

### 3. Updated Documentation
- `.github/copilot-instructions.md` - Updated Gunicorn command example
- Created `scripts/update_timeouts.sh` - Helper script for server deployment

## Deployment Instructions

### On Server (as administrator user):

#### Quick Method (Using Script)
```bash
cd /home/administrator/venus
git pull origin main

# Run the update script
sudo bash scripts/update_timeouts.sh
```

The script will:
1. Backup existing service file
2. Update systemd service with new timeout
3. Reload systemd daemon
4. Optionally restart the service

#### Manual Method

**Step 1: Update Nginx Config**
```bash
# Copy new config
sudo cp /home/administrator/venus/nginx/venus_v2.conf /etc/nginx/conf.d/venus_v2.conf

# Test config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

**Step 2: Update Gunicorn (Supervisor Configuration)**
```bash
# Backup existing configuration
sudo cp /etc/supervisor/conf.d/venus.conf /etc/supervisor/conf.d/venus.conf.backup

# Edit configuration file
sudo nano /etc/supervisor/conf.d/venus.conf
```

Update the `command` line:
```ini
[program:venus]
command=/home/administrator/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:9102 --timeout=1800 app:app
```

**Step 3: Apply Changes**
```bash
# Reload Supervisor
sudo supervisorctl reread
sudo supervisorctl update venus

# Restart service
sudo supervisorctl restart venus

# Verify
sudo supervisorctl status venus
ps aux | grep gunicorn | grep timeout
```

## Verification

### Check Nginx Timeout
```bash
grep -A5 "proxy_read_timeout" /etc/nginx/conf.d/venus_v2.conf
```

Expected output:
```
proxy_read_timeout 1800s;
proxy_connect_timeout 30s;
proxy_send_timeout 1800s;
```

### Check Gunicorn Timeout
```bash
ps aux | grep gunicorn | grep -v grep
```

Look for `--timeout=1800` in the command line.

Or check the Supervisor configuration:
```bash
grep timeout /etc/supervisor/conf.d/venus.conf
```

Or check via Supervisor:
```bash
sudo supervisorctl status venus
```

### Test Long-Running Query
```bash
# Test with a large endpoint
time curl "http://localhost:9101/api/v3/report/large_endpoint/agency/100100"
```

The request should not timeout even if it takes >5 minutes.

## Rollback (If Needed)

### Rollback Nginx
```bash
# Restore backup
sudo cp /etc/nginx/conf.d/venus_v2.conf.backup /etc/nginx/conf.d/venus_v2.conf

# Or manually edit
sudo nano /etc/nginx/conf.d/venus_v2.conf
# Change 1800s back to 300s

sudo systemctl reload nginx
```

### Rollback Gunicorn
```bash
# Restore backup
sudo cp /etc/supervisor/conf.d/venus.conf.backup /etc/supervisor/conf.d/venus.conf

# Or manually edit
sudo nano /etc/supervisor/conf.d/venus.conf
# Change 1800 back to 300

sudo supervisorctl reread
sudo supervisorctl update venus
sudo supervisorctl restart venus
```

## Configuration Matrix

| Component | Setting | Old Value | New Value | Purpose |
|-----------|---------|-----------|-----------|---------|
| Nginx | `proxy_read_timeout` | 300s | 1800s | Backend response timeout |
| Nginx | `proxy_connect_timeout` | 10s | 30s | Connection timeout |
| Nginx | `proxy_send_timeout` | (none) | 1800s | Request send timeout |
| Gunicorn | `--timeout` | 300 | 1800 | Worker timeout |

## Impact Assessment

### Positive Impacts
✅ Supports long-running MSTR queries (>5 min)  
✅ Allows large dataset Redis cache population  
✅ Enables complex cross-database SQL queries  
✅ Better user experience (no premature timeouts)

### Considerations
⚠️ Workers may be tied up longer with slow queries  
⚠️ Consider increasing worker count if needed  
⚠️ Monitor worker availability and queue times

### Monitoring Recommendations
```bash
# Check worker status
ps aux | grep gunicorn | wc -l

# Monitor slow queries
tail -f /home/administrator/venus/logs/venus.log | grep -E "took [0-9]{4,}"

# Watch nginx timeouts
tail -f /var/log/nginx/error.log | grep timeout
```

## Related Configuration

### Worker Count
If many long-running queries occur simultaneously, consider increasing workers:

```bash
# Current: 3 workers
--workers 3

# Increased capacity: 5 workers
--workers 5
```

Update in `/etc/supervisor/conf.d/venus.conf` and restart:
```bash
sudo nano /etc/supervisor/conf.d/venus.conf
sudo supervisorctl reread
sudo supervisorctl update venus
sudo supervisorctl restart venus
```

### Redis Cache Benefits
With 30-minute timeout, Redis cache becomes more effective:
- First request: May take 10-20 minutes (full dataset fetch)
- Cached requests: <1 second (in-memory filtering)

This makes the long timeout worthwhile for initial cache population.

## Testing Checklist

After deployment:
- [ ] Nginx config test passes (`sudo nginx -t`)
- [ ] Supervisor shows venus as RUNNING (`sudo supervisorctl status venus`)
- [ ] Gunicorn shows `--timeout=1800` in process list
- [ ] Short queries still work quickly (<1s)
- [ ] Long queries don't timeout (test with large endpoint)
- [ ] No errors in nginx logs
- [ ] No timeout errors in application logs (`/var/log/venus/error.log`)
- [ ] Admin dashboard loads correctly
- [ ] Health check responds (`/health`)

## Notes

- Both timeouts must match to prevent premature termination
- Nginx timeout should be ≥ Gunicorn timeout
- Consider load balancer timeouts if applicable
- Monitor worker availability with increased timeouts
- Review and optimize slow queries over time
