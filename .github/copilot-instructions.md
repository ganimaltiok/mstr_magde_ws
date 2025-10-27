# Copilot Instructions for MSTR Herald API

## Project Overview
Flask REST API that transforms MicroStrategy dossiers and PostgreSQL tables into paginated JSON responses with intelligent Redis caching.

**Core Architecture:**
- `src/web/` → Flask app factory and blueprints (separation of HTTP layer)
- `src/services/` → Business logic (report fetching, caching, config, postgres)
- `src/mstr_herald/` → MicroStrategy API client wrapper
- `src/cache_refresher/` → CLI tools for scheduled cache updates
- `src/config/dossiers.yaml` → Single source of truth for all report definitions

## Critical Architecture Patterns

### Dual Data Sources
Reports can fetch from **two backends** controlled by `data_policy` in `dossiers.yaml`:
- `microstrategy` (default): Fetch from MSTR dossiers via `mstr_herald/reports.py`
- `postgresql`: Direct table queries via `services/postgres_service.py`

When `data_policy: postgresql`, the system:
- Ignores `cube_id`, `dossier_id`, `viz_keys`, and `filters`
- Requires `postgres_table: "schema.table"` format
- Only caches under `info_type: summary` key
- Still supports full pagination and agency filtering in-memory

### Service Layer Pattern
**Never call MSTR/Postgres directly from blueprints.** Always route through services:
- `services/report_service.py` → Orchestrates data fetching, caching, pagination
- `services/cache_service.py` → Redis operations (pickled DataFrames + JSON metadata)
- `services/config_store.py` → YAML config CRUD with validation

### Flask Blueprint Registration
Entry: `src/app.py` → delegates to `web/create_app()` → `web/blueprints/__init__.py`
```python
reports_bp  → /api/v3/*        # Main REST API
cache_bp    → /refresh*         # Cache management
config_bp   → /admin/*          # Dossier config UI
logs_bp     → /admin/log        # Request logging viewer
```

### Request Logging Architecture
`web/logbook.py` maintains in-memory circular buffer of recent `/api/v3/*` requests.
Captured via `@app.after_request` in `web/app.py`. Logs include:
- Full JSON payload (truncated at 20KB)
- Response time in milliseconds
- Status code, URL, method

Access at `/admin/log` for debugging.

## Developer Workflows

### Running the API
```bash
# Local development (requires Redis running)
cd /path/to/venus/src
python app.py  # Dev server on PORT (default 5000)

# Production (Gunicorn) - from app root
cd /home/administrator/venus/src
/home/administrator/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8001 --timeout=300 app:app
# With auto-reload for development:
/home/administrator/venv/bin/gunicorn --workers 3 --reload --bind 127.0.0.1:8001 --timeout=300 app:app
```

### Cache Refresh Methods
1. **HTTP (browser/curl):** `POST /refresh` or `POST /refresh/<report_name>`
2. **CLI (cron jobs):** `cd src && python -m cache_refresher.cache_refresher`
3. **Admin UI:** `/admin/edit` → "Refresh Cache" button per report

All methods return identical metadata structure with `refreshed`, `skipped`, `errors` keys.

### Adding a New Report
1. **If MicroStrategy source:**
   - Get dossier ID → Use `/admin/configure` "Discover Keys" feature
   - Add to `dossiers.yaml` with `cube_id`, `dossier_id`, `viz_keys`, `filters`
2. **If PostgreSQL source:**
   - Set `data_policy: postgresql` and `postgres_table: "schema.table"`
   - Leave `viz_keys` and `filters` empty
3. Refresh cache: `POST /refresh/<report_name>` or use CLI

### Configuration Management
**Two admin UIs:**
- `/admin/edit` → Modern tabular editor with inline cache refresh
- `/admin/configure` → Legacy form-based editor with dossier discovery

Both persist to same `src/config/dossiers.yaml`. Changes are immediate (no restart needed).

## Key Conventions

### Agency Filtering
- If `filters.agency_name` exists in config → **must** use `/api/v3/report/<name>/agency/<code>`
- Without agency filter → use `/api/v3/report/<name>`
- Agency filtering happens **after** cache retrieval (in-memory DataFrame filtering)

### Cache Keys & Metadata
Format: `{report_name}:{scope}:{info_type}` (scope always "all" currently)
- DataFrames stored as pickled bytes
- Metadata stored as `{report_name}:meta` JSON with structure:
  ```json
  {
    "refreshed_at": "2025-10-27T14:30:00Z",
    "info_types": {
      "summary": {"rows": 1234, "columns": [...], "cache_key": "..."},
      "detail": {"rows": 5678, "columns": [...], "cache_key": "..."}
    },
    "partial": false  // true if some info_types failed
  }
  ```

### Info Types
MicroStrategy reports can have multiple visualizations:
- `summary` → Grid/summary view (required)
- `detail` → Detailed drill-down (optional)

Map in `viz_keys` to MSTR visualization IDs (format: `K52`, `W8D67A24C582045449A9EDFF9CF1702EF`)

### DataFrame Normalization Pipeline
Every DataFrame (MSTR or Postgres) flows through `services/dataframe_tools.py`:
1. `normalise_columns()` → Snake_case column names
2. `normalise_agency_code_columns()` → Standardize agency identifiers
3. `extract_cube_time()` → Extract `dataRefreshTime` column if present
4. `filter_by_agency()` → In-memory filtering by agency_code
5. `apply_filters()` → Additional query param filters
6. Pagination → `_paginate()` in `report_service.py`

### Settings & Environment
All config via `.env` at project root. Access through singleton: `services/settings.py::get_settings()`

Required for MicroStrategy:
```
MSTR_URL_API=http://server:8080/MicroStrategyLibrary/api
MSTR_USERNAME=...
MSTR_PASSWORD=...
MSTR_PROJECT=...
```

Optional for PostgreSQL:
```
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=...
PG_USER=...
PG_PASSWORD=...
```

### Error Handling Pattern
Blueprints return structured errors:
```python
try:
    payload = get_report_payload(...)
except ReportNotFoundError:
    return jsonify({"error": "Report '...' not found"}), 404
except UnsupportedInfoTypeError as exc:
    return jsonify({"error": str(exc)}), 400
```
Never let unhandled exceptions escape (defensive `except Exception` catches for logging).

## Testing & Debugging

### Check MicroStrategy Connectivity
Connection validated on startup (`web/app.py::_eager_connection_check`).
Check logs for: `"Successfully validated MicroStrategy connectivity."`

### Inspect Cache State
```bash
# Via HTTP
curl http://localhost:8000/refresh/meta/<report_name>

# Via Redis CLI (Redis runs in Docker, exposed on 6379)
redis-cli -h 127.0.0.1 -p 6379
> KEYS *
> GET "p1_anlik_uretim:meta"
```

### View Recent API Requests
Navigate to `/admin/log` for live table with:
- JSON payload previews (click to expand)
- Response times and status codes
- Auto-refresh capability

## Deployment (Nginx + Gunicorn + Supervisor)

- WSGI app: `app:app` (runs from `src/` directory; app created at import via `create_app()`)
- App location: `/home/administrator/venus`
- Virtualenv: `/home/administrator/venv`
- Gunicorn runs **directly** (not via Supervisor) on `127.0.0.1:8001`
- Nginx proxies external port `8000` → Gunicorn `127.0.0.1:8001`
- Redis runs in Docker container, exposed on `0.0.0.0:6379`

### Current Production Command
```bash
cd /home/administrator/venus/src
/home/administrator/venv/bin/gunicorn \
  --workers 3 \
  --reload \
  --bind 127.0.0.1:8001 \
  --timeout=300 \
  app:app
```

**Key settings:**
- `--workers 3` → Handles concurrent requests
- `--timeout=300` → 5-minute timeout for long-running MSTR queries
- `--reload` → Auto-restart on code changes (dev mode; remove in production)

### Nginx Configuration
Nginx listens on port `8000` and proxies to Gunicorn at `127.0.0.1:8001`.

Example snippet (actual config may vary):
```nginx
upstream gunicorn_backend {
    server 127.0.0.1:8001;
}

server {
    listen 8000;
    server_name mstrws.magdeburger.local;

    location / {
        proxy_pass http://gunicorn_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        proxy_connect_timeout 5s;
    }
}
```

### Environment Variables
Set in `.env` file at `/home/administrator/venus/.env`:
```
MSTR_URL_API=http://<mstr-host>:8080/MicroStrategyLibrary/api
MSTR_USERNAME=...
MSTR_PASSWORD=...
MSTR_PROJECT=...
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
PORT=5000
SENTRY_DSN=...
SENTRY_ENVIRONMENT=prod
```

### Service Management
Gunicorn currently runs as a foreground process (visible via `ps aux | grep gunicorn`).

To manage the application:
```bash
# Find Gunicorn processes
ps aux | grep gunicorn

# Kill all Gunicorn workers
pkill -f "gunicorn.*app:app"

# Restart (from app directory)
cd /home/administrator/venus/src
/home/administrator/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8001 --timeout=300 app:app &

# Check Nginx status
sudo systemctl status nginx

# Reload Nginx config
sudo nginx -t && sudo systemctl reload nginx
```

### Health Checks
- `/ping` → Returns `{"status": "ok"}`
- `/health` → HTML status page
- External access: `http://mstrws.magdeburger.local:8000/ping`

**Note:** Consider moving Gunicorn to systemd or Supervisor for production to ensure auto-restart on crashes/reboots.

Legacy Docker compose is no longer used for the main app; Redis still runs in Docker.## Common Pitfalls

❌ **Don't** modify `dossiers.yaml` while containers are running without refreshing cache
✅ **Do** trigger refresh after config changes

❌ **Don't** mix MSTR and Postgres fields (e.g., `postgres_table` + `viz_keys`)
✅ **Do** set `data_policy` explicitly and only populate relevant fields

❌ **Don't** forget Redis must be running for cached reports
✅ **Do** check Redis connectivity if `cache_hit: false` unexpectedly

❌ **Don't** use `/agency/<code>` endpoint for non-agency reports
✅ **Do** check `filters.agency_name` in config first

## Extension Points

### Adding New Blueprints
Register in `web/blueprints/__init__.py::register_blueprints()`

### Custom Data Transformations
Add to pipeline in `services/dataframe_tools.py` before pagination

### Alternative Cache Backends
Replace `services/cache_service.py` Redis client (currently uses pickle serialization)