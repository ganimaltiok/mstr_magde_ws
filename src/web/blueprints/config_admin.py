from __future__ import annotations

import html
from typing import Any, Dict, Optional
import json
import logging

import yaml
from flask import Blueprint, Response, jsonify, request

from mstr_herald.connection import create_connection
from mstr_herald.dossier_inspector import discover_dossier
from services.config_store import (
    load_config,
    save_config,
    resolve_cache_policy,
    CACHE_POLICY_NONE,
    CACHE_POLICY_DAILY,
)
from cache_refresher.full_report_refresher import get_report_cache_meta


logger = logging.getLogger(__name__)


def _format_cache_status(meta: Optional[Dict[str, Any]]) -> str:
    if not meta:
        return "Never cached"

    refreshed_at = meta.get("refreshed_at") or "Unknown"
    info_types = meta.get("info_types") or {}
    parts = []
    for info_type, details in info_types.items():
        rows = details.get("rows")
        cols = details.get("columns") or []
        row_txt = f"{rows} rows" if rows is not None else "rows: ?"
        col_txt = f"{len(cols)} cols" if cols else ""
        fragment = f"{info_type}: {row_txt}"
        if col_txt:
            fragment = f"{fragment} / {col_txt}"
        parts.append(fragment)

    info_summary = "; ".join(parts) if parts else "no datasets cached"
    suffix = " (partial)" if meta.get("partial") else ""
    return f"{refreshed_at} - {info_summary}{suffix}"

config_bp = Blueprint("configure", __name__)


def _generate_edit_rows(config: Dict[str, Any]) -> str:
    rows: list[str] = []
    for report_name, cfg in (config or {}).items():
        cfg = cfg or {}
        filters = cfg.get("filters") or {}
        viz_keys = cfg.get("viz_keys") or {}

        def esc(value: Any) -> str:
            return html.escape("" if value is None else str(value), quote=True)

        current_policy = resolve_cache_policy(cfg)
        options = []
        for value, label in (
            (CACHE_POLICY_NONE, "No Cache"),
            (CACHE_POLICY_DAILY, "Daily (refresh via job)"),
        ):
            selected = "selected" if current_policy == value else ""
            options.append(f"<option value='{value}' {selected}>{html.escape(label)}</option>")

        meta_error = ""
        try:
            meta = get_report_cache_meta(report_name)
        except Exception as exc:  # pragma: no cover - safety net for Redis outages
            logger.warning("Failed to load cache metadata for %s: %s", report_name, exc)
            meta = None
            meta_error = "Unavailable"

        status_text = "Cache metadata unavailable" if meta_error else _format_cache_status(meta)
        meta_json = html.escape(json.dumps(meta) if meta is not None else "", quote=True)

        rows.append(
            "<tr>"
            f"<td><input value='{esc(report_name)}'></td>"
            f"<td><input value='{esc(cfg.get('cube_id'))}'></td>"
            f"<td><input value='{esc(cfg.get('dossier_id'))}'></td>"
            f"<td><select>{''.join(options)}</select></td>"
            f"<td><input value='{esc(filters.get('agency_name'))}'></td>"
            f"<td><input value='{esc(viz_keys.get('summary'))}'></td>"
            f"<td><input value='{esc(viz_keys.get('detail'))}'></td>"
            f"<td>"
            f"  <div class='cache-status' data-report='{esc(report_name)}' data-meta='{meta_json}' data-error='{esc(meta_error)}'>"
            f"    <div class='status-text'>{html.escape(status_text)}</div>"
            f"    <button type='button' class='refresh-btn'>Refresh Cache</button>"
            f"  </div>"
            f"</td>"
            "</tr>"
        )
    return "\n".join(rows)


@config_bp.route("/admin/edit", methods=["GET"])
def edit_dossiers() -> Response:
    config = load_config() or {}
    table_rows = _generate_edit_rows(config)

    html_page = f"""
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Edit Dossiers</title>
      <style>
        body {{ font-family: sans-serif; padding: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ccc; padding: 8px; vertical-align: top; }}
        th {{ background: #f0f0f0; }}
        input, select {{ width: 100%; box-sizing: border-box; }}
        button {{ margin-top: 10px; padding: 6px 12px; }}
        .cache-status button {{ margin-top: 4px; }}
        #msg {{ margin-top:10px; color: green; }}
        .cache-status {{ display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }}
        .cache-status .status-text {{ font-size: 0.85em; color: #555; }}
        .actions {{ margin-top: 12px; display: flex; gap: 10px; }}
      </style>
      <script>
        const CACHE_POLICY_NONE = "{CACHE_POLICY_NONE}";
        const CACHE_POLICY_DAILY = "{CACHE_POLICY_DAILY}";

        function showMessage(text, color) {{
          const msg = document.getElementById('msg');
          if (!msg) return;
          if (color) {{
            msg.style.color = color;
          }}
          msg.textContent = text;
        }}

        function formatMeta(meta) {{
          if (!meta) {{
            return "Never cached";
          }}
          const timestamp = meta.refreshed_at || "Unknown";
          const partial = meta.partial ? " (partial)" : "";
          const info = meta.info_types || {{}};
          const segments = [];
          for (const key in info) {{
            if (!Object.prototype.hasOwnProperty.call(info, key)) continue;
            const details = info[key] || {{}};
            const rows = details.rows !== undefined && details.rows !== null ? details.rows : "?";
            const columns = Array.isArray(details.columns) ? details.columns.length : 0;
            const columnText = columns ? ` / ${{columns}} cols` : "";
            segments.push(`${{key}}: ${{rows}} rows${{columnText}}`);
          }}
          const infoText = segments.length ? segments.join("; ") : "no datasets cached";
          return `${{timestamp}} - ${{infoText}}${{partial}}`;
        }}

        function updateStatusBox(statusBox, meta, reportName) {{
          if (!statusBox) return;
          if (reportName) {{
            statusBox.dataset.report = reportName;
          }}
          if (meta) {{
            try {{
              statusBox.dataset.meta = JSON.stringify(meta);
            }} catch (err) {{
              statusBox.dataset.meta = "";
            }}
            statusBox.dataset.error = "";
          }} else {{
            statusBox.dataset.meta = "";
          }}
          const statusTextEl = statusBox.querySelector('.status-text');
          if (statusTextEl) {{
            if (statusBox.dataset.error) {{
              statusTextEl.textContent = "Cache metadata unavailable";
            }} else {{
              statusTextEl.textContent = formatMeta(meta);
            }}
          }}
        }}

        async function refreshReport(reportName, button) {{
          const statusBox = button.closest('.cache-status');
          const statusTextEl = statusBox ? statusBox.querySelector('.status-text') : null;
          const originalLabel = button.textContent;
          button.disabled = true;
          button.textContent = "Refreshing...";
          if (statusTextEl) {{
            statusTextEl.textContent = `Refreshing ${{reportName}}...`;
          }}
          try {{
            const response = await fetch(`/refresh/${{encodeURIComponent(reportName)}}`, {{
              method: 'POST'
            }});
            const json = await response.json();
            if (response.ok && json.meta) {{
              updateStatusBox(statusBox, json.meta, reportName);
              showMessage(`Refreshed cache for ${{reportName}}.`, "green");
            }} else if (json.status === "skipped") {{
              const reason = json.reason || `Refresh skipped for ${{reportName}}.`;
              showMessage(reason, "orange");
              if (statusTextEl) statusTextEl.textContent = reason;
            }} else if (json.status === "error") {{
              const details = Array.isArray(json.errors) ? json.errors.join("; ") : (json.errors || "Refresh failed.");
              showMessage(details, "red");
              if (statusTextEl) statusTextEl.textContent = details;
            }} else {{
              const fallback = json.error || json.reason || "Refresh failed.";
              showMessage(fallback, "red");
              if (statusTextEl) statusTextEl.textContent = fallback;
            }}
          }} catch (err) {{
            showMessage(`Error refreshing ${{reportName}}: ${{err}}`, "red");
          }} finally {{
            button.disabled = false;
            button.textContent = originalLabel;
          }}
        }}

        function cssEscape(value) {{
          if (window.CSS && typeof window.CSS.escape === "function") {{
            return window.CSS.escape(value);
          }}
          return String(value).replace(/([ #.;?+*~':"!^$\\[\\]()=>|/@])/g, '\\\\$1');
        }}

        async function refreshAll(button) {{
          const originalLabel = button.textContent;
          button.disabled = true;
          button.textContent = "Refreshing...";
          showMessage("Refreshing all daily caches...", "black");
          try {{
            const response = await fetch('/refresh', {{ method: 'POST' }});
            const json = await response.json();
            if (response.ok) {{
              const refreshed = json.refreshed || {{}};
              Object.keys(refreshed).forEach(name => {{
                const selector = `.cache-status[data-report=\"${{cssEscape(name)}}\"]`;
                const statusBox = document.querySelector(selector);
                if (statusBox) {{
                  updateStatusBox(statusBox, refreshed[name], name);
                }}
              }});

              const refreshedCount = Object.keys(refreshed).length;
              const errorKeys = json.errors ? Object.keys(json.errors) : [];
              if (errorKeys.length) {{
                showMessage(`Refreshed ${{refreshedCount}} caches. Errors: ${{errorKeys.join(", ")}}`, "orange");
              }} else {{
                showMessage(`Refreshed ${{refreshedCount}} caches.`, "green");
              }}
            }} else {{
              const fallback = json.error || json.reason || "Refresh failed.";
              showMessage(fallback, "red");
            }}
          }} catch (err) {{
            showMessage(`Error refreshing caches: ${{err}}`, "red");
          }} finally {{
            button.disabled = false;
            button.textContent = originalLabel;
          }}
        }}

        function saveTable() {{
          const rows = document.querySelectorAll('tbody tr');
          const payload = {{}};
          rows.forEach(row => {{
            const cells = row.querySelectorAll('input,select');
            const reportName = cells[0].value.trim();
            if (!reportName) return;
            payload[reportName] = {{
              cube_id: cells[1].value.trim() || null,
              dossier_id: cells[2].value.trim() || null,
              cache_policy: cells[3].value || CACHE_POLICY_NONE,
              filters: {{ agency_name: cells[4].value.trim() || null }},
              viz_keys: {{
                summary: cells[5].value.trim() || null,
                detail: cells[6].value.trim() || null
              }}
            }};
          }});

          fetch('/admin/edit', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(payload)
          }}).then(resp => resp.json())
            .then(json => {{
              if (json.status === 'ok') {{
                showMessage('Saved!', 'green');
              }} else {{
                showMessage('Error: ' + (json.error || 'unknown error'), 'red');
              }}
            }})
            .catch(err => {{
              showMessage('Error: ' + err, 'red');
            }});
        }}

        function addRow() {{
          const template = `
            <tr>
              <td><input></td>
              <td><input></td>
              <td><input></td>
              <td>
                <select>
                  <option value='{CACHE_POLICY_NONE}' selected>No Cache</option>
                  <option value='{CACHE_POLICY_DAILY}'>Daily (refresh via job)</option>
                </select>
              </td>
              <td><input></td>
              <td><input></td>
              <td><input></td>
              <td>
                <div class="cache-status" data-report="">
                  <div class="status-text">Never cached</div>
                  <button type="button" class="refresh-btn">Refresh Cache</button>
                </div>
              </td>
            </tr>`;
          document.querySelector('tbody').insertAdjacentHTML('beforeend', template);
        }}

        document.addEventListener('click', (event) => {{
          const btn = event.target.closest('.refresh-btn');
          if (!btn) return;
          const statusBox = btn.closest('.cache-status');
          const row = btn.closest('tr');
          const input = row ? row.querySelector('td:first-child input') : null;
          const datasetName = statusBox && statusBox.dataset.report ? statusBox.dataset.report.trim() : "";
          const inputName = input ? input.value.trim() : "";
          const reportName = datasetName || inputName;
          if (!reportName) {{
            showMessage("Please specify a report name before refreshing.", "red");
            return;
          }}
          refreshReport(reportName, btn);
        }});

        document.addEventListener('DOMContentLoaded', () => {{
          document.querySelectorAll('.cache-status').forEach(statusBox => {{
            const metaStr = statusBox.dataset.meta || "";
            let meta = null;
            if (metaStr) {{
              try {{
                meta = JSON.parse(metaStr);
              }} catch (err) {{
                meta = null;
              }}
            }}
            updateStatusBox(statusBox, meta, statusBox.dataset.report || "");
            if (!meta && statusBox.dataset.error) {{
              statusBox.querySelector('.status-text').textContent = "Cache metadata unavailable";
            }}
          }});

          const refreshAllBtn = document.getElementById('refresh-all-btn');
          if (refreshAllBtn) {{
            refreshAllBtn.addEventListener('click', () => refreshAll(refreshAllBtn));
          }}
        }});
      </script>
    </head>
    <body>
      <h2>Edit Dossiers</h2>
      <table>
        <thead>
          <tr>
            <th>Report Name</th>
            <th>Cube ID</th>
            <th>Dossier ID</th>
            <th>cache_policy</th>
            <th>Agency Filter Key</th>
            <th>Summary Viz Key</th>
            <th>Detail Viz Key</th>
            <th>Cache Status</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
      <div class="actions">
        <button type="button" onclick="addRow()">Add Row</button>
        <button type="button" onclick="saveTable()">Save</button>
        <button type="button" id="refresh-all-btn">Refresh All Daily Caches</button>
      </div>
      <div id="msg"></div>
    </body>
    </html>
    """
    return Response(html_page, content_type="text/html; charset=utf-8")


@config_bp.route("/admin/edit", methods=["POST"])
def save_dossiers():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"status": "error", "error": "Invalid payload"}), 400

    normalised: Dict[str, Any] = {}
    for report, cfg in payload.items():
        if not isinstance(cfg, dict):
            continue
        policy = (cfg.get("cache_policy") or CACHE_POLICY_NONE).strip().lower()
        if policy not in {CACHE_POLICY_NONE, CACHE_POLICY_DAILY}:
            policy = CACHE_POLICY_NONE
        normalised[report] = {
            **cfg,
            "cache_policy": policy,
        }

    try:
        save_config(normalised)
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500

    return jsonify({"status": "ok"})


@config_bp.route("/admin/configure", methods=["GET"])
def view_config() -> Response:
    config = load_config() or {}
    config_yaml = yaml.safe_dump(config, allow_unicode=True, default_flow_style=False)

    html_content = f'''
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Dossier Configuration</title>
      <style>
        body {{ font-family: sans-serif; padding: 20px; display: flex; gap: 40px; }}
        .section {{ flex: 1; border: 1px solid #ccc; border-radius: 8px; padding: 16px; background: #f9f9f9; }}
        pre {{ background: #eee; padding: 8px; border-radius: 4px; max-height: 300px; overflow-y: auto; }}
        input, select {{ width: 100%; padding: 6px; margin-top: 4px; margin-bottom: 8px; box-sizing: border-box; }}
        button {{ padding: 6px 12px; margin-top: 8px; }}
        .message {{ margin-top: 10px; }}
        #discover-result {{ white-space: pre-wrap; font-family: monospace; background: #f4f4f4; padding: 10px; border-radius: 5px; border: 1px solid #ddd; max-height: 300px; overflow-y: auto; margin-top: 12px; }}
      </style>
      <script>
        document.addEventListener("DOMContentLoaded", () => {{
          const saveForm = document.getElementById("save-form");
          const saveMsg = document.getElementById("save-message");
          const deleteForm = document.getElementById("delete-form");
          const deleteMsg = document.getElementById("delete-message");

          saveForm.addEventListener("submit", async (event) => {{
            event.preventDefault();
            const formData = new FormData(saveForm);
            const data = new URLSearchParams(formData);
            saveMsg.innerHTML = "⏳ Kaydediliyor...";
            try {{
              const res = await fetch("/admin/configure", {{
                method: "POST",
                headers: {{ "Content-Type": "application/x-www-form-urlencoded" }},
                body: data,
              }});
              const json = await res.json();
              saveMsg.innerHTML = res.ok
                ? `<span style='color:green;'>✔ ${{json.report}} başarıyla kaydedildi.</span>`
                : `<span style='color:red;'>Hata: ${{json.message || json.error}}</span>`;

              const yamlRes = await fetch("/admin/configure_yaml");
              const yamlText = await yamlRes.text();
              document.querySelector("pre").textContent = yamlText;
            }} catch (err) {{
              saveMsg.innerHTML = `<span style='color:red;'>Sunucu hatası: ${{err}}</span>`;
            }}
          }});

          deleteForm.addEventListener("submit", async (event) => {{
            event.preventDefault();
            const formData = new FormData(deleteForm);
            const data = new URLSearchParams(formData);
            deleteMsg.innerHTML = "⏳ Siliniyor...";
            try {{
              const res = await fetch("/admin/configure/delete", {{
                method: "POST",
                headers: {{ "Content-Type": "application/x-www-form-urlencoded" }},
                body: data,
              }});
              const json = await res.json();
              deleteMsg.innerHTML = res.ok
                ? `<span style='color:green;'>✔ ${{json.report}} silindi.</span>`
                : `<span style='color:red;'>Hata: ${{json.message || json.error}}</span>`;

              const yamlRes = await fetch("/admin/configure_yaml");
              const yamlText = await yamlRes.text();
              document.querySelector("pre").textContent = yamlText;
            }} catch (err) {{
              deleteMsg.innerHTML = `<span style='color:red;'>Sunucu hatası: ${{err}}</span>`;
            }}
          }});

          window.discoverKeys = async function(event) {{
            event.preventDefault();
            const dossierId = document.getElementById("dossier_id_discover").value;
            const resultBox = document.getElementById("discover-result");
            resultBox.textContent = "Loading...";
            try {{
              const res = await fetch("/admin/discover_json", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ dossier_id: dossierId }})
              }});
              const json = await res.json();
              resultBox.textContent = JSON.stringify(json, null, 2);
              const acenteFilter = (json.filters || []).find(f => (f.name || '').toLowerCase() === 'acente_kodu');
              if (acenteFilter) {{
                document.querySelector("[name='filter_agency_name']").value = acenteFilter.key || '';
              }}
              const viz1 = json.visualizations?.[0];
              const viz2 = json.visualizations?.[1];
              if (viz1) {{
                document.querySelector("[name='viz_summary']").value = viz1.key || '';
              }}
              if (viz2) {{
                document.querySelector("[name='viz_detail']").value = viz2.key || '';
              }}
            }} catch (e) {{
              resultBox.textContent = "Hata: " + e;
            }}
          }}
        }});
      </script>
    </head>
    <body>
      <div class='section'>
        <h2>Mevcut Yapılandırma</h2>
        <pre>{html.escape(config_yaml)}</pre>
        <h3>Discover Keys</h3>
        <form onsubmit='discoverKeys(event)'>
          <input id='dossier_id_discover' placeholder='dossier id'>
          <button type='submit'>Discover</button>
        </form>
        <div id='discover-result'></div>
      </div>
      <div class='section'>
        <h3>Dossier Güncelle</h3>
        <form id='save-form'>
          <label>Report Name:</label><input name='report_name'>
          <label>Dossier ID:</label><input name='dossier_id'>
          <label>Cube ID:</label><input name='cube_id'>
          <label>Summary Viz Key:</label><input name='viz_summary'>
          <label>Detail Viz Key:</label><input name='viz_detail'>
          <label>Agency Filter Key (acente_kodu):</label><input name='filter_agency_name'>
          <label>Cache Policy:</label>
          <select name='cache_policy'>
            <option value='{CACHE_POLICY_NONE}'>No Cache</option>
            <option value='{CACHE_POLICY_DAILY}'>Daily (refresh via job)</option>
          </select>
          <button type='submit'>Kaydet</button>
        </form>
        <div id='save-message' class='message'></div>

        <h3>Dossier Sil</h3>
        <form id='delete-form'>
          <input name='report_name' placeholder='report name'>
          <button type='submit'>Sil</button>
        </form>
        <div id='delete-message' class='message'></div>
      </div>
    </body>
    </html>
    '''

    return Response(html_content, content_type="text/html; charset=utf-8")


@config_bp.route("/admin/configure", methods=["POST"])
def add_or_update_config():
    data = request.form

    report_name = data.get("report_name")
    dossier_id = data.get("dossier_id")
    cube_id = data.get("cube_id")
    cache_policy = (data.get("cache_policy") or CACHE_POLICY_NONE).lower().strip()
    if cache_policy not in {CACHE_POLICY_NONE, CACHE_POLICY_DAILY}:
        cache_policy = CACHE_POLICY_NONE

    if not all([report_name, dossier_id, cube_id]):
        return jsonify({"error": "report_name, dossier_id and cube_id are required"}), 400

    summary_viz = data.get("viz_summary") or None
    detail_viz = data.get("viz_detail") or None
    filter_agency = data.get("filter_agency_name") or None

    new_entry = {
        "cube_id": cube_id,
        "dossier_id": dossier_id,
        "cache_policy": cache_policy,
        "filters": {
            "agency_name": filter_agency
        },
        "viz_keys": {
            "summary": summary_viz,
            "detail": detail_viz
        }
    }

    config = load_config() or {}
    config[report_name] = new_entry
    save_config(config)

    return jsonify({"status": "saved", "report": report_name})


@config_bp.route("/admin/configure/delete", methods=["POST"])
def delete_config():
    data = request.form
    report_name = data.get("report_name")

    if not report_name:
        return jsonify({"error": "report_name required"}), 400

    config = load_config() or {}
    if report_name not in config:
        return jsonify({"error": "report not found"}), 404

    del config[report_name]
    save_config(config)
    return jsonify({"status": "deleted", "report": report_name})


@config_bp.route("/admin/discover", methods=["GET"])
def discover():
    dossier_id = request.args.get("dossier_id")
    if not dossier_id:
        return jsonify({"error": "dossier_id required"}), 400
    try:
        conn = create_connection()
        info = discover_dossier(conn, dossier_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return jsonify(info)


@config_bp.route("/admin/discover_json", methods=["POST"])
def discover_json():
    payload = request.get_json(silent=True) or {}
    dossier_id = payload.get("dossier_id")
    if not dossier_id:
        return jsonify({"error": "dossier_id required"}), 400
    try:
        conn = create_connection()
        info = discover_dossier(conn, dossier_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return jsonify(info)


@config_bp.route("/admin/configure_yaml", methods=["GET"])
def get_config_yaml():
    config = load_config() or {}
    config_yaml = yaml.safe_dump(config, allow_unicode=True, default_flow_style=False)
    return Response(config_yaml, content_type="text/plain; charset=utf-8")


__all__ = ["config_bp"]
