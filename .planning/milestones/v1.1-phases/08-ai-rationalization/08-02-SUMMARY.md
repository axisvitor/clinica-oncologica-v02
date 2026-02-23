---
phase: 08-ai-rationalization
plan: 02
subsystem: ai
tags: [gemini, circuit-breaker, exceptions, feature-not-available, unit-tests]

# Dependency graph
requires:
  - phase: 08-ai-rationalization
    provides: GeminiClient.generate_content() as canonical AI entry point after LangGraph removal

provides:
  - FeatureNotAvailableError raised on circuit-open condition in GeminiClient (canonical, structured signal)
  - Unit tests confirming circuit-open raises FeatureNotAvailableError with graph_name/operation attributes
  - Backward compatibility: FeatureNotAvailableError is caught by existing except FeatureNotAvailableError handlers (enhanced_flow_engine.py)

affects:
  - enhanced_flow_engine.py (already catches FeatureNotAvailableError — no code change needed)
  - Any future Gemini caller that needs to distinguish circuit-open from actual API errors

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Circuit-open signals as FeatureNotAvailableError (not GeminiAPIError) — distinguishable from API rate limits/bad requests
    - Positional args for FeatureNotAvailableError(message, graph_name, operation) — matches constructor signature

key-files:
  created:
    - backend-hormonia/tests/unit/ai/test_circuit_breaker_exception.py
  modified:
    - backend-hormonia/app/ai/client.py

key-decisions:
  - "Import FeatureNotAvailableError from app.core.exceptions (not re-defined locally) — single source of truth"
  - "Positional args for FeatureNotAvailableError constructor: (message, graph_name='gemini', operation='generate_content') — matches __init__ signature"
  - "Test uses GeminiClient.__new__() with minimal manual init to avoid real API/Redis calls in unit tests"
  - "Monkeypatch call_gemini on the circuit breaker instance (not class) to isolate the exact used_fallback=True path"
  - "Stale .pyc files from 08-01 caused router ImportError — cleared with find -name '*.pyc' -delete before running tests"

patterns-established:
  - "Circuit breaker open signal: raise FeatureNotAvailableError(message, 'gemini', 'generate_content') — not GeminiAPIError"
  - "Unit test isolation: GeminiClient.__new__() + monkeypatch specific instance method to avoid external service calls"

requirements-completed: [AI-04]

# Metrics
duration: 20min
completed: 2026-02-23
---

# Phase 08 Plan 02: Circuit Breaker Exception Type Summary

**GeminiClient.generate_content() now raises FeatureNotAvailableError (with graph_name='gemini', operation='generate_content') when circuit breaker is open, replacing the generic GeminiAPIError — enabling structured error handling across all Gemini callers**

## Performance

- **Duration:** 20 min
- **Started:** 2026-02-23T12:39:00Z
- **Completed:** 2026-02-23T12:59:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Fixed circuit-open exception type: `GeminiAPIError("Gemini circuit breaker fallback used")` replaced with `FeatureNotAvailableError("Gemini circuit breaker open — feature unavailable", "gemini", "generate_content")`
- Added `from app.core.exceptions import FeatureNotAvailableError` import to `client.py`
- Created 4 unit tests covering: circuit-open raises FeatureNotAvailableError with correct attributes, normal operation returns response without error, FeatureNotAvailableError subclasses AIServiceError, error carries expected graph_name/operation fields
- Verified `enhanced_flow_engine.py` existing `except FeatureNotAvailableError` catch blocks work without modification

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix circuit breaker exception type in GeminiClient.generate_content()** - `5b636e6c` (fix)
2. **Task 2: Add unit test for circuit breaker FeatureNotAvailableError** - `c3e99593` (test)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `backend-hormonia/app/ai/client.py` - Added FeatureNotAvailableError import; replaced GeminiAPIError raise with FeatureNotAvailableError on used_fallback=True (lines 31, 601-607)
- `backend-hormonia/tests/unit/ai/test_circuit_breaker_exception.py` - 4 unit tests: circuit-open raises FeatureNotAvailableError, normal path returns response, subclass check, attribute check

## Decisions Made

- Used positional args `FeatureNotAvailableError(message, "gemini", "generate_content")` — matches `__init__(self, message, graph_name, operation=None)` signature; keyword args would also work but positional is cleaner
- Test fixture uses `GeminiClient.__new__()` with manual attribute initialization to bypass real API key requirement and Redis/Gemini service calls
- Monkeypatch applied to the circuit breaker instance (`client._circuit_breaker`) rather than class-level to isolate tests per instance

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Cleared stale .pyc bytecode files that caused router ImportError**
- **Found during:** Task 2 (running tests)
- **Issue:** The 08-01 execution removed `get_humanization_graph` from `graphs.py`, but stale compiled bytecode (`.pyc`) in `__pycache__/` still referenced the old name. Python loaded the cached bytecode instead of re-compiling from source, causing `cannot import name 'get_humanization_graph' from 'app.ai.langgraph.graphs'` at app startup — which blocked the root test conftest from loading.
- **Fix:** `find backend-hormonia -name '*.pyc' -delete` followed by `find -name '__pycache__' -type d -exec rm -rf {} +` to force Python to recompile from current source
- **Files modified:** No source files — only bytecode cache cleared
- **Verification:** `python3 -c "from app.main import app; print('OK')"` passed; all 4 tests collected and passed
- **Committed in:** Not committed (no source change — cache is auto-regenerated)

---

**Total deviations:** 1 auto-fixed (Rule 3 - Blocking)
**Impact on plan:** Cache clearing restored test runner to working state; no source code was altered outside the plan scope.

## Issues Encountered

- Stale `.pyc` files from 08-01 prevented test suite from running. 08-01 removed `get_humanization_graph()` from `graphs.py` but left compiled bytecode from a prior import. Python used the cached `.pyc`, which still exported the deleted function. Clearing the bytecode cache resolved the issue without any source code changes.

## Next Phase Readiness

- AI-04 satisfied: circuit-open condition now raises a structured, distinguishable exception type
- `enhanced_flow_engine.py` and any caller already catching `FeatureNotAvailableError` continues to work without changes
- Ready for 08-03 (if any) or phase completion

---
*Phase: 08-ai-rationalization*
*Completed: 2026-02-23*
