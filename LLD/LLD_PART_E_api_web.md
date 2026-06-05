# LLD Part E — API + Web (Tasks 9–10)

> Read `LLD_INDEX.md` first. Frozen contracts + two-tier GATE protocol live there.
> Build atoms: API (FastAPI boundary), WEB+WIRE (vanilla-JS frontend). These sit on top of ORCH (Task 8) and the full Part A foundation.

**HLD coverage:** §5 (API boundary), §8 (web UI + visible agent trace), §9 (structure).

**Depends on:** Task 8 (`app.orchestrator.Planner`), Task 4 (`app.memory.store.SessionStore`), Task 1 (`app.models.FinalResponse`). The API serializes typed dataclasses via `dataclasses.asdict` at the boundary — agents never return dicts.

---

## Task 9: FastAPI App (`app/main.py`)

**Files:**
- Create: `app/main.py`, `requirements.txt`
- Test: `tests/test_api.py`

The HTTP boundary (HLD §5). A single `POST /api/chat` endpoint drives `Planner.handle`, serializes the `FinalResponse` with `asdict`, and returns plain JSON. `GET /` serves the web UI; `/static` mounts the `web/` directory. The endpoint is thin by design — all reasoning lives in the orchestrator and agents.

- [ ] **Step 1: Create `requirements.txt`**

Create `requirements.txt` at the repo root with the runtime + test deps:

```
fastapi
uvicorn[standard]
httpx
pytest
```

(`httpx` is required by `fastapi.testclient.TestClient`.) Install with `py -m pip install -r requirements.txt`.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_chat_savings_full_response():
    r = client.post("/api/chat", json={
        "message": "How can I improve my monthly savings?",
        "session_id": "t1",
    })
    assert r.status_code == 200
    body = r.json()
    # FinalResponse serialized via asdict — all five keys present
    for key in ("answer_text", "insights", "recommendations", "alerts", "plan_trace"):
        assert key in body
    # insights recurses into a plain dict; pinned food May total
    assert body["insights"]["totals_by_category"]["food"] == 12000.0
    # recommendations non-empty, alerts carry the entertainment near-breach warning
    assert body["recommendations"]
    assert any(a["category"] == "entertainment" and a["severity"] == "warning"
               for a in body["alerts"])
    # visible agent trace is a non-empty list of human-readable steps
    assert isinstance(body["plan_trace"], list) and body["plan_trace"]


def test_chat_greeting_is_empty_advisory():
    r = client.post("/api/chat", json={"message": "hi", "session_id": "g1"})
    assert r.status_code == 200
    body = r.json()
    assert body["insights"] is None
    assert body["recommendations"] == []


def test_multi_turn_reuses_cached_insight():
    # first turn computes and caches the insight for session t2
    r1 = client.post("/api/chat", json={
        "message": "How can I improve my monthly savings?",
        "session_id": "t2",
    })
    assert r1.status_code == 200
    # follow-up in the SAME session should reuse the cached insight (no recompute)
    r2 = client.post("/api/chat", json={
        "message": "what about food?",
        "session_id": "t2",
    })
    assert r2.status_code == 200
    trace_text = " ".join(r2.json()["plan_trace"]).lower()
    assert "cache" in trace_text or "reused" in trace_text or "no recompute" in trace_text


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "<html" in r.text.lower()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'` (and/or `ModuleNotFoundError` for `fastapi` if deps not yet installed — install Step 1 first).

- [ ] **Step 4: Write minimal implementation**

```python
# app/main.py
"""FastAPI boundary for the Personal Finance Advisor (HLD §5).

Thin HTTP layer: one chat endpoint drives the Planner orchestrator and
serializes the typed FinalResponse with dataclasses.asdict. Static web UI
is served from the sibling web/ directory.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dataclasses import asdict
from pathlib import Path

from app.memory.store import SessionStore
from app.orchestrator import Planner

app = FastAPI(title="Personal Finance Advisor")

# Single process-wide store + planner; session isolation is by session_id.
_store = SessionStore()
_planner = Planner(_store)


class ChatIn(BaseModel):
    message: str
    session_id: str = "default"


@app.post("/api/chat")
def chat(body: ChatIn):
    final = _planner.handle(body.message, body.session_id)
    # asdict recurses nested dataclasses into JSON-serializable dicts.
    return asdict(final)


_WEB = Path(__file__).resolve().parent.parent / "web"


@app.get("/")
def index():
    return FileResponse(_WEB / "index.html")


# Serve web/ assets (app.js, style.css) under /static.
# check_dir=False: do NOT validate the directory at import time, so app.main
# imports cleanly even if web/ has not been built yet (Task 10). Without this,
# StaticFiles raises RuntimeError at import and ALL of test_api fails to collect.
app.mount("/static", StaticFiles(directory=str(_WEB), check_dir=False), name="static")
```

> **Note on `/` ordering and the `check_dir=False` guard:** the `GET /` route is declared *before* `app.mount("/static", ...)`, and the mount only owns the `/static` prefix, so the root route is unaffected. **`check_dir=False` is required**: `StaticFiles` otherwise validates the directory *at instantiation* (import time), so if `web/` does not exist yet (Task 10 not run), importing `app.main` raises `RuntimeError` and the entire `tests/test_api.py` module fails to collect — not just `test_index_served`. With `check_dir=False`, the three chat-path API tests pass independently of `web/`; only `test_index_served` needs `web/index.html` (Task 10) present, since `GET /` returns `FileResponse(web/index.html)` (a request-time 404 if missing, never an import error).

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_api.py -v`
Expected: PASS (4 tests). If `test_index_served` errors on a missing `web/` directory, create `web/index.html` (Task 10) first — the chat-path tests are independent of the static mount.

- [ ] **Step 6: Commit**

```bash
git add app/main.py requirements.txt tests/test_api.py
git commit -m "feat: FastAPI boundary (/api/chat + static web mount)"
```

**GATE — Task 9**
- **Tier A:** `pytest tests/test_api.py -v` → 4 pass.
- **Tier B:** `pytest -q` → all green (full backend + API). End-to-end behavior now holding: an HTTP client gets the complete, JSON-serialized `FinalResponse` for the savings scenario (food=12000, entertainment warning, non-empty recommendations and trace); greetings return an empty advisory; and a same-session follow-up reuses the cached insight rather than recomputing — the full orchestration is reachable over the wire.

---

## Task 10: Web UI (`web/index.html`, `web/app.js`, `web/style.css`)

**Files:**
- Create: `web/index.html`, `web/app.js`, `web/style.css`
- Test: `tests/test_web_assets.py`

A single-page vanilla chat UI (HLD §8): a chat transcript + input on the left; a side panel with three color-coded cards (Insights, Recommendations, Alerts); and a collapsible **Agent trace** panel that renders `plan_trace` lines **sequentially** (each line staggered via `setTimeout`) so the agentic steps appear to "stream" — making the orchestration visible. Zero frameworks, zero build step. The structural test guards the HTML↔JS wiring (ids + endpoint string); full visual verification is manual.

The element-id contract (HTML must expose, JS must reference): `chat`, `msg`, `chat-form`, `card-insights`, `card-recs`, `card-alerts`, `trace`, `trace-toggle`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web_assets.py
from pathlib import Path

WEB = Path("web")
HTML = WEB / "index.html"
JS = WEB / "app.js"
CSS = WEB / "style.css"


def test_html_exists_and_wires_assets():
    assert HTML.exists()
    html = HTML.read_text(encoding="utf-8")
    # script + stylesheet wired via the /static mount
    assert '<script src="/static/app.js"></script>' in html
    assert 'href="/static/style.css"' in html
    # the element ids app.js drives
    for el_id in ("chat", "msg", "chat-form",
                  "card-insights", "card-recs", "card-alerts",
                  "trace", "trace-toggle"):
        assert f'id="{el_id}"' in html, f"missing id={el_id} in index.html"


def test_app_js_posts_to_chat_and_renders_trace():
    assert JS.exists()
    js = JS.read_text(encoding="utf-8")
    assert "/api/chat" in js
    assert "fetch(" in js
    assert "plan_trace" in js
    # references the three card containers it populates
    for el_id in ("card-insights", "card-recs", "card-alerts"):
        assert el_id in js
    # fixed web session id
    assert "web-session" in js


def test_css_non_empty():
    assert CSS.exists()
    assert CSS.read_text(encoding="utf-8").strip()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_assets.py -v`
Expected: FAIL — `assert HTML.exists()` is `False` (`web/index.html` not created yet).

- [ ] **Step 3: Write minimal implementation**

Create `web/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Personal Finance Advisor</title>
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body>
  <header class="topbar">
    <h1>Personal Finance Advisor</h1>
    <span class="sub">Aarav · ₹ · balanced</span>
  </header>

  <main class="layout">
    <!-- Left: chat -->
    <section class="chat-pane">
      <div id="chat" class="chat" aria-live="polite"></div>
      <form id="chat-form" class="composer" autocomplete="off">
        <input id="msg" class="msg-input" type="text"
               placeholder="Ask about your spending, savings, budgets…" />
        <button type="submit" class="send-btn">Send</button>
      </form>
    </section>

    <!-- Right: insight/recs/alerts + agent trace -->
    <aside class="side">
      <article class="card card-insights">
        <h2>Insights</h2>
        <div id="card-insights" class="card-body muted">No insights yet.</div>
      </article>
      <article class="card card-recs">
        <h2>Recommendations</h2>
        <div id="card-recs" class="card-body muted">No recommendations yet.</div>
      </article>
      <article class="card card-alerts">
        <h2>Alerts</h2>
        <div id="card-alerts" class="card-body muted">No alerts.</div>
      </article>

      <article class="card card-trace">
        <button id="trace-toggle" class="trace-toggle" type="button"
                aria-expanded="true">Agent trace ▾</button>
        <ol id="trace" class="trace"></ol>
      </article>
    </aside>
  </main>

  <script src="/static/app.js"></script>
</body>
</html>
```

Create `web/app.js`:

```javascript
// Personal Finance Advisor — vanilla front-end (HLD §8).
// Posts to /api/chat, renders the chat transcript, populates the three
// side cards, and streams plan_trace lines sequentially for a visible
// agentic trace. No frameworks, no build step.

const SESSION_ID = "web-session";

const chatEl   = document.getElementById("chat");
const formEl   = document.getElementById("chat-form");
const inputEl  = document.getElementById("msg");
const insEl    = document.getElementById("card-insights");
const recsEl   = document.getElementById("card-recs");
const alertsEl = document.getElementById("card-alerts");
const traceEl  = document.getElementById("trace");
const traceToggle = document.getElementById("trace-toggle");

function bubble(role, text) {
  const div = document.createElement("div");
  div.className = "bubble " + role;
  div.textContent = text;
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
  return div;
}

function renderInsights(insights) {
  if (!insights) { insEl.className = "card-body muted"; insEl.textContent = "No insights yet."; return; }
  insEl.className = "card-body";
  const totals = insights.totals_by_category || {};
  const rows = Object.keys(totals).sort()
    .map(c => `<li><span>${c}</span><span>₹${totals[c].toLocaleString("en-IN")}</span></li>`)
    .join("");
  const anomalies = (insights.anomalies || [])
    .map(a => `<div class="anom">⚠ ${a.category}: ${a.note}</div>`).join("");
  insEl.innerHTML =
    `<p class="summary">${insights.summary_text || ""}</p>` +
    `<ul class="totals">${rows}</ul>${anomalies}`;
}

function renderRecs(recs) {
  if (!recs || !recs.length) { recsEl.className = "card-body muted"; recsEl.textContent = "No recommendations yet."; return; }
  recsEl.className = "card-body";
  recsEl.innerHTML = recs.map(r =>
    `<div class="rec"><strong>${r.category}</strong> — ${r.action}` +
    `<div class="save">Saves ~₹${r.est_monthly_saving.toLocaleString("en-IN")}/mo</div>` +
    `<div class="why">${r.rationale}</div></div>`).join("");
}

function renderAlerts(alerts) {
  if (!alerts || !alerts.length) { alertsEl.className = "card-body muted"; alertsEl.textContent = "No alerts."; return; }
  alertsEl.className = "card-body";
  alertsEl.innerHTML = alerts.map(a =>
    `<div class="alert sev-${a.severity}"><strong>${a.category}</strong>: ${a.message}</div>`).join("");
}

// Stream plan_trace lines in one at a time for a visible agentic trace.
function renderTrace(lines) {
  traceEl.innerHTML = "";
  (lines || []).forEach((line, i) => {
    setTimeout(() => {
      const li = document.createElement("li");
      li.textContent = line;
      li.className = "trace-line";
      traceEl.appendChild(li);
    }, i * 220);
  });
}

traceToggle.addEventListener("click", () => {
  const collapsed = traceEl.classList.toggle("collapsed");
  traceToggle.setAttribute("aria-expanded", String(!collapsed));
  traceToggle.textContent = collapsed ? "Agent trace ▸" : "Agent trace ▾";
});

async function send(message) {
  bubble("user", message);
  const pending = bubble("assistant pending", "…");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: SESSION_ID }),
    });
    const data = await res.json();
    pending.className = "bubble assistant";
    pending.textContent = data.answer_text || "(no answer)";
    renderInsights(data.insights);
    renderRecs(data.recommendations);
    renderAlerts(data.alerts);
    renderTrace(data.plan_trace);
  } catch (err) {
    pending.className = "bubble assistant error";
    pending.textContent = "Request failed: " + err;
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;
  inputEl.value = "";
  send(message);
});

// Greeting on load.
bubble("assistant", "Hi Aarav — ask me how to improve your savings, or about any spending category.");
```

Create `web/style.css`:

```css
:root {
  --bg: #0f1115;
  --panel: #181b22;
  --panel2: #1f2430;
  --line: #2b313d;
  --text: #e7eaf0;
  --muted: #8b93a3;
  --accent: #4f86f7;
  --green: #2e7d52;
  --amber: #c08a2d;
  --red: #c0453d;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font: 15px/1.5 "Segoe UI", system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
}

.topbar {
  display: flex; align-items: baseline; gap: 12px;
  padding: 14px 20px; border-bottom: 1px solid var(--line);
  background: var(--panel);
}
.topbar h1 { font-size: 18px; margin: 0; }
.topbar .sub { color: var(--muted); font-size: 13px; }

.layout {
  display: grid; grid-template-columns: 1fr 360px; gap: 16px;
  padding: 16px; height: calc(100vh - 53px);
}

/* Chat */
.chat-pane { display: flex; flex-direction: column; min-height: 0; }
.chat {
  flex: 1; overflow-y: auto; padding: 12px;
  background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
}
.bubble {
  max-width: 78%; margin: 8px 0; padding: 9px 13px;
  border-radius: 12px; white-space: pre-wrap;
}
.bubble.user { margin-left: auto; background: var(--accent); color: #fff; }
.bubble.assistant { background: var(--panel2); border: 1px solid var(--line); }
.bubble.pending { color: var(--muted); }
.bubble.error { border-color: var(--red); color: #f0b3ae; }

.composer { display: flex; gap: 8px; margin-top: 12px; }
.msg-input {
  flex: 1; padding: 11px 13px; border-radius: 10px;
  border: 1px solid var(--line); background: var(--panel); color: var(--text);
}
.msg-input:focus { outline: none; border-color: var(--accent); }
.send-btn {
  padding: 0 18px; border: none; border-radius: 10px;
  background: var(--accent); color: #fff; font-weight: 600; cursor: pointer;
}
.send-btn:hover { filter: brightness(1.08); }

/* Side cards */
.side { display: flex; flex-direction: column; gap: 12px; overflow-y: auto; }
.card {
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 10px; padding: 12px 14px;
}
.card h2 { margin: 0 0 8px; font-size: 14px; letter-spacing: .02em; }
.card-insights { border-left: 3px solid var(--accent); }
.card-recs { border-left: 3px solid var(--green); }
.card-alerts { border-left: 3px solid var(--amber); }
.card-body.muted { color: var(--muted); font-size: 13px; }

.summary { margin: 0 0 8px; }
.totals { list-style: none; margin: 0; padding: 0; }
.totals li { display: flex; justify-content: space-between; padding: 2px 0; font-size: 13px; }
.anom { color: var(--amber); font-size: 13px; margin-top: 6px; }

.rec { padding: 6px 0; border-top: 1px solid var(--line); }
.rec:first-child { border-top: none; }
.rec .save { color: var(--green); font-size: 12px; }
.rec .why { color: var(--muted); font-size: 12px; }

.alert { padding: 6px 8px; border-radius: 8px; margin: 4px 0; font-size: 13px; }
.alert.sev-info { background: rgba(79,134,247,.15); }
.alert.sev-warning { background: rgba(192,138,45,.18); }
.alert.sev-critical { background: rgba(192,69,61,.20); }

/* Agent trace */
.card-trace { display: flex; flex-direction: column; }
.trace-toggle {
  background: none; border: none; color: var(--text);
  font-size: 14px; font-weight: 600; text-align: left; cursor: pointer; padding: 0;
}
.trace {
  list-style: decimal inside; margin: 8px 0 0; padding: 0;
  color: var(--muted); font-size: 12px; font-family: "Cascadia Code", Consolas, monospace;
}
.trace.collapsed { display: none; }
.trace-line {
  padding: 3px 0; border-bottom: 1px dashed var(--line);
  animation: fade .25s ease;
}
@keyframes fade { from { opacity: 0; transform: translateY(-2px); } to { opacity: 1; } }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_assets.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web/index.html web/app.js web/style.css tests/test_web_assets.py
git commit -m "feat: vanilla-JS chat UI with cards + streamed agent trace"
```

**GATE — Task 10**
- **Tier A:** `pytest tests/test_web_assets.py -v` → 3 pass.
- **Tier B:** `pytest -q` → all green (full backend + API + web-asset wiring). End-to-end behavior now holding: the structural test guards the HTML↔JS contract (the eight element ids, the `/api/chat` endpoint string, `plan_trace` rendering, and the fixed `web-session` id), so the served page is wired to the live API. **Manual visual verification (required, not automatable here since the assets are browser JS):** run `py -m uvicorn app.main:app --reload` and open `http://127.0.0.1:8000/`. Confirm: (1) typing "How can I improve my monthly savings?" appends a user bubble then an assistant answer; (2) the Insights/Recommendations/Alerts cards populate (food ₹12,000 total, +25% anomaly note, entertainment near-breach warning); (3) the **Agent trace** panel reveals `plan_trace` lines one-by-one with a stagger and collapses/expands via its toggle. The structural test guards wiring; this manual pass guards the visual/interactive behavior.

---

**End of Part E.** The API boundary and web UI are complete and wired to the orchestrator. Proceed to `LLD_PART_F_integration.md` (Task 11 — integration, demo script, and the end-to-end smoke harness).
