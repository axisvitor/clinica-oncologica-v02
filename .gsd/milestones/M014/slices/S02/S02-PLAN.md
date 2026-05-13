# S02: ADK Auth e Session Ownership

**Goal:** Close the ADK auth/session-ownership proof gap by making `/api/v2/adk/run` session-authenticated, route-canonicalizing user identity, and enforcing stored ADK session/invocation ownership before Gemini/tool execution, with deterministic PHI-safe pytest evidence.
**Demo:** Reviewer runs ADK route/service tests where authenticated same-user sessions are allowed and missing, foreign, expired or payload-mismatched sessions are denied without invoking live Gemini.

## Must-Haves

- Owned requirements: R012/R013/R018 ADK row is closed with deterministic test evidence; supporting requirements R015/R017 are honored through controlled fixtures and PHI/secret-safe diagnostics.
- Threat Surface (Q3): anonymous ADK POSTs, payload-supplied `user_id`, nested `context.user_id`, guessed `session_id`, and guessed `invocation_id` cannot trigger wrapper/runtime/provider/tool side effects across users.
- Requirement Impact (Q4): existing anonymous ADK API tests are intentionally updated to authenticated fixtures; wrapper, runtime lifecycle, policy-block, timeout, and metrics regressions are re-run.
- Same authenticated user can run/resume/close/cancel allowed ADK lifecycle operations under mocked ADK/Gemini; missing session, invalid canonical user data, payload mismatch, foreign session, missing-owner session, expired session, foreign close, and foreign cancel deny before `_execute_request`, live Gemini, tool handlers, or `_cancel_in_flight_task`.
- Verification commands pass:
- `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`
- `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_adk.py backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py backend-hormonia/tests/unit/test_adk_runner_integration.py backend-hormonia/tests/unit/test_adk_tools_runtime.py backend-hormonia/tests/unit/test_adk_metrics.py`
- Tests and diagnostics do not read `.gsd/`, `.planning/`, `.audits/`, gitignored secrets, production providers, or real patient data.

## Proof Level

- This slice proves: Controlled backend contract/integration proof. Real runtime required: no. Human/UAT required: no. Live Gemini/WuzAPI/production data required: no; all provider/tool paths are mocked or fixture-controlled.

## Integration Closure

Upstream consumed: S01 session-backed mutation assumptions and CSRF contraction; `backend-hormonia/app/dependencies/auth_dependencies.py::get_current_user_from_session`; ADK schema/runtime/session-store contracts. New wiring introduced: `/api/v2/adk/run` depends on canonical session auth and route-owned identity; `backend-hormonia/app/ai/adk/runtime.py` enforces stored `user_id` for resume/close/cancel. Remaining milestone work: S05 only needs to map S02 commands and residual non-production posture limits into the final M014 evidence matrix.

## Verification

- Denied ADK route/runtime paths should emit low-cardinality, PHI-safe diagnostics with event type, reason, route/tool, lifecycle action, and request/correlation metadata where already available. Logs and error payloads must exclude prompts, model outputs, patient identifiers, cookies, reset/session tokens, Gemini keys, raw stored owners, and private filesystem paths. Inspection surfaces are the focused S02 pytest file, supporting ADK regression command, lifecycle error types such as `session_owner_mismatch`/`invocation_owner_mismatch`, and existing ADK invocation metrics for non-denied lifecycle results.

## Tasks

- [x] **T01: Require canonical session identity at the ADK route** `est:1.5h`
  ---
  estimated_steps: 7
  estimated_files: 3
  skills_used:
    - api-design
    - tdd
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/api/v2/routers/adk.py`, `backend-hormonia/tests/api/v2/test_adk.py`, `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_adk.py backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py -k "adk_run or route or payload or canonical or missing_auth"

- [x] **T02: Enforce ADK runtime session and invocation ownership** `est:2h`
  ---
  estimated_steps: 8
  estimated_files: 3
  skills_used:
    - api-design
    - tdd
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/ai/adk/runtime.py`, `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`, `backend-hormonia/tests/unit/test_adk_tools_runtime.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py backend-hormonia/tests/unit/test_adk_tools_runtime.py -k "owner or ownership or session or invocation or resume or close or cancel"

- [x] **T03: Lock PHI-safe diagnostics and ADK regression evidence** `est:1h`
  ---
  estimated_steps: 5
  estimated_files: 4
  skills_used:
    - observability
    - test
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/api/v2/routers/adk.py`, `backend-hormonia/app/ai/adk/runtime.py`, `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`, `backend-hormonia/tests/api/v2/test_adk.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_adk.py backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py backend-hormonia/tests/unit/test_adk_runner_integration.py backend-hormonia/tests/unit/test_adk_tools_runtime.py backend-hormonia/tests/unit/test_adk_metrics.py

## Files Likely Touched

- backend-hormonia/app/api/v2/routers/adk.py
- backend-hormonia/tests/api/v2/test_adk.py
- backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py
- backend-hormonia/app/ai/adk/runtime.py
- backend-hormonia/tests/unit/test_adk_tools_runtime.py
