# LLD Part B — Spending Analysis Agent (Task 5)

> Read `LLD_INDEX.md` first. Frozen contracts + two-tier GATE protocol live there.
> Build atom: SP (spending analysis). This is the **in-depth, critical-path** agent — the long pole the rest of the pipeline (recommend, alerting, orchestrator) consumes. It depends on M (models), D (data), T (tools) from Part A.

**HLD coverage:** §4 (spending analysis agent), §5 (anomaly detection), §8 (trace).

**Design note — why a fixed threshold, not a z-score:** with a two-month window (current + prior) there is no distribution to estimate variance from; a z-score over n=1 prior point is meaningless and would produce unstable, undemo-able output. The spec deliberately pins a fixed `ANOMALY_THRESHOLD_PCT = 20.0` MoM rule. This keeps the demo deterministic (food +25% always trips; shopping 0% never does) and the logic auditable in the trace.

---

## Task 5: Spending Analysis Agent (`app/agents/spending.py`)

**Files:**
- Create: `app/agents/__init__.py` (empty), `app/agents/spending.py`
- Test: `tests/test_spending.py`

`spending.run(query, profile, trace)` fetches current + prior month transactions through the tool layer, aggregates **debits only** per category, computes month-over-month trend, flags any category up >20% MoM as an anomaly, and returns a typed `SpendingInsight`. It appends human-readable steps to `trace` so the orchestrator can surface the agentic reasoning (HLD §8).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_spending.py
from app.agents import spending
from app.models import SpendingInsight, CategoryTrend, Anomaly
from app.memory.store import SessionStore


def _profile():
    # Real seeded profile from the session store (Aarav, ₹, balanced, budgets pinned).
    return SessionStore().get_profile("test-sess")


def test_returns_spending_insight_for_current_month():
    trace = []
    out = spending.run("how's my spending?", _profile(), trace)
    assert isinstance(out, SpendingInsight)
    assert out.month == "2026-05"


def test_totals_exclude_credits():
    # The only "transfers" row is the salary credit; debit-only aggregation must drop it.
    trace = []
    out = spending.run("spending", _profile(), trace)
    assert "transfers" not in out.totals_by_category
    # food debits for 2026-05: 3000+3200+2900+2900 = 12000.0
    assert out.totals_by_category["food"] == 12000.0


def test_food_is_anomaly():
    # food 12000 (May) vs 9600 (Apr) → (12000-9600)/9600*100 = +25.0% → > 20.0 threshold.
    trace = []
    out = spending.run("spending", _profile(), trace)
    food = [a for a in out.anomalies if a.category == "food"]
    assert len(food) == 1
    assert food[0].pct_change == 25.0
    assert food[0].current == 12000.0 and food[0].prior == 9600.0
    assert "food" in food[0].note and "25" in food[0].note


def test_entertainment_not_anomaly_no_prior():
    # entertainment has no 2026-04 debits → prior missing → pct_change None → not an anomaly.
    trace = []
    out = spending.run("spending", _profile(), trace)
    ent = [t for t in out.month_trend if t.category == "entertainment"]
    assert len(ent) == 1
    assert ent[0].pct_change is None
    assert ent[0].is_anomaly is False
    assert ent[0].prior == 0.0
    assert not any(a.category == "entertainment" for a in out.anomalies)


def test_shopping_not_anomaly_zero_change():
    # shopping 8000 (May) vs 8000 (Apr) → 0.0% → not > 20.0 → not an anomaly.
    trace = []
    out = spending.run("spending", _profile(), trace)
    shop = [t for t in out.month_trend if t.category == "shopping"]
    assert len(shop) == 1
    assert shop[0].pct_change == 0.0
    assert shop[0].is_anomaly is False
    assert not any(a.category == "shopping" for a in out.anomalies)


def test_trend_is_category_trend_and_sorted_by_spend_desc():
    trace = []
    out = spending.run("spending", _profile(), trace)
    assert out.month_trend and all(isinstance(t, CategoryTrend) for t in out.month_trend)
    spends = [t.current for t in out.month_trend]
    assert spends == sorted(spends, reverse=True)   # highest spend first


def test_anomalies_are_anomaly_dataclasses():
    trace = []
    out = spending.run("spending", _profile(), trace)
    assert all(isinstance(a, Anomaly) for a in out.anomalies)
    # exactly one anomaly in the pinned dataset: food.
    assert {a.category for a in out.anomalies} == {"food"}


def test_summary_text_mentions_month_and_anomaly():
    trace = []
    out = spending.run("spending", _profile(), trace)
    assert "May" in out.summary_text
    assert "food" in out.summary_text
    assert "anomaly" in out.summary_text.lower()


def test_trace_populated():
    trace = []
    spending.run("spending", _profile(), trace)
    assert len(trace) >= 3
    assert "get_transactions(month=2026-05)" in trace[0]
    assert any("categorised" in line for line in trace)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_spending.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.agents'` (the `app/agents/` package and `spending` module do not exist yet).

- [ ] **Step 3: Write minimal implementation**

First create the empty package marker `app/agents/__init__.py`:

```python
# app/agents/__init__.py
```

Then `app/agents/spending.py`:

```python
# app/agents/spending.py
"""Spending Analysis agent — the in-depth, critical-path specialist (HLD §4–§5).

Aggregates DEBITS ONLY per category for the current month, compares against the
prior month, and flags any category whose spend rose more than a fixed
ANOMALY_THRESHOLD_PCT (20%) month-over-month. Returns a typed SpendingInsight and
appends human-readable steps to `trace` for the agentic-reasoning view.

Why a fixed threshold and not a z-score: with only two months of data there is no
distribution to estimate variance from. A fixed MoM rule is deterministic,
auditable, and demo-stable.
"""
from app.models import Transaction, CategoryTrend, Anomaly, SpendingInsight, UserProfile
from app.tools.banking_tools import get_transactions

CURRENT_MONTH = "2026-05"
PRIOR_MONTH = "2026-04"
ANOMALY_THRESHOLD_PCT = 20.0   # any category up >20% MoM is an anomaly (fixed, not z-score)

# Human-friendly month labels for summary_text.
_MONTH_LABEL = {"2026-05": "May", "2026-04": "April"}


def _debit_totals(rows: list[Transaction]) -> dict:
    """Sum positive debit amounts per category. Credits (e.g. salary) are excluded."""
    totals: dict = {}
    for r in rows:
        if r.type == "debit":
            totals[r.category] = totals.get(r.category, 0.0) + r.amount
    return totals


def run(query: str, profile: UserProfile, trace: list) -> SpendingInsight:
    # 1. fetch current + prior month transactions via the tool layer.
    cur = get_transactions(month=CURRENT_MONTH)
    trace.append(f"SpendingAnalysis → get_transactions(month={CURRENT_MONTH}) → {len(cur)} rows")
    prior = get_transactions(month=PRIOR_MONTH)
    trace.append(f"SpendingAnalysis → get_transactions(month={PRIOR_MONTH}) → {len(prior)} rows")

    # 2. aggregate DEBITS ONLY per category (credits like the salary transfer are excluded).
    cur_tot = _debit_totals(cur)
    prior_tot = _debit_totals(prior)

    # 3. month_trend: one CategoryTrend per current-month category, sorted by spend desc.
    month_trend: list = []
    anomalies: list = []
    for cat, cur_val in sorted(cur_tot.items(), key=lambda kv: kv[1], reverse=True):
        prior_val = prior_tot.get(cat)   # may be None when no prior-month spend
        if prior_val is not None and prior_val > 0:
            pct = round((cur_val - prior_val) / prior_val * 100, 1)
        else:
            pct = None
        is_anomaly = pct is not None and pct > ANOMALY_THRESHOLD_PCT
        prior_for_trend = prior_val if prior_val is not None else 0.0
        month_trend.append(CategoryTrend(cat, cur_val, prior_for_trend, pct, is_anomaly))

        # 4. anomalies mirror the flagged trends.
        #    food: (12000 - 9600) / 9600 * 100 = 25.0 > 20.0 → anomaly.
        #    shopping: (8000 - 8000) / 8000 * 100 = 0.0 → not an anomaly.
        if is_anomaly:
            anomalies.append(Anomaly(
                category=cat,
                current=cur_val,
                prior=prior_for_trend,
                pct_change=pct,
                note=f"{cat} up {pct}% vs prior month",
            ))

    # 5. summary_text: month, total, category count, top category, anomaly count.
    grand_total = sum(cur_tot.values())
    cur = profile.currency
    label = _MONTH_LABEL.get(CURRENT_MONTH, CURRENT_MONTH)
    parts = [f"{label} spending {cur}{grand_total:.0f} across {len(cur_tot)} categories."]
    if month_trend:
        top = month_trend[0]   # already sorted by spend desc
        parts.append(f"Top: {top.category} {cur}{top.current:.0f}.")
    if anomalies:
        a = anomalies[0]
        more = f" (+{len(anomalies) - 1} more)" if len(anomalies) > 1 else ""
        parts.append(f"{len(anomalies)} anomaly: {a.category} +{a.pct_change}%{more}.")
    else:
        parts.append("No anomalies.")
    summary_text = " ".join(parts)

    # 6. trace the categorisation outcome.
    trace.append(
        f"SpendingAnalysis → categorised {len(cur_tot)} categories, "
        f"{len(anomalies)} anomaly(ies)"
    )

    return SpendingInsight(
        month=CURRENT_MONTH,
        totals_by_category=cur_tot,
        month_trend=month_trend,
        anomalies=anomalies,
        summary_text=summary_text,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_spending.py -v`
Expected: PASS (9 tests). Arithmetic check, hand-verified against the pinned dataset (Part A, Task 2):
- food: May `3000+3200+2900+2900 = 12000.0`; Apr `2500+2400+2300+2400 = 9600.0`; `(12000-9600)/9600*100 = 25.0` → `> 20.0` → **anomaly** ✓
- shopping: May `5000+3000 = 8000.0`; Apr `4000+4000 = 8000.0`; `0.0%` → not anomaly ✓
- entertainment: May `1500×3 = 4500.0`; Apr none → `prior=None` → `pct_change=None`, `prior` field `0.0`, not anomaly ✓
- transfers: only row is a `credit` (salary 50000) → excluded by debit-only filter → absent from `totals_by_category` ✓
- trend sort: food 12000 > shopping 8000 > groceries 6200 > entertainment 4500 > travel 3500 > utilities 3000 → descending ✓

- [ ] **Step 5: Commit**

```bash
git add app/agents/__init__.py app/agents/spending.py tests/test_spending.py
git commit -m "feat: spending analysis agent (debit-only trend + >20% MoM anomaly)"
```

**GATE — Task 5**
- **Tier A:** `pytest tests/test_spending.py -v` → 9 pass.
- **Tier B:** `pytest -q` → all green (models + data + tools + memory + spending; no regression). End-to-end behavior now holding: the critical-path Spending Analysis agent runs through the real tool layer over the pinned dataset and deterministically produces the canonical `SpendingInsight` — `totals_by_category` excludes the salary credit, `food` is the sole anomaly at +25.0% MoM, `entertainment` (no prior) and `shopping` (0% change) are correctly non-anomalous, the `month_trend` is sorted by spend descending, and the `trace` carries the three agentic steps. This `SpendingInsight` is the frozen input the Recommendation (Task 6) and Alerting (Task 7) agents consume next.

---

**End of Part B.** The in-depth spending analysis long pole is complete. Proceed to `LLD_PART_C_recommend_alerting.md` (Tasks 6–7), which consume this `SpendingInsight` in parallel.
