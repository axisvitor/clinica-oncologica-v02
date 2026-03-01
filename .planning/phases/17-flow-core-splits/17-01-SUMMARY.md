---
phase: 17-flow-core-splits
plan: 01
subsystem: api
tags: [flow, refactor, compatibility-shim, orchestration]

requires:
  - phase: 16-03
    provides: dead flow imports removed from core package surface before split
provides:
  - split direct flow orchestration into message, response, and shared utility modules
  - compatibility shim at legacy _flow_functions import path
  - split-contract tests for module boundaries and file-size budget
affects: [phase-17-02, phase-17-03, sequential-message-handler]

tech-stack:
  added: []
  patterns: [focused-module-split, compatibility-re-export-shim, split-contract-tests]

key-files:
  created:
    - backend-hormonia/app/services/flow/_flow_message_flow.py
    - backend-hormonia/app/services/flow/_flow_response_flow.py
    - backend-hormonia/app/services/flow/_flow_orchestration_utils.py
    - backend-hormonia/tests/unit/services/flow/test_flow_functions_split_contract.py
    - .planning/phases/17-flow-core-splits/deferred-items.md
  modified:
    - backend-hormonia/app/services/flow/_flow_functions.py

key-decisions:
  - "Kept _flow_functions.py as a strict compatibility shim with explicit __all__ to preserve legacy imports."
  - "Centralized shared state validation, thread-id checks, send-mode parsing, and context mismatch helpers in _flow_orchestration_utils.py."

patterns-established:
  - "Flow splits keep runner entrypoints in focused modules and expose old import paths via re-export shims."

requirements-completed: [SPLIT-05]

duration: 8 min
completed: 2026-02-25
---

# Phase 17 Plan 01: _flow_functions Split Summary

**Direct flow orchestration was decomposed into message-flow, response-flow, and shared utility modules with a backward-compatible `_flow_functions` shim and regression contract tests.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-25T15:35:42Z
- **Completed:** 2026-02-25T15:44:35Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Replaced the 887-line `_flow_functions.py` monolith with focused modules for message dispatch, response continuation, and shared orchestration utilities.
- Preserved existing call sites by re-exporting the public API from `_flow_functions.py` with explicit `__all__` coverage.
- Added split-contract tests validating shim exports, responsibility boundaries, and mandatory `<500` line budgets.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract _flow_functions responsibilities into message, response, and utility modules** - `bcbeaa53` (feat)
2. **Task 2: Add split-contract regression tests and enforce per-file size budget** - `3e1ea0e5` (test)

**Plan metadata:** pending

## Files Created/Modified
- `backend-hormonia/app/services/flow/_flow_orchestration_utils.py` - Shared TypedDicts, validation helpers, flow-state loading, send-mode parsing, and response-context comparison utilities.
- `backend-hormonia/app/services/flow/_flow_message_flow.py` - Message-flow context load, dispatch execution preparation, send-mode dispatch, and `run_flow_message`.
- `backend-hormonia/app/services/flow/_flow_response_flow.py` - Response-flow context load, continuation dispatch, and `run_flow_response`.
- `backend-hormonia/app/services/flow/_flow_functions.py` - Compatibility shim re-exporting the legacy public API.
- `backend-hormonia/tests/unit/services/flow/test_flow_functions_split_contract.py` - Contract checks for exports, module boundaries, and file-size guardrails.
- `.planning/phases/17-flow-core-splits/deferred-items.md` - Logged out-of-scope test-runtime issue discovered during extra verification.

## Decisions Made
- Maintained legacy import compatibility with shim exports from `_flow_functions.py` instead of updating callers.
- Kept message and response orchestration isolated while moving shared runtime validation and normalization into one utility module.

## Deviations from Plan

None - plan executed exactly as written.

## Authentication Gates

None.

## Issues Encountered
- Extra out-of-plan regression command targeting direct-flow tests surfaced a pre-existing settings monkeypatch error (`AI_FLOW_FRAMEWORK` not defined on `Settings`); logged to `.planning/phases/17-flow-core-splits/deferred-items.md` and left untouched as out of scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- SPLIT-05 target for `_flow_functions` is complete with compatibility imports and split-contract coverage.
- Phase 17 can proceed to `17-02-PLAN.md` for `flow_core.py` decomposition using the same shim pattern.

---
*Phase: 17-flow-core-splits*
*Completed: 2026-02-25*

## Self-Check: PASSED

- FOUND: `.planning/phases/17-flow-core-splits/17-01-SUMMARY.md`
- FOUND: `bcbeaa53`
- FOUND: `3e1ea0e5`
