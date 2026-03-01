---
phase: 32-test-coverage
plan: 4
subsystem: testing
tags: [pytest, shim, contracts, exports, regression]
requires: []
provides:
  - Deterministic symbol-parity contract tests for six v1.3 shim modules
  - Regression verification that parity tests coexist with split-contract identity tests
affects: [phase-32, shim-compatibility, test-suite]
tech-stack:
  added: []
  patterns: [explicit expected export sets, parametrized module contract assertions]
key-files:
  created:
    - backend-hormonia/tests/unit/services/test_shim_symbol_parity.py
  modified:
    - backend-hormonia/tests/unit/services/test_shim_symbol_parity.py
key-decisions:
  - "Expected shim symbols remain hardcoded in tests instead of introspected from shims to catch silent __all__ shrinkage."
  - "Parity assertions now require each shim to define __all__ before set comparison."
patterns-established:
  - "Shim contract pattern: assert exact __all__ set, importability, and non-None exports per shim module."
requirements-completed: [TEST-04]
duration: 9m
completed: 2026-03-01
---

# Phase 32 Plan 4: Shim contract tests verifying v1.3 export parity Summary

**Pytest contract coverage now enforces exact `__all__` parity and export validity across all six compatibility shim modules.**

## Performance

- **Duration:** 9m
- **Started:** 2026-03-01T21:12:15Z
- **Completed:** 2026-03-01T21:21:26Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Added a new shim parity test module covering `flow_core`, `enhanced_flow_engine`, `flow_management`, `flow_dashboard`, `flow_monitoring`, and `flow_integrity`.
- Enforced explicit expected symbol sets and validated `set(module.__all__) == expected_symbols` with missing/extra diffs.
- Added assertions that every symbol listed in `__all__` is both importable and resolves to a non-None object.
- Confirmed no regressions with existing split-contract identity tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create shim symbol parity test module** - `163d8283` (test)
2. **Task 2: Verify no regressions in existing split contract tests** - `bb8c8598` (test)

**Plan metadata:** pending (created after state/roadmap updates)

## Files Created/Modified
- `backend-hormonia/tests/unit/services/test_shim_symbol_parity.py` - Parametrized parity contract test suite for all six shims.

## Decisions Made
- Used explicit expected symbol sets in `SHIM_REGISTRY` to detect silent export-set drift.
- Required `__all__` presence explicitly before symbol-set comparison to fail fast on malformed shims.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `python` executable unavailable in environment**
- **Found during:** Task 1 (verification run)
- **Issue:** `python -m pytest ...` failed with `python: command not found`.
- **Fix:** Switched test execution to `python3 -m pytest ...` for this environment.
- **Files modified:** None
- **Verification:** Standalone and combined pytest commands passed.
- **Committed in:** N/A (execution-only environment fix)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep; execution command adapted to local runtime only.

## Issues Encountered
- While hardening task-2 assertions, a temporary pytest parametrization mismatch (`expected_symbols` arg rename) caused collection failure; reverted to canonical parameter names and re-ran tests successfully.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- TEST-04 coverage is complete with deterministic shim export parity checks.
- Phase 32 planning artifacts can now advance with this plan marked complete.

## Self-Check: PASSED

- FOUND: `.planning/phases/32-test-coverage/32-04-SUMMARY.md`
- FOUND: `163d8283`
- FOUND: `bb8c8598`

---
*Phase: 32-test-coverage*
*Completed: 2026-03-01*
