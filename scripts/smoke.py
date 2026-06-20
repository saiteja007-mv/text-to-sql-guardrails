"""Headless end-to-end check: NL->SQL, guardrail block, and eval accuracy.

Requires OPENROUTER_API_KEY (calls the model). Exits non-zero on failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from txtsql.db import build_connection  # noqa: E402
from txtsql.eval import run_eval  # noqa: E402
from txtsql.guardrails import validate  # noqa: E402
from txtsql.nl2sql import generate_sql  # noqa: E402
from txtsql.pipeline import answer  # noqa: E402
from txtsql.schema import allowed_tables, schema_prompt  # noqa: E402


def main() -> int:
    con = build_connection()
    allowed = allowed_tables(con)
    schema_text = schema_prompt(con)

    r = answer("How many customers are from the USA?", con)
    print(f"[nl2sql] ok={r.ok} attempts={r.attempts} sql={r.sql!r}")
    if r.ok:
        print(f"  result: {r.result.rows}")

    bad = validate("SELECT 1 FROM customers; DROP TABLE customers", allowed)
    print(f"[guardrail] injection blocked={not bad.ok} rule={bad.rule}")

    report = run_eval(con, lambda q: generate_sql(q, schema_text), allowed)
    print(f"[eval] execution accuracy={report['accuracy'] * 100:.0f}% "
          f"blocked={report['blocked']}/{report['n']}")

    ok = r.ok and not bad.ok
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
