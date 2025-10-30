# Redis Cache Enhancement - Implementation Complete

## Overview
Added optional per-endpoint Redis caching (12-hour TTL) as a middle layer between Nginx (10min) and data sources. When enabled, endpoints cache full datasets in Redis and apply filters/pagination in-memory for improved performance.

## Architecture

### Caching Layers
```
Request → Nginx (10min) → Redis (12h, optional) → Data Source
```

- **Nginx**: Fast 10-minute cache for all endpoints (unchanged)
- **Redis**: Optional 12-hour cache for expensive queries (new)
- **Data Source**: MSSQL, PostgreSQL, or MicroStrategy

### Cache Strategy
- **With Redis Enabled** (`redis_cache: true`):
  1. Check Redis cache
  2. HIT: Apply filters/pagination in-memory → return
  3. MISS: Fetch full dataset → store in Redis → apply filters/pagination → return

- **Without Redis** (`redis_cache: false`, default):
  - Current behavior: server-side filtering, database pagination

## Files Created

### 1. `src/services/redis_cache_service.py` (355 lines)
Core service for Redis operations.

**Key Features:**
- JSON serialization (human-readable, debuggable)
- Cache keys: `v3:data:{endpoint}` + `v3:meta:{endpoint}`
- Metadata tracking: last_updated, record_count, source, fetch_duration_ms, cache_size_bytes, ttl_remaining
- Connection pooling with timeout handling

**Methods:**
- `get_cached_data(endpoint_name)` → List[Dict] or None
- `set_cached_data(endpoint_name, data, source, fetch_duration_ms)` → bool
- `delete_cache(endpoint_name)` → bool
- `get_cache_metadata(endpoint_name)` → Dict or None
- `get_all_cached_endpoints()` → List[str]
- `get_redis_stats()` → Dict (version, uptime, memory, keys count)
- `refresh_endpoint_cache(endpoint_name)` → Dict (status, message)
- `refresh_all_caches()` → Dict (batch refresh all redis_cache=true endpoints)

### 2. `src/web/blueprints/admin_redis.py` (220 lines)
Admin API for Redis management.

**Routes:**
- `GET /api/admin/redis/stats` - Redis server statistics
- `POST /api/admin/redis/refresh-all` - Refresh all Redis-enabled endpoints
- `POST /api/admin/redis/refresh/:endpoint` - Refresh single endpoint
- `GET /api/admin/redis/cached-endpoints` - List all cached endpoints with metadata
- `GET /api/admin/redis/metadata/:endpoint` - Get cache metadata for specific endpoint

### 3. `scripts/add_redis_cache_field.py` (140 lines)
Migration script to add `redis_cache: false` to existing endpoints.

**Usage:**
```bash
# Dry run (preview changes)
python scripts/add_redis_cache_field.py --dry-run

# Apply changes
python scripts/add_redis_cache_field.py
```

**Features:**
- Auto-detects endpoints.yaml location
- Creates timestamped backups
- Backward compatible (adds false by default)

## Files Modified

### 1. `src/services/settings.py`
Added Redis configuration:
```python
REDIS_HOST: str         # default: 'localhost'
REDIS_PORT: int         # default: 6379
REDIS_DB: int           # default: 0
REDIS_TTL: int          # default: 43200 (12 hours)
```

### 2. `.env.example`
Added Redis configuration section:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_TTL=43200  # 12 hours in seconds
```

### 3. `src/services/endpoint_config.py`
- Added `redis_cache: bool` field to EndpointConfig (default: False)
- Updated `to_dict()` to include redis_cache in YAML serialization
- Backward compatible (missing field treated as False)

### 4. `src/services/data_fetcher.py`
- Added `_fetch_with_redis()` method (layered caching logic)
- Added `_fetch_sql_full()`, `_fetch_pg_full()`, `_fetch_mstr_full()` (fetch without filters)
- Modified `fetch()` to check redis_cache flag

**Cache Flow:**
```python
if endpoint_config.redis_cache:
    return _fetch_with_redis(...)  # Redis + in-memory filtering
else:
    # Current behavior (server-side filtering)
```

### 5. `src/services/dataframe_tools.py`
Added `apply_filters()` function for in-memory filtering of cached data:
```python
def apply_filters(df: pd.DataFrame, filters: dict[str, str]) -> pd.DataFrame:
    """Apply filters to dataframe in-memory (case-insensitive)."""
```

### 6. `src/web/blueprints/__init__.py`
Registered admin_redis blueprint:
```python
from web.blueprints.admin_redis import admin_redis_bp
app.register_blueprint(admin_redis_bp)
```

### 7. `src/web/blueprints/admin_endpoints.py`
Updated `_build_config_from_form()` to handle redis_cache checkbox:
```python
'redis_cache': data.get('redis_cache') == 'on'
```

### 8. `src/web/templates/admin_endpoints_form.html`
Added Redis Cache checkbox:
```html
<input type="checkbox" name="redis_cache" 
       {{ 'checked' if endpoint and endpoint.redis_cache else '' }}>
Enable Redis Cache (12 hours)
```

### 9. `src/web/templates/admin_dashboard.html`
Added Redis features:
- New table column: "Redis Cache" with enable status
- Cache metadata display (record count, last update, TTL remaining)
- "Refresh All Redis Cache" button (batch refresh)
- Individual "Refresh" buttons for Redis-enabled endpoints
- JavaScript functions: `refreshRedisCache()`, `refreshAllRedisCache()`, `loadRedisMetadata()`

## Configuration

### Environment Variables (.env)
```bash
# Existing variables...

# Redis Cache (optional endpoint-level caching)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_TTL=43200  # 12 hours
```

### Endpoint Configuration (endpoints.yaml)
```yaml
endpoints:
  sales_summary:
    source: mssql
    description: "Daily sales summary"
    redis_cache: true  # Enable Redis cache
    pagination:
      per_page: 100
    mssql:
      schema: "dbo"
      table: "sales"
```

## Admin UI Changes

### Dashboard (`/admin/dashboard`)
**New Features:**
1. **Redis Cache Column** - Shows enable status and metadata
2. **Refresh All Redis Cache Button** - Batch clear all Redis-enabled endpoints
3. **Individual Refresh Buttons** - Per-endpoint cache refresh
4. **Real-time Metadata** - Auto-loads cache info (record count, age, TTL)

**Display Example:**
```
Name          | Source | Redis Cache                  | Actions
sales_summary | mssql  | ✓ Enabled                   | Edit | Refresh | Delete
                        | 1500 records • 2h ago • TTL: 10h
inventory     | mssql  | -                            | Edit | Delete
```

### Endpoint Form (`/admin/endpoints/create`, `/admin/endpoints/edit`)
**New Field:**
```
☐ Enable Redis Cache (12 hours)
  When enabled, full dataset is cached in Redis for 12 hours.
  Filters and pagination are applied in-memory.
```

## API Endpoints

### Admin Redis API (`/api/admin/redis/*`)

#### Get Redis Stats
```bash
GET /api/admin/redis/stats

Response:
{
  "status": "success",
  "data": {
    "connected": true,
    "version": "7.4.4",
    "uptime_days": 3,
    "used_memory": "750M",
    "total_keys": 42,
    "v3_cache_keys": 5
  }
}
```

#### Refresh Single Endpoint
```bash
POST /api/admin/redis/refresh/sales_summary

Response:
{
  "status": "success",
  "message": "Cache cleared for 'sales_summary'. Next request will fetch fresh data.",
  "endpoint": "sales_summary",
  "cache_deleted": true
}
```

#### Refresh All Endpoints
```bash
POST /api/admin/redis/refresh-all

Response:
{
  "status": "success",
  "message": "Refreshed 5/8 endpoints",
  "endpoints_processed": 8,
  "success_count": 5,
  "results": [...]
}
```

#### Get Cached Endpoints
```bash
GET /api/admin/redis/cached-endpoints

Response:
{
  "status": "success",
  "data": {
    "total": 3,
    "endpoints": [
      {
        "name": "sales_summary",
        "last_updated": "2025-01-24T10:30:45",
        "record_count": 1500,
        "source": "mssql",
        "fetch_duration_ms": 234,
        "cache_size_bytes": 458900,
        "ttl_remaining": 39600
      }
    ]
  }
}
```

#### Get Endpoint Metadata
```bash
GET /api/admin/redis/metadata/sales_summary

Response:
{
  "status": "success",
  "data": {
    "last_updated": "2025-01-24T10:30:45",
    "record_count": 1500,
    "source": "mssql",
    "fetch_duration_ms": 234,
    "cache_size_bytes": 458900,
    "ttl_remaining": 39600
  }
}
```

## Deployment Steps

### 1. Update Server Environment
```bash
# Add Redis config to .env
echo "REDIS_HOST=localhost" >> /home/administrator/venus/.env
echo "REDIS_PORT=6379" >> /home/administrator/venus/.env
echo "REDIS_DB=0" >> /home/administrator/venus/.env
echo "REDIS_TTL=43200" >> /home/administrator/venus/.env
```

### 2. Run Migration Script
```bash
cd /home/administrator/venus

# Preview changes
python scripts/add_redis_cache_field.py --dry-run

# Apply changes
python scripts/add_redis_cache_field.py
```

### 3. Deploy Code
```bash
cd /home/administrator/venus
git pull origin main

# Restart gunicorn
sudo systemctl restart venus
sudo systemctl status venus
```

### 4. Verify Redis Connectivity
```bash
cd /home/administrator/venus
python scripts/test_redis.py localhost 6379
```

### 5. Enable Redis Cache for Endpoints (via Admin UI)
1. Navigate to `/admin/endpoints`
2. Edit endpoint
3. Check "Enable Redis Cache (12 hours)"
4. Save

## Performance Benefits

### Use Cases for Redis Cache
✅ **Good Candidates:**
- Large datasets (>1000 records) accessed frequently
- Expensive MSTR dossiers (>5 second fetch time)
- Reports with many different filter combinations
- Cross-database SQL queries

❌ **Not Recommended:**
- Real-time data requirements
- Small datasets (<100 records)
- Rarely accessed endpoints
- Frequently changing data

### Example Performance Impact
**Without Redis:**
- Request 1: 8.2s (MSTR fetch + filters)
- Request 2: 7.9s (MSTR fetch + filters)
- Request 3: 8.1s (MSTR fetch + filters)

**With Redis (after initial cache):**
- Request 1: 8.5s (MSTR fetch + store in Redis)
- Request 2: 0.3s (Redis + in-memory filter)
- Request 3: 0.2s (Redis + in-memory filter)

## Monitoring

### Check Redis Stats
```bash
# Via API
curl http://localhost:8000/api/admin/redis/stats

# Via Redis CLI
redis-cli info
redis-cli dbsize
redis-cli keys "v3:*"
```

### Check Cached Endpoints
```bash
curl http://localhost:8000/api/admin/redis/cached-endpoints
```

### View Specific Endpoint Metadata
```bash
curl http://localhost:8000/api/admin/redis/metadata/sales_summary
```

## Troubleshooting

### Redis Connection Failed
**Check Docker:**
```bash
docker ps | grep redis
docker logs redis
```

**Check Config:**
```bash
cat /home/administrator/venus/.env | grep REDIS
```

### Cache Not Working
**Verify redis_cache enabled:**
```bash
# Check endpoints.yaml
grep -A5 "sales_summary:" /home/administrator/venus/src/config/endpoints.yaml
```

**Check logs:**
```bash
tail -f /home/administrator/venus/logs/venus.log | grep -i redis
```

### High Memory Usage
**Check Redis memory:**
```bash
redis-cli info memory
redis-cli keys "v3:*" | wc -l  # Count cached endpoints
```

**Clear specific endpoint:**
```bash
curl -X POST http://localhost:8000/api/admin/redis/refresh/sales_summary
```

**Clear all:**
```bash
curl -X POST http://localhost:8000/api/admin/redis/refresh-all
```

## Backward Compatibility

✅ **Fully backward compatible:**
- Existing endpoints work unchanged (redis_cache defaults to false)
- Migration script adds field without breaking existing configs
- Old nginx caching remains active for all endpoints
- No changes to existing API responses

## Testing Checklist

### Before Deployment
- [ ] Run migration script in dry-run mode
- [ ] Verify Redis connectivity on server
- [ ] Check .env has Redis configuration
- [ ] Review endpoints.yaml backup location

### After Deployment
- [ ] Restart gunicorn successfully
- [ ] Admin dashboard loads without errors
- [ ] Can create new endpoint with Redis checkbox
- [ ] Can edit existing endpoint and enable Redis
- [ ] Redis stats API returns data
- [ ] First request caches data (check metadata)
- [ ] Second request uses cache (faster response)
- [ ] Refresh button clears cache
- [ ] Refresh All button clears all caches
- [ ] Dashboard shows cache metadata

## Summary

**Implementation Status:** ✅ Complete (10/10 tasks)

**Key Features:**
- Optional 12-hour Redis cache per endpoint
- Full dataset caching with in-memory filtering
- Admin UI integration (checkbox, buttons, metadata display)
- Batch refresh operations
- Detailed cache metadata tracking
- Backward compatible (default: disabled)

**Files Created:** 3 (redis_cache_service.py, admin_redis.py, add_redis_cache_field.py)
**Files Modified:** 9 (settings, endpoint_config, data_fetcher, dataframe_tools, blueprints, UI templates)

**Next Steps:**
1. Deploy to server
2. Run migration script
3. Test with 1-2 endpoints
4. Monitor performance and memory usage
5. Gradually enable for expensive queries
