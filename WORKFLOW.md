# Agentic Workflow

How the system *behaves at runtime* — companion to `ARCHITECTURE.md` (structure).

Read **progressively**: each section opens with an **L1** plain line, then a `Go deeper` block for the **L2** mechanism, and a nested `Internals` block for **L3** code-level detail. Every trace is captured from the running code.

> **L1 · Intuition** → **L2 · Mechanism** → **L3 · Internals**

---

## What makes it agentic

**L1.** The system doesn't follow one fixed script. It **decides what to do**, **calls tools to get data**, **changes its plan based on what it finds**, and **remembers the last answer**.

<details><summary><b>Go deeper — L2 · the four properties &amp; their proof</b></summary>

| Property | Where it shows | Proof |
|----------|----------------|-------|
| Autonomous reasoning | Planner classifies intent → builds its own plan | `plan_trace[0]` names the plan |
| Tool / function calling | Agents call typed tools, never the store | trace logs every `get_*()` + row count |
| Data-dependent flow | Plan pruned / extended on intermediate results | Alerting runs even when unplanned |
| Memory / context | Follow-ups answered from cache | trace: `reused cached insight` |

The `plan_trace` — a `list[str]` every agent appends to — is the single artifact proving all four. It renders in the UI's "Agent trace" panel.

<details><summary><b>Internals — L3 · why a trace at all</b></summary>

A rule engine has no visible "thoughts" — so reasoning is **emitted**, not inferred. Each agent receives the shared `trace: list[str]` by reference and appends to it; the Planner owns the list and returns it as `FinalResponse.plan_trace`.

This is deliberately the same shape a real LLM tool-calling loop produces. Swapping the rule-based `reason()` for a Claude loop later changes the *origin* of the lines, not the contract — UI and tests are unaffected.

</details>
</details>

---

## Turn lifecycle

**L1.** Each message runs through one function: **look for a follow-up → figure out intent → run the right agents → merge one answer**.

<details><summary><b>Go deeper — L2 · the 9 steps of <code>Planner.handle()</code></b></summary>

```
1  record the user turn in memory
2  follow-up?  → answer from cached insight, RETURN (no agents)
3  classify_intent(message)            → intent
4  plan = ROUTING[intent]              → candidate step list
5  plan empty (greeting/unknown)       → direct reply, RETURN
6  insight = spending.run(...)         → always first; cache it
7  branch:  run_alert = ("alert" in plan) OR insight.anomalies
           run_rec   = ("recommend" in plan)
8  recs/alerts = run agents conditionally
9  merge → FinalResponse, persist memory
```

Step 7 is the autonomy: the executed step list is **decided from data the agent itself produced**, not fixed up front.

<details><summary><b>Internals — L3 · trace ordering &amp; the <code>insert(0)</code> trick</b></summary>

Spending runs (step 6) and appends its tool-call lines *before* the Planner knows it succeeded. Only afterward does the Planner prepend the header:

```python
insight = spending.run(message, profile, trace)
self.store.set_last_insight(session_id, insight)
trace.insert(0, f"Planner → intent={intent}, plan={plan}")
```

`trace.insert(0, ...)` guarantees the narrative reads top-down (`Planner → … then SpendingAnalysis → …`) even though the spending lines were appended first.

The proactive line is appended only in the override case: `if run_alert and "alert" not in plan`. A planned alert stays silent about the branch; an *unplanned* one announces itself.

</details>
</details>

---

## Example 01 — full pipeline

**L1.** *"How can I improve my monthly savings?"* → the system reads the month's spending, spots that food jumped, suggests cuts, and warns that entertainment is near its budget.

<details><summary><b>Go deeper — L2 · captured trace &amp; outputs</b></summary>

`intent=IMPROVE_SAVINGS · profile=balanced · reduction=15%`

```
Planner → intent=IMPROVE_SAVINGS, plan=['spending', 'recommend', 'alert']
SpendingAnalysis → get_transactions(month=2026-05) → 14 rows
SpendingAnalysis → get_transactions(month=2026-04) → 10 rows
SpendingAnalysis → categorised 6 categories, 1 anomaly(ies)
Recommendation → get_budgets() → evaluating 4 discretionary categories
Alerting → get_budgets(), get_balance() → scanning 6 categories vs budget
```

| | |
|--|--|
| Totals | food ₹12000 · entertainment ₹4500 · shopping ₹8000 · travel ₹3500 · groceries ₹6200 · utilities ₹3000 |
| Anomaly | food **+25.0%** (₹9600 → ₹12000) |
| Recs | food 15% → ₹1800/mo · shopping 15% → ₹1200/mo |
| Alert | warning — entertainment ₹4500 / ₹5000 (90%) |

**Final answer:** May spending ₹37200 across 6 categories. Top: food ₹12000. 1 anomaly: food +25.0%. Top tip: Reduce food spending by 15% (~₹1800/mo). Alert: Nearing budget: entertainment ₹4500 / ₹5000 (90%).

<details><summary><b>Internals — L3 · debits-only, anomaly-first ranking, the 15%</b></summary>

- **Debits only.** Spending sums `type == "debit"` per category; the salary credit is excluded — that's why 14 May rows collapse to 6 spend categories.
- **Why 20% fixed, not z-score.** Two months gives no distribution to estimate variance. `pct > 20.0` is deterministic and demo-stable. food: `(12000−9600)/9600 = 25.0%` → flagged.
- **Anomaly ranked first.** Recommendation sorts by `(c not in anomaly_cats, -spend)`. `False < True`, so flagged categories sort ahead even if another spent more. Essentials (`groceries/utilities`) aren't in `DISCRETIONARY`, so never reduced.
- **The 15%.** `REDUCTION_BY_RISK = {conservative:10, balanced:15, aggressive:20}`. `balanced` → 15%. `round(12000 × 0.15) = 1800`. A different profile yields a different number on identical spending.

</details>
</details>

---

## Example 02 — proactive branching

**L1.** *"Summarize my spending last month."* only asked for a summary — but the system noticed the food anomaly and **raised an alert on its own**.

<details><summary><b>Go deeper — L2 · the unplanned step in the trace</b></summary>

`intent=SPENDING_SUMMARY · planned=['spending']`

```
Planner → intent=SPENDING_SUMMARY, plan=['spending']
SpendingAnalysis → get_transactions(month=2026-05) → 14 rows
SpendingAnalysis → get_transactions(month=2026-04) → 10 rows
SpendingAnalysis → categorised 6 categories, 1 anomaly(ies)
Alerting → get_budgets(), get_balance() → scanning 6 categories vs budget
Planner → proactively ran Alerting (anomaly detected)
```

Alerting **was not in the plan**, yet it ran. This is the difference between **scripted** and **reasoned**.

<details><summary><b>Internals — L3 · the one boolean that does it</b></summary>

```python
run_alert = ("alert" in plan) or bool(insight.anomalies)
...
if run_alert and "alert" not in plan:
    trace.append("Planner → proactively ran Alerting (anomaly detected)")
```

Because `plan == ['spending']`, `"alert" in plan` is False — the alert fires purely on `insight.anomalies` being non-empty. The trace line is conditional on the override, so it appears here but not in Example 01 (where alert was planned).

</details>
</details>

---

## Example 03 — memory

**L1.** *"What about food specifically?"* right after → the system answers instantly from what it already computed. **No agents, no tool calls.**

<details><summary><b>Go deeper — L2 · zero-recompute trace</b></summary>

`agents run=0 · tool calls=0`

```
Planner → referential follow-up detected
Planner → reused cached insight for 'food' (no recompute)
```

**Final answer:** You spent ₹12000 on food this month (up 25% vs last month). Flagged anomaly: food up 25.0% vs prior month. Tip: Reduce food spending by 15% (~₹1800/mo).

It **adds value** — the +25% delta and a targeted tip — proving the cache is used, not echoed.

<details><summary><b>Internals — L3 · detection rule, object identity, a real nuance</b></summary>

- **Detection.** `_is_followup()` returns a category only if a prior insight is cached AND the query is referential — `startswith(("what about","and ","just ","how about"))` *or* `len(split) ≤ 3` — AND a known category word appears.
- **Identity preserved.** The returned `FinalResponse.insights` is the *same object* pulled from the cache (`get_last_insight`), not a copy — verifiable by `is`. The follow-up only slices it.
- **Honest nuance.** The follow-up path uses a flat `_FOLLOWUP_PCT = 15`, *not* the risk-driven percentage the Recommendation agent uses. With `balanced` both are 15%, so they agree here — but an `aggressive` profile would get 20% from the agent and 15% from a follow-up. A known, documented simplification, not a bug.

</details>
</details>

---

## Routing reference

**L1.** The words in your message decide which agents run.

<details><summary><b>Go deeper — L2 · intent table &amp; data-dependent overrides</b></summary>

| Intent | Candidate plan |
|--------|----------------|
| IMPROVE_SAVINGS | spending → recommend → alert |
| SPENDING_SUMMARY | spending |
| BUDGET_STATUS | spending → alert |
| WHY_OVERSPENT | spending → alert → recommend |
| GENERAL_ADVICE | spending → recommend |
| GREETING / UNKNOWN | direct reply, no agents |

| Condition (after Spending) | Override |
|----------------------------|----------|
| `insight.anomalies` non-empty | run Alerting even if not planned |
| no discretionary category | Recommendation returns `[]` |
| follow-up + cached insight | bypass all agents |

<details><summary><b>Internals — L3 · first-match precedence &amp; concurrency</b></summary>

- **Precedence is order, not score.** `classify_intent` checks an *ordered* keyword list and returns on first hit. Greeting is matched by exact word / prefix first (so "hi there" ≠ a finance query). A query touching two groups routes to whichever appears earlier — deterministic by construction.
- **Fallthrough.** No keyword group hit but a finance term present → `GENERAL_ADVICE`; otherwise `UNKNOWN` (polite fallback, no agents).
- **Concurrency.** The store is single-flight-per-session — one in-flight turn per `session_id`. Fine for the demo; a real-LLM build adds a per-session lock so the in-memory dict can't race. Swap the dict for Redis; the interface stays.

</details>
</details>
