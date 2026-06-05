"""Cloudflare Python Worker entry — Personal Finance Advisor (HLD §5, edge variant).

Mirrors app/main.py's POST /api/chat boundary, but adapted for Cloudflare Workers:
  - No uvicorn (the Workers runtime is the server).
  - No StaticFiles / FileResponse: the vanilla web/ UI is served by the Workers
    static-assets ASSETS binding (see wrangler.jsonc `assets`). This Worker owns
    only /api/* (forced via `run_worker_first`); everything else is an asset.

The agent pipeline (orchestrator + specialist agents + tools + memory) is reused
verbatim from the app package — only the HTTP boundary differs from app/main.py.
"""
from dataclasses import asdict

from fastapi import FastAPI
from pydantic import BaseModel
from workers import WorkerEntrypoint

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
async def chat(body: ChatIn):
    final = _planner.handle(body.message, body.session_id)
    # asdict recurses nested dataclasses into JSON-serializable dicts.
    return asdict(final)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # ASGI shim: hand the FastAPI app the incoming request.
        import asgi

        return await asgi.fetch(app, request.js_object, self.env)
