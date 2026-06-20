"""Streamlit demo: NL -> SQL with a guardrail layer over a real DuckDB."""
from __future__ import annotations

import streamlit as st

from txtsql._openrouter import get_api_key
from txtsql.db import build_connection, execute
from txtsql.guardrails import validate
from txtsql.pipeline import answer
from txtsql.schema import allowed_tables, get_schema

st.set_page_config(page_title="Text-to-SQL with Guardrails", page_icon="🛡️", layout="wide")


@st.cache_resource
def _con():
    return build_connection()


con = _con()
schema = get_schema(con)
allowed = allowed_tables(con)

EXAMPLES = [
    "How many customers are there?",
    "What are the top 3 products by total quantity sold?",
    "What is the total revenue from completed orders?",
    "Which customers from the USA have placed orders?",
    "How many orders are there per status?",
]

st.title("🛡️ Text-to-SQL with Guardrails")
st.caption(
    "Ask in plain English → an LLM writes SQL → **guardrails validate it** "
    "(read-only · single-statement · table-allowlist · no file functions) → it runs "
    "on a real DuckDB. Blocked queries never touch the database."
)

with st.sidebar:
    st.header("Database schema")
    for t, cols in schema.items():
        st.markdown(f"**{t}** — {', '.join(cols)}")
    st.divider()
    max_rows = int(st.slider("Max rows", 5, 500, 200, 5))
    retries = int(st.slider("Self-correction retries", 0, 2, 1))
    if not get_api_key():
        st.warning("Set `OPENROUTER_API_KEY` (env or `.streamlit/secrets.toml`). See README.")

tab_ask, tab_guard = st.tabs(["Ask in English", "🛡️ Guardrail playground"])

with tab_ask:
    question = st.text_input("Your question", placeholder=EXAMPLES[1])
    picked = st.selectbox("…or pick an example", [""] + EXAMPLES, index=0)
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
        "an `INSERT`, a multi-statement, an unknown table, or "
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
