# app/smoke.py
"""CLI fallback demo (HLD §15) — runs every HLD §11 demo scenario through the
fully assembled Planner and pretty-prints the complete FinalResponse for each.

This is the guaranteed deliverable if the WebUI wiring breaks: a reviewer can
replay the entire agentic pipeline from the terminal.

Run:  py -m app.smoke
"""
from __future__ import annotations

import sys
import io
from dataclasses import asdict

from app.memory.store import SessionStore
from app.orchestrator import Planner
from app.models import FinalResponse


SCENARIOS: list[tuple[str, str, str]] = [
    ("s1", "1. Improve savings (full pipeline)",
     "How can I improve my monthly savings?"),
    ("s2", "2. Summarize spending (spending only + proactive alert)",
     "Summarize my spending last month."),
    ("s3", "3. Why did I overspend? (spending → alert → recommend)",
     "Why did I overspend?"),
    ("s1", "4. Follow-up: food specifically (memory-backed, no recompute)",
     "what about food specifically?"),
    ("g1", "5. Greeting (no analysis)",
     "hi"),
]

_RULE = "=" * 72
_SUB = "-" * 72


def _fmt_insight(ins) -> str:
    if ins is None:
        return "  insights: None"
    d = asdict(ins)
    lines = [
        f"  insights.month: {d['month']}",
        f"  insights.totals_by_category: {d['totals_by_category']}",
        f"  insights.anomalies: {len(d['anomalies'])}",
    ]
    for a in d["anomalies"]:
        lines.append(
            f"      - {a['category']}: {a['prior']} -> {a['current']} "
            f"({a['pct_change']:+.1f}%) {a['note']}"
        )
    lines.append(f"  insights.summary_text: {d['summary_text']}")
    return "\n".join(lines)


def _print_response(title: str, query: str, fr: FinalResponse) -> None:
    print(_RULE)
    print(title)
    print(_SUB)
    print(f"  user      : {query}")
    print(f"  answer    : {fr.answer_text}")
    print()
    print("  plan_trace:")
    for i, step in enumerate(fr.plan_trace, 1):
        print(f"      {i:>2}. {step}")
    print()
    print(_fmt_insight(fr.insights))
    print()
    print(f"  recommendations: {len(fr.recommendations)}")
    for r in fr.recommendations:
        rd = asdict(r)
        print(f"      - [{rd['category']}] {rd['action']} "
              f"(save ₹{rd['est_monthly_saving']:.0f}) — {rd['rationale']}")
    print()
    print(f"  alerts: {len(fr.alerts)}")
    for a in fr.alerts:
        ad = asdict(a)
        print(f"      - [{ad['severity']}] {ad['category']}: {ad['message']}")
    print()


def run() -> list[FinalResponse]:
    """Execute every scenario through one shared Planner and return the
    list of FinalResponse objects (in scenario order). Pure function +
    side-effect printing so tests can assert on the return value.
    """
    store = SessionStore()
    planner = Planner(store)
    responses: list[FinalResponse] = []
    for session_id, title, query in SCENARIOS:
        fr = planner.handle(query, session_id)
        _print_response(title, query, fr)
        responses.append(fr)
    print(_RULE)
    print(f"Done — {len(responses)} scenarios replayed through the Planner.")
    print(_RULE)
    return responses


def main() -> int:
    # Force UTF-8 stdout so the ₹ symbol prints on Windows consoles (cp1252).
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # py3.7+
    except (AttributeError, io.UnsupportedOperation):
        pass
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
