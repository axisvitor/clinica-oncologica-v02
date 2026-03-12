---
id: T01
parent: S01
milestone: M002
provides:
  - Failing local-auth contract tests for canonical login, session identity, and protected-route/logout behavior
key_files:
  - backend-hormonia/tests/api/v2/test_auth_local_login.py
  - backend-hormonia/tests/unit/test_auth_session_identity_contract.py
  - backend-hormonia/tests/integration/test_local_auth_core_flow.py
key_decisions:
  - T01 keeps the contract pinned to `POST /api/v2/auth/login` and user-id-centric Redis session identity instead of adding more Firebase-compatible test coverage.
patterns_established:
  - Contract-first auth tests assert stable failure diagnostics (`error`, `request_id`) and exercise a real protected route before implementation work lands.
observability_surfaces:
  - pytest tests/api/v2/test_auth_local_login.py
  - pytest tests/unit/test_auth_session_identity_contract.py
  - pytest tests/integration/test_local_auth_core_flow.py
duration: 45m
verification_result: passed
completed_at: 2026-03-11T21:18:00-03:00
blocker_discovered: false
---

# T01: Add failing local-auth contract tests

**Added three red contract suites that pin the local login/session-identity cutover gaps.**

## What Happened

Created the three slice-level pytest suites required by S01:

- `backend-hormonia/tests/api/v2/test_auth_local_login.py`
  - asserts against the canonical `POST /api/v2/auth/login`
  - expects normalized user/session response shape
  - checks HttpOnly cookie flags
  - checks logout response semantics
  - pins failure diagnostics on `error` + `request_id`
- `backend-hormonia/tests/unit/test_auth_session_identity_contract.py`
  - proves the happy path should work from a user-id-centric Redis session payload
  - intentionally omits `firebase_uid` from the happy-path session payload
  - asserts session-backed identity should win on the happy path
- `backend-hormonia/tests/integration/test_local_auth_core_flow.py`
  - exercises login → `GET /api/v2/users/me` → logout
  - checks Redis and DB session invalidation behavior on the same flow

The resulting failures are the intended contract gaps for T02/T03, not test-harness problems:

- `/api/v2/auth/login` is still Firebase-shaped and validates `id_token`, so local email/password payloads fail with `422`.
- `get_current_user_from_session` still hard-requires `firebase_uid` in Redis session data and returns `401 Invalid session data` when given the owned local-session payload.
- `get_current_user` still returns `401 Authentication required` instead of preferring an already-resolved session-backed identity on the happy path.

Must-have coverage from the task plan is now explicit in the suites:

- canonical `POST /api/v2/auth/login` is asserted directly
- dependency contract explicitly proves happy path must not require `firebase_uid`
- integration flow hits real protected route `GET /api/v2/users/me`
- failure-path diagnostics are asserted via `error` and `request_id`

## Verification

Ran:

- `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py tests/unit/test_auth_session_identity_contract.py tests/integration/test_local_auth_core_flow.py -q`

Observed result:

- 9 tests failed
- failures are implementation-contract failures, not fixture/import/setup failures

Failure buckets:

- login contract tests fail because the current endpoint still expects `body.id_token`
- verify-session/logout/session-identity tests fail because current session auth reports `Session missing firebase_uid` / `Invalid session data`
- session-precedence test fails because `get_current_user` still requires bearer Firebase credentials

## Diagnostics

Re-run the focused suites directly:

- `cd backend-hormonia && pytest tests/api/v2/test_auth_local_login.py -q`
- `cd backend-hormonia && pytest tests/unit/test_auth_session_identity_contract.py -q`
- `cd backend-hormonia && pytest tests/integration/test_local_auth_core_flow.py -q`

Implementation surfaces these tests now pin:

- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/dependencies/auth_dependencies.py`

The new tests make auth failures inspectable through named assertion failures plus stable response diagnostics (`error`, `request_id`) where local-login failure behavior is expected.

## Deviations

none

## Known Issues

- The logout contract test currently fails inside `get_current_user_from_session` before endpoint logout logic because session happy-path resolution still requires `firebase_uid`.
- The `get_current_user` session-precedence test is red by design until T03 teaches it to accept session-backed auth without bearer Firebase credentials.

## Files Created/Modified

- `backend-hormonia/tests/api/v2/test_auth_local_login.py` — failing API contract coverage for local login, normalized response shape, cookie flags, and logout semantics
- `backend-hormonia/tests/unit/test_auth_session_identity_contract.py` — failing dependency contract coverage for user-id-centric session identity and session precedence
- `backend-hormonia/tests/integration/test_local_auth_core_flow.py` — failing login → protected route → logout integration coverage with DB + Redis invalidation assertions
- `.gsd/milestones/M002/slices/S01/S01-PLAN.md` — marked T01 complete
- `.gsd/STATE.md` — advanced active task to T02 and recorded the red-suite outcome
- `.gsd/milestones/M002/slices/S01/tasks/T01-SUMMARY.md` — durable execution summary for recovery
