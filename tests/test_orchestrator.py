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
    assert classify_intent("Why did I overspent?") == "WHY_OVERSPENT"
    assert classify_intent("any unusual spending?") == "WHY_OVERSPENT"


def test_classify_budget_status():
    assert classify_intent("Am I within my budget limit?") == "BUDGET_STATUS"


def test_classify_spending_summary():
    assert classify_intent("Summarize my spending last month.") == "SPENDING_SUMMARY"
    assert classify_intent("where did my money go") == "SPENDING_SUMMARY"


def test_classify_general_advice():
    assert classify_intent("any advice for me?") == "GENERAL_ADVICE"


def test_classify_finance_fallthrough_is_general_advice():
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
    fr = p.handle("Why did I overspent?", "s3")
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
