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
