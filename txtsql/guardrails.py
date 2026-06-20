"""SQL guardrails — parse with sqlglot and enforce read-only, single-statement,
table-allowlist, and file-function denylist before any query runs.

Each failure maps to a named ``rule`` so the UI/eval can show *why* a query was
blocked. Parsing (not regex) is what makes this robust against obfuscation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import sqlglot
from sqlglot import exp

# Built defensively via getattr so the module imports across sqlglot versions.
_WRITE_NAMES = [
    "Insert", "Update", "Delete", "Drop", "Create", "Alter",
    "Command", "Copy", "Set", "Merge", "Pragma", "Use", "Grant",
]
WRITE_NODES = tuple(getattr(exp, n) for n in _WRITE_NAMES if hasattr(exp, n))

_READ_ROOT_NAMES = ["Select", "With", "Union", "Intersect", "Except", "Subquery"]
READ_ROOTS = tuple(getattr(exp, n) for n in _READ_ROOT_NAMES if hasattr(exp, n))

# DuckDB functions that can touch the filesystem / load extensions.
FORBIDDEN_FUNCS = {
    "read_csv", "read_csv_auto", "read_parquet", "read_json", "read_json_auto",
    "read_text", "read_blob", "glob", "install", "load", "copy",
}


@dataclass
class GuardrailResult:
    ok: bool
    reason: str
    safe_sql: Optional[str]
    rule: Optional[str] = None


def _blocked(reason: str, rule: str) -> GuardrailResult:
    return GuardrailResult(ok=False, reason=reason, safe_sql=None, rule=rule)


def validate(sql: str, allowed_tables: set[str], max_rows: int = 200) -> GuardrailResult:
    """Validate ``sql`` against the read-only guardrails. ``max_rows`` is enforced
    at execution time (fetch cap); it is accepted here for a single call site."""
    cleaned = (sql or "").strip().rstrip(";").strip()
    if not cleaned:
        return _blocked("Empty query.", "empty")

    try:
        statements = [s for s in sqlglot.parse(cleaned, read="duckdb") if s is not None]
    except Exception as e:  # noqa: BLE001 - surface a friendly parse error
        return _blocked(f"Could not parse SQL: {e}", "parse")

    if len(statements) != 1:
        return _blocked("Only a single statement is allowed.", "multi_statement")

    stmt = statements[0]

    # Read-only: root must be a query, and no write/DDL node anywhere in the tree.
    if not isinstance(stmt, READ_ROOTS):
        return _blocked("Only read-only SELECT queries are allowed.", "not_readonly")
    if WRITE_NODES and stmt.find(*WRITE_NODES) is not None:
        return _blocked("Write/DDL statements are not allowed.", "not_readonly")

    # File-access / extension functions — AST scan plus a string backstop
    # (covers dialects where these parse as a dedicated node, not Anonymous).
    for fn in stmt.find_all(exp.Anonymous):
        if (fn.name or "").lower() in FORBIDDEN_FUNCS:
            return _blocked(f"Function '{fn.name}' is not allowed.", "forbidden_func")
    compact = cleaned.lower().replace(" ", "")
    for fn in FORBIDDEN_FUNCS:
        if f"{fn}(" in compact:
            return _blocked(f"Function '{fn}' is not allowed.", "forbidden_func")

    # Table allowlist — every referenced table must be a known schema table.
    # CTE names (defined in a WITH clause) are local aliases, not real tables.
    cte_names = {c.alias_or_name for c in stmt.find_all(exp.CTE)}
    used = {t.name for t in stmt.find_all(exp.Table) if t.name}
    unknown = sorted(t for t in used if t not in allowed_tables and t not in cte_names)
    if unknown:
        return _blocked(f"Unknown table(s): {', '.join(unknown)}.", "unknown_table")
    if not used:
        return _blocked("Query does not read any known table.", "no_table")

    return GuardrailResult(ok=True, reason="ok", safe_sql=stmt.sql(dialect="duckdb"), rule=None)
