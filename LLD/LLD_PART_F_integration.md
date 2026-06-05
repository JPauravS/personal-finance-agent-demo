# LLD Part F — Integration, Demo & Smoke (Task 11)

> Read `LLD_INDEX.md` first. Frozen contracts + two-tier GATE protocol live there.
> Build atoms: INT + SMOKE (end-to-end integration test, runnable CLI fallback demo, README). This is the **final task** — it integrates everything Tasks 1–10 produced and is the last no-regression gate for the whole system.

**HLD coverage:** §11 (the four demo scenarios), §15 (Run & Demo deliverable — install, uvicorn, browser, pytest, CLI fallback), R11 (deliverables: prototype, source, workflow, demo).

**Prerequisites already landed:** the entire system. Task 1 (`app/models.py`), Task 2 (`app/data/transactions.json`), Task 3 (`app/tools/banking_tools.py`), Task 4 (`app/memory/store.py`), Task 5 (`app/agents/spending.py`), Tasks 6–7 (`app/agents/recommend.py`, `app/agents/alerting.py`), Task 8 (`app/orchestrator.py` — `Planner`), Tasks 9–10 (`app/main.py` + `web/`), and **`requirements.txt` (authored by Part E / Task 9)**.

**This task writes NO new application logic** — `Planner.handle` already exists. Task 11 only adds: an end-to-end test that drives the assembled system through the four HLD §11 scenarios, a runnable CLI demo (`app/smoke.py`), and the `README.md` quickstart. If the e2e asserts fail, the bug is in an earlier task — fix it there, do not patch around it here.

---

## Task 11: Integration, Smoke Harness & CLI Fallback

**Files:**
- Create: `tests/test_e2e.py` (the four §11 demo scenarios + greeting, end-to-end through `Planner.handle`)
- Create: `app/smoke.py` (runnable `py -m app.smoke` — prints full `FinalResponse` for every scenario; the CLI fallback demo per HLD §15)
- Create: `README.md` (quickstart: install, uvicorn, localhost:8000, pytest, CLI smoke)
- Ensure: `requirements.txt` exists (authored by Part E — **do not duplicate**; Step 3 only verifies presence)
- Test: `tests/test_smoke.py` (asserts `app.smoke.run()` executes and returns the scenario responses)

The e2e test is the **acceptance test for the whole prototype**: it constructs one real `Planner(SessionStore())` over the real tool layer and real mock data, then asserts the exact `FinalResponse` shape for each demo scenario. No mocks, no stubs — the fully assembled star-topology pipeline.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_e2e.py
"""End-to-end acceptance tests — the four HLD §11 demo scenarios driven
through the fully assembled Planner over real tools + real mock data.
No mocks. This is the system-level contract.
"""
from app.memory.store import SessionStore
from app.orchestrator import Planner
from app.models import (
    FinalResponse, SpendingInsight, Recommendation, Alert,
)


def _planner():
    return Planner(SessionStore())


# ─── Scenario 1: full pipeline ───────────────────────────────────────────────
def test_scenario1_improve_savings_full_pipeline():
    fr = _planner().handle("How can I improve my monthly savings?", "s1")

    assert isinstance(fr, FinalResponse)
    assert fr.answer_text                                  # non-empty narrative

    # insights present, food total pinned at 12000
    assert isinstance(fr.insights, SpendingInsight)
    assert fr.insights.totals_by_category["food"] == 12000.0

    # recommendations: food first, est saving 1800.0 (15% of 12000)
    assert fr.recommendations, "expected non-empty recommendations"
    assert all(isinstance(r, Recommendation) for r in fr.recommendations)
    assert fr.recommendations[0].category == "food"
    assert fr.recommendations[0].est_monthly_saving == 1800.0

    # a warning alert for entertainment (90% of budget)
    assert any(
        a.severity == "warning" and a.category == "entertainment"
        for a in fr.alerts
    ), "expected an entertainment warning alert"

    # plan_trace shows spending + recommend + alert steps
    trace = " | ".join(fr.plan_trace).lower()
    assert "spending" in trace
    assert "recommend" in trace
    assert "alert" in trace


# ─── Scenario 2: summarize (spending only, proactive alert fires) ────────────
def test_scenario2_summarize_spending_only_proactive_alert():
    fr = _planner().handle("Summarize my spending last month.", "s2")

    assert isinstance(fr.insights, SpendingInsight)
    assert fr.recommendations == []                       # summary path → no recs

    # proactive alerting still fires on the food anomaly per orchestrator branch
    assert fr.alerts, "expected proactive alerts on the summarize path"
    assert all(isinstance(a, Alert) for a in fr.alerts)

    trace = " | ".join(fr.plan_trace).lower()
    assert "proactive" in trace, "expected a proactive-alerting trace line"


# ─── Scenario 3: why did I overspend (all three populated) ───────────────────
def test_scenario3_overspend_all_populated():
    fr = _planner().handle("Why did I overspend?", "s3")

    assert isinstance(fr.insights, SpendingInsight)
    assert fr.insights is not None
    assert fr.alerts, "expected alerts"
    assert fr.recommendations, "expected recommendations"

    # the food anomaly (+25%) is present in the insight
    food_anoms = [a for a in fr.insights.anomalies if a.category == "food"]
    assert food_anoms, "expected a food anomaly"
    assert food_anoms[0].pct_change == 25.0


# ─── Scenario 4: memory-backed follow-up (no recompute, same insight) ────────
def test_scenario4_memory_followup_reuses_cached_insight():
    store = SessionStore()
    planner = Planner(store)

    first = planner.handle("How can I improve my monthly savings?", "s4")
    cached_after_first = store.get_last_insight("s4")
    assert cached_after_first is first.insights            # call 1 cached it

    second = planner.handle("what about food specifically?", "s4")

    # the follow-up reused the cached insight — no recompute
    trace = " | ".join(second.plan_trace).lower()
    assert ("no recompute" in trace) or ("reused cached insight" in trace), (
        f"expected a no-recompute trace line, got: {second.plan_trace}"
    )

    # SAME object identity — the cache was not rebuilt
    assert second.insights is first.insights
    assert store.get_last_insight("s4") is first.insights

    # food-specific recommendation surfaced
    assert second.recommendations, "expected a food-specific recommendation"
    assert any(r.category == "food" for r in second.recommendations)


# ─── Greeting: no analysis ───────────────────────────────────────────────────
def test_greeting_returns_empty_payload():
    fr = _planner().handle("hi", "g1")
    assert isinstance(fr, FinalResponse)
    assert fr.insights is None
    assert fr.recommendations == []
    assert fr.alerts == []
    assert fr.answer_text                                  # still greets the user
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_e2e.py -v`

Expected outcome — one of:
- **Collection error** if `app/smoke.py` / `README.md` siblings aren't in place yet — that's fine, the e2e file itself imports only existing modules (`Planner`, `SessionStore`, models), so it will actually *collect*.
- If Tasks 1–10 are fully green, these five tests should already **PASS** on first run (the system is assembled). If any assertion **FAILS**, the defect is upstream (orchestrator branching, recommend/alert wiring, or memory caching) — go fix the responsible earlier task, then return here. **Do not weaken an assertion to make it pass.**

This is the inversion that makes Task 11 the final gate: the test is written against the frozen §11 contract, and a red bar here means an earlier task drifted from contract.

- [ ] **Step 3: Write the demo harness, README, and verify `requirements.txt`**

The implementation under test already exists. Step 3 adds the **deliverable surface**: the CLI fallback demo and the quickstart doc.

First, ensure `requirements.txt` exists (Part E created it). If — and only if — it is missing, create it idempotently with the minimal runtime deps so the quickstart works:

```txt
# requirements.txt  (create ONLY if Part E did not — do not overwrite an existing file)
fastapi
uvicorn[standard]
pytest
```

> Idempotency rule: check first — `if (Test-Path requirements.txt) { 'exists, skip' } else { <write the 3 lines above> }`. Part E owns this file; this step is a safety net, not a rewrite.

Now create the runnable CLI demo:

```python
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


# The four HLD §11 scenarios. Scenario 4 is a follow-up that MUST run in the
# same session as scenario 1 to exercise the memory-backed (no-recompute) path,
# so we drive every scenario through ONE shared SessionStore in order.
SCENARIOS: list[tuple[str, str, str]] = [
    ("s1", "1. Improve savings (full pipeline)",
     "How can I improve my monthly savings?"),
    ("s2", "2. Summarize spending (spending only + proactive alert)",
     "Summarize my spending last month."),
    ("s3", "3. Why did I overspend? (spending → alert → recommend)",
     "Why did I overspend?"),
    # scenario 4 reuses session "s1" so the cached insight from scenario 1 is hit
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
```

Then the smoke test that proves the demo harness itself runs:

```python
# tests/test_smoke.py
"""The CLI fallback demo must run clean and return one FinalResponse per
scenario (HLD §15). Guards the deliverable from import/runtime breakage.
"""
from app import smoke
from app.models import FinalResponse


def test_run_returns_a_finalresponse_per_scenario(capsys):
    responses = smoke.run()
    assert len(responses) == len(smoke.SCENARIOS)
    assert all(isinstance(r, FinalResponse) for r in responses)

    # the printed transcript actually contains the agentic trace + a verdict
    out = capsys.readouterr().out
    assert "plan_trace" in out
    assert "scenarios replayed" in out


def test_main_exits_zero(capsys):
    assert smoke.main() == 0
    out = capsys.readouterr().out
    assert "Done" in out
```

Finally the README quickstart (exact commands from HLD §15):

```markdown
# Personal Finance Advisor — Agentic Prototype

An agentic multi-agent personal finance advisor. A **Planner** orchestrator
classifies intent, builds a data-dependent plan, and sequences three specialist
agents — **Spending Analysis**, **Recommendation**, and **Alerting** — through a
typed mock tool layer over a deterministic JSON transaction store. Results merge
into a single typed `FinalResponse` (answer + insights + recommendations +
alerts + a human-readable `plan_trace`), and per-session memory enables
follow-up questions without recomputation. Star topology, rule-based reasoning,
**zero LLM dependencies** — every agentic step is visible in the trace.

## Quickstart

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload      # serves the API + static web UI
# open http://localhost:8000
```

Run the test suite (includes the end-to-end demo-scenario acceptance tests):

```bash
pytest -q
```

CLI fallback demo — replays all four HLD §11 scenarios through the full pipeline
and prints each complete `FinalResponse` (use this if the Web UI is unavailable):

```bash
py -m app.smoke
```

## Demo Scenarios (HLD §11)

1. *"How can I improve my monthly savings?"* → full pipeline (all agents).
2. *"Summarize my spending last month."* → spending only (+ proactive alert).
3. *"Why did I overspend?"* → spending → alert → recommend (food anomaly).
4. *"What about food specifically?"* → memory-backed follow-up, no recompute.

## Architecture & Design

- **High-level design:** [`HLD.md`](HLD.md)
- **Implementation plan (this build):** [`LLD/`](LLD/) — `LLD_INDEX.md` is the
  entry point (frozen contracts, gate protocol, task map).
```

- [ ] **Step 4: Run tests to verify they pass**

Run, in order:

```bash
pytest tests/test_e2e.py -v      # the 5 acceptance tests
pytest tests/test_smoke.py -v    # the 2 CLI-demo guard tests
py -m app.smoke                  # eyeball the full transcript (CLI fallback)
```

Expected:
- `tests/test_e2e.py` → **5 pass** (scenarios 1–4 + greeting).
- `tests/test_smoke.py` → **2 pass**.
- `py -m app.smoke` → prints five scenario blocks (each with `answer`,
  numbered `plan_trace`, `insights`, `recommendations`, `alerts`) and a final
  `Done — 5 scenarios replayed…` line; **exit code 0**, no traceback.

If `py -m app.smoke` raises `UnicodeEncodeError` on `₹`, the `sys.stdout.reconfigure("utf-8")` guard in `main()` covers the module-run path; if a reviewer pipes output, also `set PYTHONUTF8=1`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_e2e.py tests/test_smoke.py app/smoke.py README.md requirements.txt
git commit -m "feat: e2e acceptance tests, CLI fallback demo (app.smoke), README quickstart"
```

> Note: `requirements.txt` is staged only if Step 3's safety-net created it; if Part E already committed it, `git add` is a no-op and it won't appear in the diff.

**GATE — Task 11 (final gate)**

- **Tier A — Task-local validation:** `pytest tests/test_e2e.py -v` → **5 pass**, and `pytest tests/test_smoke.py -v` → **2 pass**. The four §11 demo scenarios + greeting hold end-to-end through the assembled `Planner`; the CLI fallback demo runs clean.

- **Tier B — Full-system no-regression gate:** `pytest -q` → **entire suite green** (Tasks 1–11: models, data, tools, memory, spending, recommend, alerting, orchestrator, api, web, e2e, smoke). This is the **final, whole-system verification** — every frozen contract integrated, every demo scenario reproducible, zero regressions across the build. End-to-end behavior now fully holding: install → `uvicorn app.main:app` serves the live UI, `pytest -q` proves the pipeline, and `py -m app.smoke` gives the replayable CLI artifact (HLD §15 / R11 deliverables complete).

A task is **DONE** only when both tiers are green. If Tier B regresses, the defect is in an earlier task — fix it at the source, never by weakening this gate.

---

**End of Part F — and of the LLD.** The prototype is integrated, demonstrable three ways (live Web UI, `pytest -q`, `py -m app.smoke`), and contract-verified end-to-end. Deliverables per HLD §11 + §15 + R11 are complete.
