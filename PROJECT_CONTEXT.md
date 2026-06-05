# Project Context — Personal Finance Advisor

Agentic multi-agent personal finance advisor for a retail-banking use case.
A **Planner** orchestrator classifies intent, builds a data-dependent plan, and
sequences three specialists — **Spending Analysis**, **Recommendation**,
**Alerting** — over a typed mock tool layer. Rule-based reasoning, **zero LLM
deps**, every agentic step visible in a `plan_trace`. Python + FastAPI + vanilla
JS locally; the same pipeline also runs at the edge on Cloudflare Python Workers.

Docs: [`README.md`](README.md) · [`HLD.md`](HLD.md) · [`ARCHITECTURE.md`](ARCHITECTURE.md)
· [`WORKFLOW.md`](WORKFLOW.md) · [`LLD/`](LLD/) · [`NEW_SESSION_PROMPT.md`](NEW_SESSION_PROMPT.md)

**Live:**
- App (Workers): https://personal-finance-advisor.joshipaurav.workers.dev
- Architecture / Workflow doc-site (Pages): https://pf-advisor-arch.pages.dev · `/workflow`

---

## The project arc in one read

The project was built across **three Claude Code sessions on 2026-06-05** (windows
overlap — design, doc-site, and build progressed in parallel). The arc:

1. **Design** (`a3a2d9f2`) — turned a spoken brief into a reviewed **HLD**, a
   parallel-execution plan, and a task-by-task **LLD** with frozen contracts.
2. **Docs & doc-site** (`de99ee7e`) — wrote **ARCHITECTURE.md** + **WORKFLOW.md**,
   rendered them to an HTML doc-site on **Cloudflare Pages**.
3. **Build & ship** (`4148192e`) — executed the LLD via subagent-driven
   development (67 tests), then deployed the app to **Cloudflare Workers**.

Reading order to reconstruct everything: HLD → LLD/ → ARCHITECTURE → WORKFLOW →
the session summaries below.

---

## Session timeline

| # | Session | Started in | Window (UTC) | Phase | Output |
|---|---------|-----------|--------------|-------|--------|
| 1 | `a3a2d9f2` | `CC/` (parent) | 08:25 → 09:40 | Design | HLD, LLD/, parallel plan, NEW_SESSION_PROMPT |
| 2 | `de99ee7e` | `personal-finance-agent/` | 09:19 → 10:22 | Docs & doc-site | ARCHITECTURE.md, WORKFLOW.md, Pages site |
| 3 | `4148192e` | `personal-finance-agent/` | 09:39 → 10:43 | Build & ship | `app/`, `web/`, 67 tests, Workers deploy |

---

## 1 — Design / planning   `a3a2d9f2`

**Resume (run from `CC/` parent folder):**

```bash
cd C:\Users\paura\OneDrive\Documents\CC
claude --resume a3a2d9f2-b9ac-4382-92ac-a449429022fd
```

**What happened — the full design session:**

- **Brief intake (spoken).** Requirement: agentic AI personal-finance advisor,
  retail banking. Must demonstrate multi-agent architecture, orchestration,
  autonomous reasoning, tool/function calling, basic memory, personalized
  recommendations, conversational interaction. Constraints locked: **Python**,
  **WebUI**, **mock data (no API key)**, ~**1-hour live build**.
- **Agents defined (4).** Planner (coordinator) · Spending Analysis · Recommendation
  · Alerting. Decision: build **one agent in-depth** first → **Spending Analysis**
  picked (~15 min, fully self-contained, strongest concrete demo output).
- **Framework call.** Rejected LangChain/LangGraph — dead weight without a real
  LLM. Chose **pure Python + FastAPI + single HTML/JS page**. Kept the design
  credit via a "maps 1:1 to LangGraph nodes/edges, swap `ChatAnthropic` later"
  story.
- **HLD authored + hardened over two review rounds.** Drafted HLD → spawned **3
  parallel validator agents** (requirements-coverage, architecture-soundness,
  demo-feasibility), applied fixes, then **re-spawned the same 3** to confirm no
  regressions. Key decisions that came out of review:
  - **Data-dependent autonomy**, not just keyword routing (Alerting runs only on
    anomaly/breach; Recommendation skipped when nothing is reducible).
  - **Personalization** via user `profile` (`risk_pref`, `savings_goal`).
  - **Fixed >20% MoM anomaly threshold**, z-score dropped (no variance at n=2;
    deterministic + demo-stable).
  - **Pinned exact mock numbers** so the demo always fires: food 9,600→12,000
    (**+25%** anomaly), entertainment 4,500/5,000 (**90%** near-budget warning).
  - Routing made **first-match-wins**; deduped a duplicate `WHY_OVERSPENT` row;
    Alerting condition widened to **anomaly OR ≥90% budget** (the entertainment
    alert is a budget breach with no prior month, not an MoM anomaly).
  - Signature fixes (first agent is `run(query, profile, trace)`); **pytest CLI
    smoke as the fallback** if the UI breaks. → **HLD v0.3**.
- **Parallel-execution analysis** (`/deep-analysis`). Extracted build atoms +
  dependency graph; critical path `M → T → SP → ORCH → API → INT ≈ 34 min`,
  Spending is the long pole, Planner is the join. Folded into **HLD §12.1**
  (v0.4) with sequential kept as the labeled fallback.
- **LLD via `/writing-plans`.** Split into `LLD/` (INDEX + Parts A–F, **11 tasks**).
  Authored INDEX + **frozen contracts** + Part A himself (the serial spine);
  dispatched **5 parallel subagents** for Parts B–F against the frozen contracts.
  Every task carries a **two-tier gate**: Tier A (task-local tests) + Tier B
  (cumulative end-to-end, no regression).
- **Scored self-review.** Found + fixed **3 latent bugs** that would have blocked
  gates: missing root `conftest.py`, a `StaticFiles` import-time crash when `web/`
  is absent, and a `_is_followup` false-positive (tightened bare-length cue ≤4→≤3).
  First "scores" were holistic; the user challenged "expected or calculated?" →
  **recomputed from a grep-based rubric** with real counts (Spec Coverage **9.84**,
  Placeholder **9.50**, 0 real placeholders, no type drift).
- **Handoff.** Produced [`NEW_SESSION_PROMPT.md`](NEW_SESSION_PROMPT.md) — the
  paste-ready build prompt used by Session 3.

## 2 — Docs & doc-site   `de99ee7e`

**Resume (run from `personal-finance-agent/` folder):**

```bash
cd C:\Users\paura\OneDrive\Documents\CC\personal-finance-agent
claude --resume de99ee7e-413f-41d4-8e15-a798a6c2c6b9
```

**What happened:**

- **Architecture choice explained** from the HLD: orchestrator-with-specialists
  (star topology), not peer-to-peer, not monolith — with the reasoning (hits all
  reqs, acyclic/debuggable, mock-first swap-ready, typed contracts, data-dependent
  autonomy).
- **ARCHITECTURE.md** written — precise, tables over prose, diagram, no verbose
  (structure: *what the system is*).
- **Doc-site on Cloudflare Pages.** Rendered the architecture to a self-contained
  HTML page and iterated the design **four times**:
  1. hand-written dark template → 2. `/frontend-design` "systems blueprint" →
  3. unhinged brutalist "AGENT//OS terminal" (rejected) →
  4. **professional light IBM Plex page** (approved), footer stripped.
  Auth blocker fixed along the way: wrangler token had **expired 2026-05-04**;
  re-login. Live at **pf-advisor-arch.pages.dev**.
- **WORKFLOW.md** — the runtime companion (*what the system does*). Grounded in
  **real traces captured from the running orchestrator** (read-only inspection +
  a throwaway script; **zero app code touched**). Three worked examples, incl. the
  "gem": a `['spending']`-only plan where anomaly detection **forced Alerting to
  run proactively** — agentic behavior observed, not claimed. Built `workflow.html`,
  cross-linked to the architecture page, deployed to `/workflow`.
- **Progressive-difficulty rewrite.** Restructured WORKFLOW.md + workflow.html into
  **L1 Intuition → L2 Mechanism → L3 Internals** collapsible tiers (GitHub
  `<details>` in the .md). L3 exposes the real code nuances: `trace.insert(0)`
  ordering, the single `run_alert` boolean, anomaly-first sort key, cache **object
  identity** preserved, and the honest flat-15% follow-up vs risk-driven %
  divergence at `aggressive`.

## 3 — Build & ship   `4148192e`

**Resume (run from `personal-finance-agent/` folder):**

```bash
cd C:\Users\paura\OneDrive\Documents\CC\personal-finance-agent
claude --resume 4148192e-a3ed-4383-9551-d99a53d8c59b
```

**What happened — implementation, then edge deploy:**

- **Repo isolation.** Per the user's instruction (no commits on CC `main`),
  `git init`'d a **standalone repo** in the project dir; all work lands on
  `master` here.
- **LLD executed via `superpowers:subagent-driven-development`** — fresh subagent
  per task, every gate verified by the main thread (not the subagent's word),
  assertions spot-checked as not pre-weakened, frozen contracts confirmed:
  - **Wave 0 (serial):** models · data · tools · memory.
  - **Wave 1 (∥×3):** spending · recommend · alerting — Tier A only, no commit
    (avoid git-index races), combined Tier B at the boundary.
  - **Wave 2 (join):** orchestrator.
  - **Wave 3 (∥×2):** FastAPI app · web UI.
  - **Wave 4 (final):** e2e acceptance + `app.smoke` CLI + README.
  - Result: **67 tests pass**, 12 commits, zero regressions.
- **Local demo proofs:** `pytest -q` 67 · `uvicorn` live endpoints (`/`, static,
  `POST /api/chat`) · `py -m app.smoke` all 5 scenarios with pinned numbers firing.
- **Then: deploy to Cloudflare Workers (Python).** Research-first (web search —
  topic is past knowledge cutoff): FastAPI runs on **Pyodide** via `pywrangler` +
  `uv`, static via an ASSETS binding. Installed the **uv toolchain**, verified
  locally with `pywrangler dev` before deploying. **Three edge blockers hit + fixed:**

  | Problem | Fix |
  |---------|-----|
  | Pyodide doesn't bundle data files → `FileNotFoundError` on `transactions.json` | Embedded data as `app/data/transactions_data.py`; `_load()` falls back to it; generated from JSON + **parity/drift-guard test** (suite 67→69) |
  | FastAPI+pydantic ≈ 4 MiB > **free-plan 3 MiB** | Rewrote worker to a **native `WorkerEntrypoint` handler** (pure-stdlib pipeline); FastAPI/pydantic kept **local-only** |
  | Bundler swept the whole `.venv` (dev deps) into the Worker | Build tools in default `dev` group, heavy deps in a **non-default `local` group** → bundle **7 MiB → 1.6 MiB gzip** |
  | `pywrangler` refuses to run with `requirements.txt` present | Deleted it; `pyproject.toml` is the single dep source |

- **Live + verified:** **personal-finance-advisor.joshipaurav.workers.dev** — same
  deterministic demo as local. Cloudflare Python Workers gotchas persisted to memory.

---

## Quick resume reference

```bash
# Session 1 — design  (from CC/ parent)
cd C:\Users\paura\OneDrive\Documents\CC
claude --resume a3a2d9f2-b9ac-4382-92ac-a449429022fd

# Sessions 2–3 — docs / build  (from project folder)
cd C:\Users\paura\OneDrive\Documents\CC\personal-finance-agent
claude --resume de99ee7e-413f-41d4-8e15-a798a6c2c6b9   # docs & Pages doc-site
claude --resume 4148192e-a3ed-4383-9551-d99a53d8c59b   # build & Workers deploy
```
