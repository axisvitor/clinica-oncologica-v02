---
phase: 41-adk-agent-integration
plan: 01
subsystem: ai
tags: [adk, runtime, tools, lgpd, pytest]
requires:
  - phase: 40-02
    provides: PIISafeADKWrapper safety boundary contract
  - phase: 40-03
    provides: CI guard policy for ADK direct-run patterns
provides:
  - ADK tool adapters for sentiment, humanize, variation, and empathy
  - Runtime helper that executes selected ADK tool by registry with normalized payload
  - PIISafeADKWrapper _invoke_adk delegation to runtime request contract
affects: [41-02-adk-endpoint, adk-runner-wiring]
tech-stack:
  added: []
  patterns: [typed-tool-registry, pii-safe-wrapper-boundary, red-green-tdd]
key-files:
  created:
    - backend-hormonia/app/ai/adk/tools.py
    - backend-hormonia/app/ai/adk/runtime.py
    - backend-hormonia/tests/unit/test_adk_tools_runtime.py
  modified:
    - backend-hormonia/app/ai/adk/__init__.py
    - backend-hormonia/app/ai/adk/wrapper.py
key-decisions:
  - "Keep ADK execution behind PIISafeADKWrapper by delegating wrapper _invoke_adk to runtime helper."
  - "Normalize all tool and runtime responses to stable {status, result} payloads for downstream endpoint wiring."
patterns-established:
  - "Tool adapter pattern: each ADK capability delegates to existing GeminiDomainClient domain methods."
  - "Runtime request contract pattern: wrapper passes tool_name, user/session IDs, deps, and context through ADKToolRunRequest."
requirements-completed: [ADK-06]
duration: 9 min
completed: 2026-03-03
---

# Phase 41 Plan 01: ADK Tool Runtime Foundation Summary

**ADK now executes sentiment, humanize, variation, and empathy capabilities through typed adapters with PIISafe wrapper delegation and stable status/result contracts.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-03T23:00:16Z
- **Completed:** 2026-03-03T23:09:48Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added `app.ai.adk.tools` with a typed four-tool registry mapping directly to existing `GeminiDomainClient` behavior.
- Added `app.ai.adk.runtime` with `ADKToolRunRequest`, session service contract, and normalized tool execution helper.
- Implemented `PIISafeADKWrapper._invoke_adk` so valid requests no longer raise `NotImplementedError`.
- Added focused TDD regression tests proving adapter delegation, wrapper runtime call path, and CI guard compliance.

## Task Commits

Each task was committed atomically:

1. **Task 0: Define ADK interface contracts for downstream endpoint wiring** - `92057e5f` (feat)
2. **Task 1 (RED): Implement FunctionTool adapters and runtime execution path** - `3b59711f` (test)
3. **Task 1 (GREEN): Implement FunctionTool adapters and runtime execution path** - `65e44293` (feat)

## Files Created/Modified
- `backend-hormonia/app/ai/adk/tools.py` - Typed ADK adapter functions and canonical tool registry.
- `backend-hormonia/app/ai/adk/runtime.py` - Runtime request dataclass plus selected-tool execution helper.
- `backend-hormonia/app/ai/adk/wrapper.py` - Wrapper invoke path now delegates sanitized input to runtime helper.
- `backend-hormonia/app/ai/adk/__init__.py` - Exported new ADK tool/runtime contracts for downstream imports.
- `backend-hormonia/tests/unit/test_adk_tools_runtime.py` - Regression tests for delegation and runtime/wrapper contract.

## Decisions Made
- Reused existing `GeminiDomainClient` methods instead of introducing new AI behavior so Phase 41 wiring preserves proven production semantics.
- Kept wrapper ownership of runtime invocation to preserve the Phase 40 LGPD boundary (no router-level direct ADK run path).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added ADK session import fallback for environments without `google-adk` installed**
- **Found during:** Task 0 verification
- **Issue:** Import check failed with `ModuleNotFoundError: No module named 'google.adk'`.
- **Fix:** Added safe fallback class for `InMemorySessionService` in `runtime.py` so contracts import cleanly while preserving the ADK type surface.
- **Files modified:** `backend-hormonia/app/ai/adk/runtime.py`
- **Verification:** `python3 -c "from app.ai.adk import PIISafeADKWrapper; import app.ai.adk.tools, app.ai.adk.runtime; print('ok')"`
- **Committed in:** `92057e5f` (part of Task 0 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required to satisfy contract import verification in the current environment; no scope creep.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 41-02 can now wire endpoint-level ADK execution by importing `ADKToolRunRequest`, `run_adk_tool`, and `get_tool_registry` without re-discovery.
- CI direct-run guard remains green with runtime/wrapper additions.

## Self-Check: PASSED

- Verified summary and key ADK tool/runtime/test files exist on disk.
- Verified task commits `92057e5f`, `3b59711f`, and `65e44293` exist in git history.
