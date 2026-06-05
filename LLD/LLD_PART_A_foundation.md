# LLD Part A — Foundation (Tasks 1–4)

> Read `LLD_INDEX.md` first. Frozen contracts + two-tier GATE protocol live there.
> Build atoms: M (models), D (data), T (tools), MEM (memory). These are the dependency root — every later task imports them.

**HLD coverage:** §6 (tool layer), §7 (memory), §9 (structure), §10 (mock data).

---

## Task 1: Data Contracts (`app/models.py`)

**Files:**
- Create: `app/models.py`, `app/__init__.py` (empty), `conftest.py` (empty, repo root)
- Test: `tests/test_models.py`

> **Why `conftest.py` at the repo root:** every test imports `from app...`. With pytest's default `prepend` import mode and no root config, `pytest tests/...` inserts `tests/` (not the repo root) onto `sys.path`, so `import app` fails at collection. An **empty `conftest.py` at the repo root** makes pytest insert the root onto `sys.path`, so `app` is importable in every test. Create it once here.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from dataclasses import asdict
from app.models import (
    Transaction, CategoryTrend, Anomaly, SpendingInsight,
    Recommendation, Alert, UserProfile, FinalResponse,
)


def test_transaction_fields():
    t = Transaction(id="t1", date="2026-05-01", merchant="Zomato",
                    category="food", amount=300.0, type="debit")
    assert t.category == "food" and t.amount == 300.0


def test_final_response_nested_asdict():
    insight = SpendingInsight(
        month="2026-05",
        totals_by_category={"food": 12000.0},
        month_trend=[CategoryTrend("food", 12000.0, 9600.0, 25.0, True)],
        anomalies=[Anomaly("food", 12000.0, 9600.0, 25.0, "up 25%")],
        summary_text="Food up 25%.",
    )
    fr = FinalResponse(
        answer_text="hi",
        insights=insight,
        recommendations=[Recommendation("food", "cut 15%", 1800.0, "high spend")],
        alerts=[Alert("warning", "entertainment", "near budget")],
        plan_trace=["Planner → spending"],
    )
    d = asdict(fr)
    # asdict must recurse nested dataclasses into plain dicts
    assert d["insights"]["totals_by_category"]["food"] == 12000.0
    assert d["recommendations"][0]["est_monthly_saving"] == 1800.0
    assert d["alerts"][0]["severity"] == "warning"
    assert d["plan_trace"] == ["Planner → spending"]


def test_user_profile_budgets():
    p = UserProfile(name="Aarav", currency="₹", risk_pref="balanced",
                    savings_goal=8000.0, budgets={"food": 15000.0})
    assert p.budgets["food"] == 15000.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Write minimal implementation**

Create `app/__init__.py` (empty), an empty `conftest.py` at the repo root (no content needed — its mere presence puts the repo root on `sys.path`), and `app/models.py` with the **exact** frozen dataclasses from `LLD_INDEX.md` → "Frozen Contracts". Copy them verbatim (Transaction, CategoryTrend, Anomaly, SpendingInsight, Recommendation, Alert, UserProfile, FinalResponse).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py conftest.py app/models.py tests/test_models.py
git commit -m "feat: frozen data contracts (models.py) + pytest root path (conftest.py)"
```

**GATE — Task 1**
- **Tier A:** `pytest tests/test_models.py -v` → 3 pass.
- **Tier B:** `pytest -q` → all green (only models so far). End-to-end behavior now holding: typed contracts instantiate and serialize via `asdict` with full nesting.

---

## Task 2: Mock Dataset (`app/data/transactions.json`)

**Files:**
- Create: `app/data/transactions.json`
- Test: `tests/test_data.py`

This dataset is **pre-authored with verified sums** (HLD §10). Debit sums per category/month must match the pinned table exactly. One credit (salary) is included to verify debit-only filtering downstream.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data.py -v`
Expected: FAIL — `FileNotFoundError` on `app/data/transactions.json`.

- [ ] **Step 3: Write minimal implementation**

Create `app/data/transactions.json` with exactly these rows (sums hand-verified):

```json
[
  {"id": "t01", "date": "2026-04-03", "merchant": "Zomato", "category": "food", "amount": 2500.0, "type": "debit"},
  {"id": "t02", "date": "2026-04-11", "merchant": "Swiggy", "category": "food", "amount": 2400.0, "type": "debit"},
  {"id": "t03", "date": "2026-04-19", "merchant": "Dominos", "category": "food", "amount": 2300.0, "type": "debit"},
  {"id": "t04", "date": "2026-04-27", "merchant": "Cafe Coffee Day", "category": "food", "amount": 2400.0, "type": "debit"},
  {"id": "t05", "date": "2026-05-02", "merchant": "Zomato", "category": "food", "amount": 3000.0, "type": "debit"},
  {"id": "t06", "date": "2026-05-09", "merchant": "Swiggy", "category": "food", "amount": 3200.0, "type": "debit"},
  {"id": "t07", "date": "2026-05-17", "merchant": "Dominos", "category": "food", "amount": 2900.0, "type": "debit"},
  {"id": "t08", "date": "2026-05-25", "merchant": "Faasos", "category": "food", "amount": 2900.0, "type": "debit"},
  {"id": "t09", "date": "2026-05-06", "merchant": "BookMyShow", "category": "entertainment", "amount": 1500.0, "type": "debit"},
  {"id": "t10", "date": "2026-05-15", "merchant": "Netflix", "category": "entertainment", "amount": 1500.0, "type": "debit"},
  {"id": "t11", "date": "2026-05-24", "merchant": "PVR", "category": "entertainment", "amount": 1500.0, "type": "debit"},
  {"id": "t12", "date": "2026-04-08", "merchant": "Amazon", "category": "shopping", "amount": 4000.0, "type": "debit"},
  {"id": "t13", "date": "2026-04-22", "merchant": "Flipkart", "category": "shopping", "amount": 4000.0, "type": "debit"},
  {"id": "t14", "date": "2026-05-08", "merchant": "Amazon", "category": "shopping", "amount": 5000.0, "type": "debit"},
  {"id": "t15", "date": "2026-05-21", "merchant": "Myntra", "category": "shopping", "amount": 3000.0, "type": "debit"},
  {"id": "t16", "date": "2026-04-14", "merchant": "Uber", "category": "travel", "amount": 3500.0, "type": "debit"},
  {"id": "t17", "date": "2026-05-14", "merchant": "Ola", "category": "travel", "amount": 3500.0, "type": "debit"},
  {"id": "t18", "date": "2026-04-05", "merchant": "BigBasket", "category": "groceries", "amount": 3000.0, "type": "debit"},
  {"id": "t19", "date": "2026-04-20", "merchant": "DMart", "category": "groceries", "amount": 3000.0, "type": "debit"},
  {"id": "t20", "date": "2026-05-05", "merchant": "BigBasket", "category": "groceries", "amount": 3100.0, "type": "debit"},
  {"id": "t21", "date": "2026-05-20", "merchant": "DMart", "category": "groceries", "amount": 3100.0, "type": "debit"},
  {"id": "t22", "date": "2026-04-28", "merchant": "Electricity Board", "category": "utilities", "amount": 3000.0, "type": "debit"},
  {"id": "t23", "date": "2026-05-28", "merchant": "Electricity Board", "category": "utilities", "amount": 3000.0, "type": "debit"},
  {"id": "t24", "date": "2026-05-01", "merchant": "Acme Payroll", "category": "transfers", "amount": 50000.0, "type": "credit"}
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data.py -v`
Expected: PASS (2 tests). Manual arithmetic check: food Apr 2500+2400+2300+2400=9600 ✓; food May 3000+3200+2900+2900=12000 ✓; entertainment May 1500×3=4500 ✓; groceries May 3100+3100=6200 ✓.

- [ ] **Step 5: Commit**

```bash
git add app/data/transactions.json tests/test_data.py
git commit -m "feat: pinned mock transactions (deterministic demo data)"
```

**GATE — Task 2**
- **Tier A:** `pytest tests/test_data.py -v` → 2 pass.
- **Tier B:** `pytest -q` → all green (models + data). End-to-end behavior now holding: the dataset deterministically yields the +25% food anomaly and the 90% entertainment budget condition the demo depends on.

---

## Task 3: Tool Layer (`app/tools/banking_tools.py`)

**Files:**
- Create: `app/tools/__init__.py` (empty), `app/tools/banking_tools.py`
- Test: `tests/test_tools.py`

Typed mock tools + a JSON-serializable `TOOLS` registry (HLD §6). Agents call these; they never read JSON directly.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.tools.banking_tools'`.

- [ ] **Step 3: Write minimal implementation**

```python
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
    rows = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tools.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add app/tools/__init__.py app/tools/banking_tools.py tests/test_tools.py
git commit -m "feat: typed mock tool layer + TOOLS registry"
```

**GATE — Task 3**
- **Tier A:** `pytest tests/test_tools.py -v` → 8 pass.
- **Tier B:** `pytest -q` → all green (models + data + tools). End-to-end behavior now holding: agents have a typed, filterable data interface; `get_transactions(month="2026-05", category="food")` debit sum = 12000.0 confirms the tool→data path end-to-end.

---

## Task 4: Session Memory (`app/memory/store.py`)

**Files:**
- Create: `app/memory/__init__.py` (empty), `app/memory/store.py`
- Test: `tests/test_memory.py`

In-memory session store: profile (seeded), conversation history, `last_intent` + `last_insight` cache for follow-ups (HLD §7).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory.py
from app.memory.store import SessionStore
from app.models import UserProfile, SpendingInsight


def test_seeded_profile():
    s = SessionStore()
    p = s.get_profile("sess1")
    assert isinstance(p, UserProfile)
    assert p.name == "Aarav" and p.risk_pref == "balanced"
    assert p.budgets["entertainment"] == 5000.0


def test_profile_is_per_session_stable():
    s = SessionStore()
    assert s.get_profile("sess1") is s.get_profile("sess1")   # same object reused


def test_last_insight_roundtrip():
    s = SessionStore()
    assert s.get_last_insight("sess1") is None
    ins = SpendingInsight("2026-05", {"food": 12000.0}, [], [], "x")
    s.set_last_insight("sess1", ins)
    assert s.get_last_insight("sess1") is ins


def test_last_intent_roundtrip():
    s = SessionStore()
    assert s.get_last_intent("sess1") is None
    s.set_last_intent("sess1", "IMPROVE_SAVINGS")
    assert s.get_last_intent("sess1") == "IMPROVE_SAVINGS"


def test_history_append_and_read():
    s = SessionStore()
    s.append_turn("sess1", "user", "hi")
    s.append_turn("sess1", "assistant", "hello")
    h = s.get_history("sess1")
    assert h == [{"role": "user", "text": "hi"},
                 {"role": "assistant", "text": "hello"}]


def test_sessions_isolated():
    s = SessionStore()
    s.set_last_intent("a", "GREETING")
    assert s.get_last_intent("b") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.memory.store'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/memory/store.py
"""In-memory, per-session store: profile + history + follow-up cache (HLD §7).

Single-flight-per-session assumed (one in-flight turn per session_id).
Swap for Redis later; the interface stays.
"""
from typing import Optional
from app.models import UserProfile, SpendingInsight


def _seed_profile() -> UserProfile:
    return UserProfile(
        name="Aarav",
        currency="₹",
        risk_pref="balanced",
        savings_goal=8000.0,
        budgets={
            "food": 15000.0,
            "entertainment": 5000.0,
            "shopping": 12000.0,
            "travel": 6000.0,
            "groceries": 8000.0,
            "utilities": 5000.0,
        },
    )


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def _s(self, session_id: str) -> dict:
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "profile": _seed_profile(),
                "history": [],
                "last_intent": None,
                "last_insight": None,
            }
        return self._sessions[session_id]

    def get_profile(self, session_id: str) -> UserProfile:
        return self._s(session_id)["profile"]

    def get_last_insight(self, session_id: str) -> Optional[SpendingInsight]:
        return self._s(session_id)["last_insight"]

    def set_last_insight(self, session_id: str, insight: SpendingInsight) -> None:
        self._s(session_id)["last_insight"] = insight

    def get_last_intent(self, session_id: str) -> Optional[str]:
        return self._s(session_id)["last_intent"]

    def set_last_intent(self, session_id: str, intent: str) -> None:
        self._s(session_id)["last_intent"] = intent

    def append_turn(self, session_id: str, role: str, text: str) -> None:
        self._s(session_id)["history"].append({"role": role, "text": text})

    def get_history(self, session_id: str) -> list:
        return self._s(session_id)["history"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add app/memory/__init__.py app/memory/store.py tests/test_memory.py
git commit -m "feat: in-memory session store (profile, history, follow-up cache)"
```

**GATE — Task 4**
- **Tier A:** `pytest tests/test_memory.py -v` → 6 pass.
- **Tier B:** `pytest -q` → all green (models + data + tools + memory). End-to-end behavior now holding: the full foundation layer (contracts + data + tools + memory) is integrated and regression-free. The orchestrator and agents can now be built on a stable base.

---

**End of Part A.** The frozen-contract foundation is complete. Proceed to `LLD_PART_B_spending.md` (Task 5, the in-depth Spending Analysis agent — the critical-path long pole).
