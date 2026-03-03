---
phase: 40-otel-removal-adk-foundation
plan: 03
subsystem: testing
tags: [adk, ci, lint, regression]
requires:
  - phase: 40-02
    provides: PIISafeADKWrapper boundary file and exempt target
provides:
  - CI guard coverage for ADK runner direct-run patterns
  - Regression tests proving non-zero exit on violation fixtures
  - Explicit wrapper exemption coverage for ADK wrapper path
affects: [phase-41-adk-agent-integration, ci-guardrails]
tech-stack:
  added: []
  patterns: [regex static guard, subprocess regression tests]
key-files:
  created:
    - backend-hormonia/tests/unit/test_adk_run_guard_regression.py
  modified:
    - backend-hormonia/scripts/check_agent_run_calls.py
key-decisions:
  - "Keep single-script policy ownership in check_agent_run_calls.py and extend patterns in place"
  - "Allow optional scan target path in guard script to support fixture-driven regression tests"
patterns-established:
  - "ADK direct-run policy: forbid runner.run/run_async outside approved wrappers"
  - "Guard regression tests use subprocess invocation and temporary source fixtures"
requirements-completed: [ADK-05]
duration: 5 min
completed: 2026-03-03
---

# Phase 40 Plan 03: ADK Run Guard Summary

**CI lint now blocks direct ADK runner execution patterns and is backed by regression fixtures that prove non-zero failure output with file and line details.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-03T17:35:20-03:00
- **Completed:** 2026-03-03T20:40:12Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Extended `check_agent_run_calls.py` to detect `runner.run(...)` and `runner.run_async(...)` calls in addition to existing pydantic-ai `.run*` patterns.
- Added explicit wrapper exemptions for both `app/ai/agents/base.py` and `app/ai/adk/wrapper.py` to avoid false positives in approved safety boundaries.
- Added regression tests that execute the guard via subprocess with both violating and clean fixtures, including operator-friendly output assertions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend check_agent_run_calls.py for ADK direct-run pattern blocking** - `2adc5dac` (feat)
2. **Task 2: Add regression tests with failing ADK fixture and clean-path assertion** - `c2507966` (fix)

## Files Created/Modified
- `backend-hormonia/scripts/check_agent_run_calls.py` - Extended forbidden patterns, exemptions, and added optional target path scanning for fixture-based execution.
- `backend-hormonia/tests/unit/test_adk_run_guard_regression.py` - Added subprocess-based regression tests for violation and clean fixture outcomes.

## Decisions Made
- Kept one CI guard script (`check_agent_run_calls.py`) as the single enforcement point for both pydantic-ai and ADK direct-run policies.
- Added optional target-path scanning to the guard script so regression tests can validate synthetic fixtures without mutating repository app code.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added optional scan-root argument to guard script**
- **Found during:** Task 2 (Add regression tests with failing ADK fixture and clean-path assertion)
- **Issue:** Existing guard only scanned `backend-hormonia/app`, which blocked fixture-driven subprocess tests against temporary paths.
- **Fix:** Added optional CLI path argument with recursive `.py` discovery and robust path display fallback for non-repo temp files.
- **Files modified:** backend-hormonia/scripts/check_agent_run_calls.py
- **Verification:** `pytest tests/unit/test_adk_run_guard_regression.py -q`; synthetic temp fixture run returned code 1 with file/line output.
- **Committed in:** c2507966 (part of task commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Deviation was necessary to make the planned subprocess regression fixture executable and kept scope within ADK-05 guard validation.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- ADK direct-run lint guard is now enforced and regression-tested for CI.
- Phase 41 can rely on this guardrail while wiring ADK tools and runner endpoints.

## Self-Check: PASSED
- Verified summary and key code/test files exist on disk.
- Verified task commits `2adc5dac` and `c2507966` exist.
