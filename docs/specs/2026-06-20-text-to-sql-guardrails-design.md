# Text-to-SQL with Guardrails — Design

> Date: 2026-06-20 · Status: approved · Author: Sai Teja Mothukuri

## Purpose

A natural-language → SQL system over a real (DuckDB) database whose differentiator
is a **guardrail layer**, not the generation. An LLM proposes SQL from a
schema-aware prompt; before anything runs, the SQL is parsed and validated
(`sqlglot`) to be a single read-only `SELECT` over allowlisted tables with no
file-access functions, then executed with a row cap. A small execution-accuracy
eval (gold NL/SQL pairs) proves the system answers correctly, not just plausibly.

Portfolio goal: demonstrate production AI/ML judgment for an Applied-AI/LLM role —
guardrails, observability, and evaluation rigor — built on the candidate's
genuine SQL/data edge. Companion to the live Hybrid-Search-RAG and Semantic-Cache
projects.

## Non-Goals

- Not Spider/BIRD-scale benchmarking (saturated, multi-day plumbing). A compact,
  honest gold set demonstrates the eval discipline.
- No write/DDL support — read-only by design.
- No ag/multi-agent planning; a single generate → validate → execute → (optional
  narrate) loop with one self-correction retry on guardrail failure.

## Conventions (inherited from P1/P3)

- OpenRouter via OpenAI SDK for chat (`nvidia/nemotron-3-nano-30b-a3b:free`).
  (Embeddings are not needed here.) `:free` suffix required.
- Key: `OPENROUTER_API_KEY` env → `.streamlit/secrets.toml`; `load_dotenv()` for `.env`.
- Per-project `.venv`. Streamlit + Docker (HF Spaces, port 7860). Secrets gitignored.
- `huggingface_hub` only in `requirements-deploy.txt` (lean runtime image).

## Architecture

```
text-to-sql-guardrails/
├── app.py                       # Streamlit demo
├── txtsql/
│   ├── _openrouter.py           # shared key + client (+ load_dotenv)
│   ├── db.py                    # build DuckDB from data/*.sql; row-capped execute
│   ├── schema.py                # introspect schema -> prompt text + table allowlist
│   ├── guardrails.py            # sqlglot validation (the core IP)
│   ├── nl2sql.py                # schema-aware NL->SQL + SQL extraction
│   └── eval.py                  # gold NL/SQL pairs + execution-accuracy
├── data/{schema.sql, seed.sql}  # deterministic demo "shop" DB
├── scripts/{smoke.py, deploy_hf.py}
├── tests/{test_guardrails.py, test_db.py, test_eval.py}
├── Dockerfile, requirements.txt, requirements-deploy.txt, README.md
```

### Guardrails (`guardrails.py`) — the differentiator

`validate(sql, allowed_tables, max_rows) -> GuardrailResult(ok, reason, safe_sql, rule)`,
in order (first failure wins, each maps to a named `rule`):
1. **parse** — `sqlglot.parse(sql, read="duckdb")`; unparseable → block.
2. **single_statement** — exactly one statement (blocks `SELECT 1; DROP ...`).
3. **read_only** — root node ∈ {Select, With, Union, Intersect, Except, Subquery};
   and no write/DDL node anywhere (Insert/Update/Delete/Drop/Create/Alter/Command/
   Copy/Set/Merge/Pragma). Node set built defensively via `getattr(exp, name)`.
4. **forbidden_func** — deny file-access functions (`read_csv`, `read_parquet`,
   `read_json`, `glob`, `read_text`, `install`, `load`, …).
5. **table_allowlist** — every referenced table ∈ schema tables; else block (names the table).
6. pass → `safe_sql` = cleaned original; row cap enforced at execution (fetch ≤ max_rows).

### Data flow

```
question ─▶ nl2sql.generate_sql (schema-aware) ─▶ guardrails.validate
   ─ blocked ─▶ one self-correction retry (feed the reason back) ─▶ re-validate
   ─ ok ─▶ db.execute (row-capped) ─▶ results (+ optional NL summary)
```

### Eval (`eval.py`)

`execution_match(con, pred_sql, gold_sql)` compares **result sets** (order-insensitive,
stringified) — execution accuracy, not string match. `run_eval(con, generate_fn)`
loops ~8 gold questions → generate → validate → execute → match → accuracy + per-item.

## Error handling

- Missing key → clear `RuntimeError`; app shows a banner.
- LLM/parse/execution errors surfaced to UI; DB never mutated (read-only enforced).
- Guardrail block → reason shown; one retry feeding the reason back to the model.

## Testing

- `tests/test_guardrails.py` (offline): SELECT ok; INSERT/UPDATE/DELETE/DROP/ALTER
  blocked; multi-statement blocked; unknown-table blocked; known-table ok; file-fn
  blocked; markdown-fence SQL extraction; row-cap at execution.
- `tests/test_db.py` (offline): DB builds; a known SELECT returns expected rows;
  fetch cap caps rows.
- `tests/test_eval.py` (offline): `execution_match` true for equivalent queries,
  false for different ones.
- `scripts/smoke.py` (needs key): end-to-end NL→SQL→guardrail→exec on real questions
  + prints eval accuracy.

## Delivery

GitHub repo `github.com/saiteja007-mv/text-to-sql-guardrails` + README (badges,
diagram, guardrail table, how-it-works). One-command HF deploy script (deferrable).
