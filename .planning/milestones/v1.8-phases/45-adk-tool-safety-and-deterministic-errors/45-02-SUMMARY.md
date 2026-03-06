---
phase: 45-adk-tool-safety-and-deterministic-errors
plan: 02
subsystem: api
tags: [adk, deterministic-errors, tool-error, runtime]
requires:
  - phase: 45-adk-tool-safety-and-deterministic-errors
    provides: pre-tool safety guardrail and canonical ADK route envelope from plan 45-01
provides:
  - Runtime-owned `tool_error` and `upstream_error` classification across ADK runner and direct-handler execution
  - Explicit tool-origin exception markers without parsing arbitrary exception text
  - Regression coverage proving runner failures do not silently fall through to post-start direct dispatch
affects: [phase-45, adk-runtime, adk-testing]
tech-stack:
  added: []
  patterns: [source-aware failure classifier, no post-start fallback boundary]
key-files:
  created: []
  modified:
    - backend-hormonia/app/ai/adk/runtime.py
    - backend-hormonia/app/ai/adk/tools.py
    - backend-hormonia/tests/api/v2/test_adk.py
    - backend-hormonia/tests/unit/test_adk_tools_runtime.py
    - backend-hormonia/tests/unit/test_adk_runner_integration.py
key-decisions:
  - "Wrap tool-dispatch exceptions with explicit ADKToolExecutionError metadata so runtime classification never parses raw exception strings."
  - "Treat any failure after the ADK runner path starts as deterministic classification instead of falling through to direct-handler execution."
patterns-established:
  - "Tool-side failures map to `tool_error` in both direct-handler and runner-enabled branches."
  - "Runner/bootstrap/model failures map to `upstream_error` and never trigger post-start fallback."
requirements-completed: [ADK-12]
duration: 7min
completed: 2026-03-05
---

# Phase 45 Plan 02: Deterministic ADK Error Classification Summary

**Source-aware ADK failure classification now separates tool execution failures from runner/bootstrap failures without silent post-start fallback**

## Performance

- **Duration:** 7min
- **Started:** 2026-03-05T23:08:57Z
- **Completed:** 2026-03-05T23:15:40Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Replaced the generic `runtime_error` path with a runtime-owned classifier that returns `tool_error` for explicit tool-origin failures and `upstream_error` for runner/bootstrap/model failures.
- Removed the runner-start fallback that could previously fall through to the direct handler after ADK execution had already begun.
- Locked parity regressions across the API envelope, direct-handler runtime path, fake runner path, and conditional real-ADK integration coverage.

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace the ambiguous runtime fallback with a source-aware deterministic classifier** - `c2e25f7e` (feat)
2. **Task 2: Add parity coverage for `tool_error` and `upstream_error` across both execution branches** - `505ade94` (test)

**Plan metadata:** to be committed separately in this run

## Files Created/Modified
- `backend-hormonia/app/ai/adk/runtime.py` - Adds deterministic failure classification, explicit runner execution boundary, and terminal invocation statuses for `tool_error` / `upstream_error`
- `backend-hormonia/app/ai/adk/tools.py` - Wraps tool-handler failures with explicit tool-origin metadata for both runner and direct-handler execution
- `backend-hormonia/tests/api/v2/test_adk.py` - Verifies the canonical `/api/v2/adk/run` envelope preserves deterministic error statuses
- `backend-hormonia/tests/unit/test_adk_tools_runtime.py` - Covers repeated `tool_error` / `upstream_error` scenarios and proves runner failures do not silently re-dispatch the direct handler
- `backend-hormonia/tests/unit/test_adk_runner_integration.py` - Adds conditional real-ADK regression coverage for deterministic classification when `google-adk` is available

## Decisions Made
- Tool-origin failures are marked at the tool dispatch seam with `ADKToolExecutionError` so the runtime classifier can make deterministic decisions without string parsing.
- Once the ADK runner path is selected and started, missing output or raised exceptions are treated as `upstream_error` instead of triggering a compatibility fallback to the direct handler.
- `RunConfig` construction now fails through the same upstream classifier instead of being silently ignored, keeping bootstrap/configuration failures deterministic.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Local verification environment does not have `google-adk` installed, so the conditional runner integration tests were skipped by design while API and unit parity coverage ran fully.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 45 now has deterministic `tool_error` / `upstream_error` behavior locked in both runtime branches and the API contract.
- Plan 45-03 can focus on final repeated-scenario audit coverage and validation-map synchronization rather than reworking runtime semantics.

## Self-Check: PASSED

- Found `.planning/phases/45-adk-tool-safety-and-deterministic-errors/45-02-SUMMARY.md`
- Found commit `c2e25f7e`
- Found commit `505ade94`

---
*Phase: 45-adk-tool-safety-and-deterministic-errors*
*Completed: 2026-03-05*
