---
phase: 17-flow-core-splits
plan: 05
subsystem: testing
tags: [pytest, sqlalchemy, asyncsession, idempotency, rbac]

# Dependency graph
requires:
  - phase: 17-flow-core-splits
    provides: split-module baseline plus schema-guard follow-up context from 17-04
provides:
  - Critical fixture async-db override so async endpoint reads share sync test transaction state
  - AsyncSession-compatible patient validation queries using SQLAlchemy 2.0 select() path
  - Full-suite rerun evidence closing the 422-vs-403 blocker and documenting next unrelated failure
affects: [phase-17 verification closure, critical-api regression triage, patient-service async migration]

# Tech tracking
tech-stack:
  added: []
  patterns: [sync-to-async session adapter for tests, select()-first query style for async compatibility]

key-files:
  created: []
  modified:
    - backend-hormonia/tests/api/critical/conftest.py
    - backend-hormonia/app/services/patient/validation_service.py
    - backend-hormonia/app/services/patient/sync_service.py
    - .planning/phases/17-flow-core-splits/deferred-items.md

key-decisions:
  - "Bridge critical-test AsyncSession dependency with a sync-session adapter instead of changing endpoint/session architecture"
  - "Treat the new full-suite first failure as a separate concern after the 422-vs-403 blocker was closed"

patterns-established:
  - "Critical Async Paths in tests: override both get_db and get_async_db when endpoint dependencies are mixed"
  - "Patient validation async migration: prefer select().scalars().first() over legacy .query() helpers"

requirements-completed: [SPLIT-05, SPLIT-06, SPLIT-07]

# Metrics
duration: 9 min
completed: 2026-02-25
---

# Phase 17 Plan 05: AsyncSession Gap Closure Summary

**Critical idempotency RBAC coverage now reaches the expected 403 path by sharing fixture transaction state with async endpoint dependencies and removing legacy `.query()` usage from patient validation code.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-25T18:36:54Z
- **Completed:** 2026-02-25T18:46:08Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added a `SyncToAsyncSessionAdapter` and `get_async_db` override in the critical API `client` fixture so async endpoint reads can see sync test transaction data.
- Migrated two patient validation duplicate/doctor checks from `.query()` to `select()` so the same code path works with sync sessions and async-compatible adapters.
- Verified `test_idempotency_rbac_denies_other_doctor` now passes with expected `403`, then reran full suite and documented the new unrelated first failure in deferred items.

## Task Commits

Each task was committed atomically:

1. **Task 1: Override critical async DB fixture path and migrate validation queries for AsyncSession compatibility** - `9a0b275b` (fix)
2. **Task 2: Re-run full backend suite and record closure evidence in deferred items** - `9ca8f555` (docs)

## Files Created/Modified
- `backend-hormonia/tests/api/critical/conftest.py` - adds sync-to-async adapter and async dependency override for critical test client fixture.
- `backend-hormonia/app/services/patient/validation_service.py` - replaces doctor existence `.query()` with `select(User)` query execution and scalar extraction.
- `backend-hormonia/app/services/patient/sync_service.py` - replaces hashed duplicate `.query()` builder with `select(Patient)` statement flow.
- `.planning/phases/17-flow-core-splits/deferred-items.md` - records closure of the 422-vs-403 blocker and logs the next full-suite first failure.

## Decisions Made
- Kept the production endpoint/session contract unchanged and solved test visibility with a fixture-level dependency override for `get_async_db`.
- Classified the new full-suite failure (`test_patients_list` response validation mismatch) as outside this plan's split/AsyncSession idempotency scope.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Full `python3 -m pytest -x` did not go fully green due to a new first failure in `tests/api/critical/test_patients_list.py::TestPatientList::test_list_patients_empty_or_existing` (`ResponseValidationError` on `treatment_phase='onboarding'`), documented as a separate concern in deferred items.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The targeted Phase 17 blocker (`422 != 403` in idempotency RBAC path) is closed with passing targeted test evidence.
- Follow-up work should triage the patient-list response validation mismatch that now appears as the first full-suite blocker.

---
*Phase: 17-flow-core-splits*
*Completed: 2026-02-25*

## Self-Check: PASSED

- FOUND: `.planning/phases/17-flow-core-splits/17-05-SUMMARY.md`
- FOUND: `9a0b275b`
- FOUND: `9ca8f555`
