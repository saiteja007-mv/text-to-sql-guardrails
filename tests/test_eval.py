from txtsql.db import build_connection
from txtsql.eval import GOLD, execution_match, run_eval
from txtsql.schema import allowed_tables


def test_execution_match_equivalent_queries():
    con = build_connection()
    # Different column alias, same values -> match.
    assert execution_match(
        con, "SELECT count(*) FROM customers", "SELECT count(*) AS n FROM customers"
    )


def test_execution_match_order_insensitive():
    con = build_connection()
    assert execution_match(
        con,
        "SELECT name FROM customers ORDER BY name",
        "SELECT name FROM customers ORDER BY name DESC",
    )


def test_execution_match_different_results():
    con = build_connection()
    assert not execution_match(
        con, "SELECT count(*) FROM customers", "SELECT count(*) FROM products"
    )


def test_gold_set_self_consistent():
    # Every gold SQL must run and match itself (sanity-checks the seed data).
    con = build_connection()
    allowed = allowed_tables(con)

    def gold_gen(question):
        return next(g["sql"] for g in GOLD if g["q"] == question)

    report = run_eval(con, gold_gen, allowed)
    assert report["accuracy"] == 1.0
    assert report["blocked"] == 0
    assert report["n"] == len(GOLD)
