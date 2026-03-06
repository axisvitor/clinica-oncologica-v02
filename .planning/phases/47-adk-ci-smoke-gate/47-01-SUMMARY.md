---
phase: 47-adk-ci-smoke-gate
plan: 01
subsystem: testing
tags: [adk, pytest, ci, github-actions, oncology]
requires:
  - phase: 45-adk-tool-safety-and-deterministic-errors
    provides: deterministic tool policy and error classification used by smoke assertions
  - phase: 46-adk-observability-baseline
    provides: stable runtime status semantics and metrics labels for CI gating
provides:
  - Oncology ADK smoke coverage for sentiment, humanize, variation, and empathy success and policy-block trajectories
  - A dedicated smoke-adk GitHub Actions job with JUnit artifact output and no Postgres or Redis dependency
  - Backend build and overall CI status gating when any critical ADK smoke scenario regresses
affects: [verification, release-gates, build-backend]
tech-stack:
  added: []
  patterns: [adk_smoke pytest marker, parallel smoke job gating build-backend]
key-files:
  created:
    - backend-hormonia/tests/smoke/__init__.py
    - backend-hormonia/tests/smoke/test_adk_smoke.py
  modified:
    - backend-hormonia/pyproject.toml
    - backend-hormonia/app/ai/adk/runtime.py
    - backend-hormonia/tests/unit/test_adk_tools_runtime.py
    - .github/workflows/ci.yml
key-decisions:
  - "Unsupported ADK tools now return explicit `unsupported_tool` status so smoke failures and metrics distinguish configuration regressions from generic runtime errors."
  - "The smoke-adk job depends only on lint-backend so it runs in parallel with test-backend and stays service-free."
patterns-established:
  - "Critical oncology ADK regressions are covered by direct-handler smoke tests that monkeypatch GeminiDomainClient and force HAS_ADK_RUNTIME=false."
  - "Release gating happens through dedicated smoke jobs plus ci-status result checks before build artifacts are considered green."
requirements-completed: [ADK-13]
duration: 24m
completed: 2026-03-05
---

# Phase 47 Plan 01: ADK CI Smoke Gate Summary

**Oncology ADK smoke coverage now runs in CI and blocks backend builds when critical tool trajectories regress**

## Performance

- **Duration:** 24m
- **Started:** 2026-03-05T23:12:53-03:00
- **Completed:** 2026-03-05T23:36:53-03:00
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added a dedicated `adk_smoke` pytest suite covering the four oncology ADK tools across success, policy-block, and unsupported-tool trajectories without requiring google-adk, Postgres, or Redis.
- Registered the smoke marker and aligned runtime semantics so unsupported tools surface as `unsupported_tool`, keeping smoke assertions and observability labels explicit.
- Wired a `smoke-adk` GitHub Actions job into `build-backend` and `ci-status`, including JUnit artifact upload for scenario-level visibility in CI.

## Task Commits

Each task was committed atomically:

1. **Task 1: Register adk_smoke marker and create smoke test suite for four oncology tools** - `691e9c07` (test)
2. **Task 2: Add smoke-adk CI job and wire it as deploy gate dependency** - `15f5770f` (ci)

**Plan metadata:** to be committed separately in this run

## Files Created/Modified

- `backend-hormonia/tests/smoke/__init__.py` - Enables dedicated smoke test discovery package layout.
- `backend-hormonia/tests/smoke/test_adk_smoke.py` - Exercises the four oncology tools across success, policy-block, and unsupported-tool smoke scenarios.
- `backend-hormonia/pyproject.toml` - Registers the `adk_smoke` marker under strict marker validation.
- `backend-hormonia/app/ai/adk/runtime.py` - Returns and records explicit `unsupported_tool` status for missing ADK tool names.
- `backend-hormonia/tests/unit/test_adk_tools_runtime.py` - Updates runtime metric expectations to the new unsupported-tool status semantics.
- `.github/workflows/ci.yml` - Adds the `smoke-adk` job, JUnit artifact upload, and build/overall status gating.

## Decisions Made

- Kept the smoke suite on the direct-handler fallback path by forcing `HAS_ADK_RUNTIME = False`, so CI does not depend on `google-adk` availability to protect critical oncology flows.
- Ran the smoke job after `lint-backend` instead of after `test-backend` to preserve faster feedback while keeping `build-backend` blocked on the smoke result.
- Used a dedicated `unsupported_tool` runtime status instead of generic `error` so CI and observability can distinguish unsupported-tool regressions from broader execution failures.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Promote unsupported tool outcomes to a first-class runtime status**
- **Found during:** Task 1 (Register adk_smoke marker and create smoke test suite for four oncology tools)
- **Issue:** The new smoke suite expected unsupported tool invocations to report `status=\"unsupported_tool\"`, but the runtime and metric regression still classified them as generic `error`.
- **Fix:** Updated `run_adk_tool()` and the corresponding unit regression to emit and verify `unsupported_tool` as the terminal status and metric label.
- **Files modified:** `backend-hormonia/app/ai/adk/runtime.py`, `backend-hormonia/tests/unit/test_adk_tools_runtime.py`
- **Verification:** `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token .venv/bin/python -m pytest tests/smoke/test_adk_smoke.py -q -x` and `cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token .venv/bin/python -m pytest tests/unit/test_adk_tools_runtime.py -q -x -k unsupported_tool`
- **Committed in:** `691e9c07` (part of Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The deviation stayed inside the ADK runtime contract already exercised by the new smoke suite and was required for correctness and observability clarity.

## Issues Encountered

- Local verification still requires `WHATSAPP_WUZAPI_TOKEN=test-token` because backend settings bootstrap validates the WuzAPI token even when smoke tests do not call WuzAPI itself.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ADK-13 now has code-level smoke coverage plus a CI gate that blocks backend build and overall green status when a critical oncology trajectory regresses.
- Phase 47 is ready for goal verification and milestone closeout if verification passes.

## Self-Check: PASSED

- Verified `backend-hormonia/tests/smoke/test_adk_smoke.py` exists on disk.
- Verified task commits `691e9c07` and `15f5770f` exist in git history.

---
*Phase: 47-adk-ci-smoke-gate*
*Completed: 2026-03-05*
