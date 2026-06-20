"""End-to-end orchestration: generate -> guardrail -> execute, with one retry that
feeds the rejection/error reason back to the generator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .db import QueryResult, execute
from .guardrails import validate
from .nl2sql import generate_sql
from .schema import allowed_tables, schema_prompt


@dataclass
class AnswerResult:
    question: str
    sql: Optional[str]          # the SQL that ran, or the last attempted SQL
    ok: bool
    blocked: bool
    reason: str
    attempts: int
    result: Optional[QueryResult]


def answer(
    question: str,
    con,
    *,
    generate_fn: Optional[Callable[[str, Optional[str]], str]] = None,
    max_rows: int = 200,
    retries: int = 1,
) -> AnswerResult:
    """Answer ``question`` over ``con``.

    ``generate_fn(question, feedback) -> sql`` is injectable for tests; by default
    it calls the OpenRouter NL->SQL model with the DB schema. On a guardrail block
    or execution error, the reason is fed back for up to ``retries`` more attempts.
    """
    allowed = allowed_tables(con)
    schema_text = schema_prompt(con)

    def _default_gen(q: str, feedback: Optional[str]) -> str:
        prompt = q if not feedback else f"{q}\n\nYour previous SQL was rejected: {feedback}. Return corrected SQL."
        return generate_sql(prompt, schema_text)

    gen = generate_fn or _default_gen
    feedback: Optional[str] = None
    last_sql: Optional[str] = None
    last_reason = "failed"

    for attempt in range(1, retries + 2):
        sql = gen(question, feedback)
        last_sql = sql
        gr = validate(sql, allowed, max_rows)
        if not gr.ok:
            feedback = gr.reason
            last_reason = gr.reason
            continue
        try:
            res = execute(con, gr.safe_sql, max_rows)
        except Exception as e:  # noqa: BLE001 - bad column/type etc.; retry with feedback
            feedback = f"execution error: {e}"
            last_reason = feedback
            last_sql = gr.safe_sql
            continue
        return AnswerResult(question, gr.safe_sql, True, False, "ok", attempt, res)

    return AnswerResult(question, last_sql, False, True, last_reason, retries + 1, None)
