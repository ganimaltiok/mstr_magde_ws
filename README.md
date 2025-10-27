# MSTR Herald API v2.0

Flask REST API that provides unified access to MicroStrategy dossiers, MSSQL, and PostgreSQL data sources with intelligent nginx-based caching.

## Architecture Overview

### 6 Data Source Behaviors

Each endpoint can be configured with one of 6 behaviors:

| Behavior | Source | Caching | Cache Duration | Description |
|----------|--------|---------|----------------|-------------|
| `livesql` | MSSQL | None | N/A | Real-time MSSQL queries, no cache |
| `cachesql` | MSSQL | nginx | 10 minutes | Cached MSSQL data, auto-refresh |
| `livepg` | PostgreSQL | None | N/A | Real-time PostgreSQL queries, no cache |
| `cachepg` | PostgreSQL | nginx | 10 minutes | Cached PostgreSQL data, auto-refresh |
| `livemstr` | MicroStrategy | None | N/A | Live MSTR reports with full filter support |
| `cachemstr` | MicroStrategy | nginx | Until 7 AM Istanbul | Daily cached MSTR reports |

## Quick Start

### Prerequisites

- Python 3.9+
- MSSQL Server (for SQL behaviors)
- PostgreSQL (for PG behaviors)
- MicroStrategy Library Server (for MSTR behaviors)
- Nginx with cache module

### Installation

```bash
# Clone repository
cd /home/administrator/venus_v2

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Create cache directories
sudo mkdir -p /var/cache/nginx/shortcache
sudo mkdir -p /var/cache/nginx/dailycache
sudo chown -R administrator:administrator /var/cache/nginx/

# Run application
python src/app.py
```

### Nginx Setup

```bash
# Copy nginx config
sudo cp nginx/mstr_herald.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/mstr_herald.conf /etc/nginx/sites-enabled/

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

## API Endpoints

### v3 REST API (Backward Compatible)

#### GET `/api/v3/report/<report_name>/agency/<agency_code>`

Fetch report data filtered by agency.

| Query parameter | Default | Description |
|-----------------|---------|-------------|
| `info_type`     | `summary` | Must exist in the dossier's `viz_keys`. |
| `page`          | `1`     | 1-based page index. |
| `page_size`     | `50`    | Page length (integer > 0). |
| Other keys      | –       | Additional query parameters are forwarded as dossier filters. |

Response highlights: `data`, pagination metadata, `data_refresh_time`, and cache details (`is_cached`, `cache_hit`, `cache_policy`).

#### GET `/api/v3/report/<report_name>`

Fetch report data without agency filtering. Works only for dossiers that do **not** require `agency_name`. Supports the same query parameters as the agency endpoint.

#### GET `/api/v3/reports`

List configured dossiers with their cache policy, available filters, and whether agency filtering is required.

## Cache Helpers

### HTTP endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/refresh` | POST/GET | Refreshes all reports with `cache_policy = daily`. Returns a summary with refreshed metadata, skipped items, and errors. |
| `/refresh/<report_name>` | POST/GET | Refresh a single report. Response includes the refreshed metadata (`meta`) or error details. |
| `/refresh/meta/<report_name>` | GET | Retrieve cached metadata without triggering a refresh. Useful for diagnostics. |
| `/admin/log` | GET | View recent `/api/v3` requests with timestamps, status codes, and JSON payload previews. |
| `/admin/log` | GET | Live table of recent `/api/v3/...` requests with JSON preview popups. |

Returned metadata includes the `refreshed_at` timestamp and per `info_type` row/column counts plus cache keys.

### Admin console

Visit `/admin/edit` to:

- Edit dossier metadata (`cube_id`, `viz_keys`, `cache_policy`, etc.).
- Review the latest cache metadata per report (last refresh time, row counts).
- Trigger one-click cache refreshes per report or refresh all daily caches.
- Switch the data policy between MicroStrategy and PostgreSQL and edit the relevant fields inline.

### CLI / scheduled jobs

```
# Refresh every cache marked as daily (ideal for cron)
cd src
python -m cache_refresher.cache_refresher

# One-off run with logs
python src/cache_monitor.py
```

Both commands return the same metadata summary as the HTTP endpoints.

## Pagination & Filtering Tips

- `page` and `page_size` control server-side paging; the API returns `total_rows` and `total_pages` so you can build clients easily.
- Any extra query parameters (e.g. `?product=Auto&region=EMEA`) are passed through to the dossier filters by name.
- `info_type` values correspond to the keys in `viz_keys` for the dossier.

## Development

```
.
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── src
    ├── app.py                     # Entry point delegating to web.create_app
    ├── cache_monitor.py           # CLI helper for cron
    ├── cache_refresher/
    │   ├── cache_refresher.py     # Wrapper around full report refresh
    │   └── full_report_refresher.py  # Redis snapshot + metadata logic
    ├── config
    │   └── dossiers.yaml          # Dossier definitions
    ├── mstr_herald                # MicroStrategy connection helpers
    │   ├── connection.py
    │   ├── dossier_inspector.py
    │   ├── filter_utils.py
    │   └── reports.py
    ├── services                   # Shared business logic & adapters
    │   ├── cache_service.py
    │   ├── config_store.py
    │   ├── dataframe_tools.py
    │   ├── postgres_service.py
    │   ├── report_service.py
    │   └── settings.py
    └── web                        # Flask application & blueprints
        ├── app.py
        ├── errors.py
        ├── logbook.py
        └── blueprints/
            ├── __init__.py
            ├── cache_admin.py
            ├── config_admin.py
            ├── logs.py
            └── reports.py
```

## Environment Variables

Create a `.env` file at the project root with:

```
# Flask
PORT=8000

# MicroStrategy
MSTR_URL_API=http://your-mstr-server:8080/MicroStrategyLibrary/api
MSTR_BASE_URL=http://your-mstr-server:8080
MSTR_USERNAME=your_username
MSTR_PASSWORD=your_password
MSTR_PROJECT=your_project

# Postgres (optional)
PG_HOST=postgres
PG_PORT=5432
PG_DATABASE=your_database
PG_USER=your_user
PG_PASSWORD=your_password
```

## Deployment

- `docker-compose up -d` spins up the API alongside Redis.
- A sample `mstr_herald.service` unit is provided for Systemd-based deployments.

## License

[Your license information]
