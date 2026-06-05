# Personal Finance Advisor — Agentic Prototype

An agentic multi-agent personal finance advisor. A **Planner** orchestrator
classifies intent, builds a data-dependent plan, and sequences three specialist
agents — **Spending Analysis**, **Recommendation**, and **Alerting** — through a
typed mock tool layer over a deterministic JSON transaction store. Results merge
into a single typed `FinalResponse` (answer + insights + recommendations +
alerts + a human-readable `plan_trace`), and per-session memory enables
follow-up questions without recomputation. Star topology, rule-based reasoning,
**zero LLM dependencies** — every agentic step is visible in the trace.

## Live

| | |
|--|--|
| **App** (chat UI + `/api/chat`) | https://personal-finance-advisor.joshipaurav.workers.dev |
| **Architecture** (interactive doc-site) | https://pf-advisor-arch.pages.dev |
| **Agentic Workflow** (progressive L1→L3 walkthrough) | https://pf-advisor-arch.pages.dev/workflow |

## Quickstart (local)

```bash
pip install fastapi "uvicorn[standard]" httpx pytest
uvicorn app.main:app --reload      # serves the API + static web UI
# open http://localhost:8000
```

> Prefer `uv`? The FastAPI/uvicorn/test deps live in the **`local`** dependency
> group (kept out of the default env so they don't bloat the Cloudflare Worker —
> see **Deploy to Cloudflare** below). Use them with:
> `uv sync --group local` then `uv run --group local uvicorn app.main:app --reload`.
> (`requirements.txt` was removed because `pywrangler` requires `pyproject.toml`
> as the single dependency source.)

Run the test suite (includes the end-to-end demo-scenario acceptance tests):

```bash
py -m pytest -q      # or: uv run --group local pytest -q
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

## Deploy to Cloudflare (Python Workers)

**Live:** https://personal-finance-advisor.joshipaurav.workers.dev

The same agent pipeline runs at the edge on Cloudflare Python Workers (Pyodide).
The Worker entry [`worker_main.py`](worker_main.py) reuses the `app` package
verbatim but swaps the HTTP boundary for the **native Workers handler** (no
FastAPI/pydantic — the pipeline is pure stdlib, which keeps the bundle under the
free-plan 3 MiB limit). The vanilla web UI is served from
[`worker-assets/`](worker-assets/) via the static-assets binding;
`wrangler.jsonc` wires it together. Requires `uv` (the toolchain installs its own
Python 3.12 + Pyodide).

```bash
npm run dev        # uv run pywrangler dev   — local edge runtime at 127.0.0.1:8787
npm run deploy     # uv run pywrangler deploy — ships to *.workers.dev
```

`worker-assets/` is a flat copy of `web/` (index at root, JS/CSS under `static/`);
rebuild it after editing `web/` with:

```bash
cp web/index.html worker-assets/index.html
cp web/app.js     worker-assets/static/app.js
cp web/style.css  worker-assets/static/style.css
```

## Architecture & Design

- **Architecture (structure — *what it is*):** [`ARCHITECTURE.md`](ARCHITECTURE.md)
  · live: https://pf-advisor-arch.pages.dev
- **Agentic Workflow (runtime — *what it does*):** [`WORKFLOW.md`](WORKFLOW.md) —
  L1 intuition → L2 mechanism → L3 internals, traces captured from the running
  orchestrator · live: https://pf-advisor-arch.pages.dev/workflow
- **High-level design:** [`HLD.md`](HLD.md)
- **Implementation plan (this build):** [`LLD/`](LLD/) — `LLD_INDEX.md` is the
  entry point (frozen contracts, gate protocol, task map).
- **Build history (the 4 sessions that made this):** [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md)
  · dev quick-reference: [`CLAUDE.md`](CLAUDE.md)
