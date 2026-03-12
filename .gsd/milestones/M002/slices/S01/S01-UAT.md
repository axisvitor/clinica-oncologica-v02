# S01: Local Auth Core — UAT

**Milestone:** M002
**Written:** 2026-03-11T22:05:11-03:00

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01’s proof target is backend auth-core contract coverage, and the slice plan explicitly requires focused pytest verification rather than a live browser or human-experience check.

## Preconditions

- Test database and test app fixtures are available.
- Backend dependencies used by the focused auth suites are bootstrapped by the existing pytest harness.
- The local-auth slice changes are present in the working tree.

## Smoke Test

Run:

- `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/unit/test_auth_session_identity_contract.py tests/integration/test_local_auth_core_flow.py -q`

Expected quick result:

- all focused S01 auth-core tests pass

## Test Cases

### 1. Local login issues canonical session

1. Run `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py::test_post_login_with_email_password_returns_canonical_response_and_cookie_contract -q`
2. Observe the response assertions for normalized user payload and cookie headers.
3. **Expected:** `POST /api/v2/auth/login` returns 200, emits the canonical HttpOnly session cookie, and does not leak password material.

### 2. Session-backed protected route works without Firebase token exchange

1. Run `cd backend-hormonia && pytest tests/unit/test_auth_session_identity_contract.py -q`
2. Run `cd backend-hormonia && pytest tests/integration/test_local_auth_core_flow.py::test_local_auth_core_flow_invalidates_db_and_redis -q`
3. **Expected:** a user-id-centric session payload is sufficient for auth resolution, `GET /api/v2/users/me` succeeds from the session cookie, and logout revokes both DB and Redis session state.

## Edge Cases

### Invalid credentials and inactive account diagnostics remain inspectable

1. Run `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py::test_post_login_rejects_invalid_credentials_with_stable_error_payload tests/api/v2/test_auth_local_login.py::test_post_login_rejects_inactive_account_with_stable_error_payload -q`
2. **Expected:** failures return stable `error` codes plus `request_id`, with no password or hash leakage in the response payload.

## Failure Signals

- `POST /api/v2/auth/login` returns 422/503 instead of the expected 200/401/403 contract.
- `GET /api/v2/users/me` returns 401/404 after successful local login.
- Logout does not revoke the DB session or invalidate the Redis session entry.
- Failure payloads omit stable diagnostics (`error`, `request_id`) or include password/hash material.
- The debug login probe no longer reports ordered auth-step diagnostics for local auth failures.

## Requirements Proved By This UAT

- R005 — proves the backend normal login path now accepts first-party email/password credentials instead of requiring Firebase token exchange.
- R006 — proves backend Redis + HttpOnly session continuity for login, verify-session, protected-route auth, and logout on the new identity contract.
- R012 — proves backend auth-core failures are inspectable through stable structured diagnostics in both API responses and the debug login probe.

## Not Proven By This UAT

- R007 — existing-user reset / first-access migration is not part of S01.
- R008 — admin-managed account provisioning compatibility is not part of S01.
- R009 — password reset email flow is not part of S01.
- R010 — frontend dashboard and realtime auth cutover away from Firebase tokens is not covered here.
- R011 — hard-cut removal of Firebase Auth runtime/config dependencies is not completed by this slice.

## Notes for Tester

This artifact is intentionally backend-focused. Do not treat it as proof of browser remember-me restore, frontend auth context behavior, or Firebase runtime removal; those belong to later slices.
