---
phase: 13-sdk-migration-cleanup
plan: 05
subsystem: ai
tags: [celery, pydantic-ai, run-sync, validation, ast]
requires:
  - phase: 13-sdk-migration-cleanup
    provides: Sync agent/domain APIs added in plan 13-04
provides:
  - Explicit Celery AI wiring to sync-agent execution paths via `use_sync_agents=True`
  - Sequential handler bridge flag propagation for Celery automation entrypoints
  - Permanent AST validation proving AI-path sync wiring and non-AI async_to_sync boundaries
affects: [sdk-03-gap-closure, celery-ai-call-chain, verification-gates]
tech-stack:
  added: []
  patterns: [explicit sync-agent bridge flags in Celery entrypoints, AST-based regression enforcement]
key-files:
  created:
    - backend-hormonia/tests/validation/test_celery_ai_run_sync_path.py
  modified:
    - backend-hormonia/app/services/enhanced_flow_engine.py
    - backend-hormonia/app/services/flow/sequential_message_handler.py
    - backend-hormonia/app/tasks/flows/batch_tasks.py
    - backend-hormonia/app/tasks/flows/flow_tasks.py
    - backend-hormonia/app/tasks/flow_automation.py
key-decisions:
  - "Use explicit per-call flags (`use_sync_agents` / `use_sync_agent_bridge`) instead of global toggles to enforce Celery sync-agent routing."
  - "Lock SDK-03 behavior with AST checks that validate both AI wiring and non-AI async_to_sync import boundaries."
patterns-established:
  - "Celery AI entrypoints must pass explicit sync-bridge flags when invoking flow generation paths."
  - "Validation tests should assert wiring contracts at the AST level for deterministic CI regression detection."
requirements-completed: [SDK-03]
duration: 11 min
completed: 2026-02-24
---

# Phase 13 Plan 05: Celery AI Sync Wiring Summary

**Celery AI flow execution now calls run_sync-backed agent/domain methods through explicit sync flags, with permanent AST validation that guards both AI wiring and non-AI async_to_sync boundaries.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-02-24T20:05:48Z
- **Completed:** 2026-02-24T20:17:05Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added `use_sync_agents` support in `EnhancedFlowEngine.generate_flow_message` and `process_patient_response`, routing Celery sync paths through `*_sync` domain APIs via `asyncio.to_thread(...)`.
- Added `use_sync_agent_bridge` propagation in `SequentialMessageHandler` and wired Celery entrypoints to pass explicit sync flags (`batch_tasks.py` and `flow_automation.py`).
- Added deterministic validation suite `tests/validation/test_celery_ai_run_sync_path.py` with AST checks for sync wiring and non-AI wrapper import boundaries.

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewire Celery AI flow chain to call run_sync-backed methods** - `84e95b45` (feat)
2. **Task 2: Add permanent SDK-03 Celery wiring and non-AI wrapper audits** - `c6ec30cf` (test)

## Files Created/Modified
- `backend-hormonia/app/services/enhanced_flow_engine.py` - added explicit sync-agent flag handling and sync-domain API routing for variation/humanization/sentiment/empathy paths.
- `backend-hormonia/app/services/flow/sequential_message_handler.py` - added `use_sync_agent_bridge` option and propagated it to flow message generation.
- `backend-hormonia/app/tasks/flows/batch_tasks.py` - enforced `use_sync_agents=True` on daily flow message generation path.
- `backend-hormonia/app/tasks/flow_automation.py` - enforced `SequentialMessageHandler(..., use_sync_agent_bridge=True)` for `send_flow_day_for_patient`.
- `backend-hormonia/app/tasks/flows/flow_tasks.py` - updated wrapper docs to clarify non-AI async bridge role.
- `backend-hormonia/tests/validation/test_celery_ai_run_sync_path.py` - new AST-based SDK-03 regression gate.

## Decisions Made
- Used explicit call-site flags for Celery sync enforcement instead of introducing new runtime feature toggles.
- Validated non-AI `async_to_sync` wrappers by banning AI/langchain import surfaces in `app/tasks/flows/base.py` and `app/tasks/follow_up.py`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- SDK-03 gap from verification is now enforced by automated tests and explicit Celery wiring.
- Phase 13 has all five plan summaries and is ready for milestone-level verification/closure.

## Self-Check: PASSED
- Confirmed summary file exists on disk.
- Confirmed task commits `84e95b45` and `c6ec30cf` exist in git history.

---
*Phase: 13-sdk-migration-cleanup*
*Completed: 2026-02-24*
