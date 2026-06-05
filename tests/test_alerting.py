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


def test_only_entertainment_near_budget_warns():
    insight = _insight({"food": 12000.0, "entertainment": 4500.0,
                        "shopping": 8000.0, "travel": 3500.0})
    alerts = alerting.run(insight, _profile(), trace=[])
    assert len(alerts) == 1
    assert alerts[0].severity == "warning"          # 4500 / 5000 = 90%
    assert alerts[0].category == "entertainment"
    assert isinstance(alerts[0], Alert)


def test_food_at_80pct_no_alert():
    alerts = alerting.run(_insight({"food": 12000.0}), _profile(), trace=[])
    assert alerts == []


def test_over_budget_is_critical():
    alerts = alerting.run(_insight({"entertainment": 6000.0}), _profile(), trace=[])
    assert len(alerts) == 1
    assert alerts[0].severity == "critical"          # 6000 / 5000 = 120%
    assert alerts[0].category == "entertainment"


def test_critical_sorts_before_warning():
    alerts = alerting.run(
        _insight({"entertainment": 6000.0, "travel": 5800.0}),
        _profile(), trace=[],
    )
    assert [a.severity for a in alerts] == ["critical", "warning"]


def test_trace_mentions_get_budgets():
    trace = []
    alerting.run(_insight({"entertainment": 4500.0}), _profile(), trace=trace)
    assert any("get_budgets" in line for line in trace)
