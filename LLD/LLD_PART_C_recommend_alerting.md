# LLD Part C — Recommendation + Alerting (Tasks 6–7)

> Read `LLD_INDEX.md` first. Frozen contracts + two-tier GATE protocol live there.
> Build atoms: RC (recommend), AL (alerting). Both consume the frozen `SpendingInsight` from Task 5 and the seeded `UserProfile` from Task 4. Per HLD §12.1 these two tasks form **parallel track 1** — they share no state and can be authored in either order.

**HLD coverage:** §5 (specialist agents: recommendation + alerting), §6 (tool layer: `get_budgets`, `get_balance`), §8 (agentic trace).

**Prerequisites already landed:** Task 1 (`app/models.py`), Task 2 (`app/data/transactions.json`), Task 3 (`app/tools/banking_tools.py`). Task 5 (`SpendingInsight` producer) is the upstream contract source but is **not** a hard dependency for these two agents — both tasks construct `SpendingInsight` inline in their tests and accept it as an argument at runtime.

---

## Task 6: Recommendation Agent (`app/agents/recommend.py`)

**Files:**
- Create: `app/agents/__init__.py` (empty, if not already present), `app/agents/recommend.py`
- Test: `tests/test_recommend.py`

Deterministic, rule-based savings recommender (HLD §5). It reduces **discretionary** spending only — never essentials. Anomaly-flagged categories are prioritized, then highest spend. At most 2 recommendations. Reduction percentage is driven by the user's `risk_pref`. The agent calls `get_budgets()` via the trace line (the budgets read is part of the agentic narrative even though the saving math is spend-driven), and returns typed `Recommendation` dataclasses.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recommend.py
from app.agents import recommend
from app.models import SpendingInsight, Anomaly, Recommendation, UserProfile


def _profile(risk_pref="balanced"):
    return UserProfile(
        name="Aarav", currency="₹", risk_pref=risk_pref,
        savings_goal=8000.0,
        budgets={"food": 15000.0, "entertainment": 5000.0,
                 "shopping": 12000.0, "travel": 6000.0,
                 "groceries": 8000.0, "utilities": 5000.0},
    )


def _insight(totals, anomalies=None):
    return SpendingInsight(
        month="2026-05",
        totals_by_category=totals,
        month_trend=[],
        anomalies=anomalies or [],
        summary_text="x",
    )


# Canonical demo insight: food is the +25% anomaly, shopping/travel/entertainment normal.
def _demo_insight():
    return _insight(
        {"food": 12000.0, "shopping": 8000.0, "travel": 3500.0,
         "entertainment": 4500.0, "groceries": 6200.0, "utilities": 3000.0},
        anomalies=[Anomaly("food", 12000.0, 9600.0, 25.0, "up 25%")],
    )


def test_balanced_food_recommendation_present_and_saving():
    recs = recommend.run(_demo_insight(), _profile("balanced"), trace=[])
    food = [r for r in recs if r.category == "food"]
    assert food, "expected a food recommendation"
    assert food[0].est_monthly_saving == 1800.0   # 12000 * 15%
    assert isinstance(food[0], Recommendation)


def test_food_appears_first_due_to_anomaly_priority():
    # shopping (8000) outspends food (12000)? No — food is higher AND anomaly,
    # so verify anomaly priority by making shopping the bigger spend.
    recs = recommend.run(
        _insight(
            {"food": 5000.0, "shopping": 9000.0, "travel": 3500.0},
            anomalies=[Anomaly("food", 5000.0, 4000.0, 25.0, "up 25%")],
        ),
        _profile("balanced"), trace=[],
    )
    assert recs[0].category == "food"   # anomaly beats higher-spend shopping


def test_aggressive_profile_saving():
    recs = recommend.run(_demo_insight(), _profile("aggressive"), trace=[])
    food = next(r for r in recs if r.category == "food")
    assert food.est_monthly_saving == 2400.0   # 12000 * 20%


def test_conservative_profile_saving():
    recs = recommend.run(_demo_insight(), _profile("conservative"), trace=[])
    food = next(r for r in recs if r.category == "food")
    assert food.est_monthly_saving == 1200.0   # 12000 * 10%


def test_only_essentials_returns_empty_and_traces_skip():
    trace = []
    recs = recommend.run(_insight({"groceries": 6000.0}), _profile(), trace=trace)
    assert recs == []
    assert any("skipped" in line for line in trace)


def test_at_most_two_recommendations():
    recs = recommend.run(_demo_insight(), _profile("balanced"), trace=[])
    assert len(recs) <= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recommend.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.agents.recommend'` (or `app.agents` if the package dir does not yet exist).

- [ ] **Step 3: Write minimal implementation**

```python
# app/agents/recommend.py
"""Recommendation agent (HLD §5).

Rule-based, deterministic savings recommender. Reduces DISCRETIONARY spend
only — essentials (groceries/utilities/transfers) are never touched. Anomaly
categories are prioritized over plain high-spend; reduction % is risk-driven.
Returns typed Recommendation dataclasses; appends a human-readable trace line.
"""
from app.models import Recommendation, SpendingInsight, UserProfile
from app.tools.banking_tools import get_budgets

DISCRETIONARY = {"food", "shopping", "travel", "entertainment"}   # essentials never reduced
REDUCTION_BY_RISK = {"conservative": 10, "balanced": 15, "aggressive": 20}   # percent


def run(insight: SpendingInsight, profile: UserProfile, trace: list) -> list:
    """Return up to 2 Recommendation objects for discretionary categories.

    Ordering: anomaly-flagged categories first, then by spend descending.
    Saving = round(spend * pct / 100, 0), where pct is risk-driven.
    """
    pct = REDUCTION_BY_RISK.get(profile.risk_pref, 15)
    anomaly_cats = {a.category for a in insight.anomalies}

    # Candidates = discretionary categories present in this month's totals.
    cands = [c for c in insight.totals_by_category if c in DISCRETIONARY]
    # Sort: anomaly categories first (False < True), then highest spend first.
    cands.sort(key=lambda c: (c not in anomaly_cats, -insight.totals_by_category[c]))

    if not cands:
        trace.append("Recommendation → no discretionary category to reduce; skipped")
        return []

    # get_budgets() is read as part of the agentic narrative (budget context).
    get_budgets()
    trace.append(
        f"Recommendation → get_budgets() → evaluating {len(cands)} discretionary categories"
    )

    recs = []
    for c in cands[:2]:   # top 2
        spend = insight.totals_by_category[c]
        saving = round(spend * pct / 100, 0)
        flagged = " (flagged anomaly)" if c in anomaly_cats else ""
        action = f"Reduce {c} spending by {pct}%"
        rationale = (
            f"{c} spend ₹{spend:.0f}{flagged}; a {pct}% cut frees "
            f"~₹{saving:.0f}/month toward your ₹{profile.savings_goal:.0f} goal."
        )
        recs.append(Recommendation(
            category=c, action=action,
            est_monthly_saving=saving, rationale=rationale,
        ))
    return recs
```

> If `app/agents/__init__.py` does not yet exist (Task 5 may not have created it), create it empty in this step so `app.agents` is importable.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_recommend.py -v`
Expected: PASS (6 tests). Manual check: balanced food 12000×15% = 1800.0 ✓; aggressive 12000×20% = 2400.0 ✓; conservative 12000×10% = 1200.0 ✓; essentials-only → `[]` with "skipped" trace ✓; food sorts ahead of higher-spend shopping by anomaly priority ✓; ≤2 recs ✓.

- [ ] **Step 5: Commit**

```bash
git add app/agents/__init__.py app/agents/recommend.py tests/test_recommend.py
git commit -m "feat: rule-based recommendation agent (risk-driven discretionary cuts)"
```

**GATE — Task 6**
- **Tier A:** `pytest tests/test_recommend.py -v` → 6 pass.
- **Tier B:** `pytest -q` → all green (models + data + tools + memory + spending + recommend). End-to-end behavior now holding: given the canonical May insight, the recommender deterministically surfaces the food anomaly first and quantifies a ₹1800/month balanced-profile saving — the savings-advice path the demo depends on now produces typed, gate-checked `Recommendation` output.

---

## Task 7: Alerting Agent (`app/agents/alerting.py`)

**Files:**
- Create: `app/agents/alerting.py`
- Test: `tests/test_alerting.py`

Budget-breach alerting agent (HLD §5). It scans each category's current-month spend against its budget (from `get_budgets()`): `>100%` → **critical**, `>=90%` → **warning**. Critical alerts sort before warnings. Categories with no budget are skipped. The agent also reads `get_balance()` as part of the agentic narrative. Returns typed `Alert` dataclasses.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_alerting.py
from app.agents import alerting
from app.models import SpendingInsight, Alert, UserProfile


def _profile():
    return UserProfile(
        name="Aarav", currency="₹", risk_pref="balanced",
        savings_goal=8000.0,
        budgets={"food": 15000.0, "entertainment": 5000.0,
                 "shopping": 12000.0, "travel": 6000.0,
                 "groceries": 8000.0, "utilities": 5000.0},
    )


def _insight(totals):
    return SpendingInsight(
        month="2026-05",
        totals_by_category=totals,
        month_trend=[],
        anomalies=[],
        summary_text="x",
    )


# Budgets come from the REAL get_budgets(): food 15000, entertainment 5000,
# shopping 12000, travel 6000.
def test_only_entertainment_near_budget_warns():
    insight = _insight({"food": 12000.0, "entertainment": 4500.0,
                        "shopping": 8000.0, "travel": 3500.0})
    alerts = alerting.run(insight, _profile(), trace=[])
    assert len(alerts) == 1
    assert alerts[0].severity == "warning"          # 4500 / 5000 = 90%
    assert alerts[0].category == "entertainment"
    assert isinstance(alerts[0], Alert)


def test_food_at_80pct_no_alert():
    # food 12000 / 15000 = 80% → below NEAR threshold → no alert
    alerts = alerting.run(_insight({"food": 12000.0}), _profile(), trace=[])
    assert alerts == []


def test_over_budget_is_critical():
    alerts = alerting.run(_insight({"entertainment": 6000.0}), _profile(), trace=[])
    assert len(alerts) == 1
    assert alerts[0].severity == "critical"          # 6000 / 5000 = 120%
    assert alerts[0].category == "entertainment"


def test_critical_sorts_before_warning():
    # entertainment 6000/5000 = 120% critical; travel 5800/6000 ≈ 97% warning
    alerts = alerting.run(
        _insight({"entertainment": 6000.0, "travel": 5800.0}),
        _profile(), trace=[],
    )
    assert [a.severity for a in alerts] == ["critical", "warning"]


def test_trace_mentions_get_budgets():
    trace = []
    alerting.run(_insight({"entertainment": 4500.0}), _profile(), trace=trace)
    assert any("get_budgets" in line for line in trace)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alerting.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.agents.alerting'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/agents/alerting.py
"""Alerting agent (HLD §5).

Scans current-month spend against per-category budgets (from get_budgets()):
  ratio > 1.0  → "critical" (over budget)
  ratio >= 0.90 → "warning"  (nearing budget)
Categories without a budget are skipped. Critical alerts sort before warnings.
Reads get_balance() as part of the agentic narrative. Returns typed Alerts.
"""
from app.models import Alert, SpendingInsight, UserProfile
from app.tools.banking_tools import get_budgets, get_balance

NEAR = 0.90   # >=90% budget → warning ; >1.0 → critical


def run(insight: SpendingInsight, profile: UserProfile, trace: list) -> list:
    """Return Alert objects (critical first, then warning) for breached budgets."""
    budgets = get_budgets()
    balance = get_balance()   # read for the agentic narrative / future cashflow checks
    trace.append(
        f"Alerting → get_budgets(), get_balance() → scanning "
        f"{len(insight.totals_by_category)} categories vs budget"
    )

    alerts = []
    for cat, spend in insight.totals_by_category.items():
        b = budgets.get(cat)
        if not b:
            continue
        ratio = spend / b
        if ratio > 1.0:
            alerts.append(Alert(
                "critical", cat,
                f"Over budget: {cat} ₹{spend:.0f} / ₹{b:.0f} ({ratio*100:.0f}%).",
            ))
        elif ratio >= NEAR:
            alerts.append(Alert(
                "warning", cat,
                f"Nearing budget: {cat} ₹{spend:.0f} / ₹{b:.0f} ({ratio*100:.0f}%).",
            ))

    # Stable sort: critical (0) before warning (1) before info (2).
    order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: order.get(a.severity, 3))
    return alerts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alerting.py -v`
Expected: PASS (5 tests). Manual check: entertainment 4500/5000 = 90% → exactly one warning ✓; food 12000/15000 = 80% → no alert ✓; entertainment 6000/5000 = 120% → critical ✓; critical sorts ahead of the 97% travel warning ✓; trace mentions `get_budgets` ✓.

- [ ] **Step 5: Commit**

```bash
git add app/agents/alerting.py tests/test_alerting.py
git commit -m "feat: budget-breach alerting agent (warning/critical, sorted)"
```

**GATE — Task 7**
- **Tier A:** `pytest tests/test_alerting.py -v` → 5 pass.
- **Tier B:** `pytest -q` → all green (models + data + tools + memory + spending + recommend + alerting). End-to-end behavior now holding: against the canonical May insight, the alerting agent deterministically raises exactly the entertainment near-budget warning (90%) and stays silent on food (80%) — the budget-watch path the demo depends on now produces typed, severity-sorted `Alert` output. With Tasks 6 and 7 both green, **parallel track 1** (the specialist agents consuming `SpendingInsight`) is complete and the orchestrator (Task 8) can now merge spending + recommendations + alerts into a single `FinalResponse`.

---

**End of Part C.** The recommendation and alerting specialists are complete and gate-checked. Proceed to `LLD_PART_D_orchestrator.md` (Task 8, the Planner that classifies intent and sequences Spending → Recommend → Alert into the final merged response).
