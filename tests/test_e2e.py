# tests/test_e2e.py
"""End-to-end acceptance tests — the four HLD §11 demo scenarios driven
through the fully assembled Planner over real tools + real mock data.
No mocks. This is the system-level contract.
"""
from app.memory.store import SessionStore
from app.orchestrator import Planner
from app.models import (
    FinalResponse, SpendingInsight, Recommendation, Alert,
)


def _planner():
    return Planner(SessionStore())


# ─── Scenario 1: full pipeline ───────────────────────────────────────────────
def test_scenario1_improve_savings_full_pipeline():
    fr = _planner().handle("How can I improve my monthly savings?", "s1")

    assert isinstance(fr, FinalResponse)
    assert fr.answer_text

    assert isinstance(fr.insights, SpendingInsight)
    assert fr.insights.totals_by_category["food"] == 12000.0

    assert fr.recommendations, "expected non-empty recommendations"
    assert all(isinstance(r, Recommendation) for r in fr.recommendations)
    assert fr.recommendations[0].category == "food"
    assert fr.recommendations[0].est_monthly_saving == 1800.0

    assert any(
        a.severity == "warning" and a.category == "entertainment"
        for a in fr.alerts
    ), "expected an entertainment warning alert"

    trace = " | ".join(fr.plan_trace).lower()
    assert "spending" in trace
    assert "recommend" in trace
    assert "alert" in trace


# ─── Scenario 2: summarize (spending only, proactive alert fires) ────────────
def test_scenario2_summarize_spending_only_proactive_alert():
    fr = _planner().handle("Summarize my spending last month.", "s2")

    assert isinstance(fr.insights, SpendingInsight)
    assert fr.recommendations == []

    assert fr.alerts, "expected proactive alerts on the summarize path"
    assert all(isinstance(a, Alert) for a in fr.alerts)

    trace = " | ".join(fr.plan_trace).lower()
    assert "proactive" in trace, "expected a proactive-alerting trace line"


# ─── Scenario 3: why did I overspend (all three populated) ───────────────────
def test_scenario3_overspend_all_populated():
    fr = _planner().handle("Why did I overspend?", "s3")

    assert isinstance(fr.insights, SpendingInsight)
    assert fr.insights is not None
    assert fr.alerts, "expected alerts"
    assert fr.recommendations, "expected recommendations"

    food_anoms = [a for a in fr.insights.anomalies if a.category == "food"]
    assert food_anoms, "expected a food anomaly"
    assert food_anoms[0].pct_change == 25.0


# ─── Scenario 4: memory-backed follow-up (no recompute, same insight) ────────
def test_scenario4_memory_followup_reuses_cached_insight():
    store = SessionStore()
    planner = Planner(store)

    first = planner.handle("How can I improve my monthly savings?", "s4")
    cached_after_first = store.get_last_insight("s4")
    assert cached_after_first is first.insights

    second = planner.handle("what about food specifically?", "s4")

    trace = " | ".join(second.plan_trace).lower()
    assert ("no recompute" in trace) or ("reused cached insight" in trace), (
        f"expected a no-recompute trace line, got: {second.plan_trace}"
    )

    assert second.insights is first.insights
    assert store.get_last_insight("s4") is first.insights

    assert second.recommendations, "expected a food-specific recommendation"
    assert any(r.category == "food" for r in second.recommendations)


# ─── Greeting: no analysis ───────────────────────────────────────────────────
def test_greeting_returns_empty_payload():
    fr = _planner().handle("hi", "g1")
    assert isinstance(fr, FinalResponse)
    assert fr.insights is None
    assert fr.recommendations == []
    assert fr.alerts == []
    assert fr.answer_text
