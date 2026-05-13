---
id: T03
parent: S02
milestone: M014
key_files:
  - backend-hormonia/app/api/v2/routers/adk.py
  - backend-hormonia/app/ai/adk/runtime.py
  - backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py
  - backend-hormonia/tests/api/v2/test_adk.py
key_decisions:
  - ADK route/runtime denial diagnostics remain low-cardinality and PHI-safe while exposing machine-checkable event/reason/lifecycle fields.
  - S02 regression evidence is pytest-only and hermetic: no live Gemini/provider, production DB, real patient data, or gitignored secret artifacts are required.
duration: 
verification_result: passed
completed_at: 2026-05-13T16:56:43.918Z
blocker_discovered: false
---

# T03: Locked PHI-safe ADK ownership-denial diagnostics and supporting regression evidence for S02.

**Locked PHI-safe ADK ownership-denial diagnostics and supporting regression evidence for S02.**

## What Happened

Verified and recorded the already-present T03 S02 evidence lock. The focused security proof asserts route and runtime ADK denial diagnostics expose reason/lifecycle metadata while excluding prompts, payload text, patient-like strings, cookies/session tokens, raw user ids, Gemini keys, session state, and provider secrets. The supporting ADK regression suite remains authenticated/hermetic and covers route, wrapper, runner integration, runtime lifecycle, and metrics behavior without live providers or production data. The recovery pass aligned the GSD DB with the existing checked S02 plan and fresh verification evidence.

## Verification

Ran both T03 verification commands exactly from the plan. The focused S02 security proof passed 16 tests. The supporting ADK regression command passed 61 tests with 7 expected skips because `google-adk` is not installed in the local test environment.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py` | 0 | ✅ pass — 16 passed | 52971ms |
| 2 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_adk.py backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py backend-hormonia/tests/unit/test_adk_runner_integration.py backend-hormonia/tests/unit/test_adk_tools_runtime.py backend-hormonia/tests/unit/test_adk_metrics.py` | 0 | ✅ pass — 61 passed, 7 skipped | 52971ms |

## Deviations

No code changes were needed during this recovery pass because T03 diagnostics and regression tests were already present and passing; this pass reconciled stale GSD DB state with the checked S02 plan and existing T03 verification artifact.

## Known Issues

The GSD slice summary artifact remains unavailable until the slice-completion renderer runs; this task completion makes all S02 tasks complete in the DB so the slice can be closed canonically by the next available slice-completion step.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/adk.py`
- `backend-hormonia/app/ai/adk/runtime.py`
- `backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py`
- `backend-hormonia/tests/api/v2/test_adk.py`
