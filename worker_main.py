"""Cloudflare Python Worker entry — Personal Finance Advisor (HLD §5, edge variant).

The local app exposes the pipeline via FastAPI (app/main.py). At the edge we use
the *native* Workers handler instead of FastAPI/pydantic — the orchestrator and all
specialist agents are pure-stdlib Python, so dropping the web framework keeps the
Worker bundle tiny (well under the free-plan size limit). Only the HTTP boundary
differs; the agentic pipeline (app package) is reused verbatim.

Routing:
  POST /api/chat  → Planner.handle(message, session_id) → asdict → JSON
  everything else → delegated to the static-assets binding (the web/ UI)

`run_worker_first: ["/api/*"]` (wrangler.jsonc) guarantees /api/* reaches this
Worker; all other paths are served directly from worker-assets/ as static assets.
"""
import json
from dataclasses import asdict
from urllib.parse import urlparse

from workers import WorkerEntrypoint, Response

from app.memory.store import SessionStore
from app.orchestrator import Planner

# Single process-wide store + planner; session isolation is by session_id.
# (In-memory per warm isolate — see HLD §7; swap for a Durable Object / KV later.)
_store = SessionStore()
_planner = Planner(_store)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        path = urlparse(request.url).path
        if request.method == "POST" and path == "/api/chat":
            raw = await request.text()
            body = json.loads(raw) if raw else {}
            message = body.get("message", "")
            session_id = body.get("session_id", "default")
            final = _planner.handle(message, session_id)
            # asdict recurses nested dataclasses into JSON-serializable dicts.
            return Response(
                json.dumps(asdict(final)),
                headers={"Content-Type": "application/json"},
            )
        # Non-API request: serve the static web UI from the ASSETS binding.
        return await self.env.ASSETS.fetch(request)
