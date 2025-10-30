# Redis Cache Enhancement - Deployment Checklist

## Pre-Deployment Verification

### Local Testing (Mac)
- [x] All code changes completed
- [x] Migration script created and tested
- [x] Redis connectivity verified (test_redis.py)
- [x] .env.example updated with Redis config
- [x] Documentation created (REDIS_CACHE_IMPLEMENTATION.md)
- [ ] Test Redis service locally
- [ ] Run migration script locally (dry-run)
- [ ] Commit and push changes to GitHub

### Commands for Local Testing
```bash
cd /Users/ganimaltiok/Documents/GitHub/mstr_magde_ws

# Test migration script
python scripts/add_redis_cache_field.py --dry-run

# Commit changes
git status
git add -A
git commit -m "Add Redis cache enhancement (v3.1)

- Add optional 12-hour Redis caching per endpoint
- Cache full datasets with in-memory filtering
- Admin UI integration (checkbox, refresh buttons, metadata)
- New admin_redis blueprint for cache management
- Migration script for backward compatibility
- Full documentation in REDIS_CACHE_IMPLEMENTATION.md"

git push origin main
```

## Server Deployment

### Step 1: Backup
```bash
ssh administrator@venus

cd /home/administrator/venus

# Backup endpoints.yaml
cp src/config/endpoints.yaml src/config/endpoints.yaml.backup_$(date +%Y%m%d_%H%M%S)

# Backup .env
cp .env .env.backup_$(date +%Y%m%d_%H%M%S)
```

### Step 2: Update Code
```bash
cd /home/administrator/venus

# Pull latest changes
git fetch origin
git pull origin main

# Verify files
ls -l src/services/redis_cache_service.py
ls -l src/web/blueprints/admin_redis.py
ls -l scripts/add_redis_cache_field.py
```

### Step 3: Update Environment
```bash
cd /home/administrator/venus

# Add Redis config to .env
nano .env
```

Add these lines:
```bash
# Redis Cache (optional endpoint-level caching)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_TTL=43200  # 12 hours
```

### Step 4: Verify Redis
```bash
cd /home/administrator/venus

# Test Redis connectivity
/home/administrator/venv/bin/python scripts/test_redis.py localhost 6379

# Expected output:
# ✓ Connected to Redis
# ✓ PING → PONG
# ✓ SET test key
# ✓ GET test key
# Redis Info:
#   Version: 7.4.4
#   Used Memory: 750M
#   Uptime: 3 days
```

### Step 5: Run Migration Script
```bash
cd /home/administrator/venus

# Preview changes
/home/administrator/venv/bin/python scripts/add_redis_cache_field.py --dry-run

# Apply changes
/home/administrator/venv/bin/python scripts/add_redis_cache_field.py

# Verify
grep -A2 "redis_cache" src/config/endpoints.yaml | head -20
```

### Step 6: Restart Service
```bash
# Restart gunicorn
sudo systemctl restart venus

# Check status
sudo systemctl status venus

# Check logs
tail -f /home/administrator/venus/logs/venus.log

# Look for:
# - "MSTR Herald API starting on port 9102"
# - No Redis connection errors
# - Blueprint registration messages
```

### Step 7: Verify Deployment
```bash
# Test health endpoint
curl http://localhost:9102/ping

# Test Redis stats API
curl http://localhost:9102/api/admin/redis/stats

# Expected response:
# {
#   "status": "success",
#   "data": {
#     "connected": true,
#     "version": "7.4.4",
#     ...
#   }
# }
```

## Post-Deployment Testing

### Test Admin UI
1. Navigate to: http://venus-server:9101/admin/dashboard
2. Verify:
   - [ ] Dashboard loads without errors
   - [ ] "Redis Cache" column visible in endpoints table
   - [ ] "Refresh All Redis Cache" button visible
   - [ ] All existing endpoints show "-" in Redis Cache column

### Test Endpoint Creation
1. Navigate to: http://venus-server:9101/admin/endpoints/create
2. Fill form:
   - Name: test_redis_endpoint
   - Source: mssql
   - Schema: dbo
   - Table: (any test table)
   - **Check "Enable Redis Cache (12 hours)"**
3. Click "Create Endpoint"
4. Verify:
   - [ ] Endpoint created successfully
   - [ ] Dashboard shows "✓ Enabled" in Redis Cache column

### Test Endpoint Edit
1. Click "Edit" on an existing endpoint
2. Check "Enable Redis Cache (12 hours)"
3. Click "Update Endpoint"
4. Verify:
   - [ ] Endpoint updated successfully
   - [ ] Dashboard shows "✓ Enabled" in Redis Cache column

### Test Cache Functionality
```bash
# 1. Make first request (should cache data)
curl "http://venus-server:9101/api/v3/report/test_redis_endpoint/agency/100100" -w "\nTime: %{time_total}s\n"

# 2. Check cache metadata
curl http://venus-server:9101/api/admin/redis/metadata/test_redis_endpoint

# Expected response:
# {
#   "status": "success",
#   "data": {
#     "last_updated": "2025-01-24T...",
#     "record_count": 1500,
#     "source": "mssql",
#     "ttl_remaining": 43100
#   }
# }

# 3. Make second request (should be faster)
curl "http://venus-server:9101/api/v3/report/test_redis_endpoint/agency/100100" -w "\nTime: %{time_total}s\n"

# 4. Test refresh
curl -X POST http://venus-server:9101/api/admin/redis/refresh/test_redis_endpoint

# 5. Verify cache cleared
curl http://venus-server:9101/api/admin/redis/metadata/test_redis_endpoint
# Should return 404 or "Not cached yet"
```

### Test Refresh Operations
1. **Individual Refresh:**
   - Click "Refresh" button on an endpoint in dashboard
   - Verify success message
   - Verify metadata reset

2. **Batch Refresh:**
   - Click "Refresh All Redis Cache" button
   - Verify success message with count
   - Verify all Redis caches cleared

## Performance Validation

### Measure Cache Impact
```bash
# Create a test script
cat > test_redis_performance.sh << 'EOF'
#!/bin/bash
ENDPOINT="test_redis_endpoint"
AGENCY="100100"
URL="http://localhost:9101/api/v3/report/${ENDPOINT}/agency/${AGENCY}"

echo "Test 1: First request (cache miss)"
time curl -s "$URL" > /dev/null

echo "Test 2: Second request (cache hit)"
time curl -s "$URL" > /dev/null

echo "Test 3: Third request (cache hit)"
time curl -s "$URL" > /dev/null
EOF

chmod +x test_redis_performance.sh
./test_redis_performance.sh
```

### Monitor Redis Memory
```bash
# Check Redis memory usage
redis-cli info memory | grep used_memory_human

# Count cached endpoints
redis-cli keys "v3:data:*" | wc -l

# Check specific endpoint size
redis-cli memory usage "v3:data:test_redis_endpoint"
```

## Rollback Plan (If Issues Occur)

### Emergency Rollback
```bash
cd /home/administrator/venus

# Restore endpoints.yaml backup
cp src/config/endpoints.yaml.backup_YYYYMMDD_HHMMSS src/config/endpoints.yaml

# Restore .env backup
cp .env.backup_YYYYMMDD_HHMMSS .env

# Revert to previous commit
git log --oneline | head -5
git reset --hard PREVIOUS_COMMIT_HASH

# Restart service
sudo systemctl restart venus
```

### Disable Redis Without Rollback
```bash
# Edit .env - comment out Redis config
nano /home/administrator/venus/.env

# Comment these lines:
# REDIS_HOST=localhost
# REDIS_PORT=6379
# REDIS_DB=0
# REDIS_TTL=43200

# Or set endpoints to redis_cache: false
nano /home/administrator/venus/src/config/endpoints.yaml

# Restart
sudo systemctl restart venus
```

## Success Criteria

- [ ] Service starts without errors
- [ ] Admin dashboard loads and shows Redis column
- [ ] Can create/edit endpoints with Redis checkbox
- [ ] Can enable Redis cache for existing endpoint
- [ ] First request caches data (check metadata API)
- [ ] Second request is faster (cache hit)
- [ ] Refresh button clears cache successfully
- [ ] Refresh All button works for multiple endpoints
- [ ] Redis stats API returns valid data
- [ ] No errors in service logs
- [ ] Backward compatibility: endpoints without redis_cache work normally

## Monitoring After Deployment

### First 24 Hours
```bash
# Watch logs for errors
tail -f /home/administrator/venus/logs/venus.log | grep -i -E "error|redis|cache"

# Monitor Redis memory
watch -n 60 'redis-cli info memory | grep used_memory_human'

# Check endpoint count
watch -n 300 'redis-cli keys "v3:*" | wc -l'
```

### Weekly Checks
- Redis memory usage trend
- Number of cached endpoints
- Cache hit/miss ratio (if logging added)
- Endpoint performance improvements
- Error rate for Redis operations

## Gradual Rollout Plan

### Phase 1: Testing (Week 1)
- Enable Redis cache for 2-3 low-traffic endpoints
- Monitor performance and errors
- Gather user feedback

### Phase 2: Expansion (Week 2)
- Enable for expensive MSTR dossiers (>5s fetch time)
- Enable for large SQL queries (>1000 records)
- Continue monitoring

### Phase 3: Full Deployment (Week 3+)
- Review all endpoints for Redis suitability
- Enable for all appropriate candidates
- Document best practices

## Contact Information

**If Issues Arise:**
- Check service logs: `/home/administrator/venus/logs/venus.log`
- Check Redis: `docker logs redis`
- Check Nginx: `/var/log/nginx/error.log`
- Restart service: `sudo systemctl restart venus`

**For Assistance:**
- Review documentation: `REDIS_CACHE_IMPLEMENTATION.md`
- Check troubleshooting section
- Review git history: `git log --oneline`
