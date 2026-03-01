---
phase: 24-api-routers-auth-patients-flow
plan: 04
subsystem: testing
tags: [pytest, auth, sessions, async-adapter, rbac]
requires:
  - phase: 24-01
    provides: auth/users/roles AsyncSession migration baseline
provides:
  - Postgres schema guards for legacy `sessions` column drift in root and critical fixtures
  - Sync-to-async fixture adapter that supports awaited and sync write paths without incompatibility errors
  - API-01 verification evidence refreshed with auth/users/roles and RBAC checks passing
affects: [24-05, 24-06, phase-27-test-stability]
tech-stack:
  added: []
  patterns:
    - idempotent schema guard patching inside pytest bootstrap fixtures
    - dual-mode adapter methods that are awaitable and sync-compatible
key-files:
  created: []
  modified:
    - backend-hormonia/tests/conftest.py
    - backend-hormonia/tests/api/critical/conftest.py
    - backend-hormonia/tests/api/v2/test_phase24_auth_users_roles_async.py
    - backend-hormonia/tests/security/test_rbac_authorization.py
key-decisions:
  - Keep blocker fixes constrained to test fixtures and regression tests; runtime API contracts remain unchanged.
  - Preserve transactional fixture isolation by making adapter write methods compatible with both awaited and sync call sites.
patterns-established:
  - "Sessions guard pattern: add/repair missing legacy columns via ALTER TABLE ... IF NOT EXISTS before tests"
  - "Adapter compatibility pattern: return awaitable wrappers from sync-backed write operations"
requirements-completed: [API-01]
duration: 23min
completed: 2026-02-27
---

# Phase 24 Plan 04: Auth Session Blocker Closure Summary

Fixture-level session schema guards and adapter compatibility fixes now unblock API-01 verification while preserving existing auth/users/roles contracts.

## Performance

- **Duration:** 23 min
- **Started:** 2026-02-27T14:09:23Z
- **Completed:** 2026-02-27T14:33:11Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added idempotent Postgres guards in both root and critical suites to heal legacy `sessions` schema drift (`session_token`, `refresh_token`, and other required auth/session columns).
- Updated `SyncToAsyncSessionAdapter` in both suites so `execute/commit/flush/refresh` work safely for awaited async call sites and legacy sync-style call sites.
- Re-ran API-01 verification set and refreshed regression coverage to assert no sync `Depends(get_db)` leakage in auth/users/roles modules.
- Aligned RBAC security tests with current admin dependency contract helper so verification reflects active authorization wiring.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add sessions schema compatibility guards for verification environments** - `3c49bb60` (fix)
2. **Task 2: Make sync-backed async test adapter flush/commit behavior await-safe** - `92ed0b2f` (fix)
3. **Task 3: Re-run API-01 verification set after blocker fixes** - `d0552668` (test)

## Files Created/Modified

- `backend-hormonia/tests/conftest.py` - Added sessions schema guard and dual-mode adapter write-path compatibility.
- `backend-hormonia/tests/api/critical/conftest.py` - Mirrored sessions schema guard and adapter compatibility behavior for critical suite.
- `backend-hormonia/tests/api/v2/test_phase24_auth_users_roles_async.py` - Extended API-01 regression checks to prevent sync `get_db` dependency reintroduction.
- `backend-hormonia/tests/security/test_rbac_authorization.py` - Updated admin-role unit checks to use current `_require_admin` contract helper.

## Decisions Made

- Minimum-scope unblock strategy applied: all fixes stayed in test fixtures/tests, with no runtime router contract changes.
- Adapter methods were made awaitable without breaking sync invocation paths to preserve existing transaction wrapper behavior.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Expanded sessions schema guard beyond `session_token`**
- **Found during:** Task 1
- **Issue:** Verification still failed after adding `session_token` because legacy schemas also missed other `sessions` columns (for example `refresh_token`, `device_id`).
- **Fix:** Extended fixture guards to patch the full required auth/session column set with safe defaults and indexes.
- **Files modified:** `backend-hormonia/tests/conftest.py`, `backend-hormonia/tests/api/critical/conftest.py`
- **Verification:** `pytest tests/api/v2/test_auth.py::TestSessionManagement::test_list_sessions_success -q`
- **Committed in:** `3c49bb60`

**2. [Rule 3 - Blocking] Used current patient-create verification target**
- **Found during:** Task 2
- **Issue:** Planned command target `tests/api/v2/test_patients.py::TestPatientCRUD::test_create_patient_success` no longer exists.
- **Fix:** Ran equivalent active target `tests/api/v2/test_patients.py::TestPatientsV2::test_create_patient` to validate the same create-path behavior.
- **Files modified:** None (verification routing only)
- **Verification:** `pytest tests/api/v2/test_patients.py::TestPatientsV2::test_create_patient -q`
- **Committed in:** `92ed0b2f` (task commit context)

**3. [Rule 1 - Bug] Prevented adapter write-path coroutine mismatch regressions**
- **Found during:** Task 2
- **Issue:** Initial async-only `flush/refresh` updates caused `NoneType` await failures and coroutine warnings on sync call sites.
- **Fix:** Converted adapter write methods to return awaitable wrappers while executing sync session operations immediately.
- **Files modified:** `backend-hormonia/tests/conftest.py`, `backend-hormonia/tests/api/critical/conftest.py`
- **Verification:** `pytest tests/api/v2/test_patients.py::TestPatientsV2::test_create_patient -q`
- **Committed in:** `92ed0b2f`

**4. [Rule 3 - Blocking] Repaired RBAC verification calls to current admin helper contract**
- **Found during:** Task 3
- **Issue:** `tests/security/test_rbac_authorization.py` called `get_admin_user(current_user=..., context=...)`, but current signature now expects request/session dependency inputs.
- **Fix:** Switched unit assertions to `_require_admin`, preserving the same admin-vs-doctor authorization truth checks.
- **Files modified:** `backend-hormonia/tests/security/test_rbac_authorization.py`
- **Verification:** `pytest tests/api/v2/test_phase24_auth_users_roles_async.py tests/api/v2/test_auth_route_corrections.py tests/security/test_rbac_authorization.py -q`
- **Committed in:** `d0552668`

---

**Total deviations:** 4 auto-fixed (2 Rule 1, 2 Rule 3)
**Impact on plan:** All deviations were required to unblock planned verification commands and keep API-01 evidence contract-safe. No scope creep into runtime API behavior.

## Authentication Gates

None.

## Issues Encountered

- Verification suite emits pre-existing `pytest.mark.asyncio` warnings for sync tests in `test_auth_route_corrections.py`; warnings are non-blocking and out of scope for this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- API-01 blocker set is now green with schema and adapter compatibility stabilized.
- Fixtures now provide a reusable pattern for remaining Phase 24/27 async-migration verification work.

## Self-Check: PASSED

- FOUND: `.planning/phases/24-api-routers-auth-patients-flow/24-04-SUMMARY.md`
- FOUND: `3c49bb60`
- FOUND: `92ed0b2f`
- FOUND: `d0552668`
