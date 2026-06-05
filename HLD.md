# High-Level Design (HLD)
## Agentic AI Personal Finance Advisor — Retail Banking

**Version:** 0.4 (added §12.1 Parallel Execution Plan)
**Date:** 2026-06-05
**Status:** AWAITING APPROVAL
**Constraint:** 1-hour build, mock data (no LLM API key), Python + WebUI

---

## 1. Objective

Prototype an **agentic, multi-agent personal finance advisor** for retail banking that ingests a customer's transactions and, through coordinated specialist agents, produces personalized savings advice, spending insights, and proactive alerts — over a conversational web interface.

### 1.1 Requirements Traceability

| # | Requirement | Where satisfied |
|---|-------------|-----------------|
| R1 | Multi-agent architecture | §3 — 4 agents, separated by responsibility |
| R2 | Agent orchestration | §5 — Planner routes + sequences agents |
| R3 | Autonomous reasoning | §5.2 — Planner decomposes query → plan → execute |
| R4 | Tool / function calling | §6 — mock tool layer, agents call typed tools |
| R5 | Basic memory / context | §7 — session memory + conversation history |
| R6 | Personalized recommendations | Recommendation agent, §4.3 |
| R7 | Conversational interaction | §8 — WebUI chat loop, multi-turn |
| R8 | Modular architecture | §9 — package layout, one module per agent |
| R9 | Mock APIs/tools | §6, §10 — mock transaction store + tools |
| R10 | Clean code + arch explanation | This HLD + docstrings + LLD next |
| R11 | Deliverables: prototype, source, diagram, workflow, demo | §11 scenarios + §15 Run & Demo + pytest smoke |

---

## 2. Design Principles

- **Mock-first, swap-ready.** No LLM key → deterministic rule-based "reasoning". Architecture maps 1:1 to LangGraph nodes/edges so a real `ChatAnthropic` model drops in later with no structural change.
- **One responsibility per agent.** Each agent is a pure function of (context, tools) → structured output.
- **Typed contracts between agents.** Agents exchange dataclasses/dicts, not free text. Predictable, testable.
- **Orchestrator owns control flow.** Specialist agents never call each other directly — only the Planner sequences them. Keeps the graph acyclic and debuggable.
- **Data-dependent autonomy.** The plan is not a fixed pipeline. The Planner branches on *intermediate results*: Alerting runs only if Spending found an anomaly/breach; Recommendation is skipped if no reducible category exists. Reasoning is data-driven, not pure keyword lookup. (§5.3)
- **Planner injects profile.** Downstream specialists are called as `run(insight, profile)` — the Planner passes `user_profile` from memory so personalization and budgets are available without specialists reaching into memory. The **first** agent (Spending) has no upstream insight, so its signature is `run(query, profile)`; all others take `(insight, profile)`.

---

## 3. System Architecture

```
                          ┌─────────────────────────────┐
                          │          Web UI (chat)       │
                          │   HTML + JS  ──HTTP/JSON──▶   │
                          └───────────────┬─────────────┘
                                          │  POST /chat {message, session_id}
                                          ▼
                          ┌─────────────────────────────┐
                          │        FastAPI backend       │
                          └───────────────┬─────────────┘
                                          ▼
                    ┌───────────────────────────────────────┐
                    │        PLANNER  (Orchestrator)         │
                    │  • parse query                         │
                    │  • build execution plan (reasoning)    │
                    │  • route to specialists                │
                    │  • merge outputs → final answer        │
                    │  • read/write memory                   │
                    └───┬───────────┬───────────┬───────────┘
                        │           │           │
            ┌───────────▼──┐ ┌──────▼───────┐ ┌─▼──────────────┐
            │   SPENDING   │ │ RECOMMENDA-  │ │   ALERTING     │
            │   ANALYSIS   │ │   TION       │ │   AGENT        │
            │  (in-depth)  │ │   AGENT      │ │                │
            └───────┬──────┘ └──────┬───────┘ └───────┬────────┘
                    │               │                 │
                    └───────────────┼─────────────────┘
                                    ▼
                    ┌───────────────────────────────────────┐
                    │         TOOL LAYER (mock APIs)         │
                    │  get_transactions()  get_budgets()     │
                    │  get_categories()    get_balance()     │
                    └───────────────┬───────────────────────┘
                                    ▼
                    ┌───────────────────────────────────────┐
                    │   Mock Data Store (JSON transactions)  │
                    └───────────────────────────────────────┘

        ┌──────────────────────────┐
        │   MEMORY  (session)      │ ◀── read/write by Planner
        │  • conversation history  │
        │  • cached agent results  │
        │  • user profile/prefs    │
        └──────────────────────────┘
```

---

## 4. Agent Catalog

Each agent: **Input contract → Reasoning → Tools used → Output contract.**

### 4.1 Planner (Orchestrator) — *the spine*
- **Input:** user message, session memory.
- **Reasoning:** classify intent → select agents → order steps → decide if alerting should run proactively.
- **Tools:** none directly; invokes agents.
- **Output:** `FinalResponse{ answer_text, insights, recommendations, alerts, plan_trace }`.
- **Autonomy demo:** `plan_trace` exposes the decided steps (e.g. `["analyze_spending", "recommend", "alert_check"]`) so reviewers SEE the reasoning.

### 4.2 Spending Analysis Agent — *IN-DEPTH build*
- **Input:** `month` (optional), category filter.
- **Reasoning:** categorize txns → aggregate per category → compute month-over-month trend → flag anomalies via **fixed threshold: any category up >20% MoM** (deterministic; z-score dropped — too noisy over ~7 categories to guarantee the demo fires).
- **Tools:** `get_transactions()`, `get_categories()`.
- **Output:** `SpendingInsight{ totals_by_category, month_trend, anomalies[], summary_text }`.
- **Example:** `{food: 12000 (+25% MoM, ANOMALY), shopping: 8000, travel: 3500}`.

### 4.3 Recommendation Agent
- **Input:** `SpendingInsight`, `user_profile` (injected by Planner).
- **Reasoning:** target highest/anomalous categories → compute achievable reduction → estimate ₹ saved. **Personalized:** reduction aggressiveness scales with `profile.risk_pref` / `profile.savings_goal` (e.g. aggressive saver → 20% cut suggested; conservative → 10%). Two different profiles on the same spending yield different recs.
- **Tools:** `get_budgets()`.
- **Output:** `Recommendations[]{ category, action, est_monthly_saving, rationale }`.
- **Example:** "Reduce food delivery 15% → save ~₹2,000/mo."
- **Skip condition:** if no reducible category found, Planner omits this agent (§5.3).

### 4.4 Alerting Agent
- **Input:** `SpendingInsight` (budgets are a *tool dependency*, fetched via `get_budgets()` — not an upstream contract).
- **Reasoning:** compare category spend vs budget thresholds → flag breach / near-breach (≥90%) / spike.
- **Tools:** `get_budgets()`, `get_balance()`.
- **Output:** `Alerts[]{ severity, category, message }`.
- **Example:** "⚠ Nearing entertainment budget (₹4,500 / ₹5,000)."
- **Run condition:** Planner runs this only when Spending reports an anomaly or a breach is plausible (§5.3).

---

## 5. Orchestration Model

### 5.1 Sequence — "How can I improve my monthly savings?"

```
User ─▶ Planner
        Planner.reason() → intent=IMPROVE_SAVINGS
                         → plan=[spending_analysis, recommendation, alerting]
        Planner ─▶ SpendingAnalysis.run(query, profile) ─▶ tools.get_transactions()
                   ◀─ SpendingInsight
        Planner.branch(insight)  ← data-dependent (§5.3)
        Planner ─▶ Recommendation.run(insight, profile) ─▶ Recommendations[]
        Planner ─▶ Alerting.run(insight, profile)        ─▶ Alerts[]
        Planner.merge() → FinalResponse
        Planner.memory.save(turn)
Planner ─▶ User (answer + insights + recs + alerts)
```

### 5.2 Intent → Plan routing table (autonomous reasoning)

| Intent (detected from query) | Execution plan |
|------------------------------|----------------|
| IMPROVE_SAVINGS | spending → recommend → alert |
| SPENDING_SUMMARY | spending only |
| BUDGET_STATUS | alert (+ spending for context) |
| WHY_OVERSPENT / ANOMALY | spending → alert → recommend |
| GENERAL_ADVICE | spending → recommend |
| GREETING / UNKNOWN | direct reply, no agents |

**Match precedence:** first-match-wins over an ordered keyword list, so a query hitting two intent sets routes deterministically. **Fallthrough:** finance-ish but unmatched → `GENERAL_ADVICE`; non-finance → `UNKNOWN`. Routing is rule/keyword-based now; the **same interface** accepts an LLM classifier later.

### 5.3 Data-dependent branching (autonomous reasoning)

The static table above sets the *candidate* plan. The Planner then prunes/extends it on intermediate results:

| Condition after Spending runs | Planner decision |
|-------------------------------|------------------|
| `insight.anomalies` non-empty **OR** any category ≥90% of budget | run Alerting (surface anomaly and/or near-budget breach) |
| no reducible category (no discretionary category meaningfully above budget/typical) | skip Recommendation |
| anomaly is a one-off credit/refund | downgrade, don't alert |

**Alerting scans independently.** Alerting does *not* rely only on Spending's anomaly list — it pulls `get_budgets()` and checks **every** category vs budget (≥90% near-breach, >100% breach). This is why the entertainment near-budget alert (₹4,500 / ₹5,000 = 90%) fires even though entertainment has no prior-month figure and is therefore not an MoM anomaly.

This is what makes the plan *reasoned* rather than a fixed pipeline — the executed step list depends on data the agent itself produced. (Skip-condition wording is unified here as the single source of truth; §4.3/§4.4 reference it.)

---

## 6. Tool / Function-Calling Layer

Agents never touch the data store directly — they call **typed tools**. Mirrors LLM function-calling.

| Tool | Signature | Returns |
|------|-----------|---------|
| `get_transactions(month=None, category=None)` | filter mock txns | `list[Transaction]` |
| `get_categories()` | category catalog | `list[str]` |
| `get_budgets()` | per-category budgets | `dict[str,float]` |
| `get_balance()` | current balance | `float` |

Each tool has a JSON-serializable schema (name, params, description) registered in a `TOOLS` registry — exactly what an LLM tool-calling loop would consume. `plan_trace` logs every tool call for the demo.

---

## 7. Memory & Context Design

| Layer | Holds | Lifetime |
|-------|-------|----------|
| **Conversation history** | last N turns (user+assistant) | session |
| **Result cache** | `last_intent` + `last_insight` so follow-ups skip recompute | session |
| **User profile** | name, currency, `risk_pref`, `savings_goal`, budgets | seeded mock, session |

**Follow-up resolution:** "What about just food?" → Planner detects a *referential* follow-up, extracts the category ("food"), and filters `last_insight` (+ pulls the food-specific recommendation/anomaly delta) **without recompute**. Cache stores `last_intent` + `last_insight` per `session_id` so the follow-up binds to the correct prior query.

**Concurrency:** single-flight-per-session assumed (one in-flight turn per `session_id`). Fine for the demo; note for real-LLM latency a per-session lock is needed to avoid the in-memory dict racing. In-memory now; swap for Redis later.

---

## 8. Conversational Web UI

- Single page: chat transcript + input box.
- Right/side panel renders structured output: **Insights card**, **Recommendations card**, **Alerts card** (color-coded by severity).
- A collapsible **"Agent trace"** panel shows the Planner's plan + each tool call → proves agentic behavior live in the demo.
- **Trace renders sequentially** (each step appears as the agent "runs") and shows tool args + row counts — e.g. `get_transactions(month=May) → 27 rows`. Visible intermediate state is what reads as *agentic* vs hardcoded.
- Vanilla HTML/CSS/JS (no build step). `fetch('/chat')`.

---

## 9. Tech Stack & Project Structure

**Stack:** Python 3.11+, FastAPI, Uvicorn, vanilla JS frontend, pytest. Zero LLM deps.

```
personal-finance-agent/
├── HLD.md                  ← this doc
├── LLD.md                  ← next, after approval
├── README.md
├── requirements.txt
├── app/
│   ├── main.py             ← FastAPI app, /chat endpoint
│   ├── orchestrator.py     ← Planner agent
│   ├── agents/
│   │   ├── spending.py     ← Spending Analysis (in-depth)
│   │   ├── recommend.py    ← Recommendation
│   │   └── alerting.py     ← Alerting
│   ├── tools/
│   │   └── banking_tools.py← mock tool layer + registry
│   ├── memory/
│   │   └── store.py        ← session memory
│   ├── models.py           ← dataclasses (contracts)
│   └── data/
│       └── transactions.json← mock dataset
├── web/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── tests/
    └── test_agents.py
```

---

## 10. Mock Data

~60–80 transactions across 2–3 months, categories: food, shopping, travel, entertainment, utilities, groceries, transfers. Fields: `id, date, merchant, category, amount, type(debit/credit)`.

**Pinned demo numbers (hand-verified so the demo always fires):**

| Category | Prior month | Current month | Trigger |
|----------|-------------|---------------|---------|
| food | ₹9,600 | ₹12,000 | **+25% MoM → anomaly** (>20% threshold) |
| entertainment | — | ₹4,500 (budget ₹5,000) | **90% → near-budget alert** |
| shopping | ₹8,000 | ₹8,000 | normal |
| travel | ₹3,500 | ₹3,500 | normal |

`transactions.json` is **pre-authored** with exactly these sums so the anomaly + alert are deterministic, not emergent.

---

## 11. Demo Scenarios

1. "How can I improve my monthly savings?" → full pipeline (all 4 agents).
2. "Summarize my spending last month." → spending only.
3. "Why did I overspend?" → spending → alert → recommend (food anomaly).
4. Follow-up "What about food specifically?" → memory-backed, no recompute. **Adds value** (not an echo): surfaces the food anomaly delta (+₹2,400 / +25%) *and* the food-specific recommendation, proving memory does work.

---

## 12. Build Timeline (60 min *live* build)

This is the 60-min **live** budget. Honest total is ~70–75 min including the mechanical pre-clock prep below (pre-authoring data/models/HTML scaffold) — called out so the estimate isn't disguised.

**Pre-clock (min −10):** pre-author `transactions.json` (pinned numbers), `models.py` dataclasses, and a static `index.html` skeleton. Mechanical, shouldn't burn live time.

| Min | Task |
|-----|------|
| 0–20 | Spending Analysis agent (in-depth) + tools + wire mock data |
| 20–35 | Planner orchestrator + routing + branching + memory |
| 35–48 | Recommendation + Alerting agents |
| 48 | **pytest smoke test** — prints full FinalResponse to console (CLI fallback if UI breaks) |
| 48–60 | WebUI JS wiring (skeleton already exists) + live demo |

**Cut-if-behind order:** drop streaming trade animation → drop Alerting (keep 3 agents) → drop side-panel cards (chat text only). Never cut the pytest smoke test.

### 12.1 Parallel Execution Plan

The §12 table is the **sequential** baseline (safe fallback). The architecture's typed contracts + one-file-per-agent seams allow compressing it by parallelizing independent work. Analysis below (deep-analysis, 2-phase steelman, HIGH confidence).

**Build atoms + dependencies:**

| ID | Artifact | Needs | min |
|----|----------|-------|-----|
| M | `models.py` (contracts) | — | 5 |
| D | `data/transactions.json` | — | 4 |
| T | `tools/banking_tools.py` | M, D | 5 |
| MEM | `memory/store.py` | M | 5 |
| SP | `agents/spending.py` (in-depth) | M, T | **12 ← long pole** |
| RC | `agents/recommend.py` | M, T | 7 |
| AL | `agents/alerting.py` | M, T | 7 |
| ORCH | `orchestrator.py` | SP, RC, AL, MEM | 10 (skel 6 + wire 4) |
| API | `main.py` | ORCH | 5 (skel 2 + wire 3) |
| WEB | `web/` skeleton | M-shape | 6 |
| WIRE | `web/app.js` | /chat contract | 6 |
| SMOKE | `tests/` pytest | agents+ORCH | 3 |
| INT | integration + demo | API, WIRE | 5 |

**Dependency graph:**

```
M ──┬─▶ T ──┬─▶ SP ─┐
    │       ├─▶ RC ─┤
D ──┘       └─▶ AL ─┤
M ─────▶ MEM ───────┼─▶ ORCH ─▶ API ─▶ INT
M ─────▶ WEB ─▶ WIRE ───────────┘      ▲
              SP,RC,AL,ORCH ─▶ SMOKE ──┘
```

**Critical path (irreducible serial spine):**

```
M(5) → T(5) → SP(12) → ORCH_wire(4) → API_wire(3) → INT(5)  ≈ 34 min
```

`SP` (Spending, in-depth) is the long pole. **The whole build is gated by how fast Spending Analysis gets built** — everything else hides under it or runs off-path.

**Recommended parallelism — the 80/20 (high-leverage, low-risk only):**

| Track | Work | Saves | Risk |
|-------|------|-------|------|
| **GATE** | Lock `M` + `D` FIRST, treat immutable — all parallel work depends on frozen contracts | — | single point of failure → lock fully before fan-out |
| **Spine** (single-threaded) | `M → T → SP → ORCH_wire → API_wire → INT` — author yourself for full context | — | integration-sensitive; don't parallelize |
| **Track 1 — agents** | `RC ∥ AL` run concurrently under `SP` | ~14 min | low (shared frozen `SpendingInsight`) |
| **Track 2 — frontend** | `WEB + WIRE` against a **mocked `/chat`** JSON response | ~12 min | ~zero (decoupled from backend) |
| **SMOKE** | pytest runs *inside* the join, not after — catches contract drift in seconds | — | — |

**Do NOT parallelize** M, T, ORCH_wire, API_wire (short, integration-sensitive serial spine — coordination tax > payoff).

**Wall-clock:** ~34 min best · **~38–42 min realistic** (risk-weighted, dominated by join cleanliness) · 60 min safe fallback.

**Cut-if-behind:** parallel coordination fails → fall back to the §12 sequential timeline. Hard floor, no downside — parallelism is pure optional upside. Amdahl caps the gain at the 34-min spine; we don't pretend to beat it.

---

## 13. Extensibility

- **Real LLM:** replace rule-based `reason()` / `classify_intent()` with a Claude tool-calling loop; tool registry (§6) already LLM-shaped.
- **LangGraph:** Planner = graph; agents = nodes; routing table (§5.2) = conditional edges. No restructure needed.
- **Persistence:** swap in-memory memory + JSON store for DB.

---

## 14. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| 1-hour overrun | Spending in-depth first; others rule-based, time-boxed |
| Mock reasoning looks "fake" | `plan_trace` + tool-call log make agentic flow visible |
| Scope creep on WebUI | Single page, vanilla JS, no framework |
| Anomaly logic edge cases | Fixed >20% MoM threshold + pinned data so demo always fires |
| Live UI wiring fails at min 55 | pytest smoke at min 48 = guaranteed CLI fallback |

---

## 15. Run & Demo (deliverable)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload      # serves API + static web/
# open http://localhost:8000
pytest -q                          # smoke: prints full FinalResponse (CLI fallback demo)
```

**Demo deliverables:** README quickstart (above), the 4 scenarios (§11), and a scripted transcript / screenshot of the full-pipeline run as the artifact reviewers can replay.
```
