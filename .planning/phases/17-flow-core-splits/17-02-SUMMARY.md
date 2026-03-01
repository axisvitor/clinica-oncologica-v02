---
phase: 17-flow-core-splits
plan: 02
subsystem: api
tags: [flow-core, refactor, compatibility-shim, pytest]
requires:
  - phase: 16-dead-code-removal
    provides: legacy flow imports cleaned before split re-exports
provides:
  - canonical FlowCore package split across operations, transitions, and template binding modules
  - compatibility shim preserving `app.services.flow_core` import surface
  - contract tests guarding module boundaries and per-file size limits
affects: [phase-17, phase-18-flow-service-splits]
tech-stack:
  added: []
  patterns: [mixin composition for flow services, legacy import shim re-export pattern]
key-files:
  created:
    - backend-hormonia/app/services/flow/core/operations.py
    - backend-hormonia/app/services/flow/core/transitions.py
    - backend-hormonia/app/services/flow/core/template_binding.py
    - backend-hormonia/app/services/flow/core/service.py
    - backend-hormonia/tests/unit/services/test_flow_core_split_contract.py
  modified:
    - backend-hormonia/app/services/flow_core.py
    - backend-hormonia/app/services/flow/core/__init__.py
key-decisions:
  - "FlowCore now composes three responsibility-specific mixins behind a single class in app.services.flow.core.service."
  - "Legacy imports remain stable by re-exporting FlowCore exceptions and block constants from app.services.flow_core."
patterns-established:
  - "Core split modules stay below 500 lines and are guarded by contract tests."
  - "Flow transition queries prefer repository getters when available, then fall back to direct async SQLAlchemy queries."
requirements-completed: [SPLIT-06]
duration: 5 min
completed: 2026-02-25
---

# Phase 17 Plan 02: Flow Core Splits Summary

**FlowCore was decomposed into dedicated operations, transitions, and template-binding modules while preserving the existing `app.services.flow_core` import contract through a compatibility shim.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25T15:40:44Z
- **Completed:** 2026-02-25T15:45:57Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Split the previous 888-line `flow_core.py` implementation into canonical modules with clear responsibility boundaries.
- Kept backward compatibility by turning `app/services/flow_core.py` into a re-export shim for `FlowCore`, exceptions, and flow-advance block constants.
- Added split-contract tests that lock import stability, module separation, and <500 LOC file-size guarantees.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract FlowCore into operations, transitions, and template-binding modules** - `e5d81e0e` (feat)
2. **Task 2: Add FlowCore split-contract tests and run regression checks** - `a229a695` (fix)

## Files Created/Modified
- `backend-hormonia/app/services/flow/core/operations.py` - Base enrollment, day calculations, send-time, error classification, health checks, and flow-state read API.
- `backend-hormonia/app/services/flow/core/transitions.py` - Flow-type determination, day advancement, pause/resume operations, and flow transition recording.
- `backend-hormonia/app/services/flow/core/template_binding.py` - Template lookup and cache reload logic.
- `backend-hormonia/app/services/flow/core/service.py` - Composed `FlowCore` class and canonical exports.
- `backend-hormonia/app/services/flow/core/__init__.py` - Package exports for canonical path.
- `backend-hormonia/app/services/flow_core.py` - Legacy shim re-exporting canonical symbols.
- `backend-hormonia/tests/unit/services/test_flow_core_split_contract.py` - Contract tests for split stability and module boundaries.

## Decisions Made
- Adopted mixin composition (`FlowCoreOperationsMixin`, `FlowCoreTransitionsMixin`, `FlowCoreTemplateBindingMixin`) so high-risk transition logic is physically isolated from template-binding concerns.
- Kept legacy callers stable by re-exporting public surface from `app.services.flow.core.service` via `app.services.flow_core`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Restored repository-backed flow-state retrieval compatibility**
- **Found during:** Task 2 (regression check execution)
- **Issue:** `test_flow_advance_awaiting_response_block.py` failed because transition methods always awaited `db.execute`, while the regression harness uses repository getter stubs for flow retrieval.
- **Fix:** Added `_get_flow_state_by_status` in transitions mixin to prefer repository getters (`get_active_flow`/`get_paused_flow`) and fall back to async SQLAlchemy query.
- **Files modified:** `backend-hormonia/app/services/flow/core/transitions.py`
- **Verification:** `python3 -m pytest tests/unit/services/test_flow_core_split_contract.py tests/unit/services/test_flow_advance_awaiting_response_block.py -x`
- **Committed in:** `a229a695` (part of Task 2)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix was required to keep existing awaiting-response conflict guard regression semantics unchanged after split.

## Issues Encountered
- Regression check initially failed with `TypeError: object MagicMock can't be used in 'await' expression`; resolved by reintroducing repository-first flow lookup fallback in transition methods.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
FlowCore split contract is locked for SPLIT-06 and ready for downstream flow service splits.

---
*Phase: 17-flow-core-splits*
*Completed: 2026-02-25*

## Self-Check: PASSED
- FOUND: `.planning/phases/17-flow-core-splits/17-02-SUMMARY.md`
- FOUND: `e5d81e0e`
- FOUND: `a229a695`
