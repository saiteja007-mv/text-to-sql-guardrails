"""Build a query connection from a user-supplied data source.

Every source — uploaded CSV(s), a SQLite/DuckDB file, or a remote Postgres/MySQL
connection — is *copied* into the ``main`` schema of a fresh in-memory DuckDB.
That keeps the rest of the system unchanged (user queries reference unqualified
tables; the guardrails stay simple) and means we never hold a live handle to a
remote database while answering questions.

Security: remote imports are row-capped, and private/loopback/link-local hosts are
refused to reduce SSRF from a public deployment.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

from .db import new_connection

REMOTE_ROW_CAP = 100_000


def _esc(value: str) -> str:
    return str(value).replace("'", "''")


def _safe_ident(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(name)).strip("_")
    return cleaned or "table"


def _attached_tables(con, alias: str):
    """[(schema_name, table_name)] for an attached database ``alias``."""
    return con.execute(
        "SELECT schema_name, table_name FROM duckdb_tables() WHERE database_name = ?",
        [alias],
    ).fetchall()


def _copy_attached(con, alias: str, row_cap: int | None = None) -> int:
    """Copy every table of attached DB ``alias`` into the local ``main`` schema."""
    copied = 0
    for schema, table in _attached_tables(con, alias):
        target = _safe_ident(table if schema in ("main", "public") else f"{schema}_{table}")
        limit = f" LIMIT {int(row_cap)}" if row_cap else ""
        con.execute(
            f'CREATE OR REPLACE TABLE main."{target}" AS '
            f'SELECT * FROM "{alias}"."{schema}"."{table}"{limit}'
        )
        copied += 1
    if copied == 0:
        raise ValueError("No tables found in the supplied database.")
    return copied


# --- uploads -------------------------------------------------------------

def build_from_csvs(files: list[tuple[str, str]]):
    """``files`` = list of (table_name, csv_path). Each CSV becomes a main table."""
    if not files:
        raise ValueError("No CSV files provided.")
    con = new_connection()
    for name, path in files:
        target = _safe_ident(name)
        con.execute(
            f'CREATE OR REPLACE TABLE main."{target}" AS '
            f"SELECT * FROM read_csv_auto('{_esc(path)}')"
        )
    return con


def build_from_duckdb_file(path: str):
    con = new_connection()
    con.execute(f"ATTACH '{_esc(path)}' AS src (READ_ONLY)")
    try:
        _copy_attached(con, "src")
    finally:
        try:
            con.execute("DETACH src")
        except Exception:  # noqa: BLE001
            pass
    return con


def build_from_sqlite_file(path: str):
    con = new_connection()
    con.execute("INSTALL sqlite")
    con.execute("LOAD sqlite")
    con.execute(f"ATTACH '{_esc(path)}' AS src (TYPE sqlite, READ_ONLY)")
    try:
        _copy_attached(con, "src")
    finally:
        try:
            con.execute("DETACH src")
        except Exception:  # noqa: BLE001
            pass
    return con


# --- remote connection ---------------------------------------------------

def detect_db_type(conn_str: str) -> str:
    scheme = urlparse(conn_str).scheme.lower()
    if scheme in ("postgres", "postgresql"):
        return "postgres"
    if scheme == "mysql":
        return "mysql"
    raise ValueError("Only postgresql:// or mysql:// connection strings are supported.")


def _reject_internal_host(conn_str: str) -> None:
    host = urlparse(conn_str).hostname
    if not host:
        raise ValueError("Connection string has no host.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(host))
        except Exception:  # noqa: BLE001 - unresolvable; let the driver fail later
            return
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        raise ValueError(f"Refusing to connect to a private/internal host: {host}")


def build_from_connection_string(conn_str: str, row_cap: int = REMOTE_ROW_CAP):
    db_type = detect_db_type(conn_str)
    _reject_internal_host(conn_str)
    con = new_connection()
    con.execute(f"INSTALL {db_type}")
    con.execute(f"LOAD {db_type}")
    con.execute(f"ATTACH '{_esc(conn_str)}' AS src (TYPE {db_type}, READ_ONLY)")
    try:
        _copy_attached(con, "src", row_cap=row_cap)
    finally:
        try:
            con.execute("DETACH src")
        except Exception:  # noqa: BLE001
            pass
    return con
