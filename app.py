"""Streamlit demo: NL -> SQL with a guardrail layer over a user-supplied DuckDB.

Users can query the bundled demo DB, upload CSV(s) / a SQLite or DuckDB file, or
attach a remote Postgres/MySQL database. Every source is loaded into a
session-scoped in-memory DuckDB; guardrails apply to all user queries.
"""
from __future__ import annotations

import os
import tempfile

import streamlit as st

from txtsql._openrouter import get_api_key
from txtsql.db import build_connection, execute
from txtsql.guardrails import validate
from txtsql.pipeline import answer
from txtsql.schema import allowed_tables, get_schema
from txtsql.sources import (
    build_from_connection_string,
    build_from_csvs,
    build_from_duckdb_file,
    build_from_sqlite_file,
)

st.set_page_config(page_title="Text-to-SQL with Guardrails", page_icon="🛡️", layout="wide")

EXAMPLES = [
    "How many customers are there?",
    "What are the top 3 products by total quantity sold?",
    "What is the total revenue from completed orders?",
    "Which customers from the USA have placed orders?",
    "How many orders are there per status?",
]


def _save_upload(uploaded) -> str:
    suffix = os.path.splitext(uploaded.name)[1] or ".dat"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded.getbuffer())
    tmp.flush()
    tmp.close()
    return tmp.name


def _set_source(con, label: str):
    st.session_state.con = con
    st.session_state.source_label = label
    st.session_state.pop("history", None)


if "con" not in st.session_state:
    _set_source(build_connection(), "Demo shop DB")

st.title("🛡️ Text-to-SQL with Guardrails")
st.caption(
    "Connect a database → ask in plain English → an LLM writes SQL → **guardrails "
    "validate it** (read-only · single-statement · table-allowlist · no file functions) "
    "→ it runs on DuckDB. Blocked queries never touch the data."
)

with st.sidebar:
    st.header("Data source")
    choice = st.radio(
        "Connect a database",
        ["Demo shop DB", "Upload CSV(s)", "Upload SQLite / DuckDB file", "Remote (Postgres/MySQL)"],
        label_visibility="collapsed",
    )

    if choice == "Demo shop DB":
        if st.button("Load demo"):
            _set_source(build_connection(), "Demo shop DB")

    elif choice == "Upload CSV(s)":
        ups = st.file_uploader("CSV file(s)", type=["csv"], accept_multiple_files=True)
        if st.button("Load CSV(s)") and ups:
            files = [(os.path.splitext(u.name)[0], _save_upload(u)) for u in ups]
            try:
                _set_source(build_from_csvs(files), f"{len(files)} CSV(s)")
                st.success("Loaded.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Load failed: {e}")

    elif choice == "Upload SQLite / DuckDB file":
        up = st.file_uploader("Database file", type=["sqlite", "db", "duckdb"])
        if st.button("Load file") and up:
            path = _save_upload(up)
            try:
                builder = build_from_duckdb_file if up.name.endswith(".duckdb") else build_from_sqlite_file
                _set_source(builder(path), up.name)
                st.success("Loaded.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Load failed: {e}")

    else:  # Remote
        st.warning(
            "⚠️ Public app — do **not** paste production credentials. Use a "
            "**read-only / test** database. The server connects to your host and "
            "imports up to 100k rows per table; private/internal hosts are refused."
        )
        conn = st.text_input(
            "Connection string",
            placeholder="postgresql://user:pass@host:5432/db",
            type="password",
        )
        if st.button("Connect") and conn:
            with st.spinner("Connecting + importing…"):
                try:
                    _set_source(build_from_connection_string(conn), "Remote DB")
                    st.success("Connected + imported.")
                except Exception as e:  # noqa: BLE001
                    st.error(f"Connect failed: {e}")

    st.divider()
    st.caption(f"Active source: **{st.session_state.source_label}**")
    schema = get_schema(st.session_state.con)
    st.subheader("Schema")
    if schema:
        for t, cols in schema.items():
            st.markdown(f"**{t}** — {', '.join(cols)}")
    else:
        st.info("No tables loaded.")
    st.divider()
    max_rows = int(st.slider("Max rows", 5, 500, 200, 5))
    retries = int(st.slider("Self-correction retries", 0, 2, 1))
    if not get_api_key():
        st.warning("Set `OPENROUTER_API_KEY` (env or `.streamlit/secrets.toml`). See README.")

con = st.session_state.con
allowed = allowed_tables(con)

tab_ask, tab_guard = st.tabs(["Ask in English", "🛡️ Guardrail playground"])

with tab_ask:
    if not schema:
        st.info("Load a data source from the sidebar to start asking questions.")
    question = st.text_input("Your question", placeholder=EXAMPLES[1])
    picked = st.selectbox("…or pick an example (demo DB)", [""] + EXAMPLES, index=0)
    q = (question or picked).strip()
    if st.button("Run", type="primary") and q:
        with st.spinner("Generating + validating SQL…"):
            try:
                r = answer(q, con, max_rows=max_rows, retries=retries)
            except Exception as e:  # noqa: BLE001
                st.error(f"LLM error: {e}")
                r = None
        if r is not None:
            st.code(r.sql or "(no SQL produced)", language="sql")
            if r.ok and r.result is not None:
                st.success(f"✅ Guardrails passed · executed in {r.attempts} attempt(s)")
                rows = [dict(zip(r.result.columns, row)) for row in r.result.rows]
                if rows:
                    st.dataframe(rows, use_container_width=True)
                else:
                    st.info("Query ran — no rows returned.")
                if r.result.truncated:
                    st.caption(f"Showing first {max_rows} rows (row cap).")
            else:
                st.error(f"🛡️ Blocked after {r.attempts} attempt(s): {r.reason}")

with tab_guard:
    st.caption(
        "Paste raw SQL to see the guardrail verdict directly (no LLM). Try a `DROP`, "
        "an `INSERT`, a multi-statement, an unknown table, `other_schema.t`, or "
        "`SELECT * FROM read_csv('/etc/passwd')`."
    )
    raw = st.text_area("SQL", value="SELECT 1 FROM customers; DROP TABLE customers", height=110)
    if st.button("Validate"):
        gr = validate(raw, allowed, max_rows)
        if gr.ok:
            st.success("✅ Passed guardrails")
            st.code(gr.safe_sql, language="sql")
            try:
                res = execute(con, gr.safe_sql, max_rows)
                rows = [dict(zip(res.columns, row)) for row in res.rows]
                if rows:
                    st.dataframe(rows, use_container_width=True)
                else:
                    st.info("No rows.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Execution error: {e}")
        else:
            st.error(f"🛡️ Blocked [rule: {gr.rule}] — {gr.reason}")
