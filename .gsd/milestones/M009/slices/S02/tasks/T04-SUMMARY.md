---
id: T04
parent: S02
milestone: M009
provides:
  - retry.py dispatches via Taskiq .kiq() instead of Celery .delay()
  - task_scheduler.py dispatches via schedule_task_at() instead of Celery .apply_async(eta=)
  - retry_handler.py dispatches via schedule_task_at() instead of Celery .apply_async(eta=)
  - Celery/Taskiq coexistence verified (external callers still use Celery .delay())
key_files:
  - backend-hormonia/app/api/v2/messages/retry.py
  - backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py
  - backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py
key_decisions:
  - Imports from messaging_taskiq (not messaging) in messaging-domain call sites only
  - External callers (flow_automation.py, batch_tasks.py) intentionally left on Celery .delay() for S03 scope
  - task_result.task_id replaces task_result.id for Taskiq compatibility
patterns_established:
  - Celery .delay(id) → await task.kiq(id) for immediate dispatch
  - Celery .apply_async(eta=datetime) → await schedule_task_at(task, datetime, *args) for delayed dispatch
  - Import from messaging_taskiq module for Taskiq tasks, from messaging for Celery tasks (coexistence pattern)
observability_surfaces:
  - retry.py returns task_id from Taskiq task result in API response for tracing
  - task_scheduler.py logs schedule_result.schedule_id with message ID and delivery time
  - retry_handler.py stores schedule_result.schedule_id in message_metadata.retry_task_id
  - All 3 call sites use structured logger.info with message ID for delivery tracing
duration: 8m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T04: Update messaging-domain call sites and verify coexistence

**Updated 3 messaging-domain call sites (retry.py, task_scheduler.py, retry_handler.py) to dispatch via Taskiq .kiq()/schedule_task_at() instead of Celery .delay()/.apply_async(eta=). Celery messaging.py untouched. External callers (flow_automation.py, batch_tasks.py) still use Celery. All 14 slice-level verification checks pass.**

## What Happened

Updated the three messaging-domain call sites that are in S02 scope:

1. **retry.py** — Changed imports from `app.tasks.messaging` to `app.tasks.messaging_taskiq`. Replaced `send_scheduled_message.delay(str(message.id))` with `await send_scheduled_message_taskiq.kiq(str(message.id))`. Replaced `retry_failed_messages.delay()` with `await retry_failed_messages_taskiq.kiq()`. Updated `task_result.id` to `task_result.task_id` for Taskiq API.

2. **task_scheduler.py** — Added lazy imports for `send_scheduled_message` from `messaging_taskiq` and `schedule_task_at` from `taskiq_base`. Replaced `.apply_async(eta=delivery_time)` with `await schedule_task_at(send_scheduled_message, delivery_time, str(message.id))`. Updated result access to use `schedule_result.schedule_id`.

3. **retry_handler.py** — Same pattern as task_scheduler. Replaced `.apply_async(eta=retry_time)` with `await schedule_task_at(send_scheduled_message, retry_time, str(message.id))`. Updated metadata storage to use `schedule_result.schedule_id`.

Verified coexistence: `flow_automation.py` and `batch_tasks.py` still import `send_scheduled_message` from `app.tasks.messaging` (Celery) and use `.delay()` — these are S03 scope.

## Verification

All 14 slice-level verification checks pass:

```
V1:  messaging_taskiq.py AST parse — PASS
V2:  taskiq_broker.py AST parse — PASS
V3:  retry.py AST parse — PASS
V4:  task_scheduler.py AST parse — PASS
V5:  retry_handler.py AST parse — PASS
V6:  @broker.task count = 9 — PASS
V7:  schedule= count = 7 — PASS
V8:  No .delay in messaging_taskiq.py code — PASS
V9:  No run_async in messaging_taskiq.py code — PASS
V10: No sync session in main task flow — PASS (only in DLQ helpers)
V11: No Celery dispatch in retry.py — PASS
V12: No Celery dispatch in task_scheduler.py — PASS
V13: No Celery dispatch in retry_handler.py — PASS
V14: Celery tasks intact (9 @celery_app.task in messaging.py) — PASS
```

Coexistence checks:
- `flow_automation.py` still imports from `app.tasks.messaging` and uses `.delay()` — PASS
- `batch_tasks.py` still imports from `app.tasks.messaging` and uses `.delay()` — PASS

## Diagnostics

- **retry.py**: API response includes `task_id` from Taskiq for tracing retry operations. Check worker logs for `task_name=send_scheduled_message` + `event=task_start` matching the returned task_id.
- **task_scheduler.py**: Logs `schedule_result.schedule_id` with message ID and delivery time ISO. Check Dragonfly keys `taskiq:schedule:*` for pending scheduled deliveries.
- **retry_handler.py**: Stores `schedule_result.schedule_id` in `message.message_metadata.retry_task_id` and `retry_scheduled_at` timestamp. Query messages table for retry scheduling audit trail.
- **Coexistence verification**: `grep "from app.tasks.messaging import" backend-hormonia/app/tasks/flow_automation.py backend-hormonia/app/tasks/flows/batch_tasks.py` confirms external callers still use Celery module.

## Deviations

None — implementation follows the task plan exactly.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/api/v2/messages/retry.py` — Switched imports to messaging_taskiq, .delay() → await .kiq(), task_result.id → task_result.task_id
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py` — .apply_async(eta=) → await schedule_task_at(), result access updated
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py` — .apply_async(eta=) → await schedule_task_at(), metadata updated with schedule_id
