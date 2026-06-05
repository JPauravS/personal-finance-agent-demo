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
    for key in ("answer_text", "insights", "recommendations", "alerts", "plan_trace"):
        assert key in body
    assert body["insights"]["totals_by_category"]["food"] == 12000.0
    assert body["recommendations"]
    assert any(a["category"] == "entertainment" and a["severity"] == "warning"
               for a in body["alerts"])
    assert isinstance(body["plan_trace"], list) and body["plan_trace"]


def test_chat_greeting_is_empty_advisory():
    r = client.post("/api/chat", json={"message": "hi", "session_id": "g1"})
    assert r.status_code == 200
    body = r.json()
    assert body["insights"] is None
    assert body["recommendations"] == []


def test_multi_turn_reuses_cached_insight():
    r1 = client.post("/api/chat", json={
        "message": "How can I improve my monthly savings?",
        "session_id": "t2",
    })
    assert r1.status_code == 200
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
