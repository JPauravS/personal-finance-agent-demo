# tests/test_tools.py
from app.tools.banking_tools import (
    get_transactions, get_categories, get_budgets, get_balance, TOOLS,
)
from app.models import Transaction


def test_get_transactions_returns_dataclasses():
    rows = get_transactions()
    assert rows and all(isinstance(r, Transaction) for r in rows)


def test_filter_by_month():
    may = get_transactions(month="2026-05")
    assert may and all(r.date.startswith("2026-05") for r in may)


def test_filter_by_category():
    food = get_transactions(category="food")
    assert food and all(r.category == "food" for r in food)


def test_filter_by_month_and_category():
    may_food = get_transactions(month="2026-05", category="food")
    total = sum(r.amount for r in may_food if r.type == "debit")
    assert total == 12000.0


def test_get_categories_unique_sorted():
    cats = get_categories()
    assert cats == sorted(set(cats))
    assert "food" in cats and "entertainment" in cats


def test_get_budgets():
    b = get_budgets()
    assert b["entertainment"] == 5000.0 and b["food"] == 15000.0


def test_get_balance():
    assert get_balance() == 45000.0


def test_tools_registry_schema():
    names = {t["name"] for t in TOOLS}
    assert names == {"get_transactions", "get_categories", "get_budgets", "get_balance"}
    for t in TOOLS:
        assert "description" in t and "parameters" in t   # LLM-shaped schema
