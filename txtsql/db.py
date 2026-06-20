"""DuckDB demo database: built from bundled schema + seed SQL; row-capped execution."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_MAX_ROWS = 200


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
    schema_sql = Path(schema_path or DATA_DIR / "schema.sql").read_text(encoding="utf-8")
    seed_sql = Path(seed_path or DATA_DIR / "seed.sql").read_text(encoding="utf-8")
    for stmt in _statements(schema_sql):
        con.execute(stmt)
    for stmt in _statements(seed_sql):
        con.execute(stmt)
    return con


def execute(con, sql: str, max_rows: int = DEFAULT_MAX_ROWS) -> QueryResult:
    """Run a query and return at most ``max_rows`` rows (the row/cost cap)."""
    cur = con.execute(sql)
    columns = [d[0] for d in cur.description] if cur.description else []
    fetched = cur.fetchmany(max_rows + 1)
    truncated = len(fetched) > max_rows
    return QueryResult(columns=columns, rows=fetched[:max_rows], truncated=truncated)
