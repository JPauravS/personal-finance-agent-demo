# tests/test_smoke.py
"""The CLI fallback demo must run clean and return one FinalResponse per
scenario (HLD §15). Guards the deliverable from import/runtime breakage.
"""
from app import smoke
from app.models import FinalResponse


def test_run_returns_a_finalresponse_per_scenario(capsys):
    responses = smoke.run()
    assert len(responses) == len(smoke.SCENARIOS)
    assert all(isinstance(r, FinalResponse) for r in responses)

    out = capsys.readouterr().out
    assert "plan_trace" in out
    assert "scenarios replayed" in out


def test_main_exits_zero(capsys):
    assert smoke.main() == 0
    out = capsys.readouterr().out
    assert "Done" in out
