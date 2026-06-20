"""DuckDB demo database: built from bundled schema + seed SQL; row-capped execution."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import duckdb

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_MAX_ROWS = 200
DEFAULT_TIMEOUT_S = 5.0


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool = False


def _statements(script: str):
    for raw in script.split(";"):
        s = raw.strip()
        if s and not s.startswith("--"):
            yield s


def build_connection(schema_path=None, seed_path=None) -> "duckdb.DuckDBPyConnection":
    """Build an in-memory DuckDB seeded from the bundled schema + seed SQL files."""
    con = duckdb.connect(":memory:")
    # Bound resource use so an accepted-but-pathological query can't exhaust the host.
    for pragma in ("SET memory_limit='512MB'", "SET threads TO 2"):
        try:
            con.execute(pragma)
        except Exception:  # noqa: BLE001 - config name varies across DuckDB versions
            pass
    schema_sql = Path(schema_path or DATA_DIR / "schema.sql").read_text(encoding="utf-8")
    seed_sql = Path(seed_path or DATA_DIR / "seed.sql").read_text(encoding="utf-8")
    for stmt in _statements(schema_sql):
        con.execute(stmt)
    for stmt in _statements(seed_sql):
        con.execute(stmt)
    return con


def execute(
    con,
    sql: str,
    max_rows: int = DEFAULT_MAX_ROWS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> QueryResult:
    """Run a query and return at most ``max_rows`` rows.

    The cost cap has two parts: a wall-clock ``timeout_s`` (a watchdog calls
    ``con.interrupt()``) bounds execution time, and ``max_rows`` caps the result
    size. Resource limits are also set on the connection in ``build_connection``.
    """
    timer = None
    if timeout_s and hasattr(con, "interrupt"):
        timer = threading.Timer(timeout_s, con.interrupt)
        timer.start()
    try:
        cur = con.execute(sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        fetched = cur.fetchmany(max_rows + 1)
    finally:
        if timer is not None:
            timer.cancel()
    truncated = len(fetched) > max_rows
    return QueryResult(columns=columns, rows=fetched[:max_rows], truncated=truncated)
