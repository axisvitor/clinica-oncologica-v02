---
phase: 11-agent-implementation
plan: 01
subsystem: ai
tags: [pydantic-ai, lgpd, gemini, guardrails, ci]
requires:
  - phase: 10-preparation-scope
    provides: pydantic-ai installation, migration scope decisions, and guardrail source mapping
provides:
  - PIISafeAgent base wrapper enforcing prompt sanitization before Gemini calls
  - AIDeps dataclass for runtime Gemini API key/model injection
  - CI lint script to block direct agent.run* usage outside PIISafeAgent
affects: [phase-11-agents, phase-11-shim, ai-safety]
tech-stack:
  added: []
  patterns: [runtime GoogleModel injection, structured agent call logging, CI scan for direct run calls]
key-files:
  created:
    - backend-hormonia/app/ai/agents/__init__.py
    - backend-hormonia/app/ai/agents/deps.py
    - backend-hormonia/app/ai/agents/base.py
    - backend-hormonia/scripts/check_agent_run_calls.py
  modified: []
key-decisions:
  - "Use PIISafeAgent as the only allowed agent.run() entrypoint and enforce with CI script."
  - "Inject GoogleModel at call-time from AIDeps to avoid module-load API key coupling."
patterns-established:
  - "PII-first execution: sanitize prompt before every external AI call, block on sanitizer failure."
  - "Observability-first agent calls: operation/input hash/latency/success on each run."
requirements-completed: [AGENT-05]
duration: 7 min
completed: 2026-02-24
---

# Phase 11 Plan 01: Agent Scaffold Summary

**LGPD-safe pydantic-ai foundation shipped with runtime model injection, structured call logging, and CI enforcement against direct agent.run() bypasses.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-24T14:49:13Z
- **Completed:** 2026-02-24T14:56:27Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Created `AIDeps` dataclass with default `gemini-2.0-flash` model for per-call dependency injection.
- Implemented `PIISafeAgent._safe_run()` with mandatory input sanitization, runtime `GoogleModel` binding, latency-aware structured logs, and output PII warning scan.
- Added executable CI lint script to fail when direct `agent.run()`, `run_sync()`, or `run_stream()` calls appear outside `app/ai/agents/base.py`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create AIDeps dataclass and agents package scaffold** - `bed44d43` (feat)
2. **Task 2: Create PIISafeAgent base class with _safe_run method** - `0d39f091` (feat)
3. **Task 3: Create CI lint script blocking direct agent.run() calls** - `9cc34451` (feat)

## Files Created/Modified
- `backend-hormonia/app/ai/agents/deps.py` - pydantic-ai dependency container (`gemini_api_key`, `model_name`).
- `backend-hormonia/app/ai/agents/__init__.py` - package API exports for `AIDeps` and `PIISafeAgent`.
- `backend-hormonia/app/ai/agents/base.py` - LGPD-safe base wrapper with logging and output PII scanning.
- `backend-hormonia/scripts/check_agent_run_calls.py` - CI scan that blocks direct run calls outside the wrapper.

## Decisions Made
- Keep runtime model/provider construction inside `_safe_run` so agent modules load without global API key requirements.
- Keep output PII scan warning-only (CPF/phone/email patterns) to prevent blocking valid patient-safe responses.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Avoided import-order break in package scaffold**
- **Found during:** Task 1 (agents package scaffold)
- **Issue:** `from app.ai.agents.deps import AIDeps` triggered package `__init__`, which eagerly imported `base.py` before Task 2 created it.
- **Fix:** Implemented lazy exports via `__getattr__` in `app/ai/agents/__init__.py` so package import remains valid during phased rollout.
- **Files modified:** `backend-hormonia/app/ai/agents/__init__.py`
- **Verification:** `.venv/bin/python -c "from app.ai.agents.deps import AIDeps"` succeeded before Task 2.
- **Committed in:** `bed44d43`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep; change only ensured atomic task execution without temporary import failure.

## Issues Encountered
- Local shell has no global `python`; all verification commands executed with `.venv/bin/python` in `backend-hormonia`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Agent foundation is ready for Plan 11-02 sentiment agent implementation.
- CI guardrail for wrapper-only run calls is active and can protect all upcoming agents.

## Self-Check: PASSED
- Summary, key implementation files, and all task commit hashes verified on disk/git.

---
*Phase: 11-agent-implementation*
*Completed: 2026-02-24*
