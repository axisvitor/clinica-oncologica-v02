---
id: T01
parent: S02
milestone: M014
key_files:
  - backend-hormonia/app/api/v2/routers/adk.py
  - backend-hormonia/tests/api/v2/test_adk.py
  - backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py
key_decisions:
  - Treat ADK route session identity as authoritative: reject mismatched top-level payload user ids and overwrite nested context identity/lifecycle controls before wrapper execution.
  - Denied ADK route-auth paths emit low-cardinality PHI-safe `adk_route_denied` diagnostics and do not construct `AIDeps` or call `PIISafeADKWrapper.safe_run`.
duration: 
verification_result: passed
completed_at: 2026-05-13T15:08:20.945Z
blocker_discovered: false
---

# T01: Made `/api/v2/adk/run` session-authenticated and route-authoritative for ADK user identity before wrapper execution.

**Made `/api/v2/adk/run` session-authenticated and route-authoritative for ADK user identity before wrapper execution.**

## What Happened

Updated the ADK v2 route to depend on `get_current_user_from_session`, resolve the canonical authenticated user id from `current_user.id` or `current_user.user_id`, reject mismatched top-level `payload.user_id` with a generic 403 before constructing `AIDeps`, and reject malformed/blank canonical auth payloads with a generic 401 before wrapper execution. The route now builds wrapper context from payload context but overwrites route-owned fields (`tool_name`, canonical `user_id`, `request_source`, resolved `runtime`, resolved `session`, resolved `invocation`, `session_id`, and `invocation_id`) so nested context cannot spoof identity or lifecycle controls. Added PHI-safe `adk_route_denied` warning diagnostics with low-cardinality reason, route, tool, lifecycle action, method, and sanitized request id metadata. Updated existing ADK API tests to use authenticated headers and assert positive wrapper calls receive the authenticated user id. Added focused M014/S02 security tests proving missing auth, blank canonical identity, and payload identity mismatch deny before `AIDeps`/`PIISafeADKWrapper.safe_run`, while absent/matching payload user ids and nested context override attempts behave safely.

## Verification

Ran the focused task verification command: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_adk.py backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py -k "adk_run or route or payload or canonical or missing_auth"`. The final run passed 25 selected tests, covering allowed ADK route envelopes, canonical authenticated user propagation, missing-auth denial, blank-canonical denial, payload identity mismatch denial, user_id fallback, and route-owned context override protection.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_adk.py backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py -k "adk_run or route or payload or canonical or missing_auth"` | 0 | ✅ pass — 25 passed | 22618ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/adk.py`
- `backend-hormonia/tests/api/v2/test_adk.py`
- `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`
