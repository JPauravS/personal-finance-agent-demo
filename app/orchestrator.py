# app/orchestrator.py
"""Planner orchestrator (HLD §4, §5.3, §7, §8).

Star-topology coordinator. Per turn it:
  1. records the user turn,
  2. detects a referential follow-up and, if so, answers from the CACHED
     SpendingInsight with NO recompute (no agent calls),
  3. otherwise classifies intent (first-match-wins over ordered keyword groups),
  4. builds a data-dependent plan and sequences spending → recommend → alert,
  5. merges typed agent output into one FinalResponse and persists memory.

The Planner owns the shared `trace: list[str]` that each agent appends to;
that list becomes FinalResponse.plan_trace (the visible agentic narrative).
"""
from typing import Optional

from app.memory.store import SessionStore
from app.models import FinalResponse, Recommendation, SpendingInsight
from app.agents import spending, recommend, alerting

# ---- Intent classification ---------------------------------------------------

INTENT_KEYWORDS = [
    ("GREETING",         ["hi", "hello", "hey", "yo "]),
    ("WHY_OVERSPENT",    ["why", "overspe", "anomal", "unusual"]),
    ("IMPROVE_SAVINGS",  ["save", "saving", "improve", "reduce", "cut down"]),
    ("BUDGET_STATUS",    ["budget", "limit", "threshold"]),
    ("SPENDING_SUMMARY", ["summar", "spend", "spent", "breakdown", "where did"]),
    ("GENERAL_ADVICE",   ["advice", "advise", "recommend", "suggest", "help"]),
]

FINANCE_TERMS = ["money", "spend", "save", "budget", "expense",
                 "cost", "afford", "finance"]

_GREETING_EXACT = {"hi", "hello", "hey", "yo"}

ROUTING = {
    "IMPROVE_SAVINGS":  ["spending", "recommend", "alert"],
    "SPENDING_SUMMARY": ["spending"],
    "BUDGET_STATUS":    ["spending", "alert"],
    "WHY_OVERSPENT":    ["spending", "alert", "recommend"],
    "GENERAL_ADVICE":   ["spending", "recommend"],
    "GREETING":         [],
    "UNKNOWN":          [],
}

FOLLOWUP_CATS = ["food", "shopping", "travel", "entertainment",
                 "groceries", "utilities"]
FOLLOWUP_PREFIXES = ("what about", "and ", "just ", "how about")

GREETING_TEXT = "Hi! I can analyse your spending, suggest savings, and flag budget alerts."
FALLBACK_TEXT = ("I can analyse your spending, suggest savings, and flag budget "
                 "alerts. Ask away.")
_FOLLOWUP_PCT = 15


def classify_intent(msg: str) -> str:
    """First-match-wins intent classification over ordered keyword groups.

    Greeting is matched exactly/by-prefix first. If no group matches but a
    finance term appears, fall through to GENERAL_ADVICE, else UNKNOWN.
    """
    low = msg.lower()
    stripped = low.strip()
    if stripped in _GREETING_EXACT or any(
        stripped.startswith(g + " ") for g in _GREETING_EXACT
    ):
        return "GREETING"

    for intent, kws in INTENT_KEYWORDS:
        if intent == "GREETING":
            continue   # already handled exactly above
        if any(kw in low for kw in kws):
            return intent

    if any(term in low for term in FINANCE_TERMS):
        return "GENERAL_ADVICE"
    return "UNKNOWN"


class Planner:
    """Orchestrates the specialist agents into a single FinalResponse."""

    def __init__(self, store: SessionStore):
        self.store = store

    # ---- referential follow-up -------------------------------------------

    def _is_followup(self, msg: str, session_id: str) -> Optional[str]:
        """Return the targeted category if `msg` is a cached-insight follow-up."""
        last = self.store.get_last_insight(session_id)
        if last is None:
            return None
        low = msg.lower().strip()
        referential = low.startswith(FOLLOWUP_PREFIXES) or len(low.split()) <= 3
        if not referential:
            return None
        for cat in FOLLOWUP_CATS:
            if cat in low:
                return cat
        return None

    def _handle_followup(self, cat: str, session_id: str) -> FinalResponse:
        """Answer a follow-up from the CACHED insight — no agent recompute."""
        insight: SpendingInsight = self.store.get_last_insight(session_id)
        total = insight.totals_by_category.get(cat, 0.0)

        trend = next((t for t in insight.month_trend if t.category == cat), None)
        delta_txt = ""
        if trend is not None and trend.pct_change is not None:
            sign = "up" if trend.pct_change >= 0 else "down"
            delta_txt = f" ({sign} {abs(trend.pct_change):.0f}% vs last month)"

        anomaly = next((a for a in insight.anomalies if a.category == cat), None)
        anomaly_txt = ""
        if anomaly is not None:
            anomaly_txt = f" Flagged anomaly: {anomaly.note}."

        saving = round(total * _FOLLOWUP_PCT / 100, 0)
        rec = Recommendation(
            category=cat,
            action=f"Reduce {cat} spending by {_FOLLOWUP_PCT}%",
            est_monthly_saving=saving,
            rationale=(f"{cat} spend ₹{total:.0f}; a {_FOLLOWUP_PCT}% cut frees "
                       f"~₹{saving:.0f}/month."),
        )

        answer = (f"You spent ₹{total:.0f} on {cat} this month{delta_txt}."
                  f"{anomaly_txt} Tip: {rec.action} (~₹{saving:.0f}/mo).")
        trace = [
            "Planner → referential follow-up detected",
            f"Planner → reused cached insight for '{cat}' (no recompute)",
        ]
        final = FinalResponse(
            answer_text=answer,
            insights=insight,            # SAME cached object — identity preserved
            recommendations=[rec],
            alerts=[],
            plan_trace=trace,
        )
        self.store.append_turn(session_id, "assistant", answer)
        return final

    # ---- main turn -------------------------------------------------------

    def handle(self, message: str, session_id: str) -> FinalResponse:
        self.store.append_turn(session_id, "user", message)

        cat = self._is_followup(message, session_id)
        if cat is not None:
            return self._handle_followup(cat, session_id)

        intent = classify_intent(message)
        plan = ROUTING[intent]
        profile = self.store.get_profile(session_id)

        if not plan:
            answer = GREETING_TEXT if intent == "GREETING" else FALLBACK_TEXT
            final = FinalResponse(
                answer_text=answer,
                insights=None,
                recommendations=[],
                alerts=[],
                plan_trace=[f"Planner → intent={intent}, no agents needed"],
            )
            self.store.set_last_intent(session_id, intent)
            self.store.append_turn(session_id, "assistant", answer)
            return final

        trace: list = []
        insight = spending.run(message, profile, trace)
        self.store.set_last_insight(session_id, insight)
        trace.insert(0, f"Planner → intent={intent}, plan={plan}")

        has_anomaly = bool(insight.anomalies)
        run_alert = ("alert" in plan) or has_anomaly
        run_rec = ("recommend" in plan)

        recs = recommend.run(insight, profile, trace) if run_rec else []
        alerts = alerting.run(insight, profile, trace) if run_alert else []
        if run_alert and "alert" not in plan:
            trace.append("Planner → proactively ran Alerting (anomaly detected)")

        answer_text = self._compose(intent, insight, recs, alerts)
        final = FinalResponse(
            answer_text=answer_text,
            insights=insight,
            recommendations=recs,
            alerts=alerts,
            plan_trace=trace,
        )
        self.store.set_last_intent(session_id, intent)
        self.store.append_turn(session_id, "assistant", answer_text)
        return final

    # ---- answer composition ----------------------------------------------

    def _compose(self, intent: str, insight: SpendingInsight,
                 recs: list, alerts: list) -> str:
        """1–3 sentence natural-language answer merging agent output."""
        parts = [insight.summary_text]
        if recs:
            parts.append(
                f" Top tip: {recs[0].action} "
                f"(~₹{recs[0].est_monthly_saving:.0f}/mo)."
            )
        if alerts:
            parts.append(f" Alert: {alerts[0].message}")
        return "".join(parts)
