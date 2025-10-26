from __future__ import annotations

import html
import json
from typing import List

from flask import Blueprint, Response, jsonify

from web import logbook

logs_bp = Blueprint("logs", __name__)


def _render_rows(entries: List[logbook.RequestLogEntry]) -> str:
    parts = []
    for entry in entries:
        json_payload = entry.response_json or ""
        json_attr = html.escape(json_payload, quote=True)
        has_json = bool(json_payload)
        json_cell = (
            f"<button class='json-btn' data-json=\"{json_attr}\">📄</button>"
            if has_json
            else ""
        )
        parts.append(
            "<tr>"
            f"<td>{html.escape(entry.timestamp.isoformat(timespec='seconds'))}</td>"
            f"<td>{html.escape(entry.method)}</td>"
            f"<td><span class='url'>{html.escape(entry.url)}</span></td>"
            f"<td>{entry.status}</td>"
            f"<td>{entry.duration_ms} ms</td>"
            f"<td>{html.escape(entry.remote_addr or '-')}</td>"
            f"<td>{entry.response_size}</td>"
            f"<td>{json_cell}</td>"
            "</tr>"
        )
    return "".join(parts) or "<tr><td colspan='8' class='empty'>No requests captured yet.</td></tr>"


@logs_bp.route("/admin/log", methods=["GET"])
def view_logs() -> Response:
    entries = logbook.list_entries()
    rows = _render_rows(entries)
    html_page = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <title>Request Log</title>
      <style>
        body {{
          font-family: "Segoe UI", Tahoma, sans-serif;
          background: #f6f8fa;
          margin: 0;
          padding: 24px;
        }}
        h1 {{
          margin: 0 0 16px 0;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          background: #fff;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        th, td {{
          padding: 12px 16px;
          border-bottom: 1px solid #e5e7eb;
          text-align: left;
        }}
        th {{
          background: #f0f3f9;
        }}
        .url {{
          font-family: "SFMono-Regular", Consolas, monospace;
          font-size: 0.9rem;
        }}
        .json-btn {{
          cursor: pointer;
          border: none;
          background: #2563eb;
          color: white;
          border-radius: 4px;
          padding: 4px 8px;
        }}
        .json-btn:hover {{
          background: #1d4ed8;
        }}
        .empty {{
          text-align: center;
          color: #6b7280;
        }}
        #json-modal {{
          position: fixed;
          inset: 0;
          background: rgba(15, 23, 42, 0.6);
          display: none;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }}
        #json-modal .dialog {{
          background: white;
          padding: 20px;
          border-radius: 8px;
          width: 70%;
          max-height: 80%;
          overflow: auto;
          box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        }}
        #json-modal pre {{
          background: #111827;
          color: #f9fafb;
          padding: 16px;
          border-radius: 6px;
          overflow: auto;
        }}
        #json-modal button {{
          margin-top: 12px;
          padding: 6px 12px;
          border: none;
          background: #6b7280;
          color: white;
          border-radius: 4px;
          cursor: pointer;
        }}
        #json-modal button:hover {{
          background: #4b5563;
        }}
      </style>
    </head>
    <body>
      <h1>Request Log</h1>
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Method</th>
            <th>URL</th>
            <th>Status</th>
            <th>Duration</th>
            <th>Remote</th>
            <th>Bytes</th>
            <th>Response</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
      <div id="json-modal">
        <div class="dialog">
          <pre id="json-content"></pre>
          <button id="close-modal">Close</button>
        </div>
      </div>
      <script>
        document.addEventListener('click', (event) => {{
          const button = event.target.closest('.json-btn');
          if (!button) return;
          const payload = button.dataset.json || "";
          try {{
            const parsed = JSON.parse(payload);
            document.getElementById('json-content').textContent = JSON.stringify(parsed, null, 2);
          }} catch (err) {{
            document.getElementById('json-content').textContent = payload || "(empty)";
          }}
          document.getElementById('json-modal').style.display = 'flex';
        }});
        document.getElementById('close-modal').addEventListener('click', () => {{
          document.getElementById('json-modal').style.display = 'none';
        }});
        document.getElementById('json-modal').addEventListener('click', (event) => {{
          if (event.target.id === 'json-modal') {{
            document.getElementById('json-modal').style.display = 'none';
          }}
        }});
      </script>
    </body>
    </html>
    """
    return Response(html_page, content_type="text/html; charset=utf-8")


@logs_bp.route("/admin/log.json", methods=["GET"])
def log_json():
    entries = [logbook.to_serialisable(entry) for entry in logbook.list_entries()]
    return jsonify({"entries": entries})


__all__ = ["logs_bp"]

