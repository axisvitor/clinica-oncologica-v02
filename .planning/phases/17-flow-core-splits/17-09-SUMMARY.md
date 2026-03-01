---
phase: 17-flow-core-splits
plan: 09
subsystem: testing
tags: [pytest, fastapi, sqlalchemy, async-session, dependency-overrides]
requires:
  - phase: 17-flow-core-splits
    provides: Prior fail-fast blocker tracking and schema-guarded test bootstrap
provides:
  - Root test client get_async_db override bound to transactional sync test session
  - SyncToAsyncSessionAdapter coverage for AsyncSession dependencies in root test suite
  - Fresh fail-fast evidence documenting post-override blocker state
affects: [phase-17-verification, phase-18-flow-service-splits, backend-tests]
tech-stack:
  added: []
  patterns: [Dependency override bridge from AsyncSession dependencies to sync transactional fixture session]
key-files:
  created: [.planning/phases/17-flow-core-splits/17-09-SUMMARY.md]
  modified:
    - backend-hormonia/tests/conftest.py
    - .planning/phases/17-flow-core-splits/deferred-items.md
key-decisions:
  - "Override get_async_db in root client fixture so AsyncSession endpoints run inside test transaction boundaries."
  - "Keep fail-fast rerun evidence even when gate remains red, explicitly separating closed async-session blocker from new saga payload blocker."
patterns-established:
  - "Root-suite fixture parity with critical-suite async DB override pattern using a sync-session adapter."
requirements-completed: [SPLIT-05, SPLIT-06, SPLIT-07]
duration: 18 min
completed: 2026-02-25
---

# Phase 17 Plan 09: Async DB Override Closure Summary

**Root test client now overrides `get_async_db` with a sync-transaction adapter, removing the prior coroutine/scalars failure mode and advancing fail-fast to a distinct patient-onboarding saga payload mismatch.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-02-25T23:10:00Z
- **Completed:** 2026-02-25T23:28:14Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Imported `get_async_db` in root `tests/conftest.py` and added a root `client` fixture override that yields `SyncToAsyncSessionAdapter(db_session)`.
- Added `SyncToAsyncSessionAdapter` before the root `client` fixture to bridge AsyncSession dependencies back to the sync transactional session used by tests.
- Reran fail-fast and documented fresh evidence in deferred tracking, including first failing node and explicit async-session blocker closure status.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add adapter and get_async_db root fixture override** - `7f66d988` (fix)
2. **Task 2: Rerun fail-fast and record closure evidence** - `680df94d` (docs)

**Plan metadata:** pending

## Files Created/Modified
- `backend-hormonia/tests/conftest.py` - Added `get_async_db` import, `SyncToAsyncSessionAdapter`, and root `client` fixture async DB override.
- `.planning/phases/17-flow-core-splits/deferred-items.md` - Appended timestamped post-override fail-fast run with blocker transition details.

## Decisions Made
- Applied async dependency override at the root test fixture layer (instead of production code changes) to preserve plan scope and keep DB operations inside test transaction boundaries.
- Treated the remaining `422 != 201` fail-fast stop as a new blocker after confirming the prior coroutine/scalars async-session issue no longer appears.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Prevented coroutine return from adapter execute in sync call sites**
- **Found during:** Task 1 (targeted patient create test verification)
- **Issue:** The initial async `execute()` adapter shape returned a coroutine to sync service code paths, reproducing `'coroutine' object has no attribute 'scalars'`.
- **Fix:** Updated adapter `execute()` to return an awaitable proxy over the sync SQLAlchemy `Result`, allowing both sync `.scalars()` access and awaited usage.
- **Files modified:** `backend-hormonia/tests/conftest.py`
- **Verification:** Re-ran `tests/api/test_patients_endpoints.py::TestPatientCRUDEndpoints::test_create_patient_success`; coroutine/scalars warning path was removed and failure advanced to a different saga payload issue.
- **Committed in:** `7f66d988` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix was necessary to close the intended async-session blocker; fail-fast still surfaces a new distinct blocker outside the original coroutine/scalars failure mode.

## Issues Encountered
- `python3 -m pytest -x --tb=short` is still not green; first failure remains `tests/api/test_patients_endpoints.py::TestPatientCRUDEndpoints::test_create_patient_success` (`AssertionError: 422 != 201`) with saga step payload/model mismatch (`TypeError: 'allergies' is an invalid keyword argument for Patient`) and downstream compensation transaction errors.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Async-session dependency-override blocker is now closed and documented with fresh evidence.
- Phase 17 verification remains blocked by a distinct patient onboarding saga payload/model compatibility failure; full fail-fast gate is not yet green.

---
*Phase: 17-flow-core-splits*
*Completed: 2026-02-25*

## Self-Check: PASSED
- FOUND: `.planning/phases/17-flow-core-splits/17-09-SUMMARY.md`
- FOUND: `7f66d988`
- FOUND: `680df94d`
