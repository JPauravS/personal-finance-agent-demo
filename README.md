# Personal Finance Advisor — Agentic Prototype

An agentic multi-agent personal finance advisor. A **Planner** orchestrator
classifies intent, builds a data-dependent plan, and sequences three specialist
agents — **Spending Analysis**, **Recommendation**, and **Alerting** — through a
typed mock tool layer over a deterministic JSON transaction store. Results merge
into a single typed `FinalResponse` (answer + insights + recommendations +
alerts + a human-readable `plan_trace`), and per-session memory enables
follow-up questions without recomputation. Star topology, rule-based reasoning,
**zero LLM dependencies** — every agentic step is visible in the trace.

## Quickstart (local)

```bash
uv sync                                # installs runtime + dev deps (uv-managed venv)
uv run uvicorn app.main:app --reload   # serves the API + static web UI
# open http://localhost:8000
```

> No `uv`? `pip install fastapi "uvicorn[standard]" httpx pytest`, then
> `uvicorn app.main:app --reload`. (`requirements.txt` was removed because
> Cloudflare's `pywrangler` requires `pyproject.toml` as the single dependency
> source — see **Deploy to Cloudflare** below.)

Run the test suite (includes the end-to-end demo-scenario acceptance tests):

```bash
uv run pytest -q     # or: py -m pytest -q
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

The same FastAPI pipeline runs at the edge on Cloudflare Python Workers (Pyodide).
The Worker entry is [`worker_main.py`](worker_main.py) (reuses the `app` package
verbatim, swaps the HTTP boundary); the vanilla web UI is served from
[`worker-assets/`](worker-assets/) via the Workers static-assets binding;
`wrangler.jsonc` wires it together. Requires `uv` (the toolchain installs its own
Python 3.12).

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

- **High-level design:** [`HLD.md`](HLD.md)
- **Implementation plan (this build):** [`LLD/`](LLD/) — `LLD_INDEX.md` is the
  entry point (frozen contracts, gate protocol, task map).
