"""SQL guardrails — parse with sqlglot and enforce read-only, single-statement,
table-allowlist, and file-function denylist before any query runs.

Each failure maps to a named ``rule`` so the UI/eval can show *why* a query was
blocked. Parsing (not regex) is what makes this robust against obfuscation.
"""
from __future__ import annotations

import re
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
    # Backstop: strip comments + ALL whitespace so 'read_csv\n(' or 'read_csv/**/('
    # cannot slip past the AST scan (sqlglot may render such a call as an empty-name table).
    no_comments = re.sub(r"--[^\n]*", " ", cleaned)
    no_comments = re.sub(r"/\*.*?\*/", " ", no_comments, flags=re.S)
    compact = re.sub(r"\s+", "", no_comments).lower()
    for fn in FORBIDDEN_FUNCS:
        if f"{fn}(" in compact:
            return _blocked(f"Function '{fn}' is not allowed.", "forbidden_func")

    # Reject schema/catalog-qualified tables. The allowlist is bare names in the
    # 'main' schema, so a qualifier (other_schema.customers, information_schema.*,
    # an attached catalog) could reach objects outside the intended database.
    for t in stmt.find_all(exp.Table):
        catalog = (t.text("catalog") or "").lower()
        schema_q = (t.text("db") or "").lower()
        if catalog or (schema_q and schema_q != "main"):
            return _blocked(
                f"Schema/catalog-qualified tables are not allowed: {t.sql(dialect='duckdb')}.",
                "qualified_table",
            )

    # A table-valued function (e.g. read_csv(...)) parses as a Table with an empty
    # name — block it explicitly so it can't ride along with an allowlisted table.
    real_tables = list(stmt.find_all(exp.Table))
    if any(not (t.name or "").strip() for t in real_tables):
        return _blocked("Table-valued functions are not allowed.", "table_function")

    # Table allowlist — case-insensitive, like DuckDB unquoted identifiers.
    # CTE names (defined in a WITH clause) are local aliases, not real tables.
    allowed_lc = {a.lower() for a in allowed_tables}
    cte_names = {(c.alias_or_name or "").lower() for c in stmt.find_all(exp.CTE)}
    used = {t.name.lower() for t in real_tables if t.name}
    unknown = sorted(t for t in used if t not in allowed_lc and t not in cte_names)
    if unknown:
        return _blocked(f"Unknown table(s): {', '.join(unknown)}.", "unknown_table")
    if not used:
        return _blocked("Query does not read any known table.", "no_table")

    return GuardrailResult(ok=True, reason="ok", safe_sql=stmt.sql(dialect="duckdb"), rule=None)
