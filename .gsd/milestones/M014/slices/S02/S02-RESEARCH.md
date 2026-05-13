# S02 Research — ADK Auth e Session Ownership

## Summary

Depth: targeted-to-deep research. The ADK endpoint is a real security gap today: `/api/v2/adk/run` is included in the v2 router without an auth dependency, accepts `user_id` from the request body, and forwards that value into the ADK wrapper/runtime. The runtime/session store already records `user_id` on sessions and invocations, but resume/close/cancel checks only validate tool/status existence, not owner. S02 should therefore close both route-level identity trust and service/runtime session ownership, then prove denied paths stop before Gemini/tool execution under controlled pytest fixtures.

Primary active requirements: R012/R013 for ADK hardening/proof, R015 for controlled fixture-only proof, R017 for PHI/secret-safe diagnostics, and R018 so the M014 evidence matrix can explicitly close the ADK row.

## Recommendation

Implement a two-layer guard:

1. **Route auth/identity gate** in `backend-hormonia/app/api/v2/routers/adk.py`:
   - Add `Request` and `current_user: dict = Depends(get_current_user_from_session)`.
   - Resolve canonical authenticated user ID from `current_user["id"]`/`current_user["user_id"]`.
   - Reject missing/invalid session via the existing dependency (401).
   - Reject `payload.user_id` when present and different from the authenticated user (403) before calling `PIISafeADKWrapper.safe_run`.
   - Always pass the canonical authenticated user ID into the ADK context/runtime; do not trust payload or nested `context.user_id`.

2. **Runtime/session ownership gate** in `backend-hormonia/app/ai/adk/runtime.py` (or a small helper near `_resolve_session`):
   - On resume/close, compare stored `session["user_id"]` with `request.user_id` before returning session context or closing.
   - On cancel, compare stored invocation `user_id` with `request.user_id` before cancelling in-flight work.
   - Treat missing owner metadata on an existing session/invocation as ambiguous and deny rather than launder it into the caller.
   - Keep error payloads generic and ID/reason-only; avoid prompt text, raw cookies/tokens, or patient content.

This preserves existing direct runtime tests while making the HTTP route session-first. It also prevents a caller with a guessed/known ADK session ID from resuming, closing, or cancelling another user's ADK session.

## Implementation Landscape

- `backend-hormonia/app/api/v2/router.py` includes `adk_router` at `prefix="/adk"` with no router-level dependencies.
- `backend-hormonia/app/api/v2/routers/adk.py` currently defines `async def run_adk(payload: ADKRunRequest)` only. It builds context from `payload.context`, then sets `"user_id": payload.user_id or "api-v2-adk-user"` and invokes `PIISafeADKWrapper().safe_run(...)`. This is the main route seam.
- `backend-hormonia/app/schemas/v2/adk.py` permits optional `user_id`, legacy `session_id`, explicit `session` controls, and `invocation` controls. Current validators only catch structural contradictions such as mismatched legacy/nested session IDs, missing session ID for close/resume, or missing invocation ID for cancel. Add no auth logic here except possibly documentation/deprecation on payload `user_id`.
- `backend-hormonia/app/ai/adk/wrapper.py` sanitizes the prompt before runtime and scans output for PII warning types. `_invoke_adk` constructs `ADKToolRunRequest(... user_id=str(payload.get("user_id") or "pii-safe-adk"), ...)`. After route hardening, the route should supply canonical `user_id`; direct callers remain responsible for passing a trusted user ID.
- `backend-hormonia/app/ai/adk/runtime.py` records invocation/session metrics and resolves sessions before `_execute_request`. `_resolve_session` currently checks session existence/status/tool only. `_cancel_invocation` checks invocation existence/tool only. These are the natural service-level ownership seams because they run before tool/Gemini execution.
- `backend-hormonia/app/ai/adk/session_store.py` stores `user_id` on created sessions and registered invocations. `prepare_resume`, `close_session`, and `cancel_invocation` expose enough metadata for caller-side owner checks; no schema migration is needed.
- `backend-hormonia/app/dependencies/auth_dependencies.py` provides canonical `get_current_user_from_session`, backed by `auth_session_contract.resolve_authenticated_session_user`. This contract is cookie-first; S01 tightened CSRF/session-backed mutation assumptions, so S02 tests should use cookie/dependency overrides and include CSRF headers when exercising the full app stack.
- `backend-hormonia/tests/api/v2/test_adk.py` currently proves anonymous payloads work and patches `PIISafeADKWrapper.safe_run`. These tests will need updating to authenticated fixtures plus new negative tests.
- Supporting tests already cover PII-safe wrapper and runtime lifecycle: `backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py`, `backend-hormonia/tests/unit/test_adk_runner_integration.py`, `backend-hormonia/tests/smoke/test_adk_smoke.py`, `backend-hormonia/tests/unit/test_adk_metrics.py`.

## Natural Seams / Task Candidates

1. **HTTP route guard and test updates**
   - Files: `app/api/v2/routers/adk.py`, `tests/api/v2/test_adk.py`, maybe `tests/security/test_m014_s02_adk_auth_session_ownership.py`.
   - Work: require session auth, canonicalize user ID, reject payload mismatch before wrapper, update existing positive tests to override `get_current_user_from_session`.

2. **Runtime ownership guard**
   - Files: `app/ai/adk/runtime.py`, possibly `app/ai/adk/session_store.py` only if helper methods are cleaner.
   - Work: deny resume/close/cancel when stored `user_id` is absent or differs from `request.user_id`. Add `session_owner_mismatch` / `invocation_owner_mismatch` style error types with generic messages.

3. **Controlled proof file**
   - Files: new `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`.
   - Work: route-level missing auth and payload mismatch sentries; service/runtime same-user allow and foreign/expired deny; assert tool/Gemini sentinel is not invoked on denied cases.

4. **Diagnostics / evidence polish**
   - Files: whichever module emits denial logs if logging is added.
   - Work: log `event_type`, `reason`, route/tool/status, request/session ID prefix or hash only. Do not log prompt, output, cookies, reset/session tokens, patient identifiers, or free-text responses.

## First Proof

Start with a failing route test because it captures the riskiest current behavior and is cheap:

- No dependency override and no session cookie: `POST /api/v2/adk/run` should return 401/403-class denial and `PIISafeADKWrapper.safe_run` should not be called.
- Authenticated user A with `payload.user_id=user-b`: response should be 403 and wrapper call count should remain zero.
- Authenticated user A with no payload `user_id`: wrapper receives context `user_id=user-a`.

Then add runtime/service proof:

- Create/open an ADK session for user A; resume as user A reaches a mocked tool handler.
- Resume/close the same session as user B returns a denial before `_execute_request`/Gemini/tool handler.
- Expired session returns denial before `_execute_request`.
- Cancel invocation owned by user A as user B returns denial and does not call `_cancel_in_flight_task`.

## Verification Plan

Focused security proof command:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml \
  backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py
```

Supporting ADK regression command:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml \
  backend-hormonia/tests/api/v2/test_adk.py \
  backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py \
  backend-hormonia/tests/unit/test_adk_runner_integration.py \
  backend-hormonia/tests/unit/test_adk_tools_runtime.py \
  backend-hormonia/tests/unit/test_adk_metrics.py
```

Expected evidence: same-user authenticated session passes under mocked ADK/Gemini; missing session, payload user mismatch, foreign session, expired session, foreign close, and foreign cancel deny before live Gemini/tool/provider execution. Diagnostics remain generic and PHI-safe.

## Watch-outs / Constraints

- Existing `tests/api/v2/test_adk.py` assumes anonymous access. Update those tests rather than preserving the anonymous behavior.
- The route currently returns HTTP 200 for runtime `status="error"` envelopes. For auth/ownership failures, prefer HTTPException 401/403 before wrapper when possible. If runtime returns an owner/status denial, either map it in the route to 403/410 or document why the ADK API keeps a 200 lifecycle envelope; M014 evidence should be explicit.
- `payload.context` is copied before route-set fields. Keep route-owned fields (`user_id`, `session`, `runtime`, `invocation`, `request_source`) authoritative so nested user-supplied context cannot override identity or controls.
- S01 narrowed CSRF bypasses: `/api/v2/adk/run` is a session-backed mutating POST, so browser-style full-stack tests may need valid CSRF cookie/header. Dependency-only unit tests can patch auth directly, but final proof should not imply CSRF is irrelevant.
- `ADKSessionStore` uses module-level in-memory fallback dictionaries when Redis is absent. Tests should isolate/clear memory state or inject a fake Redis/store to avoid cross-test leakage.
- Do not add a live Gemini requirement. Mock `_execute_request`, ADK tool handlers, or `PIISafeADKWrapper.safe_run` depending on the layer being tested.

## Skill Discovery

Installed skills relevant from the prompt: `api-design` for auth/error contract shape, `observability` for PHI-safe denial diagnostics, and `verify-before-complete` for evidence discipline. External skill search (`gsd_exec cc27828c-dbaf-44f1-917c-7b8315af2f6b`) found optional but not installed skills:

- FastAPI: `npx skills add wshobson/agents@fastapi-templates` (16.8K installs), `npx skills add mindrally/skills@fastapi-python` (8.6K), `npx skills add fastapi/fastapi@fastapi` (2.4K).
- pytest: `npx skills add github/awesome-copilot@pytest-coverage` (10.1K installs), `npx skills add manutej/luxor-claude-marketplace@pytest-patterns` (328).

No skill installation is needed to execute S02; local code patterns are sufficient.

## Research Sources

- Memory: MEM002 shared auth/ownership dependencies; MEM003 PHI-safe fail-closed boundaries; MEM061 M014 slice order; MEM062 controlled posture/proof boundary.
- Code scan: `gsd_exec dbeb206e-fda4-417c-85fa-8ba117a7211f` (ADK/Gemini/session files), `gsd_exec d08a6634-6ac9-462f-92c5-2c8972274eb5` (router inclusion/auth dependency patterns), `gsd_exec 5bba0c5b-8a46-45dc-aa34-5dca5af8cff9` (runtime session/cancel helper excerpts).
- Key files read: `backend-hormonia/app/api/v2/routers/adk.py`, `backend-hormonia/app/schemas/v2/adk.py`, `backend-hormonia/app/ai/adk/runtime.py`, `backend-hormonia/app/ai/adk/session_store.py`, `backend-hormonia/app/ai/adk/wrapper.py`, `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/tests/api/v2/test_adk.py`.
