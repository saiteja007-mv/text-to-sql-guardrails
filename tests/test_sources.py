import duckdb
import pytest

from txtsql.db import execute
from txtsql.sources import (
    _reject_internal_host,
    build_from_csvs,
    build_from_duckdb_file,
    build_from_sqlite_file,
    detect_db_type,
)


def test_build_from_csvs(tmp_path):
    p = tmp_path / "people.csv"
    p.write_text("id,name\n1,Alice\n2,Bob\n", encoding="utf-8")
    con = build_from_csvs([("people", str(p))])
    assert execute(con, "SELECT count(*) FROM people").rows[0][0] == 2
    assert execute(con, "SELECT name FROM people WHERE id = 1").rows[0][0] == "Alice"


def test_build_from_csvs_sanitizes_table_name(tmp_path):
    p = tmp_path / "weird.csv"
    p.write_text("a\n1\n", encoding="utf-8")
    con = build_from_csvs([("my data!", str(p))])  # -> my_data
    assert execute(con, "SELECT count(*) FROM my_data").rows[0][0] == 1


def test_build_from_duckdb_file(tmp_path):
    path = str(tmp_path / "u.duckdb")
    c = duckdb.connect(path)
    c.execute("CREATE TABLE t (a INTEGER, b VARCHAR)")
    c.execute("INSERT INTO t VALUES (1, 'x'), (2, 'y')")
    c.close()
    con = build_from_duckdb_file(path)
    assert execute(con, "SELECT count(*) FROM t").rows[0][0] == 2


def test_build_from_sqlite_file(tmp_path):
    import sqlite3

    path = str(tmp_path / "u.sqlite")
    s = sqlite3.connect(path)
    s.execute("CREATE TABLE items (id INTEGER, label TEXT)")
    s.executemany("INSERT INTO items VALUES (?, ?)", [(1, "a"), (2, "b"), (3, "c")])
    s.commit()
    s.close()
    try:
        con = build_from_sqlite_file(path)
    except Exception as e:  # sqlite extension may be unavailable offline
        pytest.skip(f"sqlite extension unavailable: {e}")
    assert execute(con, "SELECT count(*) FROM items").rows[0][0] == 3


@pytest.mark.parametrize("url", [
    "postgresql://u:p@localhost:5432/db",
    "postgresql://u:p@127.0.0.1/db",
    "mysql://u:p@10.0.0.5/db",
    "postgres://u:p@192.168.1.10/db",
    "postgresql://u:p@169.254.1.1/db",
])
def test_reject_internal_host(url):
    with pytest.raises(ValueError):
        _reject_internal_host(url)


def test_public_host_allowed():
    _reject_internal_host("postgresql://u:p@8.8.8.8:5432/db")  # must not raise


def test_detect_db_type():
    assert detect_db_type("postgresql://x/y") == "postgres"
    assert detect_db_type("postgres://x/y") == "postgres"
    assert detect_db_type("mysql://x/y") == "mysql"
    with pytest.raises(ValueError):
        detect_db_type("sqlite:///x.db")
