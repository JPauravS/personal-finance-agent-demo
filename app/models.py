# app/models.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class Transaction:
    id: str
    date: str          # ISO "YYYY-MM-DD"
    merchant: str
    category: str      # lowercase canonical, e.g. "food"
    amount: float      # positive magnitude
    type: str          # "debit" | "credit"


@dataclass
class CategoryTrend:
    category: str
    current: float
    prior: float
    pct_change: Optional[float]   # None when no prior-month data
    is_anomaly: bool


@dataclass
class Anomaly:
    category: str
    current: float
    prior: float
    pct_change: float
    note: str


@dataclass
class SpendingInsight:
    month: str
    totals_by_category: dict      # {category: float}
    month_trend: list             # list[CategoryTrend]
    anomalies: list               # list[Anomaly]
    summary_text: str


@dataclass
class Recommendation:
    category: str
    action: str
    est_monthly_saving: float
    rationale: str


@dataclass
class Alert:
    severity: str      # "info" | "warning" | "critical"
    category: str
    message: str


@dataclass
class UserProfile:
    name: str
    currency: str        # "₹"
    risk_pref: str       # "conservative" | "balanced" | "aggressive"
    savings_goal: float  # monthly target amount
    budgets: dict        # {category: float}


@dataclass
class FinalResponse:
    answer_text: str
    insights: Optional[SpendingInsight]
    recommendations: list   # list[Recommendation]
    alerts: list            # list[Alert]
    plan_trace: list        # list[str] — human-readable agent/tool steps
