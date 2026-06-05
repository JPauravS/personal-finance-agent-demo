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
    assert d["insights"]["totals_by_category"]["food"] == 12000.0
    assert d["recommendations"][0]["est_monthly_saving"] == 1800.0
    assert d["alerts"][0]["severity"] == "warning"
    assert d["plan_trace"] == ["Planner → spending"]


def test_user_profile_budgets():
    p = UserProfile(name="Aarav", currency="₹", risk_pref="balanced",
                    savings_goal=8000.0, budgets={"food": 15000.0})
    assert p.budgets["food"] == 15000.0
