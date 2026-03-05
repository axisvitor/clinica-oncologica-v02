---
phase: 45-adk-tool-safety-and-deterministic-errors
plan: 01
subsystem: api
tags: [adk, policy_block, tool-safety, runtime]
requires:
  - phase: 44-adk-runtime-controls
    provides: explicit ADK runtime/session contract and canonical wrapper-only route handoff
provides:
  - Runtime-owned pre-tool guardrail that blocks unsafe calls before any tool side effect
  - Shared `policy_block` normalization across runner-enabled and direct-handler execution
  - Wrapper-to-runtime policy context forwarding without bypassing prompt sanitization
affects: [phase-45, adk-runtime, testing]
tech-stack:
  added: [app-owned tool policy evaluator]
  patterns: [before-tool policy callback, shared runtime guardrail fallback]
key-files:
  created: []
  modified:
    - backend-hormonia/app/ai/adk/runtime.py
    - backend-hormonia/app/ai/adk/wrapper.py
    - backend-hormonia/tests/api/v2/test_adk.py
    - backend-hormonia/tests/unit/test_adk_tools_runtime.py
    - backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py
key-decisions:
  - "Keep tool safety decisions at the runtime boundary so both ADK runner execution and direct-handler fallback share the same policy verdict."
  - "Forward normalized `tool_policy` metadata from `PIISafeADKWrapper` instead of letting tool handlers infer safety from prompt text."
patterns-established:
  - "Unsafe tool calls are rejected before handler/domain execution begins."
  - "Policy metadata is evaluated once and normalized to the canonical `{status, result}` runtime envelope."
requirements-completed: [ADK-11]
duration: 41min
completed: 2026-03-05
---

# Phase 45 Plan 01: ADK Tool Safety and Deterministic Errors Summary

**Runtime-owned `policy_block` guardrails now stop unsafe ADK tool calls before execution while preserving the canonical route envelope**

## Performance

- **Duration:** 41min
- **Started:** 2026-03-05T22:18:29Z
- **Completed:** 2026-03-05T23:00:01Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added a runtime-level policy evaluator plus `before_tool_callback` hook so unsafe requests are blocked before the tool or domain code executes.
- Reused the same guardrail for the direct-handler compatibility branch so ADK-unavailable execution cannot bypass safety checks.
- Locked route, runtime, and wrapper regressions proving `policy_block` preserves the existing `/api/v2/adk/run` envelope and still passes through prompt sanitization first.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add a runtime-owned pre-tool guardrail that returns deterministic `policy_block` results** - `29dfcdbd` (feat)
2. **Task 2: Lock route/runtime regression coverage for blocked tool requests** - `0ff1d30c` (test)

**Plan metadata:** to be committed separately in this run

## Files Created/Modified
- `backend-hormonia/app/ai/adk/runtime.py` - Adds policy block data structures, runtime evaluators, and the ADK `before_tool_callback` / fallback guardrail flow
- `backend-hormonia/app/ai/adk/wrapper.py` - Normalizes and forwards `tool_policy` metadata while keeping prompt sanitization mandatory
- `backend-hormonia/tests/api/v2/test_adk.py` - Verifies the API contract returns `policy_block` through the canonical response envelope
- `backend-hormonia/tests/unit/test_adk_tools_runtime.py` - Proves blocked requests never execute handler/domain side effects in either execution branch
- `backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py` - Verifies policy forwarding does not bypass sanitization or duplicate runtime calls

## Decisions Made
- Evaluated tool policy at the runtime boundary instead of in individual handlers so every execution path shares one deterministic guardrail.
- Kept policy inputs explicit through `tool_policy` / `policy` context metadata, including required-context keys, blocked prompts, and blocked tools.
- Preserved `PIISafeADKWrapper.safe_run()` as the only entrypoint, with policy metadata forwarding layered on top of sanitization rather than around it.

## Deviations from Plan

The `gsd-executor` subagent stalled after landing both task commits. Summary/state/roadmap metadata were completed manually against the committed code instead of replaying implementation work.

## Issues Encountered

- The orchestration agent failed to emit its final closeout, but the code changes and test evidence were already complete and could be verified locally.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 45 now has a stable `policy_block` foundation for broader deterministic error classification.
- Wave 2 can focus on separating `tool_error` and `upstream_error` without reworking the safety boundary, which is the remaining work to fully satisfy ADK-12.

## Self-Check: PASSED

- Found `.planning/phases/45-adk-tool-safety-and-deterministic-errors/45-01-SUMMARY.md`
- Found commit `29dfcdbd`
- Found commit `0ff1d30c`

---
*Phase: 45-adk-tool-safety-and-deterministic-errors*
*Completed: 2026-03-05*
