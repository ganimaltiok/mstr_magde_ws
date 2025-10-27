from __future__ import annotations

import html
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List

from services.cache_service import get_redis_client
from services.config_store import get_config_path
from services.settings import get_settings
from services.postgres_service import pg_connection
from mstr_herald.connection import create_connection


@dataclass
class HealthCheck:
    name: str
    status: str
    detail: str
    duration_ms: int


def _safe_duration(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _check(name: str, fn: Callable[[], str]) -> HealthCheck:
    start = time.perf_counter()
    try:
        detail = fn() or "OK"
        status = "ok"
    except Exception as exc:
        detail = str(exc)
        status = "error"
    return HealthCheck(name=name, status=status, detail=detail, duration_ms=_safe_duration(start))


def _check_microstrategy() -> str:
    conn = create_connection()
    try:
        project = getattr(conn, "project_name", None) or "Unknown project"
        return f"Connected to {project}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _check_redis() -> str:
    client = get_redis_client()
    response = client.ping()
    return "PING OK" if response else "PING failed"


def _check_config_file() -> str:
    path = get_config_path()
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    return f"{path} ({path.stat().st_size} bytes)"


def _check_postgres() -> str:
    with pg_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    return "Connected"


def collect_health_checks() -> List[HealthCheck]:
    settings = get_settings()
    checks: Iterable[tuple[str, Callable[[], str]]] = (
        ("MicroStrategy connection", _check_microstrategy),
        ("Redis connection", _check_redis),
        ("Dossier config file", _check_config_file),
    )
    results = [_check(name, fn) for name, fn in checks]
    if settings.pg_database:
        results.append(_check("PostgreSQL connection", _check_postgres))
    return results


def render_health_page() -> str:
    settings = get_settings()
    checks = collect_health_checks()
    rows = []
    for check in checks:
        status_color = "#28a745" if check.status == "ok" else "#dc3545"
        rows.append(
            "<tr>"
            f"<td>{html.escape(check.name)}</td>"
            f"<td style='color:{status_color}; font-weight:600'>{html.escape(check.status.upper())}</td>"
            f"<td>{html.escape(check.detail)}</td>"
            f"<td style='text-align:right'>{check.duration_ms} ms</td>"
            "</tr>"
        )

    html_page = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <title>Service Health</title>
      <style>
        body {{
          font-family: "Segoe UI", Tahoma, sans-serif;
          background: #f6f8fa;
          margin: 0;
          padding: 24px;
        }}
        h1 {{
          margin-top: 0;
        }}
        table {{
          border-collapse: collapse;
          width: 100%;
          background: white;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        th, td {{
          padding: 12px 16px;
          border-bottom: 1px solid #e5e7eb;
        }}
        th {{
          text-align: left;
          background: #f0f3f9;
          font-weight: 600;
        }}
        tbody tr:last-child td {{
          border-bottom: none;
        }}
        .meta {{
          margin-top: 16px;
          color: #4b5563;
          font-size: 0.9rem;
        }}
      </style>
    </head>
    <body>
      <h1>Service Health</h1>
      <table>
        <thead>
          <tr>
            <th>Check</th>
            <th>Status</th>
            <th>Details</th>
            <th>Duration</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
      <div class="meta">
        <div><strong>App root:</strong> {html.escape(str(settings.base_dir))}</div>
        <div><strong>Config path:</strong> {html.escape(str(get_config_path()))}</div>
        <div><strong>Redis:</strong> {html.escape(f"{settings.redis_host}:{settings.redis_port}/{settings.redis_db}")}</div>
      </div>
    </body>
    </html>
    """
    return html_page


__all__ = ["collect_health_checks", "render_health_page"]
