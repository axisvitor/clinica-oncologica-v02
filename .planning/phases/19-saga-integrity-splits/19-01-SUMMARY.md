---
phase: 19-saga-integrity-splits
plan: 01
subsystem: api
tags: [saga, orchestration, prometheus, pytest, split-contract]

requires:
  - phase: 17-flow-core-splits
    provides: Existing saga_orchestrator package boundaries and compatibility-wrapper pattern
provides:
  - Prometheus metrics and phone-format helper extracted into saga_orchestrator/metrics.py
  - SagaOrchestrator kept import-compatible with compat wrappers preserved and orchestrator.py reduced below 500 lines
  - Split contract tests validating import identity, metrics exports, wrappers, and line budgets for SPLIT-08
affects: [phase-19-02, phase-19-03, saga-observability]

tech-stack:
  added: []
  patterns: [internal metrics module extraction, strict compatibility wrappers, split contract tests]

key-files:
  created:
    - backend-hormonia/app/orchestration/saga_orchestrator/metrics.py
    - backend-hormonia/tests/unit/orchestration/test_saga_orchestrator_split_contract.py
    - .planning/phases/19-saga-integrity-splits/deferred-items.md
  modified:
    - backend-hormonia/app/orchestration/saga_orchestrator/orchestrator.py
    - backend-hormonia/app/orchestration/saga_orchestrator/__init__.py

key-decisions:
  - "Keep all SagaOrchestrator compensation compat wrappers in orchestrator.py while trimming non-functional verbosity to satisfy the <500 line budget."
  - "Export all metric symbols from metrics.py and define ImportError fallbacks to preserve import stability when prometheus_client is unavailable."
  - "Treat async MagicMock regression failures in legacy saga tests as pre-existing out-of-scope blockers and document them in deferred-items.md."

patterns-established:
  - "Prometheus instrumentation can be split to internal modules without changing package-level orchestrator imports."
  - "Split contract tests enforce API parity and line-budget constraints for refactor-only plans."

requirements-completed: [SPLIT-08]
duration: 14 min
completed: 2026-02-26
---

# Phase 19 Plan 01: Saga Integrity Splits Summary

**Saga orchestration metrics are now isolated in a dedicated module while preserving legacy SagaOrchestrator imports, compensation wrapper compatibility, and explicit split-contract evidence for line-budget and API parity.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-02-26T16:14:25Z
- **Completed:** 2026-02-26T16:29:01Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Extracted the full Prometheus metrics block and `_detect_phone_format` helper from `orchestrator.py` into a new `metrics.py` module with explicit exports.
- Reduced `orchestrator.py` from 645 to 482 lines while keeping all required compatibility wrapper methods on `SagaOrchestrator`.
- Updated package architecture documentation in `saga_orchestrator/__init__.py` to include the new `metrics.py` module.
- Added SPLIT-08 contract tests covering package import identity, metrics module exports, wrapper presence, helper behavior, and file-size budgets.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract metrics and phone helper into saga_orchestrator/metrics.py and slim orchestrator.py** - `8fb9e67c` (feat)
2. **Task 2: Add saga orchestrator split contract tests and verify line budgets** - `08d69e2f` (test)

**Plan metadata:** pending

## Files Created/Modified

- `backend-hormonia/app/orchestration/saga_orchestrator/metrics.py` - centralizes Prometheus saga metrics, guard flag, and phone-format helper.
- `backend-hormonia/app/orchestration/saga_orchestrator/orchestrator.py` - imports metrics from the new module and preserves orchestrator compatibility surface under 500 lines.
- `backend-hormonia/app/orchestration/saga_orchestrator/__init__.py` - documents metrics module in package architecture section.
- `backend-hormonia/tests/unit/orchestration/test_saga_orchestrator_split_contract.py` - contract coverage for SPLIT-08 API parity and line-budget assertions.
- `.planning/phases/19-saga-integrity-splits/deferred-items.md` - records pre-existing out-of-scope regression blockers discovered during requested verification runs.

## Decisions Made

- Kept all compatibility wrappers on `SagaOrchestrator` and removed only non-functional verbosity/comments to satisfy strict line-budget requirements without behavior changes.
- Added explicit ImportError fallback assignments for all exported metric symbols so `from ...metrics import SAGA_STARTS_TOTAL` stays import-safe even when metrics are disabled.
- Preserved `steps.py` untouched as a pre-existing out-of-scope >500 LOC condition per plan constraints.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added ImportError fallback symbols for exported metrics names**
- **Found during:** Task 1 (metrics extraction)
- **Issue:** After extraction, `orchestrator.py` imports metric symbols from `metrics.py`; without fallback assignments in the ImportError path, imports can fail when `prometheus_client` is unavailable.
- **Fix:** Added `None` fallback assignments for all exported metric collectors while keeping `METRICS_AVAILABLE = False` and warning logging.
- **Files modified:** `backend-hormonia/app/orchestration/saga_orchestrator/metrics.py`
- **Verification:** `python3 -c "from app.orchestration.saga_orchestrator import SagaOrchestrator; from app.orchestration.saga_orchestrator.metrics import METRICS_AVAILABLE, _detect_phone_format; print('imports OK')"`
- **Committed in:** `8fb9e67c` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Required for robust import compatibility in non-Prometheus environments; no scope creep.

## Issues Encountered

- Requested regression command `python3 -m pytest tests/unit/orchestration/test_saga_orchestrator_split_contract.py tests/orchestration/test_saga_orchestrator.py tests/services/test_saga_compensation.py -x -q` stops on pre-existing saga tests that use sync `MagicMock` DB fixtures against async `await self.db.flush/execute` code paths.
- Deferred out-of-scope failures were logged to `.planning/phases/19-saga-integrity-splits/deferred-items.md`; no unrelated behavior changes were introduced in this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SPLIT-08 refactor objective is complete with contract test evidence and line-budget compliance (`orchestrator.py`: 482 LOC, `metrics.py`: 98 LOC).
- Phase 19 can continue to `19-02-PLAN.md` (compensation split), with noted legacy async-test-fixture debt tracked separately.

---
*Phase: 19-saga-integrity-splits*
*Completed: 2026-02-26*

## Self-Check: PASSED

- FOUND: `.planning/phases/19-saga-integrity-splits/19-01-SUMMARY.md`
- FOUND: `backend-hormonia/app/orchestration/saga_orchestrator/metrics.py`
- FOUND: `backend-hormonia/tests/unit/orchestration/test_saga_orchestrator_split_contract.py`
- FOUND: `8fb9e67c`
- FOUND: `08d69e2f`
