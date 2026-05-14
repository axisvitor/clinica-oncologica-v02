---
id: T02
parent: S02
milestone: M015
key_files:
  - backend-hormonia/app/dependencies/auth_session_invalidation.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/api/v2/routers/users.py
  - backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py
  - backend-hormonia/tests/api/v2/conftest.py
  - tests/security/test_m015_s02_session_runtime_contract.py
  - tests/unit/test_auth_session_cache_canonical_identity.py
  - tests/api/v2/test_auth_session_shared_canonical_identity.py
key_decisions:
  - Redis invalidation on explicit session revocation is best-effort and sanitized; PostgreSQL session rows remain the hard fail-closed authorization source.
  - Raw Redis fallback deletes `session:{session_id}` plus the raw session ID for compatibility and avoids broad scans for single-session revocation.
duration: 
verification_result: mixed
completed_at: 2026-05-14T08:21:38.963Z
blocker_discovered: false
---

# T02: Added shared best-effort Redis session invalidation for explicit revocation while preserving PostgreSQL as the fail-closed session authority.

**Added shared best-effort Redis session invalidation for explicit revocation while preserving PostgreSQL as the fail-closed session authority.**

## What Happened

Implemented the T02 revocation boundary by adding `app.dependencies.auth_session_invalidation`, a shared helper that supports wrapper cache contracts (`invalidate_session`, `delete_session`) and raw Redis `delete`, targeting the canonical `session:{session_id}` key plus a raw-ID compatibility key. Wired auth logout/logout-all to the shared helper and updated `/api/v2/users|auth/sessions/{session_id}` revocation to commit the DB revocation first, then invalidate Redis best-effort with sanitized warning logs on cache failure. Extended the M015/S02 runtime contract tests for wrapper fallback, raw Redis deletion, sanitized cache failure warnings, no side effects for missing/foreign rows, DB-before-cache ordering, and cache-failure-after-commit behavior. While running the task-plan auth regression suite, fixed narrow compatibility issues it exposed by restoring the legacy Firebase verify seam expected by existing tests and by making API v2 auth test fixtures consistently expose request.state.session_id/default preferences. Also added root-level test-path shims so the automated root-relative verification command delegates to the canonical backend tests instead of failing before collection.

## Verification

Fresh verification passed after all file changes. The focused M015/S02 security contract passed (`21 passed`). The task-plan verification `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/api/v2/test_auth.py -q` passed with 99 tests. The previously failing root-relative automated gate command `PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q` now passes with 37 tests; it still emits non-fatal marker/deprecation warnings because root pytest does not load the backend pyproject marker config.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py -q` | 2 | ✅ expected red: missing shared invalidation module before implementation | 27728ms |
| 2 | `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py -q` | 0 | ✅ pass: focused M015/S02 session invalidation contract | 20108ms |
| 3 | `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/api/v2/test_auth.py -q` | 1 | ❌ fail: broader auth compatibility regressions surfaced before fixture/Firebase compatibility fixes | 30251ms |
| 4 | `cd backend-hormonia && PYTHONPATH=. pytest tests/api/v2/test_auth.py::TestSessionManagement::test_verify_session_valid tests/api/v2/test_auth.py::TestUserPreferences::test_get_preferences_success tests/api/v2/test_auth.py::TestFirebaseAndHealth::test_firebase_verify_valid_token tests/api/v2/test_auth.py::TestFirebaseAndHealth::test_firebase_verify_invalid_token tests/api/v2/test_auth.py::TestFirebaseAndHealth::test_firebase_verify_expired_token tests/api/v2/test_auth.py::TestFirebaseAndHealth::test_firebase_verify_creates_session tests/api/v2/test_auth.py::TestFirebaseAndHealth::test_firebase_verify_updates_user -q` | 0 | ✅ pass: targeted compatibility fixes | 21984ms |
| 5 | `PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q` | 4 | ❌ fail reproduced: root-relative automated gate could not find tests before shims | 814ms |
| 6 | `PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q` | 0 | ✅ pass: root-relative automated gate after shims (37 passed, warnings only) | 19678ms |
| 7 | `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/api/v2/test_auth.py -q` | 0 | ✅ pass: final task-plan verification after all file changes | 22335ms |

## Deviations

Added a legacy Firebase verify compatibility endpoint, adjusted API v2 auth fixtures, and added root test-path shims because the task-plan verification and automated root-relative gate exposed compatibility failures outside the originally listed revocation files. These changes preserve existing public response shapes and keep session authorization DB-authoritative.

## Known Issues

Root-relative shim verification passes but emits existing non-fatal pytest warnings about marker registration/deprecation because it runs from repository root without backend pyproject marker configuration.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_session_invalidation.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/api/v2/routers/users.py`
- `backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py`
- `backend-hormonia/tests/api/v2/conftest.py`
- `tests/security/test_m015_s02_session_runtime_contract.py`
- `tests/unit/test_auth_session_cache_canonical_identity.py`
- `tests/api/v2/test_auth_session_shared_canonical_identity.py`
