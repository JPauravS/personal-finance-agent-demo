# app/tools/banking_tools.py
"""Mock banking tool layer. Typed, LLM-function-call-shaped.

Agents call these tools; they never touch the JSON store directly.
"""
import json
from pathlib import Path
from app.models import Transaction

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "transactions.json"

_BUDGETS = {
    "food": 15000.0,
    "entertainment": 5000.0,
    "shopping": 12000.0,
    "travel": 6000.0,
    "groceries": 8000.0,
    "utilities": 5000.0,
}
_BALANCE = 45000.0


def _load() -> list[Transaction]:
    # Prefer the canonical JSON file (used locally + by tests). At the edge
    # (Cloudflare Python Workers) arbitrary data files are NOT bundled into the
    # Pyodide FS, so fall back to the embedded Python module, which IS bundled.
    try:
        rows = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError):
        from app.data.transactions_data import TRANSACTIONS as rows
    return [Transaction(**r) for r in rows]


def get_transactions(month: str | None = None, category: str | None = None) -> list[Transaction]:
    """Return transactions, optionally filtered by month ('YYYY-MM') and/or category."""
    rows = _load()
    if month:
        rows = [r for r in rows if r.date.startswith(month)]
    if category:
        rows = [r for r in rows if r.category == category]
    return rows


def get_categories() -> list[str]:
    """Return the sorted, unique category catalog."""
    return sorted({r.category for r in _load()})


def get_budgets() -> dict:
    """Return per-category monthly budgets."""
    return dict(_BUDGETS)


def get_balance() -> float:
    """Return current account balance."""
    return _BALANCE


# JSON-serializable registry — exactly what an LLM tool-calling loop consumes.
TOOLS = [
    {"name": "get_transactions",
     "description": "Fetch transactions, optionally filtered by month (YYYY-MM) and category.",
     "parameters": {"month": "string|null", "category": "string|null"}},
    {"name": "get_categories",
     "description": "List all spending categories.",
     "parameters": {}},
    {"name": "get_budgets",
     "description": "Per-category monthly budget limits.",
     "parameters": {}},
    {"name": "get_balance",
     "description": "Current account balance.",
     "parameters": {}},
]
