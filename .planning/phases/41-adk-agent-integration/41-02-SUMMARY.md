---
phase: 41-adk-agent-integration
plan: 02
subsystem: api
tags: [fastapi, adk, pydantic, pytest, lgpd]
requires:
  - phase: 41-01
    provides: ADK runtime/tool contracts and PIISafeADKWrapper delegation path
provides:
  - Live `/api/v2/adk/run` endpoint wired through `PIISafeADKWrapper.safe_run`
  - ADK v2 request/response schema contract for prompt/tool/session payloads
  - Integration tests asserting wrapper call path and validation behavior
affects: [adk-endpoint-consumers, phase-42-admin-integration]
tech-stack:
  added: []
  patterns: [thin-router-wrapper-delegation, normalized-adk-response, red-green-tdd]
key-files:
  created:
    - backend-hormonia/app/schemas/v2/adk.py
    - backend-hormonia/app/api/v2/routers/adk.py
    - backend-hormonia/tests/api/v2/test_adk.py
  modified:
    - backend-hormonia/app/api/v2/router.py
key-decisions:
  - "Keep ADK endpoint execution behind PIISafeADKWrapper instead of direct runtime calls in router."
  - "Expose normalized API payload with status/tool_name/session_id/output and request_source metadata."
patterns-established:
  - "ADK endpoint contract pattern: strict request validation with extra=forbid and stable response envelope."
  - "Wrapper-path verification pattern: monkeypatch safe_run and assert operation/context metadata."
requirements-completed: [ADK-07]
duration: 9 min
completed: 2026-03-04
---

# Phase 41 Plan 02: ADK Endpoint Wiring Summary

**FastAPI now exposes `/api/v2/adk/run` with strict schema validation and PIISafe wrapper delegation, validated by deterministic endpoint integration tests.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-04T00:09:46Z
- **Completed:** 2026-03-04T00:19:07Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `ADKRunRequest` and `ADKRunResponse` schemas for prompt/tool/session payload handling in `app/schemas/v2/adk.py`.
- Added `app/api/v2/routers/adk.py` with `POST /run` handler that builds `AIDeps`, routes through `PIISafeADKWrapper.safe_run`, and normalizes output.
- Registered the ADK router family in `app/api/v2/router.py` under `/api/v2/adk`.
- Added `tests/api/v2/test_adk.py` endpoint integration coverage for normalized output, wrapper invocation metadata, and 422 validation behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Add ADK endpoint contract and router implementation** - `d55af21b` (test)
2. **Task 1 (GREEN): Add ADK endpoint contract and router implementation** - `bbbb9f09` (feat)
3. **Task 2 (RED): Add integration tests proving wrapper path metadata** - `b62e3ac2` (test)
4. **Task 2 (GREEN): Add integration tests proving wrapper path metadata** - `5d6d18fd` (feat)

## Files Created/Modified

- `backend-hormonia/app/schemas/v2/adk.py` - Request/response models for ADK run endpoint.
- `backend-hormonia/app/api/v2/routers/adk.py` - Endpoint handler invoking PIISafe wrapper and returning normalized payload.
- `backend-hormonia/app/api/v2/router.py` - Router registration for `/api/v2/adk/*`.
- `backend-hormonia/tests/api/v2/test_adk.py` - Integration tests for wrapper call path and validation guardrails.

## Decisions Made

- Used a thin endpoint that never calls ADK runtime directly, preserving the mandatory PIISafe boundary.
- Added `request_source=api_v2_adk` to wrapper context to make endpoint-origin metadata explicit in integration assertions.

## Deviations from Plan

None - plan executed exactly as written.

## Authentication Gates

None.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ADK endpoint contract is stable for downstream consumers.
- Phase 41 remains ready for final phase-level verification/transition work.

## Self-Check: PASSED

- FOUND: `.planning/phases/41-adk-agent-integration/41-02-SUMMARY.md`
- FOUND: `backend-hormonia/app/schemas/v2/adk.py`
- FOUND: `backend-hormonia/app/api/v2/routers/adk.py`
- FOUND: `backend-hormonia/tests/api/v2/test_adk.py`
- FOUND commits: `d55af21b`, `bbbb9f09`, `b62e3ac2`, `5d6d18fd`
