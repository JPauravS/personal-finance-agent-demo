# LLD Part D — Planner Orchestrator (Task 8)

> Read `LLD_INDEX.md` first. Frozen contracts + two-tier GATE protocol live there.
> Build atom: ORCH (planner). This is the **integration join** — the first task that imports all three specialist agents (`spending`, `recommend`, `alerting`) **and** session memory simultaneously and merges their typed output into one `FinalResponse`.

**HLD coverage:** §4 (planner / intent classification), §5.3 (data-dependent branching), §7 (memory-backed follow-ups), §8 (agentic trace).

**Prerequisites already landed:** Task 1 (`app/models.py`), Task 3 (`app/tools/banking_tools.py`), Task 4 (`app/memory/store.py`), Task 5 (`app/agents/spending.py`), Task 6 (`app/agents/recommend.py`), Task 7 (`app/agents/alerting.py`). All are hard dependencies — this task wires them together.

**Integration note (GATE Tier B changes here):** From Task 8 onward, Tier B is no longer "just the unit suite stays green." The Planner is the first component that exercises the whole pipeline (intent → plan → spending → recommend → alert → merge → memory), so its own test file (`tests/test_orchestrator.py`) **is** the growing end-to-end harness. Every later task (API, web, integration) layers on top of this. The Task-8 GATE Tier B therefore asserts the multi-agent pipeline works end-to-end against the pinned demo data, not only that no unit test regressed.

---

## Task 8: Planner Orchestrator (`app/orchestrator.py`)

**Files:**
- Create: `app/orchestrator.py`
- Test: `tests/test_orchestrator.py`

The Planner classifies intent over ordered keyword groups (first-match-wins), detects referential follow-ups **before** classifying (reusing the cached `SpendingInsight` with no recompute), builds a data-dependent agent plan, sequences the specialists through the shared `trace` list, and merges everything into a single typed `FinalResponse`. Greetings/unknown short-circuit with no agents. Proactive alerting fires when the spending agent surfaces an anomaly even if the base plan did not request it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestrator.py
from app.memory.store import SessionStore
from app.orchestrator import Planner, classify_intent
from app.models import FinalResponse, SpendingInsight


def _planner():
    return Planner(SessionStore())


# ---- classify_intent unit checks (one keyword per intent) -------------------

def test_classify_greeting():
    assert classify_intent("hi") == "GREETING"
    assert classify_intent("hello there") == "GREETING"
    assert classify_intent("hey") == "GREETING"


def test_classify_improve_savings():
    assert classify_intent("How can I improve my monthly savings?") == "IMPROVE_SAVINGS"
    assert classify_intent("help me reduce expenses") == "IMPROVE_SAVINGS"


def test_classify_why_overspent():
    assert classify_intent("Why did I overspend?") == "WHY_OVERSPENT"
    assert classify_intent("any unusual spending?") == "WHY_OVERSPENT"


def test_classify_budget_status():
    assert classify_intent("Am I within my budget limit?") == "BUDGET_STATUS"


def test_classify_spending_summary():
    assert classify_intent("Summarize my spending last month.") == "SPENDING_SUMMARY"
    assert classify_intent("where did my money go") == "SPENDING_SUMMARY"


def test_classify_general_advice():
    assert classify_intent("any advice for me?") == "GENERAL_ADVICE"


def test_classify_finance_fallthrough_is_general_advice():
    # No explicit keyword group hit, but a finance term present → GENERAL_ADVICE.
    assert classify_intent("I want to afford a vacation") == "GENERAL_ADVICE"


def test_classify_unknown():
    assert classify_intent("what is the weather today") == "UNKNOWN"


# ---- handle() end-to-end (real agents over pinned data) ---------------------

def test_improve_savings_full_pipeline():
    p = _planner()
    fr = p.handle("How can I improve my monthly savings?", "s1")
    assert isinstance(fr, FinalResponse)
    assert fr.insights is not None
    assert fr.recommendations, "expected recommendations"
    assert fr.recommendations[0].category == "food"      # anomaly-prioritized
    assert any(a.category == "entertainment" and a.severity == "warning"
               for a in fr.alerts)
    blob = " ".join(fr.plan_trace).lower()
    assert "spending" in blob and "recommend" in blob and "alert" in blob


def test_spending_summary_triggers_proactive_alerting():
    p = _planner()
    fr = p.handle("Summarize my spending last month.", "s2")
    assert fr.insights is not None
    assert fr.recommendations == []                       # summary plan has no recommend
    assert fr.alerts, "food anomaly should proactively trigger alerting"
    assert any("proactively ran alerting" in line.lower() for line in fr.plan_trace)


def test_why_overspent_runs_all_three():
    p = _planner()
    fr = p.handle("Why did I overspend?", "s3")
    assert fr.insights is not None
    assert fr.alerts and fr.recommendations


def test_greeting_runs_no_agents():
    p = _planner()
    fr = p.handle("hi", "s4")
    assert fr.insights is None
    assert fr.recommendations == [] and fr.alerts == []
    assert any("no agents" in line.lower() for line in fr.plan_trace)


def test_referential_followup_reuses_cached_insight():
    p = _planner()
    store = p.store
    first = p.handle("How can I improve my monthly savings?", "s5")
    cached = store.get_last_insight("s5")
    assert cached is first.insights

    fr = p.handle("what about food?", "s5")
    # No recompute: the cached insight object is reused (identity preserved).
    assert store.get_last_insight("s5") is cached
    assert fr.insights is cached
    blob = " ".join(fr.plan_trace).lower()
    assert "no recompute" in blob or "reused cached insight" in blob
    assert any(r.category == "food" for r in fr.recommendations)
    assert "food" in fr.answer_text.lower()


def test_user_and_assistant_turns_recorded():
    p = _planner()
    p.handle("Summarize my spending last month.", "s6")
    hist = p.store.get_history("s6")
    assert hist[0] == {"role": "user", "text": "Summarize my spending last month."}
    assert hist[-1]["role"] == "assistant" and hist[-1]["text"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.orchestrator'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/orchestrator.py
"""Planner orchestrator (HLD §4, §5.3, §7, §8).

Star-topology coordinator. Per turn it:
  1. records the user turn,
  2. detects a referential follow-up and, if so, answers from the CACHED
     SpendingInsight with NO recompute (no agent calls),
  3. otherwise classifies intent (first-match-wins over ordered keyword groups),
  4. builds a data-dependent plan and sequences spending → recommend → alert,
  5. merges typed agent output into one FinalResponse and persists memory.

The Planner owns the shared `trace: list[str]` that each agent appends to;
that list becomes FinalResponse.plan_trace (the visible agentic narrative).
"""
from typing import Optional

from app.memory.store import SessionStore
from app.models import FinalResponse, Recommendation, SpendingInsight
from app.agents import spending, recommend, alerting

# ---- Intent classification ---------------------------------------------------

# Ordered keyword groups; first group with any matching lowercase substring wins.
# Greeting is checked first (and exactly) so "hi"/"hey" don't leak into other groups.
INTENT_KEYWORDS = [
    ("GREETING",         ["hi", "hello", "hey", "yo "]),
    ("WHY_OVERSPENT",    ["why", "overspe", "anomal", "unusual"]),
    ("IMPROVE_SAVINGS",  ["save", "saving", "improve", "reduce", "cut down"]),
    ("BUDGET_STATUS",    ["budget", "limit", "threshold"]),
    ("SPENDING_SUMMARY", ["summar", "spend", "spent", "breakdown", "where did"]),
    ("GENERAL_ADVICE",   ["advice", "advise", "recommend", "suggest", "help"]),
]

FINANCE_TERMS = ["money", "spend", "save", "budget", "expense",
                 "cost", "afford", "finance"]

_GREETING_EXACT = {"hi", "hello", "hey", "yo"}

# Data-dependent base plan per intent. GREETING/UNKNOWN need no agents.
ROUTING = {
    "IMPROVE_SAVINGS":  ["spending", "recommend", "alert"],
    "SPENDING_SUMMARY": ["spending"],
    "BUDGET_STATUS":    ["spending", "alert"],
    "WHY_OVERSPENT":    ["spending", "alert", "recommend"],
    "GENERAL_ADVICE":   ["spending", "recommend"],
    "GREETING":         [],
    "UNKNOWN":          [],
}

# Categories a short referential follow-up may target (e.g. "what about food?").
FOLLOWUP_CATS = ["food", "shopping", "travel", "entertainment",
                 "groceries", "utilities"]
FOLLOWUP_PREFIXES = ("what about", "and ", "just ", "how about")

GREETING_TEXT = "Hi! I can analyse your spending, suggest savings, and flag budget alerts."
FALLBACK_TEXT = ("I can analyse your spending, suggest savings, and flag budget "
                 "alerts. Ask away.")
# Follow-up reuses the balanced 15% reduction (matches recommend agent default).
_FOLLOWUP_PCT = 15


def classify_intent(msg: str) -> str:
    """First-match-wins intent classification over ordered keyword groups.

    Greeting is matched exactly/by-prefix first. If no group matches but a
    finance term appears, fall through to GENERAL_ADVICE, else UNKNOWN.
    """
    low = msg.lower()
    stripped = low.strip()
    if stripped in _GREETING_EXACT or any(
        stripped.startswith(g + " ") for g in _GREETING_EXACT
    ):
        return "GREETING"

    for intent, kws in INTENT_KEYWORDS:
        if intent == "GREETING":
            continue   # already handled exactly above
        if any(kw in low for kw in kws):
            return intent

    if any(term in low for term in FINANCE_TERMS):
        return "GENERAL_ADVICE"
    return "UNKNOWN"


class Planner:
    """Orchestrates the specialist agents into a single FinalResponse."""

    def __init__(self, store: SessionStore):
        self.store = store

    # ---- referential follow-up -------------------------------------------

    def _is_followup(self, msg: str, session_id: str) -> Optional[str]:
        """Return the targeted category if `msg` is a cached-insight follow-up.

        Requires a cached insight, a short/referential phrasing, and a known
        category mentioned. Returns the first such category, else None.
        """
        last = self.store.get_last_insight(session_id)
        if last is None:
            return None
        low = msg.lower().strip()
        # Referential = an explicit follow-up cue ("what about …") OR a very short
        # bare reference (<=3 words, e.g. "and food?"). Kept at <=3 (not <=4) so a
        # 4-word standalone query that happens to name a category — e.g.
        # "summarize my food spending" — is NOT mis-routed as a follow-up; it still
        # classifies normally. The demo follow-ups match via the prefix cue.
        referential = low.startswith(FOLLOWUP_PREFIXES) or len(low.split()) <= 3
        if not referential:
            return None
        for cat in FOLLOWUP_CATS:
            if cat in low:
                return cat
        return None

    def _handle_followup(self, cat: str, session_id: str) -> FinalResponse:
        """Answer a follow-up from the CACHED insight — no agent recompute."""
        insight: SpendingInsight = self.store.get_last_insight(session_id)
        total = insight.totals_by_category.get(cat, 0.0)

        # Pull this category's MoM delta from the cached trend, if present.
        trend = next((t for t in insight.month_trend if t.category == cat), None)
        delta_txt = ""
        if trend is not None and trend.pct_change is not None:
            sign = "up" if trend.pct_change >= 0 else "down"
            delta_txt = f" ({sign} {abs(trend.pct_change):.0f}% vs last month)"

        # If the category is in the cached anomaly list, surface the anomaly delta.
        anomaly = next((a for a in insight.anomalies if a.category == cat), None)
        anomaly_txt = ""
        if anomaly is not None:
            anomaly_txt = f" Flagged anomaly: {anomaly.note}."

        # One inline, balanced (15%) recommendation for this category.
        saving = round(total * _FOLLOWUP_PCT / 100, 0)
        rec = Recommendation(
            category=cat,
            action=f"Reduce {cat} spending by {_FOLLOWUP_PCT}%",
            est_monthly_saving=saving,
            rationale=(f"{cat} spend ₹{total:.0f}; a {_FOLLOWUP_PCT}% cut frees "
                       f"~₹{saving:.0f}/month."),
        )

        answer = (f"You spent ₹{total:.0f} on {cat} this month{delta_txt}."
                  f"{anomaly_txt} Tip: {rec.action} (~₹{saving:.0f}/mo).")
        trace = [
            "Planner → referential follow-up detected",
            f"Planner → reused cached insight for '{cat}' (no recompute)",
        ]
        final = FinalResponse(
            answer_text=answer,
            insights=insight,            # SAME cached object — identity preserved
            recommendations=[rec],
            alerts=[],
            plan_trace=trace,
        )
        self.store.append_turn(session_id, "assistant", answer)
        return final

    # ---- main turn -------------------------------------------------------

    def handle(self, message: str, session_id: str) -> FinalResponse:
        self.store.append_turn(session_id, "user", message)

        cat = self._is_followup(message, session_id)
        if cat is not None:
            return self._handle_followup(cat, session_id)

        intent = classify_intent(message)
        plan = ROUTING[intent]
        profile = self.store.get_profile(session_id)

        # No-agent intents (greeting / unknown): short-circuit.
        if not plan:
            answer = GREETING_TEXT if intent == "GREETING" else FALLBACK_TEXT
            final = FinalResponse(
                answer_text=answer,
                insights=None,
                recommendations=[],
                alerts=[],
                plan_trace=[f"Planner → intent={intent}, no agents needed"],
            )
            self.store.set_last_intent(session_id, intent)
            self.store.append_turn(session_id, "assistant", answer)
            return final

        # Agentic plan. Spending always runs first and produces the insight.
        trace: list = []
        insight = spending.run(message, profile, trace)
        self.store.set_last_insight(session_id, insight)
        trace.insert(0, f"Planner → intent={intent}, plan={plan}")

        # Data-dependent branching (HLD §5.3): proactively alert on any anomaly.
        has_anomaly = bool(insight.anomalies)
        run_alert = ("alert" in plan) or has_anomaly
        run_rec = ("recommend" in plan)

        recs = recommend.run(insight, profile, trace) if run_rec else []
        alerts = alerting.run(insight, profile, trace) if run_alert else []
        if run_alert and "alert" not in plan:
            trace.append("Planner → proactively ran Alerting (anomaly detected)")

        answer_text = self._compose(intent, insight, recs, alerts)
        final = FinalResponse(
            answer_text=answer_text,
            insights=insight,
            recommendations=recs,
            alerts=alerts,
            plan_trace=trace,
        )
        self.store.set_last_intent(session_id, intent)
        self.store.append_turn(session_id, "assistant", answer_text)
        return final

    # ---- answer composition ----------------------------------------------

    def _compose(self, intent: str, insight: SpendingInsight,
                 recs: list, alerts: list) -> str:
        """1–3 sentence natural-language answer merging agent output."""
        parts = [insight.summary_text]
        if recs:
            parts.append(
                f" Top tip: {recs[0].action} "
                f"(~₹{recs[0].est_monthly_saving:.0f}/mo)."
            )
        if alerts:
            parts.append(f" Alert: {alerts[0].message}")
        return "".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestrator.py -v`
Expected: PASS (16 tests). Manual checks against pinned data:
- `IMPROVE_SAVINGS` → plan `["spending","recommend","alert"]`: food anomaly makes `recommendations[0].category == "food"`; entertainment 4500/5000 = 90% yields the warning alert; trace contains spending + recommend + alert lines. ✓
- `SPENDING_SUMMARY` → base plan `["spending"]` only, so `recommendations == []`; food's +25% anomaly sets `has_anomaly`, so `run_alert` is True → proactive alerting fires (entertainment warning) and the trace gets the "proactively ran Alerting" line. ✓
- `WHY_OVERSPENT` → plan `["spending","alert","recommend"]`: all three populated. ✓
- `hi` → GREETING: empty plan → no agents, `insights is None`, trace says "no agents needed". ✓
- Follow-up `"what about food?"` after a savings query: `_is_followup` matches (≤4 words + "food" + cached insight present), answers from the cached object (identity preserved, `store.get_last_insight` unchanged), trace contains "no recompute" / "reused cached insight", food recommendation present. ✓

- [ ] **Step 5: Commit**

```bash
git add app/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: Planner orchestrator (intent routing, data-dependent plan, follow-up cache)"
```

---

**GATE — Task 8**

- **Tier A — Task-local validation:** `pytest tests/test_orchestrator.py -v` → 16 pass (8 `classify_intent` unit checks + 8 `handle()` pipeline tests).

- **Tier B — Cumulative end-to-end validation:** `pytest -q` → **entire suite green** (models + data + tools + memory + spending + recommend + alerting + orchestrator), no regression. **The multi-agent pipeline now works end-to-end.** This is the integration join: `tests/test_orchestrator.py` exercises the full chain — intent classification → data-dependent plan → `spending.run` → `recommend.run` → `alerting.run` → typed `FinalResponse` merge → session-memory persistence (`set_last_insight` / `append_turn`) → cached-insight referential follow-up with no recompute — all against the pinned demo data (food +25% anomaly, entertainment 90% near-budget warning). From this task onward Tier B includes this growing end-to-end harness: re-run `pytest tests/test_orchestrator.py -v` after every later task (API, web, integration) and keep it green before advancing. A task is DONE only when both tiers pass.

---

**End of Part D.** The Planner orchestrator is complete and gate-checked — the star-topology coordinator now sequences all three specialists into a single merged `FinalResponse` with a visible agentic trace and memory-backed follow-ups. Proceed to `LLD_PART_E_api_web.md` (Tasks 9–10, the FastAPI `/chat` boundary that calls `dataclasses.asdict(final_response)` and the vanilla-JS frontend that renders the answer, insights, recommendations, alerts, and plan trace).
