# app/memory/store.py
"""In-memory, per-session store: profile + history + follow-up cache (HLD §7).

Single-flight-per-session assumed (one in-flight turn per session_id).
Swap for Redis later; the interface stays.
"""
from typing import Optional
from app.models import UserProfile, SpendingInsight


def _seed_profile() -> UserProfile:
    return UserProfile(
        name="Aarav",
        currency="₹",
        risk_pref="balanced",
        savings_goal=8000.0,
        budgets={
            "food": 15000.0,
            "entertainment": 5000.0,
            "shopping": 12000.0,
            "travel": 6000.0,
            "groceries": 8000.0,
            "utilities": 5000.0,
        },
    )


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def _s(self, session_id: str) -> dict:
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "profile": _seed_profile(),
                "history": [],
                "last_intent": None,
                "last_insight": None,
            }
        return self._sessions[session_id]

    def get_profile(self, session_id: str) -> UserProfile:
        return self._s(session_id)["profile"]

    def get_last_insight(self, session_id: str) -> Optional[SpendingInsight]:
        return self._s(session_id)["last_insight"]

    def set_last_insight(self, session_id: str, insight: SpendingInsight) -> None:
        self._s(session_id)["last_insight"] = insight

    def get_last_intent(self, session_id: str) -> Optional[str]:
        return self._s(session_id)["last_intent"]

    def set_last_intent(self, session_id: str, intent: str) -> None:
        self._s(session_id)["last_intent"] = intent

    def append_turn(self, session_id: str, role: str, text: str) -> None:
        self._s(session_id)["history"].append({"role": role, "text": text})

    def get_history(self, session_id: str) -> list:
        return self._s(session_id)["history"]
