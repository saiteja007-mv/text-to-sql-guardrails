"""Text-to-SQL with guardrails: schema-aware NL->SQL, validated read-only execution."""
from .db import QueryResult, build_connection, execute
from .eval import GOLD, execution_match, run_eval
from .guardrails import GuardrailResult, validate
from .nl2sql import extract_sql, generate_sql
from .pipeline import AnswerResult, answer
from .schema import allowed_tables, get_schema, schema_prompt
from .sources import (
    build_from_connection_string,
    build_from_csvs,
    build_from_duckdb_file,
    build_from_sqlite_file,
    detect_db_type,
)

__all__ = [
    "build_connection",
    "execute",
    "QueryResult",
    "build_from_csvs",
    "build_from_sqlite_file",
    "build_from_duckdb_file",
    "build_from_connection_string",
    "detect_db_type",
    "validate",
    "GuardrailResult",
    "generate_sql",
    "extract_sql",
    "answer",
    "AnswerResult",
    "get_schema",
    "schema_prompt",
    "allowed_tables",
    "run_eval",
    "execution_match",
    "GOLD",
]
