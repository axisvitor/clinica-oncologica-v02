---
estimated_steps: 25
estimated_files: 3
skills_used: []
---

# T01: Require canonical session identity at the ADK route

---
estimated_steps: 7
estimated_files: 3
skills_used:
  - api-design
  - tdd
  - verify-before-complete
---

Why: `/api/v2/adk/run` is currently public and trusts `payload.user_id`; this task closes the route-level identity authority gap before the wrapper can sanitize/invoke ADK.

Do:
1. In `backend-hormonia/app/api/v2/routers/adk.py`, import `Request`, `Depends`, `HTTPException`, and `status`, plus `get_current_user_from_session` from `backend-hormonia/app/dependencies/auth_dependencies.py`.
2. Change `run_adk` to accept `request: Request` and `current_user: dict = Depends(get_current_user_from_session)`.
3. Add a small local helper (or equivalent local code) that resolves the canonical authenticated user id from `current_user["id"]` or `current_user["user_id"]`; missing/blank canonical identity must raise a generic 401/403-class HTTP exception before `PIISafeADKWrapper.safe_run`.
4. Reject `payload.user_id` when present and different from the canonical authenticated user id with HTTP 403 before constructing `AIDeps` or calling the wrapper.
5. Build `context` from `payload.context` but make route-owned fields authoritative: `tool_name`, canonical `user_id`, `request_source`, resolved `runtime`, resolved `session`, resolved `invocation`, `session_id`, and `invocation_id` must override any nested payload values.
6. Update `backend-hormonia/tests/api/v2/test_adk.py` so every positive route test installs an authenticated session dependency override (and valid CSRF cookie/header if the test client exercises S01 CSRF middleware) and expects the wrapper context user id to be the authenticated id.
7. Create `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py` with the route proof subset: missing auth denies and wrapper is not called; authenticated user A with `payload.user_id=user-b` returns 403 and wrapper is not called; authenticated user A with no/matching payload user id succeeds and wrapper receives canonical `user-a`; nested `context.user_id`, `context.session`, `context.runtime`, or `context.invocation` cannot override route-owned fields.

Must-haves:
- Route denial happens before wrapper/provider/tool construction side effects; use call-count sentries in tests.
- Error detail and logs remain generic and do not include prompt text, cookies, tokens, Gemini keys, patient identifiers, or raw PHI.
- Preserve existing ADK response envelope for allowed calls.

Failure Modes (Q5): auth dependency missing/expired/invalid session returns 401 before wrapper; malformed canonical session payload returns denial before wrapper; mismatched payload identity returns 403; wrapper exceptions remain existing behavior only after auth passes.

Load Profile (Q6): one session-auth dependency resolution per ADK POST plus no new provider calls on denied paths; at 10x load the auth/session store is the first shared-resource pressure point, not Gemini/tool execution for denied traffic.

Negative Tests (Q7): missing session, payload user mismatch, blank canonical user id, nested context identity override, and nested lifecycle controls trying to override resolved controls.

Done when: route-level ADK security tests and updated API route tests pass, proving anonymous/payload-mismatched calls cannot reach `PIISafeADKWrapper.safe_run` and allowed calls use the authenticated user id.

## Inputs

- `backend-hormonia/app/api/v2/routers/adk.py`
- `backend-hormonia/app/schemas/v2/adk.py`
- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/dependencies/auth_session_contract.py`
- `backend-hormonia/tests/conftest.py`
- `backend-hormonia/tests/api/v2/test_adk.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/adk.py`
- `backend-hormonia/tests/api/v2/test_adk.py`
- `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_adk.py backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py -k "adk_run or route or payload or canonical or missing_auth"

## Observability Impact

Adds or preserves PHI-safe route denial diagnostics keyed by event/reason only; future agents inspect `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py` and HTTP 401/403 assertions to localize route-auth regressions.
