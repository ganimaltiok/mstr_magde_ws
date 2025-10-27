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
    resolve_data_policy,
    CACHE_POLICY_NONE,
    CACHE_POLICY_DAILY,
    DATA_POLICY_MICROSTRATEGY,
    DATA_POLICY_POSTGRESQL,
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

    info_summary = "\n".join(parts) if parts else "no datasets cached"
    suffix = " (partial)" if meta.get("partial") else ""
    return f"{refreshed_at}{suffix}\n{info_summary}" if info_summary else f"{refreshed_at}{suffix}"

config_bp = Blueprint("configure", __name__)


def _generate_edit_rows(config: Dict[str, Any]) -> str:
    rows: list[str] = []
    for report_name, cfg in (config or {}).items():
        cfg = cfg or {}
        filters = cfg.get("filters") or {}
        viz_keys = cfg.get("viz_keys") or {}
        postgres_table = cfg.get("postgres_table") or ""

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

        data_policy = resolve_data_policy(cfg)
        data_policy_options = []
        for value, label in (
            (DATA_POLICY_MICROSTRATEGY, "MicroStrategy"),
            (DATA_POLICY_POSTGRESQL, "PostgreSQL"),
        ):
            selected = "selected" if data_policy == value else ""
            data_policy_options.append(
                f"<option value='{value}' {selected}>{html.escape(label)}</option>"
            )

        rows.append(
            f"<tr data-policy='{data_policy}'>"
            f"<td><input data-field='report_name' value='{esc(report_name)}'></td>"
            f"<td><select data-field='data_policy' class='data-policy-select'>{''.join(data_policy_options)}</select></td>"
            f"<td class='micro-field'><input data-field='cube_id' value='{esc(cfg.get('cube_id'))}'></td>"
            f"<td class='micro-field'><input data-field='dossier_id' value='{esc(cfg.get('dossier_id'))}'></td>"
            f"<td class='postgres-field'><input data-field='postgres_table' placeholder='schema.table' value='{esc(postgres_table)}'></td>"
            f"<td><select data-field='cache_policy'>{''.join(options)}</select></td>"
            f"<td class='micro-field'><input data-field='agency_name' value='{esc(filters.get('agency_name'))}'></td>"
            f"<td class='micro-field'><input data-field='summary_viz' value='{esc(viz_keys.get('summary'))}'></td>"
            f"<td class='micro-field'><input data-field='detail_viz' value='{esc(viz_keys.get('detail'))}'></td>"
            f"<td class='status-cell'>"
            f"  <div class='cache-status' data-report='{esc(report_name)}' data-meta='{meta_json}' data-error='{esc(meta_error)}'>"
            f"    <div class='status-text'>{html.escape(status_text)}</div>"
            f"  </div>"
            f"</td>"
            f"<td class='actions-cell'>"
            f"  <button type='button' class='refresh-btn'>Refresh Cache</button>"
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
        #msg {{ margin-top:10px; color: green; }}
        .cache-status {{ display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }}
        .cache-status .status-text {{ font-size: 0.85em; color: #555; white-space: pre-line; }}
        .actions {{ margin-top: 12px; display: flex; gap: 10px; }}
        .actions-cell {{ text-align: center; }}
        .actions-cell .refresh-btn {{ margin-top: 0; padding: 6px 12px; }}
        tr[data-policy="{DATA_POLICY_POSTGRESQL}"] .micro-field {{ display: none; }}
        tr[data-policy="{DATA_POLICY_MICROSTRATEGY}"] .postgres-field {{ display: none; }}
      </style>
      <script>
        const CACHE_POLICY_NONE = "{CACHE_POLICY_NONE}";
        const CACHE_POLICY_DAILY = "{CACHE_POLICY_DAILY}";
        const DATA_POLICY_MICROSTRATEGY = "{DATA_POLICY_MICROSTRATEGY}";
        const DATA_POLICY_POSTGRESQL = "{DATA_POLICY_POSTGRESQL}";

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
          const row = button.closest('tr');
          const statusBox = row ? row.querySelector('.cache-status') : null;
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

        function applyPolicyToRow(row, policy) {{
          if (!row) return;
          row.dataset.policy = policy;
          const microCells = row.querySelectorAll('.micro-field');
          const postgresCells = row.querySelectorAll('.postgres-field');
          microCells.forEach(cell => {{
            cell.style.display = policy === DATA_POLICY_MICROSTRATEGY ? '' : 'none';
            cell.querySelectorAll('input,select,textarea').forEach(el => {{
              el.disabled = policy === DATA_POLICY_POSTGRESQL;
            }});
          }});
          postgresCells.forEach(cell => {{
            cell.style.display = policy === DATA_POLICY_POSTGRESQL ? '' : 'none';
            cell.querySelectorAll('input,select,textarea').forEach(el => {{
              el.disabled = policy === DATA_POLICY_MICROSTRATEGY;
            }});
          }});
        }}

        function saveTable() {{
          const rows = document.querySelectorAll('tbody tr');
          const payload = {{}};
          rows.forEach(row => {{
            const data = {{}};
            row.querySelectorAll('[data-field]').forEach(input => {{
              const key = input.dataset.field;
              if (!key) return;
              data[key] = (input.value || '').trim();
            }});
            const reportName = data.report_name;
            if (!reportName) return;
            const dataPolicy = data.data_policy || DATA_POLICY_MICROSTRATEGY;
            payload[reportName] = {{
              data_policy: dataPolicy,
              cube_id: data.cube_id || null,
              dossier_id: data.dossier_id || null,
              postgres_table: data.postgres_table || null,
              cache_policy: (data.cache_policy || CACHE_POLICY_NONE),
              filters: {{ agency_name: data.agency_name || null }},
              viz_keys: {{
                summary: data.summary_viz || null,
                detail: data.detail_viz || null
              }}
            }};
            if (dataPolicy === DATA_POLICY_POSTGRESQL) {{
              payload[reportName].cube_id = null;
              payload[reportName].dossier_id = null;
              payload[reportName].filters = {{}};
              payload[reportName].viz_keys = {{}};
            }} else {{
              payload[reportName].postgres_table = null;
            }}
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
            <tr data-policy='${{DATA_POLICY_MICROSTRATEGY}}'>
              <td><input data-field='report_name'></td>
              <td><select data-field='data_policy' class='data-policy-select'>
                    <option value='${{DATA_POLICY_MICROSTRATEGY}}' selected>MicroStrategy</option>
                    <option value='${{DATA_POLICY_POSTGRESQL}}'>PostgreSQL</option>
                  </select></td>
              <td class="micro-field"><input data-field='cube_id'></td>
              <td class="micro-field"><input data-field='dossier_id'></td>
              <td class="postgres-field"><input data-field='postgres_table' placeholder='schema.table'></td>
              <td>
                <select data-field='cache_policy'>
                  <option value='{CACHE_POLICY_NONE}' selected>No Cache</option>
                  <option value='{CACHE_POLICY_DAILY}'>Daily (refresh via job)</option>
                </select>
              </td>
              <td class="micro-field"><input data-field='agency_name'></td>
              <td class="micro-field"><input data-field='summary_viz'></td>
              <td class="micro-field"><input data-field='detail_viz'></td>
              <td class="status-cell">
                <div class="cache-status" data-report="">
                  <div class="status-text">Never cached</div>
                </div>
              </td>
              <td class="actions-cell">
                <button type="button" class="refresh-btn">Refresh Cache</button>
              </td>
            </tr>`;
          const tbody = document.querySelector('tbody');
          tbody.insertAdjacentHTML('beforeend', template);
          const newRow = tbody.lastElementChild;
          applyPolicyToRow(newRow, DATA_POLICY_MICROSTRATEGY);
        }}

        document.addEventListener('click', (event) => {{
          const btn = event.target.closest('.refresh-btn');
          if (!btn) return;
          const row = btn.closest('tr');
          if (!row) return;
          const statusBox = row.querySelector('.cache-status');
          if (!statusBox) {{
            showMessage("Cache status unavailable for this row.", "red");
            return;
          }}
          const input = row.querySelector('[data-field="report_name"]');
          const datasetName = statusBox && statusBox.dataset.report ? statusBox.dataset.report.trim() : "";
          const inputName = input ? input.value.trim() : "";
          const reportName = datasetName || inputName;
          if (!reportName) {{
            showMessage("Please specify a report name before refreshing.", "red");
            return;
          }}
          refreshReport(reportName, btn);
        }});

        document.addEventListener('change', (event) => {{
          const select = event.target.closest('.data-policy-select');
          if (!select) return;
          const row = select.closest('tr');
          const policy = select.value || DATA_POLICY_MICROSTRATEGY;
          applyPolicyToRow(row, policy);
        }});

        document.addEventListener('DOMContentLoaded', () => {{
          document.querySelectorAll('tbody tr').forEach(row => {{
            const select = row.querySelector('.data-policy-select');
            const policy = select ? (select.value || DATA_POLICY_MICROSTRATEGY) : DATA_POLICY_MICROSTRATEGY;
            applyPolicyToRow(row, policy);
          }});
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
            <th>Data Policy</th>
            <th>Cube ID</th>
            <th>Dossier ID</th>
            <th>Postgres Table</th>
            <th>cache_policy</th>
            <th>Agency Filter Key</th>
            <th>Summary Viz Key</th>
            <th>Detail Viz Key</th>
            <th>Cache Status</th>
            <th>Actions</th>
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
        data_policy = (cfg.get("data_policy") or DATA_POLICY_MICROSTRATEGY).strip().lower()
        if data_policy not in {DATA_POLICY_MICROSTRATEGY, DATA_POLICY_POSTGRESQL}:
            data_policy = DATA_POLICY_MICROSTRATEGY

        entry = dict(cfg)
        entry["cache_policy"] = policy
        entry["data_policy"] = data_policy

        filters = entry.get("filters") or {}
        if not isinstance(filters, dict):
            filters = {}

        viz_keys = entry.get("viz_keys") or {}
        if not isinstance(viz_keys, dict):
            viz_keys = {}

        if data_policy == DATA_POLICY_POSTGRESQL:
            entry["cube_id"] = None
            entry["dossier_id"] = None
            entry["postgres_table"] = (entry.get("postgres_table") or "").strip() or None
            filters = {}
            viz_keys = {}
        else:
            entry["postgres_table"] = None
            entry["cube_id"] = (entry.get("cube_id") or "").strip() or None
            entry["dossier_id"] = (entry.get("dossier_id") or "").strip() or None
            filters["agency_name"] = (filters.get("agency_name") or "").strip() or None
            viz_keys["summary"] = (viz_keys.get("summary") or "").strip() or None
            viz_keys["detail"] = (viz_keys.get("detail") or "").strip() or None

        entry["filters"] = filters
        entry["viz_keys"] = viz_keys

        normalised[report] = entry

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
          <label>Data Policy:</label>
          <select name='data_policy'>
            <option value='{DATA_POLICY_MICROSTRATEGY}'>MicroStrategy</option>
            <option value='{DATA_POLICY_POSTGRESQL}'>PostgreSQL</option>
          </select>
          <label>Postgres Table (schema.table):</label><input name='postgres_table'>
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
    dossier_id = data.get("dossier_id") or None
    cube_id = data.get("cube_id") or None
    postgres_table = (data.get("postgres_table") or "").strip() or None
    data_policy = (data.get("data_policy") or DATA_POLICY_MICROSTRATEGY).strip().lower()
    if data_policy not in {DATA_POLICY_MICROSTRATEGY, DATA_POLICY_POSTGRESQL}:
        data_policy = DATA_POLICY_MICROSTRATEGY
    cache_policy = (data.get("cache_policy") or CACHE_POLICY_NONE).lower().strip()
    if cache_policy not in {CACHE_POLICY_NONE, CACHE_POLICY_DAILY}:
        cache_policy = CACHE_POLICY_NONE

    if not report_name:
        return jsonify({"error": "report_name is required"}), 400

    if data_policy == DATA_POLICY_POSTGRESQL:
        if not postgres_table:
            return jsonify({"error": "postgres_table is required when data_policy=postgresql"}), 400
    else:
        if not all([dossier_id, cube_id]):
            return jsonify({"error": "dossier_id and cube_id are required when data_policy=microstrategy"}), 400

    summary_viz = data.get("viz_summary") or None
    detail_viz = data.get("viz_detail") or None
    filter_agency = data.get("filter_agency_name") or None

    if data_policy == DATA_POLICY_POSTGRESQL:
        summary_viz = None
        detail_viz = None
        filter_agency = None

    new_entry = {
        "data_policy": data_policy,
        "cube_id": cube_id if data_policy == DATA_POLICY_MICROSTRATEGY else None,
        "dossier_id": dossier_id if data_policy == DATA_POLICY_MICROSTRATEGY else None,
        "cache_policy": cache_policy,
        "postgres_table": postgres_table if data_policy == DATA_POLICY_POSTGRESQL else None,
        "filters": {
            "agency_name": filter_agency if data_policy == DATA_POLICY_MICROSTRATEGY else None
        },
        "viz_keys": {
            "summary": summary_viz if data_policy == DATA_POLICY_MICROSTRATEGY else None,
            "detail": detail_viz if data_policy == DATA_POLICY_MICROSTRATEGY else None
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
