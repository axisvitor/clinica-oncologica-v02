---
phase: 21-async-foundation
plan: 05
subsystem: testing
tags: [celery, asyncsession, pytest, ci-lint]
requires:
  - phase: 21-02
    provides: Async isolation lint guard baseline for Celery task modules
provides:
  - Runtime integration proof that Celery task modules do not leak async DB symbols
  - Runtime guard validation for get_async_db usage outside async contexts
  - Expanded lint guard coverage for async_sessionmaker imports in app/tasks
affects: [phase-22, phase-23, celery-workers, async-migration-safety]
tech-stack:
  added: []
  patterns: [runtime isolation assertions, task-module namespace inspection, lint-regression smoke test]
key-files:
  created: [backend-hormonia/tests/integration/test_celery_async_isolation.py]
  modified: [backend-hormonia/scripts/check_async_isolation.py]
key-decisions:
  - "Validate get_async_db runtime guard by advancing async generator from sync context using __anext__().send(None)."
  - "Fail task isolation test on module import errors to guarantee full app/tasks coverage."
patterns-established:
  - "Celery async-safety verification combines runtime tests plus static task linting."
  - "Async DB symbol leakage checks inspect imported module namespaces, not only source regex matches."
requirements-completed: [FOUND-03]
duration: 5 min
completed: 2026-02-27
---

# Phase 21 Plan 05: Celery Async Isolation Summary

**Runtime and static safeguards now jointly prove Celery task modules stay isolated from async DB infrastructure.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-27T00:28:45Z
- **Completed:** 2026-02-27T00:33:59Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `test_celery_async_isolation.py` with 5 focused integration tests for task import isolation, runtime guard behavior, DualSessionMixin mode detection, and lint agreement.
- Verified `get_async_db` fail-fast behavior in non-async contexts and confirmed sync-path service behavior remains safe for Celery-like usage.
- Enhanced `check_async_isolation.py` to flag `async_sessionmaker` imports in `app/tasks/` while preserving existing false-positive controls.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create integration test for Celery async isolation** - `b2821c65` (test)
2. **Task 2: Enhance CI lint guard for broader pattern coverage** - `8fc8890a` (fix)

## Files Created/Modified
- `backend-hormonia/tests/integration/test_celery_async_isolation.py` - Runtime integration coverage for async isolation and guard behavior.
- `backend-hormonia/scripts/check_async_isolation.py` - Added `async_sessionmaker` import detection in Celery task lint checks.

## Decisions Made
- Chose strict module import coverage for `app/tasks` (import failures fail the test) to avoid false confidence from skipped modules.
- Validated runtime guard by directly advancing async generator machinery from sync context, matching the fail-fast contract.

## Deviations from Plan

None - plan executed exactly as written.

## Authentication Gates

None.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- FOUND-03 now has both runtime and static verification artifacts committed.
- Ready for Phase 21 follow-up closure and Phase 22 async migration work.

## Self-Check: PASSED

- Found `.planning/phases/21-async-foundation/21-05-SUMMARY.md` on disk.
- Verified task commits `b2821c65` and `8fc8890a` exist in git history.

---
*Phase: 21-async-foundation*
*Completed: 2026-02-27*
