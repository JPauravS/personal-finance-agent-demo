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
