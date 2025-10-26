from __future__ import annotations

import html
from pathlib import Path

from flask import Blueprint, Response

from services.settings import get_settings

logs_bp = Blueprint("logs", __name__)


def _log_path() -> Path:
    return get_settings().refresh_log_path


@logs_bp.route("/admin/log")
def live_log() -> Response:
    log_path = _log_path()

    if not log_path.exists():
        return Response("<p>Log file not found.</p>", status=404, content_type="text/html")

    try:
        content = log_path.read_text(encoding="utf-8")
    except Exception as exc:
        return Response(f"<p>Error reading log file: {html.escape(str(exc))}</p>", status=500, content_type="text/html")

    escaped_content = html.escape(content)

    html_page = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <title>Refresh Log</title>
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: "Segoe UI", Tahoma, sans-serif;
                background-color: #ffffff;
                color: #333;
                height: 100vh;
                overflow: hidden;
            }}
            .container {{
                padding: 20px;
                height: 100vh;
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
            }}
            h2 {{
                margin-bottom: 10px;
                color: #444;
            }}
            #log-box {{
                flex: 1;
                overflow-y: auto;
                background-color: #f9f9f9;
                border: 1px solid #ccc;
                padding: 16px;
                border-radius: 8px;
                font-size: 14px;
                line-height: 1.6;
                white-space: pre-wrap;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Refresh Log (Updates every 2s)</h2>
            <div id="log-box">{escaped_content}</div>
        </div>

        <script>
            function fetchLog() {{
                fetch(window.location.href, {{ cache: "no-store" }})
                    .then(response => response.text())
                    .then(html => {{
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, "text/html");
                        const newLog = doc.getElementById("log-box").innerHTML;

                        const logBox = document.getElementById("log-box");
                        const atBottom = (logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight) < 50;

                        logBox.innerHTML = newLog;

                        if (atBottom) {{
                            logBox.scrollTop = logBox.scrollHeight;
                        }}
                    }})
                    .catch(console.error);
            }}

            setInterval(fetchLog, 2000);

            window.onload = () => {{
                const logBox = document.getElementById("log-box");
                logBox.scrollTop = logBox.scrollHeight;
            }};
        </script>
    </body>
    </html>
    """

    return Response(html_page, content_type="text/html")


__all__ = ["logs_bp"]

