"""Text-to-SQL with guardrails: schema-aware NL->SQL, validated read-only execution."""
from .db import QueryResult, build_connection, execute
from .eval import GOLD, execution_match, run_eval
from .guardrails import GuardrailResult, validate
from .nl2sql import extract_sql, generate_sql
from .pipeline import AnswerResult, answer
from .schema import allowed_tables, get_schema, schema_prompt

__all__ = [
    "build_connection",
    "execute",
    "QueryResult",
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
