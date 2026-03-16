---
estimated_steps: 5
estimated_files: 1
---

# T02: Create messaging_taskiq.py with send_scheduled_message task

**Slice:** S02 — Messaging tasks migradas
**Milestone:** M009

## Description

`send_scheduled_message` is the most complex messaging task (367 lines in the Celery version). It uses `run_async()` to bridge sync Celery to an inner `_send_message_async()`, manual `self.retry(countdown=)` for "message not found" race conditions, sync `get_db_session()` for DLQ routing in exception handlers, and `self.request.retries` for retry count access.

In Taskiq, the inner `_send_message_async()` becomes the task body directly (no bridge). Retry is handled by SmartRetryMiddleware labels. Retry count is read from `Context.message.labels.get('_retries', 0)`. DLQ routing uses the task's async session.

This task creates the new module and proves the hardest translation pattern. The remaining 8 tasks follow this pattern in T03.

## Steps

1. **Create `backend-hormonia/app/tasks/messaging_taskiq.py`** with module docstring, imports from `app.taskiq_broker` (broker) and `app.tasks.taskiq_base` (DbSession, log helpers, schedule_task_at).

2. **Import pure helper functions from `messaging.py`** — these have zero Celery dependency:
   - `from app.tasks.messaging import _build_idempotency_key, _parse_time_str, _add_months, _compute_next_reminder_time, _schedule_next_reminder`
   - Also import: `from app.models.message import Message, MessageStatus, MessageDirection, MessageType, DeliveryStatus`
   - And: `from app.services.unified_whatsapp_service import create_unified_whatsapp_service`
   - And: `from app.utils.timezone import now_sao_paulo`
   - And: `from sqlalchemy import select, update`; `from sqlalchemy.orm import selectinload`; `from sqlalchemy.ext.asyncio import AsyncSession`
   - And: `from taskiq import Context, TaskiqDepends`
   - And: `from uuid import UUID`

3. **Implement `send_scheduled_message` as a Taskiq task**:
   - Decorator: `@broker.task(retry_on_error=True, max_retries=3, delay=2)` — The short delay (2s) handles the "message not found" race condition (saga commit lag). SmartRetryMiddleware applies exponential backoff on top.
   - Signature: `async def send_scheduled_message(message_id: str, db: AsyncSession = DbSession, context: Context = TaskiqDepends()) -> dict[str, Any]:`
   - Task body: Flatten the inner `_send_message_async()` into the task body directly. This is the core translation:
     a. **Atomic claim**: `UPDATE Message SET status=SENDING WHERE id=X AND status IN (PENDING, SCHEDULED)` via async `db.execute(update(...))`
     b. **rowcount==0 check**: If message not found, return dict with `found=False` and let SmartRetryMiddleware handle retry (raise a lightweight exception like `RuntimeError("Message not found, will retry")`). Access retry count from `context.message.labels.get('_retries', 0)` — if retries exhausted (>= 3), log error and return failure dict instead of raising.
     c. **Load message + patient**: `select(Message).options(selectinload(Message.patient)).where(Message.id == message_uuid)`
     d. **Validation checks**: already_processed, patient not found, patient deleted, patient no phone — same logic as Celery version
     e. **Non-retriable failure DLQ routing**: Replace `with get_db_session() as dlq_db:` (sync) with using the task's `db` (AsyncSession). Use async select: `result = await db.execute(select(Message).where(Message.id == UUID(message_id)))` then DLQ add. The `DLQService` is sync — for the specific `add_to_dlq()` call, create a fresh sync session via `from app.database import get_db_session; with get_db_session() as sync_db:` ONLY for DLQ writes. This is the pragmatic approach from the research (risk mitigation).
     f. **Send via WhatsApp**: `whatsapp_service = create_unified_whatsapp_service(db)` → `await whatsapp_service.send_message(message)`. Same as the inner async function.
     g. **Success path**: Update status, schedule next reminder via `_schedule_next_reminder(message, db)`, commit.
     h. **Exception handler**: Instead of Celery's complex `self.request.retries`/`self.handle_retry`/`get_db_session()` pattern, simplify: update message metadata with error info via the async session, then `raise` the exception to let SmartRetryMiddleware handle retry/exhaustion. For max retries exhaustion DLQ routing, check `context.message.labels.get('_retries', 0) >= 3` — if at max, set message status to FAILED and route to DLQ before raising.
   - Use `log_task_start`, `log_task_success`, `log_task_error` from taskiq_base throughout

4. **Verify the module**:
   - `python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/messaging_taskiq.py').read())"`
   - `grep -c "@broker.task" backend-hormonia/app/tasks/messaging_taskiq.py` — returns `1`
   - `grep "run_async\|get_scoped_session" backend-hormonia/app/tasks/messaging_taskiq.py` — returns nothing

5. **Verify Celery task untouched**:
   - `grep -c "def send_scheduled_message" backend-hormonia/app/tasks/messaging.py` — still returns `1`

## Must-Haves

- [ ] `messaging_taskiq.py` exists with `send_scheduled_message` as `@broker.task` async function
- [ ] No `run_async()` bridge — task body is directly async
- [ ] No sync `get_scoped_session()` or `get_db_session()` for the main flow (DLQ exception handler may use sync session pragmatically)
- [ ] Retry count accessed via `Context.message.labels.get('_retries', 0)`, not `self.request.retries`
- [ ] SmartRetryMiddleware handles retry logic (task raises exception, middleware decides)
- [ ] DLQ routing for non-retriable failures uses async query for message load + sync DLQService for DLQ write (pragmatic)
- [ ] Pure helper functions imported from `messaging.py` (not duplicated)
- [ ] File passes `ast.parse()` check
- [ ] Original `messaging.py` completely untouched

## Observability Impact

- Signals added/changed: `log_task_start("send_scheduled_message", message_id=message_id)` produces structured log with `task_name`, `event=task_start`. `log_task_error` includes `error_type` and `duration_ms`. SmartRetryMiddleware logs retry attempts ("Retrying N/M in X.XX seconds").
- How a future agent inspects this: Search worker logs for `task_name=send_scheduled_message` + `event=task_start|task_success|task_error`. Check `message.message_metadata.last_retry_error` in DB.
- Failure state exposed: Message `status=FAILED`, `failure_reason` set, `retry_count` incremented, `last_retry_at` updated. DLQ entry created with `error_message`, `error_type`, and `payload` including `flow_context`.

## Inputs

- `backend-hormonia/app/taskiq_broker.py` — broker instance, SmartRetryMiddleware configured with 3 retries, 60s base, exponential backoff capped at 600s, jitter
- `backend-hormonia/app/tasks/taskiq_base.py` — `DbSession = TaskiqDepends(get_db_session)`, `log_task_start`, `log_task_success`, `log_task_error`
- `backend-hormonia/app/tasks/messaging.py` — Source of pure helpers and the reference implementation. Key functions: `_build_idempotency_key` (line 42), `_parse_time_str` (line 56), `_add_months` (line 70), `_compute_next_reminder_time` (line 74), `_schedule_next_reminder` (line 150). The `send_scheduled_message` Celery task starts at line 212.
- `Context` from `taskiq` — provides `context.message.labels` dict. SmartRetryMiddleware stores retry count in `context.message.labels['_retries']`.
- `app.services.unified_whatsapp_service.create_unified_whatsapp_service(db)` — async WhatsApp service, takes an AsyncSession-backed `db`.
- `app.domain.messaging.core.MessageService` — sync ORM-based service. Used in process/retry tasks, NOT in send_scheduled_message main flow.
- `app.services.dlq.service.DLQService` — sync only (uses sync `Session`). For DLQ writes in exception handlers.
- `app.models.failed_message.FailureReason` — enum for DLQ categorization.

## Expected Output

- `backend-hormonia/app/tasks/messaging_taskiq.py` — NEW file with `send_scheduled_message` Taskiq task. ~200-250 lines. Async, no bridge, SmartRetryMiddleware retry, structured logging.
