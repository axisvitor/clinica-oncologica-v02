---
id: S02
parent: M014
milestone: M014
provides:
  - ADK route/session ownership proof for downstream S05 evidence-matrix closure.
  - Fresh pytest evidence that missing, foreign, expired, payload-mismatched, and owner-missing ADK paths deny before side effects.
  - PHI/secret-safe ADK denial diagnostic contract.
requires:
  []
affects:
  - S05
key_files:
  - backend-hormonia/app/api/v2/routers/adk.py
  - backend-hormonia/app/ai/adk/runtime.py
  - backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py
  - backend-hormonia/tests/api/v2/test_adk.py
  - backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py
  - backend-hormonia/tests/unit/test_adk_runner_integration.py
  - backend-hormonia/tests/unit/test_adk_tools_runtime.py
  - backend-hormonia/tests/unit/test_adk_metrics.py
key_decisions:
  - Treat route session identity as authoritative and reject mismatched payload identities before wrapper/runtime side effects.
  - Fail closed on missing/blank stored ADK session or invocation owner metadata rather than assigning ownership opportunistically.
  - Keep ADK denial diagnostics low-cardinality and PHI/secret-safe while preserving reason/lifecycle metadata for tests and reviewers.
patterns_established:
  - Route-owned identity canonicalization before constructing downstream ADK dependencies.
  - Stored-owner runtime authorization checks before lifecycle mutation, provider execution, tool handlers, or cancellation side effects.
  - Security proof tests that assert both denial behavior and absence of PHI/secret leakage from diagnostics.
observability_surfaces:
  - `adk_route_denied` warning diagnostics with sanitized reason, route, tool, lifecycle action, method, and request id metadata.
  - Runtime lifecycle error types such as `session_owner_mismatch`, `session_owner_missing`, `invocation_owner_mismatch`, and `invocation_owner_missing`.
  - Focused pytest proof in `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`.
drill_down_paths:
  - .gsd/milestones/M014/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M014/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M014/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-05-13T18:25:58.604Z
blocker_discovered: false
---

# S02: ADK Auth e Session Ownership

**ADK route and runtime ownership paths now enforce session-authenticated canonical identity and stored session/invocation ownership before Gemini/tool side effects, with PHI-safe diagnostics and deterministic pytest proof.**

## What Happened

S02 closed the ADK auth/session-ownership gap across the route and runtime boundary. T01 made `/api/v2/adk/run` depend on canonical session authentication, reject mismatched payload user ids before wrapper construction, and overwrite nested context identity/lifecycle fields so the request payload cannot spoof the authenticated caller. T02 enforced fail-closed runtime ownership checks for session resume/close and invocation cancel paths, denying missing/blank/foreign stored owners before lifecycle mutation, `_execute_request`, provider/tool execution, or in-flight cancellation. T03 locked the diagnostic surface and regression evidence: denial events expose low-cardinality route/reason/lifecycle metadata while excluding prompts, payload text, patient-like strings, cookies, session tokens, raw user ids, Gemini keys, session state, and provider secrets. This recovery pass did not change implementation code; it reran the S02 verification commands fresh and used the canonical GSD slice completion tool to reconcile the previously stuck closeout state.

## Verification

Fresh slice-level verification ran after the last code changes and before completion. `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py` exited 0 with 19 passed in 0.84s. `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_adk.py backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py backend-hormonia/tests/unit/test_adk_runner_integration.py backend-hormonia/tests/unit/test_adk_tools_runtime.py backend-hormonia/tests/unit/test_adk_metrics.py` exited 0 with 61 passed and 7 expected skips for missing local `google-adk` in 11.82s.

## Requirements Advanced

- R012 — Closed the ADK auth hardening portion with controlled route/runtime pytest proof and no live provider dependency.
- R013 — Closed the ADK session ownership proof-gap portion with deterministic same-user/foreign/missing-owner lifecycle tests.
- R018 — Made the ADK medium-finding coverage explicit for later evidence-matrix closure instead of silently dropping it.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

The implementation scope did not change. Auto-mode previously left S02 in a closeout loop with all tasks complete but no slice summary/UAT and an unchecked roadmap row; this recovery pass reran verification and closed the slice canonically.

## Known Limitations

S02 intentionally does not prove live Gemini/provider behavior, production-like runtime, JWT/config posture, or milestone-wide R012/R013 evidence-matrix closure. Those remain out of scope for this slice and feed S05/M015 as planned.

## Follow-ups

S05 should cite the fresh S02 proof commands and include the ADK auth/session-ownership row in `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md`.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/adk.py` — ADK route uses canonical session authentication, rejects payload identity mismatch, overwrites spoofable context identity/lifecycle fields, and emits sanitized denial diagnostics.
- `backend-hormonia/app/ai/adk/runtime.py` — Runtime enforces stored session/invocation ownership before resume/close/cancel side effects and exposes generic lifecycle ownership errors.
- `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py` — Focused M014/S02 proof covers route identity, runtime ownership, side-effect denial, and PHI/secret-safe diagnostics.
- `backend-hormonia/tests/api/v2/test_adk.py` — Existing ADK API tests were updated for authenticated route behavior and canonical user propagation.
- `backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py` — Supporting ADK wrapper regression coverage included in S02 verification.
- `backend-hormonia/tests/unit/test_adk_runner_integration.py` — Supporting ADK runner integration regression coverage included in S02 verification; local `google-adk`-dependent cases are skipped when dependency is unavailable.
- `backend-hormonia/tests/unit/test_adk_tools_runtime.py` — Supporting runtime lifecycle regression coverage included in S02 verification.
- `backend-hormonia/tests/unit/test_adk_metrics.py` — Supporting ADK metrics regression coverage included in S02 verification.
