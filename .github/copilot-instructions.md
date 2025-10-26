# Copilot Instructions for MSTR Herald API

## Project Overview
- **Purpose:** Flask REST API for serving MicroStrategy dossier data as paginated JSON, with Redis caching and admin tooling.
- **Main API:** `/api/v3` endpoints (see `src/api_v3.py`) for report data, filtering, and pagination.
- **Cache System:** Daily Redis snapshots, metadata, and refresh logic (see `src/cache_refresher/`, `src/cache_routes.py`).
- **Admin UI:** `/admin/edit` for dossier config and cache management (see `src/configurator.py`).

## Key Files & Structure
- `src/app.py`: Flask app factory, blueprint registration.
- `src/api_v3.py`: Main REST endpoints.
- `src/cache_routes.py`: HTTP cache refresh endpoints.
- `src/cache_refresher/`: CLI and logic for cache refreshes.
- `src/configurator.py`: Admin UI and cache actions.
- `src/config/dossiers.yaml`: Dossier definitions (IDs, viz_keys, filters, cache_policy).
- `src/mstr_herald/`: MicroStrategy connection and utility code.

## Developer Workflows
- **Run API:**
  - `python src/app.py` (manual)
  - `docker-compose up -d` (with Redis)
- **Refresh Caches:**
  - HTTP: `POST /refresh` or `POST /refresh/<report_name>`
  - CLI: `python -m cache_refresher.cache_refresher`
- **Edit Dossiers:**
  - Use `/admin/edit` or modify `src/config/dossiers.yaml` directly.
- **Scheduled Jobs:**
  - Use CLI cache refresher for cron: `python -m cache_refresher.cache_refresher`

## Patterns & Conventions
- **API v3** is the canonical interface; older versions are legacy.
- **Dossier config**: All report logic is driven by `src/config/dossiers.yaml`.
- **Agency filtering**: Endpoints use `/agency/<agency_code>` if required by dossier config.
- **Flexible filters**: Extra query params are passed to dossier filters.
- **Cache policy**: Only dossiers with `cache_policy: daily` are cached; others are always live.
- **Metadata**: All cache refreshes return detailed metadata (row counts, timestamps, cache keys).

## Integration Points
- **MicroStrategy**: Credentials and API URLs set via `.env`.
- **Redis**: Used for caching; required for full functionality.
- **Docker/Systemd**: Supported for deployment; see `docker-compose.yml` and sample unit files.

## Examples
- To add a new report: update `src/config/dossiers.yaml` and refresh cache.
- To debug cache: use `/refresh/meta/<report_name>` or CLI tools.
- To extend API: add endpoints in `src/api_v3.py` and update config as needed.

## Tips for AI Agents
- Always reference `src/config/dossiers.yaml` for report logic.
- Prefer API v3 endpoints and patterns.
- Use CLI tools for cache refresh in automation.
- Return metadata in all cache-related responses.
- Keep Docker and Redis integration in mind for full-stack changes.

---
If any section is unclear or missing, please provide feedback for further refinement.