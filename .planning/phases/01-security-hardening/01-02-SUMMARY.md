---
phase: 01-security-hardening
plan: 02
subsystem: auth
tags: [firebase, fastapi, pytest, dependency_overrides, security, credentials]

# Dependency graph
requires: []
provides:
  - "Production code with zero TEST_TOKEN_REGISTRY references (SEC-02)"
  - "Firebase service account key file startup guardrail (SEC-03)"
  - "Test fixtures using dependency_overrides pattern exclusively"
  - ".gitignore coverage for Firebase credential files"
affects:
  - 01-security-hardening
  - auth
  - testing

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "dependency_overrides pattern for test auth mocking (replaces TEST_TOKEN_REGISTRY)"
    - "Fail-fast startup guardrail for credential file detection"

key-files:
  created: []
  modified:
    - backend-hormonia/app/dependencies/auth_dependencies.py
    - backend-hormonia/app/api/v2/routers/admin/dependencies.py
    - backend-hormonia/tests/api/conftest.py
    - backend-hormonia/tests/api/v2/conftest_auth.py
    - backend-hormonia/app/core/lifespan.py
    - backend-hormonia/.gitignore

key-decisions:
  - "Override get_admin_user (admin/dependencies.py) in admin_token fixture — admin endpoints bypass get_current_user via their own dependency"
  - "Also override get_current_user_from_session in token fixtures — session-based auth paths in admin endpoints need this override"
  - "firebase_auth_headers and session_auth_headers fixtures changed from return to yield for proper teardown"
  - "SEC-03 guardrail raises RuntimeError in production/staging, logs CRITICAL in development (non-blocking)"

patterns-established:
  - "Test auth pattern: override get_current_user + get_current_user_from_session + get_admin_user for full coverage"
  - "Startup guardrail pattern: fail-fast check before service init, severity-aware (env-sensitive)"

requirements-completed: [SEC-02, SEC-03]

# Metrics
duration: 16min
completed: 2026-02-22
---

# Phase 1 Plan 02: Remove TEST_TOKEN_REGISTRY and Add Firebase Credential Guardrail Summary

**TEST_TOKEN_REGISTRY eliminated from production binary and replaced with dependency_overrides in tests; startup guardrail rejects service account key files in production/staging**

## Performance

- **Duration:** 16 min
- **Started:** 2026-02-22T16:33:41Z
- **Completed:** 2026-02-22T16:49:51Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Deleted TEST_TOKEN_REGISTRY symbol entirely from app/ — zero references remain in production code (SEC-02)
- Replaced all test fixtures with FastAPI dependency_overrides pattern with proper yield teardown
- Added `_check_no_service_account_file()` to lifespan.py called during startup — raises RuntimeError in production/staging if credential files detected (SEC-03)
- Updated .gitignore with Firebase key file patterns (`*service_account*.json`, `*firebase_adminsdk*.json`, `*serviceAccountKey*.json`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove TEST_TOKEN_REGISTRY from app/dependencies/auth_dependencies.py and app/api/v2/routers/admin/dependencies.py** - `66284102` (fix)
2. **Task 2: Update test fixtures to use dependency_overrides instead of TEST_TOKEN_REGISTRY** - `f26e984e` (fix)
3. **Task 3: Add Firebase service account key file startup guardrail and .gitignore coverage** - `fb3bdf9c` (feat)

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_dependencies.py` - Removed TEST_TOKEN_REGISTRY variable, _is_test_mode_enabled(), _app_environment gating, and TEST_TOKEN_REGISTRY lookup block in get_current_user()
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` - Removed TEST_TOKEN_REGISTRY import and lookup block in get_admin_user()
- `backend-hormonia/tests/api/conftest.py` - Rewrote admin_token and user_token fixtures to use dependency_overrides (including get_admin_user override for admin endpoints)
- `backend-hormonia/tests/api/v2/conftest_auth.py` - Rewrote firebase_auth_headers and session_auth_headers to use dependency_overrides with yield teardown
- `backend-hormonia/app/core/lifespan.py` - Added _check_no_service_account_file() function and call during _startup()
- `backend-hormonia/.gitignore` - Added Firebase service account key patterns

## Decisions Made

- Override `get_admin_user` from `admin/dependencies.py` in the `admin_token` fixture — admin router endpoints depend on this function directly, not `get_current_user`, so the override must cover it explicitly
- Also override `get_current_user_from_session` in token fixtures to cover session-based auth paths that admin dependency internally resolves
- Changed `firebase_auth_headers` and `session_auth_headers` from `return` to `yield` to guarantee teardown cleanup of overrides
- SEC-03 guardrail uses severity-aware behavior: RuntimeError in production/staging (blocks startup), CRITICAL log only in development (non-blocking)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] admin_token fixture needed to also override get_admin_user**
- **Found during:** Task 2 (update test fixtures)
- **Issue:** After removing TEST_TOKEN_REGISTRY from admin/dependencies.py, the `admin_token` fixture only overrode `get_current_user`, but admin router endpoints use `get_admin_user` (from admin/dependencies.py) as their dependency — this caused 401 responses on admin contract tests
- **Fix:** Added `get_admin_user` and `get_current_user_from_session` to the dependency_overrides set in the admin_token fixture
- **Files modified:** backend-hormonia/tests/api/conftest.py
- **Verification:** TestSystemStatsContract tests went from 401 to 200; 58 tests pass across admin/API contract tests
- **Committed in:** f26e984e (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Required fix — removing TEST_TOKEN_REGISTRY from admin/dependencies.py exposed that admin fixtures needed a broader override. No scope creep.

## Issues Encountered

- Pre-existing test failure in `tests/api/critical/test_patients_list.py` (treatment_phase validation error: 'onboarding' not in regex pattern) — confirmed pre-existing by checking it failed on the original branch too. Out of scope for this plan.
- Pre-existing failures in `test_api_contracts.py::TestNotificationsAPIContract` (missing notifications.notification_type column) — database schema issue unrelated to auth changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SEC-02 complete: `grep -r TEST_TOKEN_REGISTRY app/ | wc -l` returns 0
- SEC-03 complete: `_check_no_service_account_file()` defined and called in lifespan.py
- Test suite passes for all auth/admin contract tests (58 tests, 7 skipped for Firebase-only features)
- .gitignore protects against accidental credential file commits

---
*Phase: 01-security-hardening*
*Completed: 2026-02-22*
