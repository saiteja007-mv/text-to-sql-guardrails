"""Introspect the demo DB schema -> prompt text + table allowlist."""
from __future__ import annotations


def get_schema(con) -> dict[str, list[str]]:
    """Return {table_name: [column, ...]} for the main schema."""
    tables = [
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
    ]
    schema: dict[str, list[str]] = {}
    for t in tables:
        cols = con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            [t],
        ).fetchall()
        schema[t] = [c[0] for c in cols]
    return schema


def allowed_tables(con) -> set[str]:
    return set(get_schema(con).keys())


def schema_prompt(con) -> str:
    """Compact schema rendering for the LLM prompt: ``table(col1, col2, ...)``."""
    return "\n".join(f"{t}({', '.join(cols)})" for t, cols in get_schema(con).items())
