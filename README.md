<h1 align="center">🛡️ Text-to-SQL with Guardrails</h1>

<p align="center">
  <b>Ask your database in plain English — safely.</b><br>
  An LLM writes the SQL; a guardrail layer validates it before a single row is read.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/DB-DuckDB-FFF000?logo=duckdb&logoColor=black" alt="DuckDB">
  <img src="https://img.shields.io/badge/SQL%20parser-sqlglot-16A34A" alt="sqlglot">
  <img src="https://img.shields.io/badge/LLM-OpenRouter%20(free)-6E56CF" alt="OpenRouter">
  <img src="https://img.shields.io/badge/License-MIT-22C55E" alt="MIT License">
</p>

---

A natural-language → SQL system whose point is the **guardrail layer**, not the
generation. The LLM proposes SQL from a schema-aware prompt; before anything runs,
the query is **parsed with `sqlglot`** and checked to be a single **read-only
`SELECT`** over **allowlisted tables** with **no file-access functions**. Only then
does it execute on a real DuckDB, with a row cap. A small **execution-accuracy
eval** proves it answers correctly — not just plausibly.

```
question ─▶ LLM writes SQL ─▶ guardrails (sqlglot)
                                  ├─ parse ok? single statement?
                                  ├─ read-only SELECT? (no DML/DDL)
                                  ├─ tables ∈ allowlist?
                                  └─ no read_csv/glob/… ?
                       blocked ◀──┤ (feed reason back, retry once)
                          ok  ───▶ DuckDB execute (row-capped) ─▶ results
```

## 🛡️ The guardrails

| Rule | Blocks | How |
|---|---|---|
| `single_statement` | `SELECT 1; DROP TABLE t` | `sqlglot.parse` returns >1 statement |
| `not_readonly` | INSERT / UPDATE / DELETE / DROP / ALTER / CREATE … | root node not a query + write-node scan |
| `unknown_table` | `SELECT * FROM secrets` | table not in the schema allowlist (CTE names excluded) |
| `forbidden_func` | `read_csv` / `read_parquet` / `glob` / `install` … | AST scan + string backstop |
| `empty` / `parse` | blank or unparseable input | — |

Validation is **parse-based, not regex** — so it isn't fooled by comments, casing,
or whitespace tricks. Every block returns a named `rule` and a human reason, and on
a block the pipeline feeds the reason back to the model for **one self-correction**.

## ✨ Features

- **Schema-aware NL→SQL** over a real (DuckDB) database, fully offline-seeded.
- **Read-only by construction** — write/DDL can never reach the DB.
- **Row/cost cap** at fetch time; **self-correction retry** on block or exec error.
- **Execution-accuracy eval** — gold NL/SQL pairs scored by result-set match (order-insensitive), not string similarity.
- **Guardrail playground** in the UI: paste raw SQL, see exactly why it's allowed or blocked.
- Cloud LLM via free OpenRouter; no GPU, no local model weights.

## 🖥️ Run locally

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

streamlit run app.py        # http://localhost:8501
```

Tests (offline — DuckDB + sqlglot, no network) and the headless smoke check:

```powershell
python -m pytest -q          # 27 tests: guardrails, db, eval, pipeline
python scripts/smoke.py      # needs a key: NL->SQL + injection block + eval accuracy
```

### 🔑 OpenRouter API key

Free key at <https://openrouter.ai/keys>. Use any one of:
`.streamlit/secrets.toml` (`OPENROUTER_API_KEY = "sk-or-v1-..."`), a `.env` file, or
the `OPENROUTER_API_KEY` env var. Override the model with `OPENROUTER_MODEL`.

## 🚀 Deploy (Hugging Face Spaces, free)

```powershell
pip install -r requirements-deploy.txt   # huggingface_hub (deploy-only)
python scripts/deploy_hf.py --space-name text-to-sql-guardrails
```

(Needs a HF token via `huggingface-cli login` or `HF_TOKEN`.) The `Dockerfile` runs
Streamlit on port 7860.

## 🔧 How it works

| Stage | File | What it does |
|---|---|---|
| DB | `txtsql/db.py` | Build in-memory DuckDB from `data/*.sql`; row-capped execute |
| Schema | `txtsql/schema.py` | Introspect tables/columns → prompt text + allowlist |
| Generate | `txtsql/nl2sql.py` | Schema-aware OpenRouter prompt + SQL extraction |
| **Guardrails** | `txtsql/guardrails.py` | `sqlglot` validation (the core IP) |
| Pipeline | `txtsql/pipeline.py` | generate → validate → execute, with self-correction retry |
| Eval | `txtsql/eval.py` | Gold NL/SQL pairs scored by execution accuracy |
| UI | `app.py` | Ask-in-English tab + guardrail playground |

## 🗂️ Demo database

A small, deterministic **shop** schema seeded from `data/`:
`customers`, `products`, `orders`, `order_items` — enough for joins and aggregations.

## ⚖️ Honest notes / scale path

- The eval is a compact gold set (8 questions) to demonstrate **execution-accuracy
  discipline**, not a Spider/BIRD leaderboard run — that's the natural next step.
- In-memory DuckDB seeded at startup; swap `data/*.sql` for your own schema.
- Guardrails are deliberately conservative (deny-by-default tables + functions).
  A statement-level timeout is a sensible next hardening step.

## 📄 License

MIT
