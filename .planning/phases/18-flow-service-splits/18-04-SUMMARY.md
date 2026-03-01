---
phase: 18-flow-service-splits
plan: 04
subsystem: api
tags: [flow, sequential-message-handler, shim, pytest, service-split]

requires:
  - phase: 17-flow-core-splits
    provides: Shim-based split pattern and split-contract verification conventions
provides:
  - sequential_message_handler split into sequencing/state/personalization/quiz/service modules under 500 lines
  - Legacy app.services.flow.sequential_message_handler path preserved as compatibility shim
  - Contract tests proving shim identity, factory re-export, responsibility boundaries, and line-budget compliance
affects: [phase-18-service-splits, flow-automation, response-processing]

tech-stack:
  added: []
  patterns: [service composition via mixins, strict shim re-exports, split contract tests]

key-files:
  created:
    - backend-hormonia/app/services/flow/sequential_message_handler_pkg/__init__.py
    - backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py
    - backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py
    - backend-hormonia/app/services/flow/sequential_message_handler_pkg/personalization.py
    - backend-hormonia/app/services/flow/sequential_message_handler_pkg/quiz.py
    - backend-hormonia/app/services/flow/sequential_message_handler_pkg/service.py
    - backend-hormonia/tests/unit/services/flow/test_sequential_message_handler_split_contract.py
  modified:
    - backend-hormonia/app/services/flow/sequential_message_handler.py
    - backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py

key-decisions:
  - "Keep sequential_message_handler.py as a strict shim that re-exports SequentialMessageHandler and get_sequential_message_handler from sequential_message_handler_pkg."
  - "Preserve TYPE_CHECKING EnhancedFlowEngine references and lazy _get_ai_engine() in personalization mixin to avoid runtime circular imports."

patterns-established:
  - "Split modules keep business logic intact while relocating methods by responsibility under a composed service class."
  - "Contract tests enforce module responsibility ownership and <500-line budgets for each split file."

requirements-completed: [SPLIT-01]
duration: 5 min
completed: 2026-02-26
---

# Phase 18 Plan 04: Flow Service Splits Summary

**Sequential message flow orchestration is now modularized into focused package mixins with full shim compatibility and split-contract evidence covering import identity, module boundaries, and file-size limits.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-26T15:02:39Z
- **Completed:** 2026-02-26T15:07:49Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Split the 1,135-line `sequential_message_handler.py` into dedicated modules for sequencing, state management, personalization, quiz-link injection, and composed service wiring.
- Replaced `app/services/flow/sequential_message_handler.py` with a thin compatibility shim preserving existing caller imports and factory access.
- Added contract tests that validate shim-to-canonical identity, factory re-export parity, responsibility placement by module, and sub-500-line guardrails.
- Executed regressions for sequential handler behavior and the full Phase 18 split-contract gate across monitoring, dashboard, engine, and handler services.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract sequential_message_handler.py into focused modules in sequential_message_handler_pkg/** - `4ac0a5fd` (refactor)
2. **Task 2: Add sequential_message_handler split contract tests, run regressions, and execute phase gate** - `5a010b29` (test)

**Plan metadata:** pending

## Files Created/Modified

- `backend-hormonia/app/services/flow/sequential_message_handler.py` - compatibility shim re-exporting canonical package symbols.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py` - send-loop orchestration and message dispatch flow.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` - flow-state lookup/progress persistence and day config retrieval.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/personalization.py` - AI personalization, fallback grounding, and template variation logic.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/quiz.py` - quiz link injection and monthly session linkage.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/service.py` - composed handler class with preserved constructor/factory behavior.
- `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler_split_contract.py` - split contract assertions for shim identity, module responsibilities, and line limits.
- `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py` - regression fixture hardening for direct-flow framework forcing in current settings model.

## Decisions Made

- Applied mixin composition so all existing method contracts remain available on one `SequentialMessageHandler` class while physically separating concerns.
- Kept compatibility at the original import path using explicit named re-exports and `__all__` in both package and shim surfaces.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Sequential regression fixture attempted to mutate missing settings field**
- **Found during:** Task 2 (regression execution)
- **Issue:** `test_sequential_message_handler.py` tried to set `app.config.settings.AI_FLOW_FRAMEWORK`, which raises `ValueError` under the current Pydantic settings model.
- **Fix:** Added `_force_direct_framework` helper to set the field when present or fall back to env-var forcing when absent.
- **Files modified:** `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py`
- **Verification:** `python3 -m pytest tests/unit/services/flow/test_sequential_message_handler_split_contract.py tests/unit/services/flow/test_sequential_message_handler.py -x -q` passed.
- **Committed in:** `5a010b29` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Blocker fix was required to execute the requested regression gate; no architectural or scope-expansion changes.

## Issues Encountered

- Pytest emitted existing `pytest-asyncio` loop-scope deprecation warnings; tests still passed and no behavior changes were required.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SPLIT-01 now has split-contract and regression evidence with all required modules below 500 lines.
- Remaining incomplete plan in phase directory is `18-03-PLAN.md`; this plan is ready for handoff/closure sequencing as needed.

---
*Phase: 18-flow-service-splits*
*Completed: 2026-02-26*

## Self-Check: PASSED

- FOUND: `.planning/phases/18-flow-service-splits/18-04-SUMMARY.md`
- FOUND: `4ac0a5fd`
- FOUND: `5a010b29`
