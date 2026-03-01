---
phase: 22-critical-async-fixes
plan: 01
subsystem: api
tags: [sqlalchemy, asyncsession, missinggreenlet, pytest]

requires:
  - phase: 21-async-foundation
    provides: DualSessionMixin and async DI factory patterns
provides:
  - Async-safe SQLAlchemy execution for all CRIT-01 methods in DataIntegrityMonitoringService
  - Regression tests that fail on sync db.query usage in async integrity paths
affects: [22-02, 22-03, 23-service-migration]

tech-stack:
  added: []
  patterns:
    - select(...) plus await self._execute/_scalars in async service methods
    - awaitable-resolution helper to preserve sync and async session behavior

key-files:
  created:
    - backend-hormonia/tests/unit/services/test_data_integrity_monitoring_async.py
  modified:
    - backend-hormonia/app/services/data_integrity_monitoring.py

key-decisions:
  - "Use a local _resolve helper so async methods can await AsyncSession operations while still tolerating sync Session return values."
  - "Use focused unit fakes that hard-fail on db.query to guard against MissingGreenlet regressions."

patterns-established:
  - "DualSession async path: replace db.query chains with select statements through mixin helpers."
  - "Async regression tests should assert db.query is never called in migrated methods."

requirements-completed: [CRIT-01]

duration: 6 min
completed: 2026-02-27
---

# Phase 22 Plan 01: Data Integrity Async Safety Summary

**Data integrity monitoring now executes its five critical async scan/dashboard methods via async-safe SQLAlchemy statement execution with dedicated regression tests preventing sync-query relapse.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-27T01:50:44Z
- **Completed:** 2026-02-27T01:56:45Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Migrated `_scan_patient_integrity`, `_scan_flow_integrity`, `_scan_message_integrity`, `_check_patient_orphaned_relationships`, and `get_integrity_dashboard` to `select(...)` with mixin execution helpers.
- Preserved service constructor and sync/Celery compatibility by resolving both awaitable and direct return values from `DualSessionMixin` helpers.
- Added async unit regression coverage for scan aggregation, orphaned doctor detection, health score computation, and dashboard error payload behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace sync ORM calls in the five async integrity methods** - `911b8f41` (fix)
2. **Task 2: Add async regression tests for integrity monitoring paths** - `3a075880` (test)

**Plan metadata:** pending

## Files Created/Modified
- `backend-hormonia/app/services/data_integrity_monitoring.py` - Replaced sync query chains in CRIT-01 async methods with async-safe statement execution.
- `backend-hormonia/tests/unit/services/test_data_integrity_monitoring_async.py` - Added async regression tests that enforce no sync query fallback in migrated methods.

## Decisions Made
- Added a private `_resolve` helper in `DataIntegrityMonitoringService` to support dual-session execution semantics without changing constructor/API behavior.
- Tests use async-capable fake results and explicit `db.query` guards to detect regressions early.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Replaced unavailable `rg` verification tool with equivalent no-match content check**
- **Found during:** Final verification commands
- **Issue:** Environment does not provide `rg`, so the plan's shell verification command could not run.
- **Fix:** Used a direct content search to confirm `db.query(` is absent from `data_integrity_monitoring.py`.
- **Files modified:** None
- **Verification:** `grep` tool returned no matches for `db.query(` in target module.
- **Committed in:** N/A

**2. [Rule 3 - Blocking] Recovered from transient HEAD mismatch during task-2 commit**
- **Found during:** Task 2 commit
- **Issue:** Git reported `cannot lock ref 'HEAD'` due to concurrent HEAD movement.
- **Fix:** Re-read repository head/state and retried commit once on current HEAD.
- **Files modified:** None
- **Verification:** Task-2 commit succeeded as `3a075880` with correct staged file.
- **Committed in:** `3a075880`

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** No scope creep; both deviations were execution-environment blockers and did not change planned deliverables.

## Authentication Gates

None.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- CRIT-01 is complete with async-safe implementations and regression guards.
- Ready for `22-02-PLAN.md` (flow alerts async conversion).

---
*Phase: 22-critical-async-fixes*
*Completed: 2026-02-27*

## Self-Check: PASSED
- FOUND: `.planning/phases/22-critical-async-fixes/22-01-SUMMARY.md`
- FOUND: `911b8f41`
- FOUND: `3a075880`
