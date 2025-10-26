from __future__ import annotations

import logging
import time
from datetime import datetime
from io import StringIO
from typing import Any, Dict

import pandas as pd
from mstrio.connection import Connection
from mstrio.project_objects import OlapCube

logger = logging.getLogger(__name__)


def get_cube_last_update_time(conn: Connection, cube_id: str | None) -> str | None:
    if not cube_id:
        return None

    cube = OlapCube(connection=conn, id=cube_id)
    timestamp = cube.last_update_time
    if isinstance(timestamp, datetime):
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    try:
        parsed = datetime.fromisoformat(str(timestamp))
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(timestamp)


def fetch_report_dataframe(
    conn: Connection,
    report_name: str,
    cfg: Dict[str, Any],
    filters: Dict[str, Any],
    info_type: str,
    poll_interval: float = 0.5,
    timeout: int = 90,
) -> pd.DataFrame:
    dossier_id = cfg.get("dossier_id")
    viz_keys = cfg.get("viz_keys") or {}
    viz_key = viz_keys.get(info_type)
    cube_id = cfg.get("cube_id")

    if not dossier_id or not viz_key:
        raise KeyError(f"Report '{report_name}' is missing dossier_id or viz key for '{info_type}'.")

    applied_filters = []
    filter_key = (cfg.get("filters") or {}).get("agency_name")
    filter_value = (filters or {}).get("agency_name")
    if filter_key and filter_value not in (None, ""):
        applied_filters.append({"key": filter_key, "selections": [{"name": filter_value}]})

    if applied_filters:
        logger.info("Fetching '%s' (%s) with %d filters.", report_name, info_type, len(applied_filters))
    else:
        logger.info("Fetching '%s' (%s) without filters.", report_name, info_type)

    inst = conn.post(
        f"{conn.base_url}/api/dossiers/{dossier_id}/instances",
        json={"filters": applied_filters},
    )
    inst.raise_for_status()
    mid = inst.json().get("mid")
    if not mid:
        raise RuntimeError(f"Failed to create dossier instance for {report_name}.")

    csv_url = f"{conn.base_url}/api/documents/{dossier_id}/instances/{mid}/visualizations/{viz_key}/csv"

    start_time = time.time()
    while True:
        res = conn.post(csv_url)
        if res.ok:
            break
        if time.time() - start_time > timeout:
            res.raise_for_status()
        time.sleep(poll_interval)

    res = conn.post(csv_url)
    res.raise_for_status()
    df = pd.read_csv(StringIO(res.content.decode("utf-16")))
    df["dataRefreshTime"] = get_cube_last_update_time(conn, cube_id)
    return df


__all__ = ["fetch_report_dataframe", "get_cube_last_update_time"]

