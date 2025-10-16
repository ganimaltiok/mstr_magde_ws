from __future__ import annotations

from typing import Any, Dict, List
from mstrio.connection import Connection


def post_dossier_instance(conn: Connection, dossier_id: str) -> dict:
    """Create a dossier instance and return JSON."""
    res = conn.post(f"{conn.base_url}/api/dossiers/{dossier_id}/instances")
    res.raise_for_status()
    return res.json()


def get_dossier_instance_def(conn: Connection, dossier_id: str, instance_id: str) -> dict:
    """Fetch dossier definition JSON."""
    res = conn.get(
        f"{conn.base_url}/api/v2/dossiers/{dossier_id}/instances/{instance_id}/definition"
    )
    res.raise_for_status()
    return res.json()


def list_filter_keys(def_json: dict) -> List[Dict[str, Any]]:
    """Return list of dictionaries describing filters and selectors."""
    rows: list[dict] = []

    def walk(node: Any, path: str = "root") -> None:
        if isinstance(node, dict):
            for coll, typ in (("filters", "filter"), ("selectors", "selector")):
                for idx, item in enumerate(node.get(coll, []) or []):
                    rows.append(
                        {
                            "path": f"{path}/{coll}[{idx}]",
                            "key": item.get("key"),
                            "name": item.get("name"),
                            "type": typ,
                        }
                    )
            for k, v in node.items():
                if isinstance(v, (dict, list)):
                    walk(v, f"{path}/{k}")
        elif isinstance(node, list):
            for i, el in enumerate(node):
                walk(el, f"{path}[{i}]")

    walk(def_json)
    return rows


def list_visualization_keys(def_json: dict) -> List[Dict[str, str]]:
    """Return list of visualization key/name info from dossier definition."""
    result: list[dict] = []
    for ch in def_json.get("chapters", []) or []:
        ch_name = ch.get("name")
        for pg in ch.get("pages", []) or []:
            pg_name = pg.get("name")
            for viz in pg.get("visualizations", []) or []:
                result.append(
                    {
                        "chapter": ch_name,
                        "page": pg_name,
                        "key": viz.get("key"),
                        "name": viz.get("name"),
                    }
                )
    return result


def discover_dossier(conn: Connection, dossier_id: str) -> dict:
    """Return filtered visualization and agency_code filter info for a given dossier."""
    inst = post_dossier_instance(conn, dossier_id)
    mid = inst.get("mid")
    def_json = get_dossier_instance_def(conn, dossier_id, mid)

    visualizations = list_visualization_keys(def_json)

    # Only keep the filter where name == 'acente_kodu'
    filters = [
        f for f in list_filter_keys(def_json)
        if (f.get("name") or "").strip().lower() == "acente_kodu"
    ]

    return {
        "visualizations": visualizations,
        "filters": filters
    }

