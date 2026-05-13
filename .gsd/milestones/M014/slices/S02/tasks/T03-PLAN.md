---
estimated_steps: 23
estimated_files: 4
skills_used: []
---

# T03: Lock PHI-safe diagnostics and ADK regression evidence

---
estimated_steps: 5
estimated_files: 4
skills_used:
  - observability
  - test
  - verify-before-complete
---

Why: S02 must leave auditable evidence for S05 and R018, not just local code changes; denial diagnostics must help a future agent localize failures without exposing PHI or secrets.

Do:
1. Review route/runtime denial paths from T01/T02 and add or tighten low-cardinality structured logging only where useful: event type, reason, route/tool, lifecycle action, request/correlation id if already available, and hashed/prefix-safe references only if a helper already exists.
2. Add/extend `caplog` assertions in `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py` for at least one route denial and one runtime ownership denial, verifying a reason is visible and prompts, payload text, cookies, raw user ids, Gemini keys, session state, and patient-like text are absent.
3. Ensure tests do not read `.gsd/`, `.planning/`, `.audits/`, local `.env`, production secrets, or any gitignored proof artifacts.
4. Run the focused S02 proof command and the supporting ADK regression command exactly as they should appear in the slice summary/evidence matrix.
5. If supporting tests fail only because they assumed anonymous ADK route access, update `backend-hormonia/tests/api/v2/test_adk.py` to use authenticated dependency overrides; do not reintroduce anonymous access.

Must-haves:
- Fresh verification evidence covers both focused security proof and supporting ADK regressions.
- Denial diagnostics are PHI/secret-safe and generic while still exposing machine-checkable reason codes.
- No live Gemini, external provider, production DB, real patient data, or gitignored local secret is needed.

Failure Modes (Q5): auth/session store/provider mocks unavailable should fail tests explicitly; logging failures must not mask denials; supporting regression failures should be fixed only inside ADK auth/runtime/test seams unless real unrelated breakage is proven.

Load Profile (Q6): diagnostics must be low-cardinality and avoid per-prompt or per-token log volume; at 10x denied traffic logs should remain reason-level, not PHI-level.

Negative Tests (Q7): PHI-safe log absence checks for prompt/patient-like strings, raw users, cookies/tokens, and provider key names; full focused proof includes missing auth, mismatched identity, foreign ownership, expired ownership, and missing-owner cases.

Done when: both final verification commands pass from a clean test invocation and the focused proof file provides explicit S02 evidence for the M014 matrix.

## Inputs

- `backend-hormonia/app/api/v2/routers/adk.py`
- `backend-hormonia/app/ai/adk/runtime.py`
- `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`
- `backend-hormonia/tests/api/v2/test_adk.py`
- `backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py`
- `backend-hormonia/tests/unit/test_adk_runner_integration.py`
- `backend-hormonia/tests/unit/test_adk_tools_runtime.py`
- `backend-hormonia/tests/unit/test_adk_metrics.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/adk.py`
- `backend-hormonia/app/ai/adk/runtime.py`
- `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`
- `backend-hormonia/tests/api/v2/test_adk.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_adk.py backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py backend-hormonia/tests/unit/test_adk_runner_integration.py backend-hormonia/tests/unit/test_adk_tools_runtime.py backend-hormonia/tests/unit/test_adk_metrics.py

## Observability Impact

Finalizes PHI-safe ADK denial observability: route/runtime logs expose event/reason without PHI or secrets, and focused tests become the inspection surface for future agents and S05 evidence mapping.
