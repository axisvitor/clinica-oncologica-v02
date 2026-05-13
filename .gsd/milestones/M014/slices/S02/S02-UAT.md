# S02: ADK Auth e Session Ownership — UAT

**Milestone:** M014
**Written:** 2026-05-13T18:25:58.611Z

# S02: ADK Auth e Session Ownership — UAT

**Milestone:** M014
**Written:** 2026-05-13

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S02 is a backend security/proof slice. The accepted contract is deterministic pytest evidence over mocked ADK/Gemini boundaries, not live provider or human UI behavior.

## Preconditions

- Repository checkout contains the S02 code and tests.
- Python test dependencies used by `backend-hormonia/pyproject.toml` are installed.
- No production database, live Gemini provider, real patient data, cookies, tokens, or gitignored secret artifacts are required.

## Smoke Test

Run the focused S02 security proof:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py
```

Expected: command exits 0; latest recovery run produced `19 passed`.

## Test Cases

### 1. ADK route requires canonical authenticated identity

1. Run the focused S02 security proof above.
2. Review route-auth cases for missing auth, blank canonical identity, payload user mismatch, absent/matching payload user id, and nested context spoof attempts.
3. **Expected:** Denied route paths return generic auth/forbidden failures before `AIDeps` construction or `PIISafeADKWrapper.safe_run`; allowed paths propagate the authenticated canonical user id.

### 2. Runtime lifecycle ownership is fail-closed

1. Run the focused S02 security proof above.
2. Review resume, close, cancel, expired-session, missing-owner, foreign-owner, and tool-mismatch cases.
3. **Expected:** Foreign/missing/blank owner paths deny before session close mutation, invocation cancel mutation, `_execute_request`, `_cancel_in_flight_task`, provider calls, or tool handlers; same-owner lifecycle paths remain allowed where expected.

### 3. ADK regression suite remains hermetic

1. Run:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_adk.py backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py backend-hormonia/tests/unit/test_adk_runner_integration.py backend-hormonia/tests/unit/test_adk_tools_runtime.py backend-hormonia/tests/unit/test_adk_metrics.py
```

2. **Expected:** command exits 0. Local environments without `google-adk` may skip the integration tests guarded by that dependency; latest recovery run produced `61 passed, 7 skipped`.

## Edge Cases

### PHI/secret-safe denial diagnostics

1. In the focused S02 security proof, inspect tests covering denial diagnostics.
2. **Expected:** route/runtime denial diagnostics include machine-checkable reason/lifecycle metadata and exclude prompts, patient-like strings, cookies, session tokens, raw user ids, Gemini keys, session state, provider secrets, and private paths.

## Failure Signals

- Focused S02 proof exits non-zero.
- Missing/foreign/mismatched identity paths invoke wrapper/runtime/provider/tool side effects.
- Runtime ownership failures mutate session/invocation state or cancel in-flight tasks before ownership checks.
- Error payloads or logs expose prompts, patient-like data, raw owners, cookies, tokens, provider keys, or private filesystem paths.

## Requirements Proved By This UAT

- R012 — Advances the ADK auth hardening row with controlled backend proof.
- R013 — Advances the ADK session ownership proof gap with deterministic route/runtime tests.
- R018 — Demonstrates the ADK medium-finding row was explicitly handled, not silently dropped.

## Not Proven By This UAT

- Live Gemini/provider behavior and production-like ADK runtime execution are not proven; they remain outside M014/S02 scope.
- Final R012/R013 milestone-wide validation, JWT/config posture, and evidence-matrix closure remain owned by S05.

## Notes for Tester

The `google-adk` skips in the supporting regression suite are expected in this local environment. Treat a non-zero exit, side-effect-before-denial assertion, or PHI/secret leakage assertion as a real S02 regression.
