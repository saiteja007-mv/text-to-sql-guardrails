import pytest

from txtsql.guardrails import validate

ALLOWED = {"customers", "products", "orders", "order_items"}


def v(sql):
    return validate(sql, ALLOWED)


def test_simple_select_allowed():
    r = v("SELECT name FROM customers WHERE country = 'USA'")
    assert r.ok and r.safe_sql and r.rule is None


def test_join_aggregate_allowed():
    r = v(
        "SELECT c.name, count(*) FROM customers c "
        "JOIN orders o ON o.customer_id = c.customer_id GROUP BY c.name"
    )
    assert r.ok


def test_cte_allowed():
    r = v("WITH t AS (SELECT * FROM orders) SELECT count(*) FROM t")
    assert r.ok


@pytest.mark.parametrize("sql", [
    "INSERT INTO customers VALUES (9, 'x', 'y', 'z', DATE '2024-01-01')",
    "UPDATE customers SET name = 'x' WHERE customer_id = 1",
    "DELETE FROM customers WHERE customer_id = 1",
    "DROP TABLE customers",
    "ALTER TABLE customers ADD COLUMN x INTEGER",
    "CREATE TABLE evil (x INTEGER)",
])
def test_write_and_ddl_blocked(sql):
    r = v(sql)
    assert not r.ok
    assert r.rule == "not_readonly"


def test_multi_statement_blocked():
    r = v("SELECT 1 FROM customers; DROP TABLE customers")
    assert not r.ok and r.rule == "multi_statement"


def test_unknown_table_blocked():
    r = v("SELECT * FROM secrets")
    assert not r.ok and r.rule == "unknown_table"


@pytest.mark.parametrize("sql", [
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM read_parquet('s3://x/y.parquet')",
    "SELECT glob('*') AS f",
])
def test_file_functions_blocked(sql):
    r = v(sql)
    assert not r.ok and r.rule in ("forbidden_func", "unknown_table")


def test_file_function_with_newline_separator_blocked():
    # read_csv separated from '(' by a newline must NOT slip past the backstop.
    r = v("SELECT * FROM customers, read_csv\n('/etc/passwd')")
    assert not r.ok and r.rule in ("forbidden_func", "table_function")


def test_file_function_with_block_comment_blocked():
    r = v("SELECT * FROM customers, read_csv/* x */('/etc/passwd')")
    assert not r.ok and r.rule in ("forbidden_func", "table_function")


@pytest.mark.parametrize("sql", [
    "SELECT * FROM other_schema.customers",
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM mydb.main.customers",
])
def test_schema_qualified_table_blocked(sql):
    r = v(sql)
    assert not r.ok and r.rule in ("qualified_table", "unknown_table")


def test_main_schema_qualifier_allowed():
    assert v("SELECT name FROM main.customers").ok


def test_case_insensitive_table_allowed():
    # DuckDB resolves unquoted identifiers case-insensitively; guardrail must too.
    assert v("SELECT * FROM Customers").ok


def test_empty_blocked():
    r = v("   ")
    assert not r.ok and r.rule == "empty"


def test_trailing_semicolon_is_cleaned():
    r = v("SELECT name FROM customers;")
    assert r.ok
