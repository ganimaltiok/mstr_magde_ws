# MSTR Herald API

MicroStrategy Herald is a Flask-based REST service that turns MicroStrategy dossiers into clean, paginated JSON responses, optionally backed by Redis caching. The project now focuses on the v3 API and provides tooling to manage cache refreshes from the browser, CLI, or automation jobs.

## Features

- Modern `/api/v3` endpoints with consistent JSON payloads
- Flexible filtering, pagination, and per-agency data slicing
- Redis-backed daily cache snapshots with rich metadata
- Admin console for dossier configuration plus one-click cache refresh
- Helper HTTP endpoints and CLI scripts for cron-friendly cache refreshes
- Docker and Systemd deployment recipes

## Quick Start

### Using Docker

```bash
# Clone the repository
git clone <repository-url>
cd mstr_magde_ws

# Configure environment variables
cp .env.example .env
# Edit .env with your MicroStrategy credentials

# Start with Docker Compose
docker-compose up -d
```

### Manual Installation

```bash
# Clone the repository
git clone <repository-url>
cd mstr_magde_ws

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your MicroStrategy credentials

# Run the application
cd src
python app.py
```

## Configuration

All dossier definitions live in `src/config/dossiers.yaml`. Key fields:

- `cube_id`, `dossier_id`: MicroStrategy identifiers.
- `viz_keys`: Maps logical info types (e.g. `summary`, `detail`) to dossier visualization keys. Only non-null entries are cached.
- `filters`: Dictionary of filter keys. Specify `agency_name` when the dossier requires an agency selection.
- `cache_policy`: Either `none` (always live) or `daily` (cacheable).

The admin UI at `/admin/edit` lets you edit these values, view the latest cache metadata, and trigger manual refreshes.

## API (v3)

### GET `/api/v3/report/<report_name>/agency/<agency_code>`

Fetch report data filtered by agency.

| Query parameter | Default | Description |
|-----------------|---------|-------------|
| `info_type`     | `summary` | Must exist in the dossier's `viz_keys`. |
| `page`          | `1`     | 1-based page index. |
| `page_size`     | `50`    | Page length (integer > 0). |
| Other keys      | –       | Additional query parameters are forwarded as dossier filters. |

Response highlights: `data`, pagination metadata, `data_refresh_time`, and cache details (`is_cached`, `cache_hit`, `cache_policy`).

### GET `/api/v3/report/<report_name>`

Fetch report data without agency filtering. Works only for dossiers that do **not** require `agency_name`. Supports the same query parameters as the agency endpoint.

### GET `/api/v3/reports`

List configured dossiers with their cache policy, available filters, and whether agency filtering is required.

## Cache Helpers

### HTTP endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/refresh` | POST/GET | Refreshes all reports with `cache_policy = daily`. Returns a summary with refreshed metadata, skipped items, and errors. |
| `/refresh/<report_name>` | POST/GET | Refresh a single report. Response includes the refreshed metadata (`meta`) or error details. |
| `/refresh/meta/<report_name>` | GET | Retrieve cached metadata without triggering a refresh. Useful for diagnostics. |

Returned metadata includes the `refreshed_at` timestamp and per `info_type` row/column counts plus cache keys.

### Admin console

Visit `/admin/edit` to:

- Edit dossier metadata (`cube_id`, `viz_keys`, `cache_policy`, etc.).
- Review the latest cache metadata per report (last refresh time, row counts).
- Trigger one-click cache refreshes per report or refresh all daily caches.

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
    ├── app.py                     # Flask app factory & blueprint registration
    ├── api_v3.py                  # Primary REST endpoints
    ├── cache_routes.py            # /refresh helpers
    ├── cache_monitor.py           # CLI helper for cron
    ├── cache_refresher/
    │   ├── cache_refresher.py     # Wrapper around full report refresh
    │   └── full_report_refresher.py  # Redis snapshot + metadata logic
    ├── configurator.py            # Admin UI for dossiers + cache actions
    ├── config
    │   └── dossiers.yaml          # Dossier definitions
    └── mstr_herald                # MicroStrategy connection + utility code
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
```

## Deployment

- `docker-compose up -d` spins up the API alongside Redis.
- A sample `mstr_herald.service` unit is provided for Systemd-based deployments.

## License

[Your license information]
