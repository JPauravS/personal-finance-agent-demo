# tests/test_memory.py
from app.memory.store import SessionStore
from app.models import UserProfile, SpendingInsight


def test_seeded_profile():
    s = SessionStore()
    p = s.get_profile("sess1")
    assert isinstance(p, UserProfile)
    assert p.name == "Aarav" and p.risk_pref == "balanced"
    assert p.budgets["entertainment"] == 5000.0


def test_profile_is_per_session_stable():
    s = SessionStore()
    assert s.get_profile("sess1") is s.get_profile("sess1")   # same object reused


def test_last_insight_roundtrip():
    s = SessionStore()
    assert s.get_last_insight("sess1") is None
    ins = SpendingInsight("2026-05", {"food": 12000.0}, [], [], "x")
    s.set_last_insight("sess1", ins)
    assert s.get_last_insight("sess1") is ins


def test_last_intent_roundtrip():
    s = SessionStore()
    assert s.get_last_intent("sess1") is None
    s.set_last_intent("sess1", "IMPROVE_SAVINGS")
    assert s.get_last_intent("sess1") == "IMPROVE_SAVINGS"


def test_history_append_and_read():
    s = SessionStore()
    s.append_turn("sess1", "user", "hi")
    s.append_turn("sess1", "assistant", "hello")
    h = s.get_history("sess1")
    assert h == [{"role": "user", "text": "hi"},
                 {"role": "assistant", "text": "hello"}]


def test_sessions_isolated():
    s = SessionStore()
    s.set_last_intent("a", "GREETING")
    assert s.get_last_intent("b") is None
