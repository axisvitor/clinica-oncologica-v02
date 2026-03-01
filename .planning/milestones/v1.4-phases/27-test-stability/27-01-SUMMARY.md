---
phase: 27-test-stability
plan: 01
subsystem: testing
tags: [pytest, asyncsession, sqlalchemy, admin-api]

requires:
  - phase: 26-api-routers-analytics-admin-system-remaining
    provides: async router migration baseline for v2 API
provides:
  - Async-safe shared auth session user lookup compatible with Session and AsyncSession
  - Stable TestBulkDelete admin identity resolution in admin API tests
  - Removed final TODO(async-migration) annotation under app/
affects: [phase-27-02, test-stability, admin-tests]

tech-stack:
  added: []
  patterns: [awaitable execute resolution, dependency override fixture isolation]

key-files:
  created:
    - .planning/phases/27-test-stability/deferred-items.md
  modified:
    - backend-hormonia/app/api/v2/auth_session_shared.py
    - backend-hormonia/app/services/patient/sync_service.py
    - backend-hormonia/tests/api/v2/test_admin.py
    - backend-hormonia/app/api/v2/routers/admin/dependencies.py

key-decisions:
  - "Use db.execute(select(User)) with inspect.isawaitable in auth_session_shared to support both Session and AsyncSession callers without changing function signatures."
  - "Pin TestBulkDelete admin identity via class-local autouse dependency override to eliminate fixture collision with multiple_users."
  - "In test-mode admin dependency fallback, prefer admin@test.com and fallback to first active admin to avoid MultipleResultsFound crashes."

patterns-established:
  - "Dual-mode session callback pattern: execute statement, await only when result is awaitable."
  - "Bulk operation tests should explicitly override auth dependencies when fixture identity matters."

requirements-completed: [TEST-02, TEST-03]

duration: 11 min
completed: 2026-02-27
---

# Phase 27 Plan 01: Test Stability Summary

**Shared auth-session lookup now resolves users safely in both async and sync DB contexts, bulk-delete admin tests are deterministic, and the final async-migration TODO marker was removed.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-02-27T23:40:58Z
- **Completed:** 2026-02-27T23:52:14Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Replaced `db.query(User)` in `get_user_data_from_session` callback with `execute(select(User))` awaitable-aware logic.
- Removed the last `TODO(async-migration)` marker from `app/services/patient/sync_service.py`.
- Added `TestBulkDelete` autouse override for `get_admin_user` to keep authenticated admin fixed to `admin_user`.
- Hardened `get_admin_user` test fallback to avoid `MultipleResultsFound` when multiple active admins exist.

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix auth session lookup and remove TODO annotation** - `ba951134` (fix)
2. **Task 2: Fix bulk delete admin user resolution in tests** - `84a68326` (fix)
3. **Task 2 deviation fix: harden test-mode admin fallback** - `94d14233` (fix)

## Files Created/Modified
- `.planning/phases/27-test-stability/deferred-items.md` - Captures out-of-scope test-module failure discovered during full verification.
- `backend-hormonia/app/api/v2/auth_session_shared.py` - Async-safe user lookup callback using `select` + awaitable result resolution.
- `backend-hormonia/app/services/patient/sync_service.py` - Removed stale migration TODO annotation.
- `backend-hormonia/tests/api/v2/test_admin.py` - Added class-scoped autouse dependency override for deterministic admin identity in bulk delete tests.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` - Test-mode fallback now prefers `admin@test.com` and avoids scalar-one-or-none crash with multiple admins.

## Decisions Made
- Kept `get_user_data_from_session` API unchanged and applied dual-mode execution inside nested callback for compatibility with existing callers.
- Applied test-local dependency override in `TestBulkDelete` instead of cross-file fixture rewrites to keep scope narrow.
- Treated broad `test_admin.py` failure in activity stats as out-of-scope and logged it to deferred items.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `python` command unavailable in environment**
- **Found during:** Task 2 verification
- **Issue:** `python -m pytest ...` failed with `python: command not found`.
- **Fix:** Switched verification commands to `python3 -m pytest ...`.
- **Files modified:** None
- **Verification:** Bulk delete tests passed under `python3`.
- **Committed in:** N/A (command-level fix only)

**2. [Rule 1 - Bug] Test-mode admin fallback crashed with multiple active admins**
- **Found during:** Plan-level verification (`tests/api/v2/test_admin.py -x -q`)
- **Issue:** `get_admin_user` used `scalar_one_or_none()`, raising `MultipleResultsFound` in multi-admin fixtures.
- **Fix:** Prefer explicit `admin@test.com` in test mode, then fallback via `scalars().first()`.
- **Files modified:** `backend-hormonia/app/api/v2/routers/admin/dependencies.py`
- **Verification:** `python3 -m pytest tests/api/v2/test_admin.py::TestBulkDelete -x -q` passes.
- **Committed in:** `94d14233`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Fixes were required to complete verification and stabilize admin test behavior; no architectural scope change.

## Issues Encountered
- `python3 -m pytest tests/api/v2/test_admin.py -x -q` still fails on `TestActivityStatistics::test_get_activity_statistics` due to pre-existing `AuditLog.severity` select error in `backend-hormonia/app/api/v2/routers/admin/stats.py`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 27-01 blockers from objective are resolved: async session user lookup, bulk delete regression, and TODO marker cleanup.
- Deferred item logged for unrelated admin activity-stats failure; Plan 27-02 can proceed with broader suite verification context.

---
*Phase: 27-test-stability*
*Completed: 2026-02-27*

## Self-Check: PASSED

- Verified summary and key modified files exist on disk.
- Verified task commits `ba951134`, `84a68326`, and `94d14233` exist in git history.
