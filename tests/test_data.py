# tests/test_data.py
import json
from collections import defaultdict
from pathlib import Path

DATA = Path("app/data/transactions.json")


def _sums():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    by = defaultdict(float)
    for r in rows:
        if r["type"] == "debit":
            by[(r["category"], r["date"][:7])] += r["amount"]
    return by


def test_pinned_sums():
    s = _sums()
    assert s[("food", "2026-04")] == 9600.0
    assert s[("food", "2026-05")] == 12000.0
    assert s[("entertainment", "2026-05")] == 4500.0
    assert ("entertainment", "2026-04") not in s     # no prior → not an anomaly
    assert s[("shopping", "2026-04")] == 8000.0
    assert s[("shopping", "2026-05")] == 8000.0
    assert s[("travel", "2026-05")] == 3500.0
    assert s[("groceries", "2026-05")] == 6200.0
    assert s[("utilities", "2026-05")] == 3000.0


def test_has_credit_row():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    assert any(r["type"] == "credit" for r in rows)


def test_embedded_data_matches_json():
    # The Cloudflare-edge fallback (app/data/transactions_data.py) must never
    # drift from the canonical JSON. Regenerate the .py if this fails.
    from app.data.transactions_data import TRANSACTIONS
    assert TRANSACTIONS == json.loads(DATA.read_text(encoding="utf-8"))


def test_load_falls_back_to_embedded_when_file_missing(monkeypatch):
    # Simulate the edge: the JSON file is unreadable → _load() uses the embedded
    # module and still returns the full pinned dataset.
    from pathlib import Path as _P
    from app.tools import banking_tools
    monkeypatch.setattr(banking_tools, "_DATA_PATH", _P("does/not/exist.json"))
    rows = banking_tools._load()
    assert len(rows) == 24
    may_food = sum(r.amount for r in rows
                   if r.category == "food" and r.date.startswith("2026-05")
                   and r.type == "debit")
    assert may_food == 12000.0
