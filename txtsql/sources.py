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
import threading
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .db import new_connection

REMOTE_ROW_CAP = 100_000
REMOTE_TIMEOUT_S = 20.0
# Catalogs/metadata exposed by attached databases — never import these as user tables.
SYSTEM_SCHEMAS = ("information_schema", "pg_catalog", "pg_toast", "sys", "mysql", "performance_schema")


def _esc(value: str) -> str:
    return str(value).replace("'", "''")


def _safe_ident(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(name)).strip("_")
    return cleaned or "table"


def _attached_tables(con, alias: str):
    """[(schema_name, table_name)] for the *user* tables of attached DB ``alias``
    (system catalogs like information_schema / pg_catalog are excluded)."""
    placeholders = ", ".join("?" for _ in SYSTEM_SCHEMAS)
    return con.execute(
        f"SELECT schema_name, table_name FROM duckdb_tables() "
        f"WHERE database_name = ? AND lower(schema_name) NOT IN ({placeholders})",
        [alias, *SYSTEM_SCHEMAS],
    ).fetchall()


def _with_timeout(fn, timeout_s: float):
    """Run ``fn`` in a thread; raise TimeoutError if it doesn't finish in time.

    Bounds an unreachable-host hang (e.g. a public deployment that cannot route to
    a Tailscale/LAN-only database) so the UI shows an error instead of spinning.
    """
    box: dict = {}

    def run():
        try:
            box["value"] = fn()
        except Exception as e:  # noqa: BLE001
            box["error"] = e

    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive():
        raise TimeoutError(
            f"Connection/import timed out after {timeout_s:.0f}s — is the host reachable "
            "from this server? A public deployment cannot reach a Tailscale/LAN-only address; "
            "run the app locally for those."
        )
    if "error" in box:
        raise box["error"]
    return box.get("value")


def _with_pg_connect_timeout(conn_str: str, seconds: int = 8) -> str:
    """Add libpq ``connect_timeout`` so an unreachable Postgres fails fast."""
    u = urlparse(conn_str)
    q = dict(parse_qsl(u.query))
    q.setdefault("connect_timeout", str(seconds))
    return urlunparse(u._replace(query=urlencode(q)))


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


def build_from_connection_string(
    conn_str: str,
    row_cap: int = REMOTE_ROW_CAP,
    timeout_s: float = REMOTE_TIMEOUT_S,
):
    db_type = detect_db_type(conn_str)
    _reject_internal_host(conn_str)
    dsn = _with_pg_connect_timeout(conn_str) if db_type == "postgres" else conn_str

    def _do():
        con = new_connection()
        con.execute(f"INSTALL {db_type}")
        con.execute(f"LOAD {db_type}")
        con.execute(f"ATTACH '{_esc(dsn)}' AS src (TYPE {db_type}, READ_ONLY)")
        try:
            _copy_attached(con, "src", row_cap=row_cap)
        finally:
            try:
                con.execute("DETACH src")
            except Exception:  # noqa: BLE001
                pass
        return con

    return _with_timeout(_do, timeout_s)
