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
