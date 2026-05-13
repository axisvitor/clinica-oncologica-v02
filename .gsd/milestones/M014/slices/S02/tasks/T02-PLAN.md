---
estimated_steps: 26
estimated_files: 3
skills_used: []
---

# T02: Enforce ADK runtime session and invocation ownership

---
estimated_steps: 8
estimated_files: 3
skills_used:
  - api-design
  - tdd
  - verify-before-complete
---

Why: route auth alone does not protect direct runtime calls or guessed ADK `session_id`/`invocation_id`; the runtime already stores `user_id`, so resume/close/cancel must compare it to `request.user_id` before lifecycle side effects.

Do:
1. In `backend-hormonia/app/ai/adk/runtime.py`, add a small owner-check helper for session/invocation payloads that compares stored `payload["user_id"]` to `request.user_id`.
2. Treat missing/blank stored owner metadata as ambiguous and deny fail-closed rather than assigning it to the caller.
3. For `session.action == "close"`, fetch the session, deny foreign/missing-owner sessions before `store.close_session`, and avoid leaking stored owner, prompt, or state in the error payload.
4. For resume/auto-with-session, check ownership before `store.prepare_resume` touches session activity; only the matching owner can proceed to existing closed/expired/tool/oversized checks and context merge.
5. For invocation cancel, read the invocation first with `store.get_invocation`, check owner and tool before mutating via `store.cancel_invocation` or calling `_cancel_in_flight_task`.
6. Return deterministic generic lifecycle errors such as `session_owner_mismatch`, `session_owner_missing`, `invocation_owner_mismatch`, or `invocation_owner_missing` in the existing ADK error-envelope shape; do not introduce live Gemini/provider requirements.
7. Extend `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py` with runtime proof: same-user resume reaches a mocked handler; foreign resume/close/cancel deny before `_execute_request`/handler/cancel task; expired same-owner session denies before execution; missing-owner session/invocation denies fail-closed.
8. Update `backend-hormonia/tests/unit/test_adk_tools_runtime.py` only where existing lifecycle tests need explicit owner fixtures or additional ownership assertions.

Must-haves:
- Denied runtime ownership paths do not execute ADK tool handlers, `_execute_request`, live Gemini, session close mutation, invocation cancel mutation, or `_cancel_in_flight_task`.
- Same-user lifecycle behavior remains backward-compatible with current runtime success/closed/expired/tool-mismatch semantics.
- Error payloads do not include raw user ids, prompt text, session state, cookies, tokens, or provider secrets.

Failure Modes (Q5): session store miss returns existing not-found error; malformed/missing owner fails closed; expired same-owner sessions return lifecycle expired without execution; Redis/in-memory store behavior remains fixture-controlled.

Load Profile (Q6): resume/close/cancel may add one O(1) session/invocation lookup before existing lifecycle mutation; at 10x load the session store is the pressure point, while denied paths still avoid LLM/tool cost.

Negative Tests (Q7): foreign session resume, foreign session close, missing-owner session resume/close, expired session resume, foreign invocation cancel, missing-owner invocation cancel, and tool mismatch without owner leakage.

Done when: focused runtime ownership tests pass and existing ADK lifecycle unit tests still pass for same-owner sessions/invocations.

## Inputs

- `backend-hormonia/app/ai/adk/runtime.py`
- `backend-hormonia/app/ai/adk/session_store.py`
- `backend-hormonia/app/ai/adk/wrapper.py`
- `backend-hormonia/app/schemas/v2/adk.py`
- `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`
- `backend-hormonia/tests/unit/test_adk_tools_runtime.py`

## Expected Output

- `backend-hormonia/app/ai/adk/runtime.py`
- `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`
- `backend-hormonia/tests/unit/test_adk_tools_runtime.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py backend-hormonia/tests/unit/test_adk_tools_runtime.py -k "owner or ownership or session or invocation or resume or close or cancel"

## Observability Impact

Adds deterministic ADK lifecycle denial types for future debugging and keeps denied-path metrics/logs low-cardinality and PHI-safe; future agents inspect focused security tests plus ADK lifecycle error `type` values.
