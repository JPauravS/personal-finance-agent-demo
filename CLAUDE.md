# CLAUDE.md — Personal Finance Advisor

Quick reference for this project. Deeper docs linked inline.

## What

Agentic multi-agent personal-finance advisor (retail banking). **Planner**
orchestrator classifies intent → builds a **data-dependent** plan → sequences 3
specialists over a typed **mock tool layer**. Rule-based reasoning, **zero LLM
deps**; every agentic step visible in `plan_trace`. Runs locally (FastAPI) and at
the edge (Cloudflare Python Workers) from the **same** `app/` pipeline.

| Layer | What |
|-------|------|
| **Planner** (`app/orchestrator.py`) | intent → plan → route → branch on results → merge `FinalResponse` |
| **Spending Analysis** (`app/agents/spending.py`) | categorize debits, MoM trend, flag anomaly (>20% MoM). In-depth agent. |
| **Recommendation** (`app/agents/recommend.py`) | target high discretionary cats, ₹ saved, scales to `profile.risk_pref` |
| **Alerting** (`app/agents/alerting.py`) | scan cats vs budget, flag breach / ≥90% near-breach |
| **Tools** (`app/tools/banking_tools.py`) | typed mock APIs (`get_transactions/categories/budgets/balance`). Agents never touch the store directly. LLM-function-call shaped. |
| **Memory** (`app/memory/store.py`) | per-session history + insight cache + profile. In-memory. |
| **Models** (`app/models.py`) | **FROZEN CONTRACTS** — dataclasses. Immutable. |

Boundaries: `app/main.py` (local FastAPI) · `worker_main.py` (Workers, native
`WorkerEntrypoint`, no FastAPI). UI: `web/` (local) mirrored to `worker-assets/`.

## How — commands

Windows: use **`py`** (not python/python3).

```bash
# Local API + UI
uv sync --group local
uv run --group local uvicorn app.main:app --reload     # http://localhost:8000

# Tests  (69 incl. e2e acceptance + edge-guard)
py -m pytest -q

# CLI demo (no UI) — replays 5 HLD scenarios
py -m app.smoke

# Edge: local Pyodide runtime / deploy
npm run dev        # uv run pywrangler dev  @ 127.0.0.1:8787
npm run deploy     # uv run pywrangler deploy
```

**Live:** app https://personal-finance-advisor.joshipaurav.workers.dev ·
doc-site https://pf-advisor-arch.pages.dev (`/workflow`)

## Conventions / gotchas

- **Frozen contracts.** `app/models.py` is immutable — every agent uses exact
  names/signatures. First agent is `run(query, profile, trace)`; others
  `run(insight, profile, trace)`. No drift.
- **Trace is the agentic proof.** Each agent appends to the shared `trace:
  list[str]`; Planner owns it → `FinalResponse.plan_trace`. Keep this shape (it
  matches a real LLM tool-calling loop — swap-ready).
- **Pinned demo numbers** (deterministic, don't change casually): food
  9,600→12,000 = **+25%** anomaly; entertainment 4,500/5,000 = **90%** warning;
  `balanced` food saving ₹1,800. Tests assert these.
- **Fixed >20% MoM threshold**, not z-score (no variance at n=2).
- **Debits only** in spending sums (salary credit excluded).
- **Two-tier gate** when extending: Tier A (task-local tests) + Tier B
  (`pytest -q` whole suite green). Never weaken an assertion to pass a gate — the
  defect is upstream.
- **Commits land on this repo's `master`** (standalone `git init`, isolated from
  CC parent `main`). Commit only when asked.
- **Cloudflare Workers (Pyodide) gotchas:**
  - No filesystem bundling → data embedded in `app/data/transactions_data.py`;
    `_load()` falls back to it. Regenerate + parity test if `transactions.json`
    changes (they must not drift).
  - Worker bundle must stay < **3 MiB** (free plan) → worker is **pure stdlib**,
    FastAPI/pydantic are **local-only** (`local` dep group, not `dev`).
  - `pyproject.toml` is the **single** dep source — no `requirements.txt`.
  - After editing `web/`, rebuild `worker-assets/` (flat copy: index at root,
    js/css under `static/`).

## Docs map

| File | Purpose |
|------|---------|
| [`README.md`](README.md) | human-facing overview + quickstart (local + Cloudflare deploy) |
| [`HLD.md`](HLD.md) | design context (§5.3 branching, §10 pinned data, §12.1 parallel plan) |
| [`LLD/`](LLD/) | task-by-task build plan; `LLD_INDEX.md` = frozen contracts + gate protocol |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | structure — *what the system is* |
| [`WORKFLOW.md`](WORKFLOW.md) | runtime — *what it does*; L1→L2→L3 progressive depth |
| [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) | **the 3 build sessions + resume commands** |
| [`NEW_SESSION_PROMPT.md`](NEW_SESSION_PROMPT.md) | paste-ready prompt that drove the build |

## Extensibility

Real LLM: replace `reason()`/`classify_intent()` with a Claude tool-calling loop
(trace contract unchanged). LangGraph: Planner = graph, agents = nodes, `ROUTING`
= conditional edges. Persistence: swap in-memory store / JSON for a DB.
