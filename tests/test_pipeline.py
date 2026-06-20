from txtsql.db import build_connection
from txtsql.pipeline import answer


def test_answer_runs_valid_sql_first_try():
    con = build_connection()
    r = answer("how many customers", con, generate_fn=lambda q, fb: "SELECT count(*) FROM customers")
    assert r.ok and not r.blocked and r.attempts == 1
    assert r.result.rows[0][0] == 8


def test_answer_retries_after_guardrail_block():
    con = build_connection()
    seq = iter([
        "DROP TABLE customers",          # blocked -> triggers retry
        "SELECT count(*) FROM customers",  # valid on retry
    ])

    def gen(q, feedback):
        return next(seq)

    r = answer("how many customers", con, generate_fn=gen, retries=1)
    assert r.ok and r.attempts == 2
    assert r.result.rows[0][0] == 8


def test_answer_gives_up_after_retries():
    con = build_connection()
    r = answer("bad", con, generate_fn=lambda q, fb: "DROP TABLE customers", retries=1)
    assert not r.ok and r.blocked and r.attempts == 2 and r.result is None


def test_answer_retries_after_execution_error():
    con = build_connection()
    seq = iter([
        "SELECT nonexistent_col FROM customers",  # passes guardrail, fails execution
        "SELECT name FROM customers",             # valid on retry
    ])
    r = answer("names", con, generate_fn=lambda q, fb: next(seq), retries=1)
    assert r.ok and r.attempts == 2
