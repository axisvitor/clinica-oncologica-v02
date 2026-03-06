---
phase: 50-pipeline-reliability
plan: 03
subsystem: follow-up-and-flow-state
tags: [flow, follow-up, retry, atomicity, celery]
provides:
  - Celery retry task for deferred follow-up sends that fail during execution
  - Scheduler-backed MessageExecutor retry enqueueing instead of silent follow-up drops
  - Atomic day completion helper with optimistic locking and verification flagging
affects: [follow-up-execution, celery, sequential-message-handler, flow-state]
tech-stack:
  added: []
  patterns: [background retry task, optimistic locking, atomic verification writes]
key-files:
  created:
    - .planning/phases/50-pipeline-reliability/50-03-SUMMARY.md
    - backend-hormonia/app/tasks/flows/followup_retry.py
    - backend-hormonia/tests/unit/tasks/test_followup_retry_task.py
    - backend-hormonia/tests/unit/services/test_day_advancement_atomic.py
  modified:
    - backend-hormonia/app/services/follow_up_system/execution/message.py
    - backend-hormonia/app/services/follow_up_system/service.py
    - backend-hormonia/app/tasks/flows/__init__.py
    - backend-hormonia/app/services/flow/management/advancement.py
    - backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py
key-decisions:
  - "Retry deferred follow-up sends through Celery using persisted follow-up metadata so execution failures are re-queued instead of disappearing in-process."
  - "Move day completion into `advance_day_atomic()` so `day_complete` and verification metadata are written in a controlled optimistic-lock flow."
patterns-established:
  - "Silent follow-up send failures now transition into explicit retry or terminal-failure state updates."
requirements-completed: [FLOW-03, FLOW-04]
duration: 20m
completed: 2026-03-06
---

# Phase 50 Plan 03: Deferred Follow-Up Retry And Atomic Day Advancement Summary

**Deferred follow-up send failures now retry in the background, and day completion writes verification metadata instead of leaving silent inconsistent state**

## Performance

- **Duration:** 20m
- **Started:** 2026-03-06T16:26:11-03:00
- **Completed:** 2026-03-06T16:46:04-03:00
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added `retry_failed_followup_send`, a Celery task that replays deferred follow-up message actions with backoff and jitter, updates Redis-backed action status on success, and marks terminal failures explicitly after retry exhaustion.
- Updated `MessageExecutor` and `FollowUpSystemService` so deferred message execution failures enqueue the retry task through a scheduler callback instead of being silently dropped.
- Added `advance_day_atomic()` and routed sequential day-completion paths through it so optimistic-lock version checks, `day_complete`, and `day_advance_verified` writes happen in a deterministic verified flow.

## Task Commits

Each task was committed atomically:

1. **Task 1: Retry failed deferred follow-up sends** - `695dccb3` (feat)
2. **Task 2: Verify day completion with atomic advancement helper** - `5d8de8d7` (feat)

## Files Created/Modified

- `backend-hormonia/app/tasks/flows/followup_retry.py` - Implements the deferred follow-up retry task, retry schedule, and terminal failure bookkeeping.
- `backend-hormonia/tests/unit/tasks/test_followup_retry_task.py` - Covers retry success, retry scheduling, missing-action skips, and terminal failure handling.
- `backend-hormonia/app/services/follow_up_system/execution/message.py` - Enqueues retry work when deferred follow-up message execution fails.
- `backend-hormonia/app/services/follow_up_system/service.py` - Injects the scheduler-backed retry path into `MessageExecutor`.
- `backend-hormonia/app/tasks/flows/__init__.py` - Exports the new follow-up retry task for Celery autodiscovery.
- `backend-hormonia/app/services/flow/management/advancement.py` - Adds `advance_day_atomic()` with optimistic-lock version checks and verification writes.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py` - Replaces inline day-completion writes with the shared atomic advancement helper.
- `backend-hormonia/tests/unit/services/test_day_advancement_atomic.py` - Verifies successful verification writes, commit failure behavior, and optimistic-lock handling.

## Deviations from Plan

- The implementation routes multiple deferred message action types through the retryable message executor path so the retry protection covers the real follow-up execution surface instead of a narrower single action branch.

## Self-Check: PASSED

- Verified `backend-hormonia/tests/unit/tasks/test_followup_retry_task.py` passes.
- Verified `backend-hormonia/tests/unit/services/test_day_advancement_atomic.py` passes.
- Verified `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler_split_contract.py` passes after the day-completion refactor.
- Verified `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py -k "completes_day_if_all_non_response"` passes with atomic advancement enabled.
- Verified `backend-hormonia/tests/unit/services/flow -k "not 30_days"` passes with the new advancement helper.
- Verified `backend-hormonia/tests/tasks/test_follow_up_tasks.py` and `backend-hormonia/tests/services/follow_up_system/test_message_scheduler_integration.py` pass with deferred retry wiring enabled.
- Verified commits `695dccb3` and `5d8de8d7` exist in git history.

---
*Phase: 50-pipeline-reliability*
*Completed: 2026-03-06*
