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
