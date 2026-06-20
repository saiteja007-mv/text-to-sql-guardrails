"""OpenRouter NL->SQL: schema-aware prompt + robust SQL extraction."""
from __future__ import annotations

import os
import re

from ._openrouter import get_api_key, make_client

DEFAULT_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"

SYSTEM_PROMPT = (
    "You are an expert data analyst who writes DuckDB SQL. Given a database schema "
    "and a question, return ONE read-only SELECT query that answers it.\n"
    "Rules:\n"
    "1. SELECT only — never INSERT/UPDATE/DELETE/DROP/ALTER or any DDL.\n"
    "2. Use ONLY the tables and columns listed in the schema.\n"
    "3. Return ONLY the SQL — no prose, no explanation, no markdown fences."
)

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.S | re.I)


def get_model() -> str:
    return os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL).strip()


def build_messages(question: str, schema_text: str) -> list[dict]:
    user = f"Schema:\n{schema_text}\n\nQuestion: {question}\n\nSQL:"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def extract_sql(text: str) -> str:
    """Pull a SQL statement out of a model response (handles ```sql fences and prose)."""
    if not text:
        return ""
    m = _FENCE.search(text)
    sql = (m.group(1) if m else text).strip()
    # Trim leading prose: jump to the first WITH/SELECT keyword.
    low = sql.lower()
    idx = min(
        (i for i in (low.find("with "), low.find("select ")) if i != -1),
        default=-1,
    )
    if idx > 0:
        sql = sql[idx:]
    return sql.strip().rstrip(";").strip()


def generate_sql(
    question: str,
    schema_text: str,
    api_key: str | None = None,
    model: str | None = None,
    temperature: float = 0.0,
) -> str:
    api_key = api_key or get_api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set. See the README.")
    client = make_client(api_key)
    resp = client.chat.completions.create(
        model=model or get_model(),
        messages=build_messages(question, schema_text),
        temperature=temperature,
    )
    return extract_sql(resp.choices[0].message.content or "")
