---
phase: 04-ai-reliability
plan: 01
subsystem: ai
tags: [langgraph, exceptions, lifespan, startup, fail-fast]

# Dependency graph
requires:
  - phase: 01-security-hardening
    provides: SEC-03 pattern (_check_no_service_account_file) used as structural template
provides:
  - FeatureNotAvailableError exception class (app.core.exceptions)
  - LangGraph startup health check (_check_langgraph_available in lifespan.py)
affects:
  - 04-02 (uses FeatureNotAvailableError to replace None fallbacks)
  - ai-layer plans (LangGraph dependency check at startup)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Startup fail-fast gate: check import sentinel (_LANGGRAPH_IMPORT_ERROR) before asyncio.gather()"
    - "Severity-aware startup guard: RuntimeError in production/staging, CRITICAL log in dev/test"
    - "FeatureNotAvailableError for explicit AI feature failure signaling (replaces silent None returns)"

key-files:
  created: []
  modified:
    - backend-hormonia/app/core/exceptions.py
    - backend-hormonia/app/core/lifespan.py

key-decisions:
  - "AI-01: FeatureNotAvailableError uses error_code='FEATURE_NOT_AVAILABLE' and is_recoverable=True — callers can retry without cascading failure"
  - "AI-01: _check_langgraph_available inspects only _LANGGRAPH_IMPORT_ERROR sentinel — no graph compilation at startup (graphs compiled lazily via @lru_cache)"
  - "AI-01: Call placed before asyncio.gather() so RuntimeError propagates — placing inside _initialize_ai_services() would be silently swallowed by return_exceptions=True"
  - "AI-01: Same env tuple ('production', 'prod', 'staging') as SEC-03 guardrail for consistency"

patterns-established:
  - "Startup health check pattern: module-level function, import sentinel inspection, RuntimeError in prod, CRITICAL log in dev"
  - "AI feature error pattern: FeatureNotAvailableError wraps missing LangGraph capability for explicit failure signaling"

requirements-completed: [AI-01]

# Metrics
duration: 2min
completed: 2026-02-22
---

# Phase 4 Plan 01: AI Reliability — Startup Health Check Summary

**LangGraph fail-fast startup guard and FeatureNotAvailableError exception class added to prevent silent AI humanization degradation in production**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-22T21:03:35Z
- **Completed:** 2026-02-22T21:05:35Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `FeatureNotAvailableError(AIServiceError)` to `app/core/exceptions.py` — explicit exception class for AI feature failures that replaces silent None returns
- Added `_check_langgraph_available()` to `app/core/lifespan.py` — startup health check that raises RuntimeError in production/staging when LangGraph is not importable
- Call site placed before `asyncio.gather()` to ensure RuntimeError propagates (not swallowed by `return_exceptions=True`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add FeatureNotAvailableError to exception hierarchy** - `a19b5793` (feat)
2. **Task 2: Add LangGraph startup health check to lifespan.py** - `504f92fc` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend-hormonia/app/core/exceptions.py` - Added `FeatureNotAvailableError` as subclass of `AIServiceError`; accepts `graph_name` and `operation` params; error_code='FEATURE_NOT_AVAILABLE'; is_recoverable=True
- `backend-hormonia/app/core/lifespan.py` - Added `_check_langgraph_available()` function and call site at line 90, before `asyncio.gather()` at line 112

## Decisions Made

- `FeatureNotAvailableError` uses `is_recoverable=True` so callers can retry without cascading failure
- Startup check inspects only `_LANGGRAPH_IMPORT_ERROR` sentinel (set at import time in graphs.py) — no graph compilation at startup
- Call placed before `asyncio.gather()` (not inside `_initialize_ai_services()`) to prevent RuntimeError being silently swallowed by `return_exceptions=True`
- Same `("production", "prod", "staging")` tuple as SEC-03 guardrail for consistency

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `FeatureNotAvailableError` is ready for use in Plan 04-02 (None-fallback elimination)
- LangGraph startup guard is active — any production deployment without langgraph installed will now fail fast at startup instead of serving non-humanized messages silently

## Self-Check: PASSED

- `backend-hormonia/app/core/exceptions.py` — FOUND
- `backend-hormonia/app/core/lifespan.py` — FOUND
- `.planning/phases/04-ai-reliability/04-01-SUMMARY.md` — FOUND
- Commit `a19b5793` (feat: FeatureNotAvailableError) — FOUND
- Commit `504f92fc` (feat: _check_langgraph_available) — FOUND

---
*Phase: 04-ai-reliability*
*Completed: 2026-02-22*
