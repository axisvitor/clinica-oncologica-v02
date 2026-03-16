---
estimated_steps: 5
estimated_files: 5
---

# T04: Update messaging-domain call sites and verify coexistence

**Slice:** S02 — Messaging tasks migradas
**Milestone:** M009

## Description

The Taskiq messaging tasks exist in `messaging_taskiq.py` but nothing calls them yet from the messaging domain. This task wires the three external call sites in S02 scope to dispatch via Taskiq instead of Celery: `api/v2/messages/retry.py` (uses `.delay()`), `task_scheduler.py` (uses `.apply_async(eta=)`), and `retry_handler.py` (uses `.apply_async(eta=)`). Also verifies that Celery tasks in `messaging.py` remain untouched and that external callers in `flow_automation.py` and `batch_tasks.py` still work with Celery dispatch.

## Steps

1. **Update `backend-hormonia/app/api/v2/messages/retry.py`**:
   - Change import from: `from app.tasks.messaging import send_scheduled_message, retry_failed_messages as retry_failed_messages_task`
   - To: `from app.tasks.messaging_taskiq import send_scheduled_message as send_scheduled_message_taskiq, retry_failed_messages as retry_failed_messages_taskiq`
   - In `retry_message()` endpoint: Replace `send_scheduled_message.delay(str(message.id))` with `await send_scheduled_message_taskiq.kiq(str(message.id))`. The endpoint is already `async def` so `await` works directly.
   - In `retry_failed_messages()` endpoint: Replace `task_result = retry_failed_messages_task.delay(limit=limit, max_retries=3)` with `task_result = await retry_failed_messages_taskiq.kiq(limit=limit, max_retries=3)`. Replace `task_result.id` with `task_result.task_id` (Taskiq's `AsyncTaskiqTask` uses `.task_id` not `.id`).
   - Keep the `list_failed_messages` endpoint unchanged — it doesn't dispatch tasks.

2. **Update `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py`**:
   - Change import from: `from app.tasks.messaging import send_scheduled_message`
   - To: `from app.tasks.messaging_taskiq import send_scheduled_message` and `from app.tasks.taskiq_base import schedule_task_at`
   - In `schedule_celery_task()` method:
     - Replace `task_result = send_scheduled_message.apply_async(args=[str(message.id)], eta=delivery_time)` with `schedule_result = await schedule_task_at(send_scheduled_message, delivery_time, str(message.id))`
     - Replace `task_result.id` with `schedule_result.schedule_id` (or adapt the return dict accordingly)
     - The distributed lock (`async_message_delivery_lock`) stays — it's independent of the task framework
   - Optionally rename the method from `schedule_celery_task` to `schedule_task` for accuracy (but callers in S02 scope may reference the old name — check first)
   - The `cancel_celery_task` method stays as-is (uses `celery_app.control.revoke`) — cancellation of Taskiq schedules is out of scope for S02

3. **Update `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py`**:
   - Change import from: `from app.tasks.messaging import send_scheduled_message`
   - To: `from app.tasks.messaging_taskiq import send_scheduled_message` and `from app.tasks.taskiq_base import schedule_task_at`
   - In `schedule_retry()` method:
     - Replace `task_result = send_scheduled_message.apply_async(args=[str(message.id)], eta=retry_time)` with `schedule_result = await schedule_task_at(send_scheduled_message, retry_time, str(message.id))`
     - Replace `task_result.id` in metadata with `schedule_result.schedule_id` (or string repr)
   - The `route_to_dlq_on_max_retries` method stays as-is — it uses `DLQHandler` directly, not Celery dispatch
   - `notify_flow_engine_failure` stays as-is — pure DB operations

4. **Verify Celery tasks untouched and external callers still work**:
   - `grep -c "@celery_app.task" backend-hormonia/app/tasks/messaging.py` still returns `9`
   - `grep "send_scheduled_message.delay" backend-hormonia/app/tasks/flow_automation.py` still finds the Celery call
   - `grep "send_scheduled_message.delay" backend-hormonia/app/tasks/flows/batch_tasks.py` still finds the Celery call
   - `grep "from app.tasks.messaging import" backend-hormonia/app/tasks/flow_automation.py` confirms external callers still import from Celery module

5. **AST parse all modified files**:
   - `python3 -c "import ast; ast.parse(open('backend-hormonia/app/api/v2/messages/retry.py').read())"`
   - `python3 -c "import ast; ast.parse(open('backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py').read())"`
   - `python3 -c "import ast; ast.parse(open('backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py').read())"`
   - Verify no `.delay()` or `.apply_async()` in the three modified files:
   - `grep "\.delay\|\.apply_async" backend-hormonia/app/api/v2/messages/retry.py backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py` returns nothing

## Must-Haves

- [ ] `retry.py` imports from `messaging_taskiq` and dispatches via `.kiq()`
- [ ] `task_scheduler.py` imports from `messaging_taskiq` and uses `schedule_task_at()` for delayed dispatch
- [ ] `retry_handler.py` imports from `messaging_taskiq` and uses `schedule_task_at()` for retry scheduling
- [ ] No `.delay()` or `.apply_async()` in any of the three modified files
- [ ] `task_result.id` in retry.py adjusted to `task_result.task_id` (Taskiq's attribute name)
- [ ] Celery `messaging.py` untouched (9 `@celery_app.task` decorators)
- [ ] `flow_automation.py` and `batch_tasks.py` still import from `app.tasks.messaging` (Celery) — NOT broken
- [ ] All 3 modified files pass `ast.parse()` check

## Verification

- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/api/v2/messages/retry.py').read())"` passes
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py').read())"` passes
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py').read())"` passes
- `grep "\.delay\|\.apply_async" backend-hormonia/app/api/v2/messages/retry.py backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py` returns nothing
- `grep -c "@celery_app.task" backend-hormonia/app/tasks/messaging.py` returns `9`
- `grep "send_scheduled_message.delay" backend-hormonia/app/tasks/flow_automation.py` finds at least 1 Celery call (coexistence proof)

## Inputs

- `backend-hormonia/app/tasks/messaging_taskiq.py` — T02+T03 output: all 9 Taskiq tasks defined
- `backend-hormonia/app/tasks/taskiq_base.py` — T01 output: `schedule_task_at()` helper
- `backend-hormonia/app/api/v2/messages/retry.py` — Current: imports from `app.tasks.messaging`, uses `.delay()`. Has 3 endpoints: `retry_message`, `retry_failed_messages`, `list_failed_messages`. The first two dispatch tasks.
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py` — Current: imports `send_scheduled_message` from `app.tasks.messaging`, uses `.apply_async(args=[...], eta=delivery_time)`. Single method `schedule_celery_task()`.
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py` — Current: imports `send_scheduled_message` from `app.tasks.messaging`, uses `.apply_async(args=[...], eta=retry_time)`. Method `schedule_retry()`.
- Taskiq's `.kiq()` returns `AsyncTaskiqTask` with `.task_id` attribute (not `.id` like Celery).
- `schedule_task_at()` returns whatever `schedule_by_time()` returns — a `CreatedSchedule` with `.schedule_id`.
- `flow_automation.py` (line 265) and `batch_tasks.py` (line 348) — these are S03 scope, must NOT be changed.

## Expected Output

- `backend-hormonia/app/api/v2/messages/retry.py` — Modified: imports from `messaging_taskiq`, uses `.kiq()` and `.task_id`
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py` — Modified: imports from `messaging_taskiq`, uses `schedule_task_at()`
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py` — Modified: imports from `messaging_taskiq`, uses `schedule_task_at()`

## Observability Impact

- **Changed signal:** `retry.py` endpoints now return `task_id` from Taskiq's `AsyncTaskiqTask.task_id` (UUID format) instead of Celery's `AsyncResult.id`. Consumers of the `/retry-failed` response must use this new ID format for task tracking.
- **Changed signal:** `task_scheduler.py` returns `schedule_result.schedule_id` (string) instead of Celery `task_result.id`. The `task_id` key in the return dict now holds a Taskiq schedule ID — downstream code that calls `get_task_status(task_id)` still works because the method delegates to `get_celery_task_status` (which will need updating in a future task for full Taskiq status tracking).
- **Changed signal:** `retry_handler.py` writes `schedule_result.schedule_id` to `message_metadata.retry_task_id`. This changes the format of the stored ID from Celery task UUID to Taskiq schedule UUID — visible when querying `message.message_metadata` in DB.
- **Inspection:** Search worker logs for `task_name=send_scheduled_message` + `event=task_start` to verify dispatched tasks are being picked up by Taskiq worker.
- **Failure visibility:** If `schedule_task_at()` fails in `task_scheduler.py` or `retry_handler.py`, the existing try/except blocks log the error and propagate. If `.kiq()` fails in `retry.py`, the HTTP 500 surfaces the issue.
- **Coexistence check:** `grep "from app.tasks.messaging import" backend-hormonia/app/tasks/flow_automation.py` confirms external Celery callers are not disrupted.
