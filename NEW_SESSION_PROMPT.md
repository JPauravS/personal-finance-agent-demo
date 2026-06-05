# New-Session Execution Prompt — Personal Finance Advisor

Paste everything in the box below into a fresh Claude Code session opened at
`C:\Users\paura\OneDrive\Documents\CC\personal-finance-agent`.

---

```
Implement the Personal Finance Advisor prototype by executing the written LLD, task-by-task, using subagent-driven development with parallelism where the plan allows.

REQUIRED SKILL: Use superpowers:subagent-driven-development. Dispatch a fresh subagent per task, review between tasks. Do NOT implement tasks yourself in the main thread except the integration/review glue.

READ FIRST (in order, do not skip):
1. personal-finance-agent/HLD.md                 (design context, esp. §5.3 branching, §10 pinned data, §12.1 parallel plan)
2. personal-finance-agent/LLD/LLD_INDEX.md       (frozen contracts, two-tier GATE protocol, task map, parallel mapping, self-review)
3. personal-finance-agent/LLD/LLD_PART_A_foundation.md         (Tasks 1–4)
4. personal-finance-agent/LLD/LLD_PART_B_spending.md           (Task 5)
5. personal-finance-agent/LLD/LLD_PART_C_recommend_alerting.md (Tasks 6–7)
6. personal-finance-agent/LLD/LLD_PART_D_orchestrator.md       (Task 8)
7. personal-finance-agent/LLD/LLD_PART_E_api_web.md            (Tasks 9–10)
8. personal-finance-agent/LLD/LLD_PART_F_integration.md        (Task 11)

NON-NEGOTIABLE RULES:
- FROZEN CONTRACTS: app/models.py (LLD_INDEX "Frozen Contracts") is immutable once Task 1 lands. Every later task uses those exact names/signatures. No drift.
- TDD per task: write the failing test → run, confirm it fails → minimal real implementation → run, confirm pass → commit. The LLD gives the exact test + code for every step.
- TWO-TIER GATE after EVERY task (from LLD_INDEX): Tier A = this task's tests pass in isolation; Tier B = `pytest -q` whole suite green (no regression), and from Task 8 on, the end-to-end harness stays green. A task is DONE only when BOTH tiers pass. Never advance on a red suite.
- If an end-to-end assertion fails in a later task, the defect is UPSTREAM. Fix the responsible earlier task. NEVER weaken an assertion to make a gate pass.
- Windows: use `py` (not python/python3). Run tests with `pytest`. An empty conftest.py at the repo root (Task 1) puts the repo root on sys.path — keep it.
- Commit after each task with the message given in that task's Step 5.

EXECUTION ORDER — serial spine + parallel waves (per LLD_INDEX "Parallel Execution Mapping" / HLD §12.1):

  WAVE 0  (serial foundation — frozen contracts, do NOT parallelize):
    Task 1 (models + conftest) → Task 2 (data) → Task 3 (tools) → Task 4 (memory).
    Gate each before the next.

  WAVE 1  (PARALLEL — dispatch 3 subagents concurrently, one per task):
    Task 5 (spending) ∥ Task 6 (recommend) ∥ Task 7 (alerting).
    They touch disjoint files (app/agents/spending.py | recommend.py | alerting.py + separate test files) and all consume the frozen SpendingInsight — no shared state.
    NOTE: app/agents/__init__.py is created empty by whichever lands first (Tasks 6/7 say "create if not present") — harmless if two create it.
    After all three return: run the combined Tier B gate (`pytest -q`) once; confirm Tasks 5+6+7 unit suites all green; commit each task's files with its given message.

  WAVE 2  (serial JOIN — the integration point):
    Task 8 (orchestrator). This imports all three agents + memory. Its test file IS the growing end-to-end harness. Full Tier B must be green before proceeding.

  WAVE 3  (PARALLEL — dispatch 2 subagents):
    Task 9 (FastAPI app) ∥ Task 10 (web UI).
    Disjoint files (app/main.py + tests/test_api.py | web/* + tests/test_web_assets.py). main.py uses StaticFiles(check_dir=False) so it imports even before web/ exists.
    After both: Tier B gate; note test_index_served needs web/index.html (Task 10) present — run it after Task 10 lands.

  WAVE 4  (serial FINAL gate):
    Task 11 (e2e acceptance tests + app/smoke.py CLI demo + README). Run `pytest -q` (whole suite), `pytest tests/test_e2e.py -v` (5 scenarios), `py -m app.smoke` (eyeball the transcript). This is the final no-regression gate.

REVIEW BETWEEN TASKS (subagent-driven-development): after each subagent returns, verify its Tier A + Tier B are actually green (run the commands yourself, don't take the subagent's word), check it used the frozen contracts, then proceed. For the parallel waves, review all sibling tasks together at the wave boundary.

FALLBACK: if parallel coordination gets messy (merge/contract friction), drop to fully sequential Task 1→11 — the plan is authored to run sequentially with zero loss. Per HLD §12.1 the parallel waves are optional upside with a hard floor.

DELIVERABLE WHEN DONE: full `pytest -q` green, `uvicorn app.main:app --reload` serves the chat UI at http://localhost:8000, and `py -m app.smoke` prints all 5 scenario transcripts. Report the final suite count + the three demo proofs.

Two known low-severity nits flagged in review (optional to clear): Task 9 GATE says "4 pass" but test_index_served needs web/ from Task 10 (run it after Task 10); and spending.run reuses the local var `cur` (transactions then currency symbol) — cosmetic. Neither blocks; fix inline if trivial.

Begin with Wave 0, Task 1.
```

---

**Notes for you (not part of the paste):**
- First install deps in the new session: `py -m pip install -r requirements.txt` (created in Task 9; for Waves 0–1 only `pytest` is needed — `py -m pip install pytest`).
- The parallel waves use multiple subagent dispatches in one message. If you'd rather watch each task land one at a time, tell the new session "run fully sequential" and it'll go 1→11.
