from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator

import pandas as pd
import psycopg2

from services.settings import get_settings


@dataclass(frozen=True)
class TableRef:
    schema: str | None
    table: str


def parse_table_reference(ref: str | None) -> TableRef | None:
    if not ref:
        return None
    ref = ref.strip()
    if not ref:
        return None
    parts = ref.split(".")
    if len(parts) == 1:
        name = parts[0].strip()
        if not _is_valid_identifier(name):
            raise ValueError(f"Invalid Postgres identifier: {name}")
        return TableRef(schema=None, table=name)
    schema = parts[0]
    table = parts[1]
    if not _is_valid_identifier(schema) or not _is_valid_identifier(table):
        raise ValueError("Invalid Postgres schema/table identifier")
    return TableRef(schema=schema, table=table)


def _is_valid_identifier(value: str) -> bool:
    return bool(value) and all(ch.isalnum() or ch == "_" for ch in value)


@contextmanager
def pg_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    settings = get_settings()
    conn = psycopg2.connect(
        host=settings.pg_host,
        port=settings.pg_port,
        dbname=settings.pg_database,
        user=settings.pg_user,
        password=settings.pg_password,
    )
    try:
        yield conn
    finally:
        conn.close()


def fetch_table_dataframe(table_ref: TableRef, limit: int | None = None) -> pd.DataFrame:
    if table_ref.schema:
        qualified = f'"{table_ref.schema}"."{table_ref.table}"'
    else:
        qualified = f'"{table_ref.table}"'
    base_query = f"SELECT * FROM {qualified}"
    with pg_connection() as conn:
        if limit is not None and limit > 0:
            query = base_query + " LIMIT %s"
            df = pd.read_sql_query(query, conn, params=[limit])
        else:
            df = pd.read_sql_query(base_query, conn)
    return df


__all__ = ["TableRef", "parse_table_reference", "fetch_table_dataframe", "pg_connection"]
