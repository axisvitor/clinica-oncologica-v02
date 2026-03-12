# T03: Deferred follow-up retry and atomic day advancement

**Slice:** S01 — **Milestone:** M001

## Description

Ensure deferred follow-up sends are retried on failure and day advancement is atomic and verified.

Purpose: Two related silent-failure paths are fixed: (1) When the follow-up system's MessageExecutor fails to send a deferred message, the failure is swallowed and the follow-up is silently dropped. This plan adds a Celery retry task for follow-up sends. (2) When a flow day completes and the day advancement step fails, the flow can end up in a broken state where day_complete=True but current_step was never incremented. This plan makes day advancement atomic with a verification flag.

Output: New Celery task `followup_retry.py`, modified MessageExecutor, atomic day advancement in sequencing, and tests for both.

## Must-Haves

- [ ] "When a deferred follow-up send fails, it is re-queued via a Celery task instead of being silently dropped"
- [ ] "Day advancement after day_complete is verified: if advance fails, the flow stays at the current day with an error flag instead of silently skipping to a broken state"
- [ ] "The day advancement writes current_step and day_complete atomically in a single DB commit with optimistic locking"

## Files

- `backend-hormonia/app/tasks/flows/followup_retry.py`
- `backend-hormonia/app/services/follow_up_system/execution/message.py`
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py`
- `backend-hormonia/app/services/flow/management/advancement.py`
- `backend-hormonia/tests/unit/tasks/test_followup_retry_task.py`
- `backend-hormonia/tests/unit/services/test_day_advancement_atomic.py`
