from __future__ import annotations

import yaml
from flask import Blueprint, request, jsonify, Response
from mstr_herald.utils import load_config, save_config
from mstr_herald.connection import create_connection
from mstr_herald.dossier_inspector import discover_dossier
import json

configure_bp = Blueprint("configure", __name__)

@configure_bp.route("/admin/configure", methods=["GET"])
def view_config():
    import yaml
    from flask import Response
    config = load_config()
    config_yaml = yaml.safe_dump(config, allow_unicode=True, default_flow_style=False)

    html_content = '''
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Dossier Configuration</title>
      <style>
        body {{ font-family: sans-serif; padding: 20px; display: flex; gap: 40px; }}
        .section {{ flex: 1; border: 1px solid #ccc; border-radius: 8px; padding: 16px; background: #f9f9f9; }}
        pre {{ background: #eee; padding: 8px; border-radius: 4px; max-height: 300px; overflow-y: auto; }}
        input, select {{ width: 100%; padding: 6px; margin-top: 4px; margin-bottom: 8px; }}
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
              const acenteFilter = json.filters.find(f => (f.name || '').toLowerCase() === 'acente_kodu');
              if (acenteFilter) {{
                document.querySelector("[name='filter_agency_name']").value = acenteFilter.key;
              }}
              const viz1 = json.visualizations?.[0];
              const viz2 = json.visualizations?.[1];
              if (viz1) {{
                document.querySelector("[name='viz_summary']").value = viz1.key;
              }}
              if (viz2) {{
                document.querySelector("[name='viz_detail']").value = viz2.key;
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
        <pre>{}</pre>
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
          <label>is_csv_cached:</label>
          <select name='is_csv_cached'>
            <option value='0'>0</option>
            <option value='1'>1</option>
            <option value='2'>2</option>
            <option value='3'>3</option>
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
    '''.format(config_yaml)

    return Response(html_content, content_type="text/html; charset=utf-8")


@configure_bp.route("/admin/configure", methods=["POST"])
def add_or_update_config():
    data = request.form

    report_name = data.get("report_name")
    dossier_id = data.get("dossier_id")
    cube_id = data.get("cube_id")
    is_csv_cached = int(data.get("is_csv_cached", 0))

    if not all([report_name, dossier_id, cube_id]):
        return jsonify({"error": "report_name, dossier_id and cube_id are required"}), 400

    summary_viz = data.get("viz_summary") or None
    detail_viz = data.get("viz_detail") or None
    filter_agency = data.get("filter_agency_name") or None

    new_entry = {
        "cube_id": cube_id,
        "dossier_id": dossier_id,
        "is_csv_cached": is_csv_cached,
        "filters": {
            "agency_name": filter_agency
        },
        "viz_keys": {
            "summary": summary_viz,
            "detail": detail_viz
        }
    }

    config = load_config()
    config[report_name] = new_entry
    save_config(config)

    return jsonify({"status": "saved", "report": report_name})



@configure_bp.route("/admin/configure/delete", methods=["POST"])
def delete_config():
    data = request.form
    report_name = data.get("report_name")

    if not report_name:
        return jsonify({"error": "report_name required"}), 400

    config = load_config()
    if report_name not in config:
        return jsonify({"error": "report not found"}), 404

    del config[report_name]
    save_config(config)
    return jsonify({"status": "deleted", "report": report_name})



@configure_bp.route("/admin/discover", methods=["GET"])
def discover():
    dossier_id = request.args.get("dossier_id")
    if not dossier_id:
        return jsonify({"error": "dossier_id required"}), 400
    try:
        conn = create_connection()
        info = discover_dossier(conn, dossier_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return jsonify(info)

@configure_bp.route("/admin/discover_json", methods=["POST"])
def discover_json():
    dossier_id = request.json.get("dossier_id")
    if not dossier_id:
        return jsonify({"error": "dossier_id required"}), 400
    try:
        conn = create_connection()
        info = discover_dossier(conn, dossier_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return jsonify(info)

@configure_bp.route("/admin/configure_yaml", methods=["GET"])
def get_config_yaml():
    import yaml
    config = load_config()
    config_yaml = yaml.safe_dump(config, allow_unicode=True, default_flow_style=False)
    return Response(config_yaml, content_type="text/plain; charset=utf-8")
