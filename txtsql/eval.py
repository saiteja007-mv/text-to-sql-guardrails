"""Tiny execution-accuracy eval: gold NL/SQL pairs scored by result-set match
(order-insensitive), not string similarity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .db import QueryResult, execute
from .guardrails import validate

# Gold questions with a known-correct reference SQL over the demo "shop" DB.
GOLD = [
    {"q": "How many customers are there?",
     "sql": "SELECT count(*) AS n FROM customers"},
    {"q": "List all distinct product categories.",
     "sql": "SELECT DISTINCT category FROM products ORDER BY category"},
    {"q": "How many orders have the status completed?",
     "sql": "SELECT count(*) AS n FROM orders WHERE status = 'completed'"},
    {"q": "Which product has the highest price? Return its name.",
     "sql": "SELECT name FROM products ORDER BY price DESC LIMIT 1"},
    {"q": "List the names of customers from the USA.",
     "sql": "SELECT name FROM customers WHERE country = 'USA' ORDER BY name"},
    {"q": "How many products are in the Electronics category?",
     "sql": "SELECT count(*) AS n FROM products WHERE category = 'Electronics'"},
    {"q": "What is the total revenue (quantity times unit_price) across all order items?",
     "sql": "SELECT sum(quantity * unit_price) AS revenue FROM order_items"},
    {"q": "How many orders did each customer place? Return customer name and the count.",
     "sql": "SELECT c.name, count(*) AS orders FROM customers c "
            "JOIN orders o ON o.customer_id = c.customer_id GROUP BY c.name ORDER BY c.name"},
]


def _normalize(qr: QueryResult):
    return sorted(tuple(str(x) for x in row) for row in qr.rows)


def execution_match(con, pred_sql: str, gold_sql: str, max_rows: int = 1000) -> bool:
    """True if both queries return the same result set (order-insensitive)."""
    try:
        pred = execute(con, pred_sql, max_rows)
        gold = execute(con, gold_sql, max_rows)
    except Exception:  # noqa: BLE001 - a broken prediction simply fails to match
        return False
    return _normalize(pred) == _normalize(gold)


@dataclass
class EvalItem:
    question: str
    gold_sql: str
    pred_sql: str
    ok: bool
    blocked: bool
    reason: str


def run_eval(
    con,
    generate_fn: Callable[[str], str],
    allowed: set[str],
    max_rows: int = 1000,
) -> dict:
    """Run the gold set through generate -> guardrail -> execute -> match.

    ``generate_fn(question) -> sql`` (the LLM, or a stub for offline runs)."""
    items: list[EvalItem] = []
    for g in GOLD:
        pred = generate_fn(g["q"])
        gr = validate(pred, allowed, max_rows)
        if not gr.ok:
            items.append(EvalItem(g["q"], g["sql"], pred, False, True, gr.reason))
            continue
        ok = execution_match(con, gr.safe_sql, g["sql"], max_rows)
        items.append(EvalItem(g["q"], g["sql"], gr.safe_sql, ok, False, "ok" if ok else "result mismatch"))
    n = len(items)
    accuracy = sum(1 for i in items if i.ok) / n if n else 0.0
    blocked = sum(1 for i in items if i.blocked)
    return {"accuracy": accuracy, "n": n, "blocked": blocked, "items": items}
