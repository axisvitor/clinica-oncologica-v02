---
estimated_steps: 4
estimated_files: 3
---

# T01: Add failing local-auth contract tests

**Slice:** S01 — Local Auth Core
**Milestone:** M002

## Description

Create the slice’s auth-core proof suite before changing production code so the implementation is forced to satisfy the owned login/session requirements instead of drifting into another Firebase-shaped path.

## Steps

1. Add API tests in `backend-hormonia/tests/api/v2/test_auth_local_login.py` covering local email/password login success, invalid-credentials / inactive-account failures, normalized user/session response shape, cookie flags, and logout response semantics.
2. Add unit tests in `backend-hormonia/tests/unit/test_auth_session_identity_contract.py` that pin the new session payload contract, prove auth resolution can work without `firebase_uid`, and assert `get_current_user` / `get_current_user_from_session` prefer session-backed identity on the happy path.
3. Add an integration flow in `backend-hormonia/tests/integration/test_local_auth_core_flow.py` that seeds a local user, logs in, calls `GET /api/v2/users/me`, logs out, and verifies both DB and Redis session invalidation behavior.
4. Run the three suites, tighten assertions until failures point at missing local-auth behavior rather than fixture/setup bugs, and leave them red for the exact contract gaps T02/T03 will close.

## Must-Haves

- [ ] The new API suite asserts on the canonical v2 route (`POST /api/v2/auth/login`) rather than hidden/legacy session endpoints.
- [ ] The dependency suite explicitly proves the happy path no longer requires `firebase_uid` in Redis session data.
- [ ] The integration suite exercises a real protected route (`/api/v2/users/me`) after login, not just the auth endpoints in isolation.
- [ ] The tests pin at least one inspectable failure-path signal (`error`, `request_id`, or debug step) so diagnostics are part of the contract.

## Verification

- `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/unit/test_auth_session_identity_contract.py tests/integration/test_local_auth_core_flow.py -q`
- Confirm the new tests fail because the local-login/session-identity contract is missing, not because fixtures or imports are broken.

## Observability Impact

- Signals added/changed: The tests lock in auth error codes / request IDs and debug-step visibility as required outputs.
- How a future agent inspects this: Run the three new pytest files directly to see exactly which contract edge still fails.
- Failure state exposed: Missing local-login handling, session payload drift, or protected-route auth regressions show up as named assertion failures tied to one boundary each.

## Inputs

- `backend-hormonia/tests/conftest.py` — existing user, DB, and Redis/session fixtures that can seed local users without new scaffolding.
- `backend-hormonia/app/api/v2/routers/auth.py` / `backend-hormonia/app/dependencies/auth_dependencies.py` — current Firebase-centric auth surfaces the new tests are meant to replace on the happy path.

## Expected Output

- `backend-hormonia/tests/api/v2/test_auth_local_login.py` — failing API contract coverage for the slice demo.
- `backend-hormonia/tests/unit/test_auth_session_identity_contract.py` — failing dependency/identity contract coverage.
- `backend-hormonia/tests/integration/test_local_auth_core_flow.py` — failing login → protected route → logout flow coverage.
