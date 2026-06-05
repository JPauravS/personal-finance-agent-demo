# Architecture

Agentic personal finance advisor. **Orchestrator + specialists** pattern. Mock-first, swap-ready to real LLM / LangGraph.

## Diagram

```
                 ┌──────────────────────┐
                 │     Web UI (chat)    │
                 │  HTML/JS ─HTTP/JSON─▶ │
                 └──────────┬───────────┘
                            │ POST /chat {message, session_id}
                            ▼
                 ┌──────────────────────┐
                 │   FastAPI backend    │
                 └──────────┬───────────┘
                            ▼
          ┌─────────────────────────────────────┐
          │        PLANNER (orchestrator)        │
          │  parse → plan → route → merge        │
          │  read/write memory                   │
          └───┬────────────┬────────────┬────────┘
              │            │            │
     ┌────────▼──┐  ┌──────▼─────┐  ┌───▼────────┐
     │ SPENDING  │  │RECOMMENDA- │  │  ALERTING  │
     │ ANALYSIS  │  │   TION     │  │            │
     └────────┬──┘  └──────┬─────┘  └───┬────────┘
              └────────────┼────────────┘
                           ▼
          ┌─────────────────────────────────────┐
          │      TOOL LAYER (mock APIs)          │
          │ get_transactions  get_categories     │
          │ get_budgets       get_balance        │
          └──────────────────┬──────────────────┘
                             ▼
          ┌─────────────────────────────────────┐
          │   Mock data store (JSON txns)        │
          └─────────────────────────────────────┘

     ┌──────────────────────────┐
     │   MEMORY (session)       │ ◀── Planner read/write
     │ history · cache · profile│
     └──────────────────────────┘
```

## Components

| Component | Role |
|-----------|------|
| **Planner** | Spine. Classify intent → build plan → sequence specialists → branch on results → merge `FinalResponse`. |
| **Spending Analysis** | Categorize txns, MoM trend, flag anomaly (>20% MoM). In-depth agent. |
| **Recommendation** | Target high categories, compute ₹ saved. Scales to `profile.risk_pref`. |
| **Alerting** | Scan every category vs budget. Flag breach / near-breach (≥90%). |
| **Tool layer** | Typed mock APIs. Agents never touch store directly. LLM-function-call shaped. |
| **Memory** | Session history + result cache + user profile. In-memory. |

## Control flow

1. UI POSTs message → FastAPI → Planner.
2. Planner classifies intent → candidate plan (§routing).
3. Spending runs first (`run(query, profile)`).
4. Planner **branches on result**: Alerting only if anomaly/near-breach; skip Recommendation if nothing reducible.
5. Specialists return typed contracts → Planner merges → `FinalResponse`.
6. Planner saves turn to memory. UI renders cards + agent trace.

## Routing

| Intent | Plan |
|--------|------|
| IMPROVE_SAVINGS | spending → recommend → alert |
| SPENDING_SUMMARY | spending |
| BUDGET_STATUS | alert (+ spending context) |
| WHY_OVERSPENT | spending → alert → recommend |
| GENERAL_ADVICE | spending → recommend |
| GREETING / UNKNOWN | direct reply, no agents |

First-match-wins keyword routing. Same interface accepts LLM classifier later.

## Why this architecture

| Principle | Payoff |
|-----------|--------|
| **Orchestrator owns control flow** | Specialists never call each other → acyclic, debuggable star topology. |
| **Typed contracts** | Dataclasses not free text → testable, predictable. |
| **Mock-first, swap-ready** | Rule-based `reason()` now; maps 1:1 to LangGraph nodes/edges + LLM tool registry. Real model drops in, zero restructure. |
| **Data-dependent autonomy** | Executed steps depend on agent's own output → reasoned, not fixed pipeline. |
| **One file per agent** | Parallel build seams; modular. |

**Rejected:** monolith (fails multi-agent req, no visible orchestration) · peer-to-peer (cycles, coordination tax) · real-LLM-now (no key, 1-hr budget).

## Extensibility

- **LLM:** replace `reason()`/`classify_intent()` with Claude tool-calling loop.
- **LangGraph:** Planner = graph, agents = nodes, routing table = conditional edges.
- **Persistence:** swap in-memory + JSON for DB.
