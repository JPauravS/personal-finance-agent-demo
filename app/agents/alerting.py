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
