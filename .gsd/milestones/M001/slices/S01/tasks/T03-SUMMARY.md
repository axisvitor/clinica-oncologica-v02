---
id: T03
parent: S01
milestone: M001
provides:
  - Celery retry task for deferred follow-up sends that fail during execution
  - Scheduler-backed MessageExecutor retry enqueueing instead of silent follow-up drops
  - Atomic day completion helper with optimistic locking and verification flagging
requires: []
affects: []
key_files: []
key_decisions: []
patterns_established: []
observability_surfaces: []
drill_down_paths: []
duration: 20m
verification_result: passed
completed_at: 2026-03-06
blocker_discovered: false
---
# T03: Deferred follow-up retry and atomic day advancement

**# Phase 50 Plan 03: Deferred Follow-Up Retry And Atomic Day Advancement Summary**

## What Happened

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
