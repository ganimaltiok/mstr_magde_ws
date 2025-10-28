# Copilot Instructions for MSTR Herald API v2

## Project Overview
Flask REST API that provides unified access to MicroStrategy dossiers, MSSQL, and PostgreSQL data sources with intelligent nginx-based caching.

**Core Architecture (v2):**
- `src/web/` → Flask app factory and blueprints (HTTP layer)
- `src/services/` → Business logic (data fetching, caching, config, health checks)
- `src/mstr_herald/` → MicroStrategy API client wrapper
- `src/config/endpoints.yaml` → Single source of truth for all endpoint definitions

## Critical Architecture Changes (v1 → v2)

### ❌ REMOVED (v1)
- Redis cache backend (`services/cache_service.py`)
- Dual data policy system (`data_policy: microstrategy|postgresql`)
- Cache refresher CLI tools (`cache_refresher/`)
- Old admin UI (`/admin/configure`, `/admin/edit`)
- In-memory post-fetch filtering
- `dossiers.yaml` configuration format

### ✅ NEW (v2)
- **Nginx proxy cache** (replaces Redis)
- **6 explicit behaviors** (livesql, cachesql, livepg, cachepg, livemstr, cachemstr)
- **Server-side filtering** (MSTR API filters + SQL WHERE clauses)
- **Database-level pagination** (for SQL/PostgreSQL)
- **Admin dashboard** (`/admin/dashboard`, `/admin/endpoints`, `/admin/cache`)
- **MSTR auto-discovery** ("Gather Info" button)
- **Access logging service** (request frequency tracking)
- `endpoints.yaml` configuration format

## Data Source Behaviors

Each endpoint configured in `endpoints.yaml` has one of 6 behaviors:

| Behavior | Source | Caching | Cache Duration | Server-Side Filtering |
|----------|--------|---------|----------------|----------------------|
| `livesql` | MSSQL | None | N/A | ✅ SQL WHERE clauses |
| `cachesql` | MSSQL | nginx | 10 minutes | ✅ SQL WHERE clauses |
| `livepg` | PostgreSQL | None | N/A | ✅ SQL WHERE clauses |
| `cachepg` | PostgreSQL | nginx | 10 minutes | ✅ SQL WHERE clauses |
| `livemstr` | MicroStrategy | None | N/A | ✅ MSTR filter API |
| `cachemstr` | MicroStrategy | nginx | Until 7 AM Istanbul | ✅ MSTR filter API |

**Key principle:** Filtering happens **before** data is fetched, not after.

## Service Layer Pattern

**Never call data sources directly from blueprints.** Always route through services:

```python
# ✅ Correct
from services.data_fetcher import get_data_fetcher
from services.endpoint_config import get_config_store

config = get_config_store().get(endpoint_name)
result = get_data_fetcher().fetch(config, query_params, info_type, page, per_page)

# ❌ Wrong (v1 pattern)
from services.report_service import get_report_service  # This file no longer exists
```

**Service hierarchy:**
- `data_fetcher.py` → Orchestrates based on behavior
- `sql_fetcher.py` → MSSQL queries with server-side filtering
- `pg_fetcher.py` → PostgreSQL queries with server-side filtering
- `mstr_fetcher.py` → MicroStrategy API with full filter support
- `cache_manager.py` → Nginx cache purge operations
- `endpoint_config.py` → YAML config CRUD

## Flask Blueprint Registration

Entry: `src/app.py` → `web/__init__.py::create_app()` → `web/blueprints/__init__.py`

```python
v3_bp              → /api/v3/*              # Main REST API (unchanged)
admin_dashboard_bp → /admin/dashboard       # Health & endpoint listing
admin_endpoints_bp → /admin/endpoints       # Endpoint CRUD
admin_cache_bp     → /admin/cache           # Cache management
admin_mstr_bp      → /api/admin/mstr/*      # Dossier discovery
health_bp          → /ping, /health         # Health checks
```

## Developer Workflows

### Running the API

```bash
# Local development (no Redis required)
cd /Users/ganimaltiok/Documents/GitHub/mstr_magde_ws/src
python app.py  # Dev server on PORT 9101

# Production (Gunicorn)
cd /home/administrator/venus/src
/home/administrator/venv/bin/gunicorn \
  --workers 3 \
  --bind 127.0.0.1:9101 \
  --timeout=300 \
  app:app
```

**Port change:** v2 uses **9101** (was 8001 in v1) to run in parallel during migration.

### Cache Management

**v1 (deprecated):**
```bash
# Old Redis-based refresh
python -m cache_refresher.cache_refresher  # ❌ Removed
POST /refresh/<report_name>                # ❌ Removed
```

**v2 (current):**
```bash
# Admin UI - navigate to /admin/cache
# Click "Clear All Cache" or select endpoint to purge

# HTTP API
curl -X POST http://localhost:8000/admin/cache/purge \
  -H "Content-Type: application/json" \
  -d '{"target": "all"}'

curl -X POST http://localhost:8000/admin/cache/purge \
  -H "Content-Type: application/json" \
  -d '{"target": "endpoint", "endpoint_name": "sales_summary"}'
```

**Cache refresh is automatic:**
- `cachesql`, `cachepg`: First request after 10 min expiry rebuilds cache
- `cachemstr`: First request after 7 AM Istanbul rebuilds cache

### Adding a New Endpoint

**v2 Admin UI (recommended):**
1. Navigate to `/admin/endpoints/create`
2. Fill endpoint name (URL slug)
3. Select behavior (livesql, cachesql, livepg, cachepg, livemstr, cachemstr)
4. **For SQL/PG:** Enter schema and table name
5. **For MSTR:** Enter dossier ID → Click "Gather Info" → Auto-populate viz keys and filters
6. Save

**Manual YAML edit:**
```yaml
# src/config/endpoints.yaml
endpoints:
  new_report:
    behavior: cachemstr
    description: "My new report"
    pagination:
      per_page: 100
    mstr:
      dossier_id: "ABC123"
      viz_keys:
        summary: "K52"
        detail: "W8D67A24C..."
      filter_mappings:
        agency_code: "W7B89C12D..."
        date_start: "W6A45F23E..."
```

Changes are **immediate** (no restart needed).

## Configuration Management

### Single Admin UI
`/admin/dashboard` → Unified interface with:
- Health status panel
- Endpoint table with access stats
- Cache statistics
- Actions: Edit, Delete, Clear Cache per endpoint

**Old admin pages removed:**
- `/admin/configure` ❌
- `/admin/edit` ❌
- `/admin/log` ❌ (replaced by access logger service)

### Endpoint Configuration Structure

```yaml
endpoints:
  # MSTR example
  sales_summary:
    behavior: cachemstr
    description: "Daily sales summary"
    pagination:
      per_page: 100
    mstr:
      dossier_id: "ABC123"
      cube_id: "XYZ789"  # Optional
      viz_keys:
        summary: "K52"
        detail: "W8D67A24C..."
      filter_mappings:
        agency_code: "W7B89C12D..."
        date_start: "W6A45F23E..."
  
  # SQL example
  inventory:
    behavior: livesql
    description: "Real-time inventory"
    pagination:
      per_page: 50
    mssql:
      schema: "dbo"
      table: "inventory"
  
  # PostgreSQL example
  customers:
    behavior: cachepg
    description: "Customer master"
    pagination:
      per_page: 200
    postgresql:
      schema: "public"
      table: "customers"
```

## Key Conventions

### Agency Filtering (v2)

**No longer special-cased.** Agency filtering is just another server-side filter: