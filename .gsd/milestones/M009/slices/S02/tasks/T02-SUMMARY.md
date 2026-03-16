---
id: T02
parent: S02
milestone: M009
provides:
  - send_scheduled_message Taskiq task in messaging_taskiq.py (async-native, SmartRetryMiddleware retry)
  - _route_to_dlq helper for sync DLQ writes from async task exception paths
  - Proven pattern for all remaining 8 messaging task migrations (T03)
key_files:
  - backend-hormonia/app/tasks/messaging_taskiq.py
key_decisions:
  - DLQ writes use sync get_scoped_session() in _route_to_dlq helper (DLQService is sync-only; pragmatic isolation)
  - Short base delay=2 handles saga commit lag; SmartRetryMiddleware applies exponential backoff on top
  - Retry exhaustion check via context.message.labels.get('_retries', 0) >= 3 gates DLQ routing and FAILED status
patterns_established:
  - Celery run_async() bridge eliminated: async inner function becomes direct task body
  - @broker.task(retry_on_error=True, max_retries=3, delay=N) + raise exception = SmartRetryMiddleware handles retry
  - context.message.labels.get('_retries', 0) replaces self.request.retries for retry count access
  - Pure helpers imported from Celery module (no duplication): _build_idempotency_key, _compute_next_reminder_time, _schedule_next_reminder
  - Non-retriable validation failures: set FAILED status via async session, route to DLQ via sync _route_to_dlq helper
  - Exception handler: rollback, reload message, update metadata, set PENDING or FAILED based on retry count, re-raise
observability_surfaces:
  - log_task_start("send_scheduled_message", message_id=) → structured log with task_name, event=task_start
  - log_task_success → event=task_success, duration_ms
  - log_task_error → event=task_error, error_type, duration_ms
  - SmartRetryMiddleware logs "Retrying N/M in X.XX seconds" on retry
  - Message DB fields: status=FAILED, failure_reason, retry_count, last_retry_at, message_metadata.last_retry_error
  - DLQ entries with error_message, error_type, payload including flow_context
duration: 12m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T02: Create messaging_taskiq.py with send_scheduled_message task

**Created async-native send_scheduled_message Taskiq task — eliminates run_async() bridge, uses SmartRetryMiddleware for retry, and proves the migration pattern for all 8 remaining messaging tasks.**

## What Happened

Created `backend-hormonia/app/tasks/messaging_taskiq.py` with the full `send_scheduled_message` task translated from the Celery version. The core translation flattened the inner `_send_message_async()` into the task body directly — no `run_async()` bridge needed since Taskiq tasks are natively async.

Key translation decisions:
1. **Atomic claim** → same UPDATE...WHERE...IN pattern, using async `db.execute(update(...))`
2. **Retry for "not found"** → raise `RuntimeError`, SmartRetryMiddleware handles retry. Retry exhaustion checked via `context.message.labels.get('_retries', 0) >= 3` — returns failure dict instead of raising when exhausted.
3. **Validation failures (patient not found, deleted, no phone)** → set status via async session, then call `_route_to_dlq()` helper for sync DLQ write.
4. **Exception handler** → rollback + reload message, update metadata (retry_count, last_retry_at, last_retry_error), set PENDING or FAILED based on retry count, re-raise for SmartRetryMiddleware.
5. **DLQ routing** → extracted to `_route_to_dlq()` helper using sync `get_scoped_session()` because `DLQService` is sync-only. This is isolated to the helper — main task flow is fully async.

Pure helper functions (`_build_idempotency_key`, `_compute_next_reminder_time`, `_schedule_next_reminder`) are imported from `messaging.py` — no duplication.

## Verification

```
✅ python3 -c "import ast; ast.parse(...)" — messaging_taskiq.py parses clean
✅ grep -c "@broker.task" → 1 (send_scheduled_message)
✅ grep "run_async(" (code only) → nothing (only in docstring comments)
✅ grep "get_scoped_session" → only in _route_to_dlq helper (DLQ exception path, not main flow)
✅ grep "_retries" → context.message.labels.get('_retries', 0) used for retry count
✅ grep "from app.tasks.messaging import" → pure helpers imported, not duplicated
✅ grep "from celery|celery_app" → nothing (no Celery dependency)
✅ Celery messaging.py untouched: grep -c "def send_scheduled_message" → still 1
✅ Celery tasks intact: grep -c "@celery_app.task" → still 9
```

Slice-level checks (partial — T02 is intermediate):
- ✅ messaging_taskiq.py AST parse
- ✅ taskiq_broker.py AST parse
- ✅ @broker.task count = 1 (will be 9 after T03)
- ✅ No .delay in new module
- ✅ No run_async in new module
- ✅ Celery @celery_app.task count = 9 (untouched)
- ⏳ @broker.task count = 9 (T03)
- ⏳ schedule= count = 7 (T03)
- ⏳ Call site migration (T04)

## Diagnostics

- Search worker logs for `task_name=send_scheduled_message` + `event=task_start|task_success|task_error`
- Check `message.message_metadata.last_retry_error` in DB for retry failure details
- DLQ entries include `error_message`, `error_type`, `payload.flow_context` for tracing
- SmartRetryMiddleware logs retry attempts with "Retrying N/M in X.XX seconds"

## Deviations

None — implementation follows the task plan exactly.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/tasks/messaging_taskiq.py` — NEW: send_scheduled_message Taskiq task + _route_to_dlq helper (~310 lines)
