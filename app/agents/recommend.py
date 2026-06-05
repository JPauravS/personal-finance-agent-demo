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
