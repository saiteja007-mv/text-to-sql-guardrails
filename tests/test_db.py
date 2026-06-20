from txtsql.db import build_connection, execute


def test_db_builds_and_counts():
    con = build_connection()
    assert execute(con, "SELECT count(*) FROM customers").rows[0][0] == 8
    assert execute(con, "SELECT count(*) FROM products").rows[0][0] == 10
    assert execute(con, "SELECT count(*) FROM order_items").rows[0][0] == 17


def test_execute_columns_and_row_cap():
    con = build_connection()
    r = execute(con, "SELECT order_item_id FROM order_items ORDER BY order_item_id", max_rows=5)
    assert r.columns == ["order_item_id"]
    assert len(r.rows) == 5
    assert r.truncated is True


def test_execute_not_truncated_when_under_cap():
    con = build_connection()
    r = execute(con, "SELECT * FROM customers", max_rows=100)
    assert len(r.rows) == 8
    assert r.truncated is False
