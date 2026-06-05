# tests/test_spending.py
from app.agents import spending
from app.models import SpendingInsight, CategoryTrend, Anomaly
from app.memory.store import SessionStore


def _profile():
    return SessionStore().get_profile("test-sess")


def test_returns_spending_insight_for_current_month():
    trace = []
    out = spending.run("how's my spending?", _profile(), trace)
    assert isinstance(out, SpendingInsight)
    assert out.month == "2026-05"


def test_totals_exclude_credits():
    trace = []
    out = spending.run("spending", _profile(), trace)
    assert "transfers" not in out.totals_by_category
    assert out.totals_by_category["food"] == 12000.0


def test_food_is_anomaly():
    trace = []
    out = spending.run("spending", _profile(), trace)
    food = [a for a in out.anomalies if a.category == "food"]
    assert len(food) == 1
    assert food[0].pct_change == 25.0
    assert food[0].current == 12000.0 and food[0].prior == 9600.0
    assert "food" in food[0].note and "25" in food[0].note


def test_entertainment_not_anomaly_no_prior():
    trace = []
    out = spending.run("spending", _profile(), trace)
    ent = [t for t in out.month_trend if t.category == "entertainment"]
    assert len(ent) == 1
    assert ent[0].pct_change is None
    assert ent[0].is_anomaly is False
    assert ent[0].prior == 0.0
    assert not any(a.category == "entertainment" for a in out.anomalies)


def test_shopping_not_anomaly_zero_change():
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
    assert spends == sorted(spends, reverse=True)


def test_anomalies_are_anomaly_dataclasses():
    trace = []
    out = spending.run("spending", _profile(), trace)
    assert all(isinstance(a, Anomaly) for a in out.anomalies)
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
