# Personal Finance Advisor — Low-Level Design (LLD) / Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an agentic multi-agent personal finance advisor (Planner + Spending Analysis + Recommendation + Alerting) over FastAPI + vanilla-JS, on deterministic mock data, demonstrating orchestration, autonomous reasoning, tool-calling, memory, and conversation.

**Architecture:** Star topology — a Planner orchestrator classifies intent, builds a data-dependent plan, sequences specialist agents through a typed tool layer over a mock JSON store, merges results, and persists session memory. See `../HLD.md` (v0.4).

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, pytest, vanilla HTML/CSS/JS. Zero LLM deps.

---

## Plan File Map

| File | Tasks | Build atoms (HLD §12.1) |
|------|-------|--------------------------|
| `LLD_INDEX.md` (this) | — | Contracts, gate protocol, task map, execution handoff |
| `LLD_PART_A_foundation.md` | 1–4 | M (models), D (data), T (tools), MEM (memory) |
| `LLD_PART_B_spending.md` | 5 | SP (spending analysis — in-depth) |
| `LLD_PART_C_recommend_alerting.md` | 6–7 | RC (recommend), AL (alerting) |
| `LLD_PART_D_orchestrator.md` | 8 | ORCH (planner) |
| `LLD_PART_E_api_web.md` | 9–10 | API (FastAPI), WEB+WIRE (frontend) |
| `LLD_PART_F_integration.md` | 11 | INT + SMOKE (integration, demo, smoke) |

Execute tasks in numeric order. The gate protocol (below) runs after every task.

---

## Frozen Contracts (the universal gate — `app/models.py`)

**These dataclasses are immutable once Task 1 lands. Every other task references these exact names/fields. Do not rename or restructure.**

```python
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
```

**Serialization rule:** the API boundary calls `dataclasses.asdict(final_response)` — `asdict` recurses nested dataclasses automatically. Agents return typed dataclasses, never dicts.

**Tracing rule:** every agent's `run(...)` takes a `trace: list[str]` it appends to (e.g. `"SpendingAnalysis → get_transactions(month=2026-05) → 14 rows"`). The orchestrator owns the list and sets `FinalResponse.plan_trace = trace`. This produces the visible agentic trace (HLD §8).

**Frozen signatures:**

```python
# tools — app/tools/banking_tools.py
get_transactions(month: str | None = None, category: str | None = None) -> list[Transaction]
get_categories() -> list[str]
get_budgets() -> dict          # {category: float}
get_balance() -> float
TOOLS: list[dict]              # JSON-serializable tool schemas

# memory — app/memory/store.py  (class SessionStore)
get_profile(session_id: str) -> UserProfile
get_last_insight(session_id: str) -> Optional[SpendingInsight]
set_last_insight(session_id: str, insight: SpendingInsight) -> None
get_last_intent(session_id: str) -> Optional[str]
set_last_intent(session_id: str, intent: str) -> None
append_turn(session_id: str, role: str, text: str) -> None
get_history(session_id: str) -> list      # list[{"role","text"}]

# agents
spending.run(query: str, profile: UserProfile, trace: list) -> SpendingInsight
recommend.run(insight: SpendingInsight, profile: UserProfile, trace: list) -> list   # list[Recommendation]
alerting.run(insight: SpendingInsight, profile: UserProfile, trace: list) -> list     # list[Alert]

# orchestrator — app/orchestrator.py  (class Planner)
Planner(store: SessionStore)
Planner.handle(message: str, session_id: str) -> FinalResponse
```

---

## Pinned Mock Data (HLD §10 — deterministic demo)

Current month = `2026-05`, prior = `2026-04`. `transactions.json` must produce these **debit** sums:

| Category | 2026-04 | 2026-05 | budget | Effect |
|----------|---------|---------|--------|--------|
| food | 9600 | 12000 | 15000 | +25% MoM → **anomaly**; 80% budget (no alert) |
| entertainment | (none) | 4500 | 5000 | 90% budget → **near-breach alert**; no prior → not anomaly |
| shopping | 8000 | 8000 | 12000 | normal |
| travel | 3500 | 3500 | 6000 | normal |
| groceries | 6000 | 6200 | 8000 | normal (essential) |
| utilities | 3000 | 3000 | 5000 | normal (essential) |

`get_balance()` → `45000.0`. Seeded profile: `name="Aarav", currency="₹", risk_pref="balanced", savings_goal=8000, budgets=<above>`.

Discretionary (reducible) categories: `food, shopping, travel, entertainment`. Essential (never reduced): `groceries, utilities, transfers`.

---

## Two-Tier Gate Protocol (run after EVERY task)

After each task's own steps, run its **GATE** block, which has two tiers:

- **Tier A — Task-local validation:** the new unit tests for this task pass in isolation.
- **Tier B — Cumulative end-to-end validation:** the **entire** `pytest` suite to date passes (no regression), plus — from Task 8 onward — the end-to-end smoke harness `tests/test_e2e.py` runs every demo scenario reachable so far and asserts the full `FinalResponse`.

A task is **DONE** only when both tiers are green. If Tier B regresses, fix before advancing (do not stack new work on a red suite).

Standard GATE commands:

```bash
# Tier A — this task only
pytest tests/<this_task_test>.py -v

# Tier B — everything so far (no regression)
pytest -q
# from Task 8 onward, the suite includes the growing e2e harness:
pytest tests/test_e2e.py -v
```

Each task below specifies its exact Tier-A test path and the Tier-B expectation (what new end-to-end behavior must now hold).

---

## Parallel Execution Mapping (HLD §12.1)

The plan is authored in numeric order, but execution may parallelize per HLD §12.1:

- **Serial spine (author single-threaded):** Task 1 (M) → Task 2 (D) → Task 3 (T) → Task 5 (SP) → Task 8 (ORCH) → Task 9 (API) → Task 11 (INT).
- **Parallel track 1:** Task 6 (RC) ∥ Task 7 (AL) run under Task 5 (SP) — all consume the frozen `SpendingInsight`.
- **Parallel track 2:** Task 10 (WEB) builds against a mocked `/chat` JSON, independent of backend.
- **GATE applies regardless:** whichever order, a task isn't DONE until its two-tier gate is green against the integrated suite.

---

## Self-Review Checklist (author runs before handoff)

1. **Spec coverage:** every HLD section (§3–§11) maps to a task — see the per-part coverage notes.
2. **Placeholder scan:** no "TBD / add validation / handle edge cases / similar to Task N" — every code step shows real code.
3. **Type consistency:** all tasks use the frozen names above (`SpendingInsight.totals_by_category`, `Recommendation.est_monthly_saving`, `Alert.severity`, `Planner.handle`, etc.). No drift.

---

## Execution Handoff

After the full plan is reviewed and saved:

**Two execution options:**
1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks (REQUIRED SUB-SKILL: superpowers:subagent-driven-development).
2. **Inline Execution** — execute in-session with checkpoints (REQUIRED SUB-SKILL: superpowers:executing-plans).
