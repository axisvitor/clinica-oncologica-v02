---
estimated_steps: 5
estimated_files: 1
---

# T03: Migrate remaining 8 messaging tasks with schedule labels

**Slice:** S02 — Messaging tasks migradas
**Milestone:** M009

## Description

With `send_scheduled_message` proven in T02, this task adds the remaining 8 Celery messaging tasks to `messaging_taskiq.py`. Most are LOW complexity — straightforward session replacement and async conversion. `send_bulk_messages` uses `schedule_by_time()` for ETA dispatch. `process_whatsapp_dlq` drops the `run_async()` bridge for DLQHandler async calls. All 7 beat schedule entries get Taskiq label decorators.

Internal cross-calls (e.g., `process_scheduled_messages` calling `send_scheduled_message.delay()`) switch to `await send_scheduled_message.kiq()`.

## Steps

1. **Add `process_scheduled_messages`** (LOW complexity):
   - Decorator: `@broker.task(schedule=[{"interval": {"seconds": 60}, "kwargs": {"limit": 60}}])`
   - Replace `get_db_session()` with `db: AsyncSession = DbSession`
   - `MessageService(db)` works with sync session — since this task does `get_scheduled_messages()` (sync ORM), we need to decide: either (a) use sync session via `from app.database import get_db_session` for this specific task, or (b) convert the query to async. **Pragmatic approach**: Use the approach from the Celery version — `MessageService` uses sync ORM, so create a sync session wrapper. BUT since `process_scheduled_messages` only calls `message_service.get_scheduled_messages()` then dispatches `.kiq()`, the simplest path: use async raw query `select(Message).where(Message.status == MessageStatus.PENDING, Message.scheduled_for <= now)` instead of `MessageService`. This avoids sync session entirely.
   - Replace `send_scheduled_message.delay(str(message.id))` → `await send_scheduled_message.kiq(str(message.id))`
   - Use `log_task_start/success/error` from taskiq_base

2. **Add `retry_failed_messages`** (LOW complexity):
   - Decorator: `@broker.task(schedule=[{"interval": {"seconds": 300}, "kwargs": {"limit": 50, "max_retries": 3}}])`
   - Replace `get_db_session()` with `db: AsyncSession = DbSession`
   - Convert `db.query(Message).filter(...)` to `await db.execute(select(Message).where(...))`
   - Replace `db.commit()` with `await db.commit()`
   - Replace `.delay()` calls with `await send_scheduled_message.kiq()`

3. **Add remaining 6 tasks**:

   a. **`send_bulk_messages`** (MEDIUM):
      - No schedule label (not periodic — triggered on demand)
      - Replace `get_scoped_session()` with `db: AsyncSession = DbSession`
      - Replace `.apply_async(args=[str(message.id)], eta=eta)` with `await schedule_task_at(send_scheduled_message, eta, str(message.id))` using the helper from T01
      - Note: `schedule_task_at` returns a `CreatedSchedule`, not `AsyncTaskiqTask`. The `scheduled_tasks` list should use `schedule_result.schedule_id` instead of `task.id`.
      - Convert sync `MessageService` calls to async queries

   b. **`cleanup_old_messages`** (LOW):
      - Decorator: `@broker.task(schedule=[{"interval": {"seconds": 86400}, "kwargs": {"days_old": 90}}])`
      - Replace `get_scoped_session()` with `db: AsyncSession = DbSession`
      - Convert all sync `db.query()` to async `await db.execute(select(...))`
      - Convert `db.add()`, `db.delete()`, `db.commit()` to async equivalents

   c. **`generate_message_analytics`** (LOW):
      - Decorator: `@broker.task(schedule=[{"interval": {"seconds": 3600}, "kwargs": {"days_back": 7}}])`
      - Replace `get_scoped_session()` with `db: AsyncSession = DbSession`
      - Convert raw sync SQLAlchemy queries (`db.query(Message).filter(...)`) to async `select()` statements
      - `MessageService.get_message_statistics()` is sync — replicate the query logic with async selects

   d. **`process_whatsapp_dlq`** (MEDIUM):
      - Decorator: `@broker.task(schedule=[{"interval": {"seconds": 600}, "kwargs": {"limit": 50}}])`
      - Replace `get_scoped_session()` with `db: AsyncSession = DbSession`
      - Replace `run_async(dlq_handler.get_pending_review(limit=limit))` with `await dlq_handler.get_pending_review(limit=limit)` — DLQHandler methods are already async
      - Replace `run_async(dlq_handler.requeue_for_retry(...))` with `await dlq_handler.requeue_for_retry(...)`
      - **Critical**: `DLQHandler(db)` is initialized with whatever session type is passed. Verify it works with AsyncSession — its methods use `await self.db.execute()` patterns, so AsyncSession should work. If not, note it as a limitation.

   e. **`process_dlq_messages`** (LOW):
      - Decorator: `@broker.task(schedule=[{"cron": "*/5 * * * *", "kwargs": {"limit": 100}}])`
      - `DLQService` is sync-only (uses sync `Session`). **Pragmatic approach**: Create a sync session for this task: `from app.database import get_db_session; with get_db_session() as sync_db:` then `DLQService(sync_db).process_scheduled_retries()`. This matches the research recommendation. Do NOT inject `DbSession` — this task specifically needs sync.
      - Add a comment: `# DLQService is sync-only — uses dedicated sync session. Async conversion deferred.`

   f. **`retry_pending_welcome_messages`** (LOW):
      - Decorator: `@broker.task(schedule=[{"interval": {"seconds": 600}, "kwargs": {"limit": 50, "min_age_minutes": 5, "max_age_hours": 24}}])`
      - Replace `get_db_session()` with `db: AsyncSession = DbSession`
      - Convert sync queries to async
      - Replace `send_scheduled_message.delay()` with `await send_scheduled_message.kiq()`

4. **Verify task count and patterns**:
   - `grep -c "@broker.task" backend-hormonia/app/tasks/messaging_taskiq.py` returns `9`
   - `grep -c "schedule=" backend-hormonia/app/tasks/messaging_taskiq.py` returns `7`
   - `grep "\.delay\b" backend-hormonia/app/tasks/messaging_taskiq.py` returns nothing
   - `grep "run_async" backend-hormonia/app/tasks/messaging_taskiq.py` returns nothing
   - `grep "get_scoped_session" backend-hormonia/app/tasks/messaging_taskiq.py` returns nothing

5. **AST parse check**:
   - `python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/messaging_taskiq.py').read())"`

## Must-Haves

- [ ] All 9 Taskiq messaging tasks defined in `messaging_taskiq.py` (1 from T02 + 8 new)
- [ ] 7 schedule labels present (process_scheduled_messages, retry_failed_messages, retry_pending_welcome_messages, cleanup_old_messages, generate_message_analytics, process_whatsapp_dlq, process_dlq_messages)
- [ ] No `.delay()` calls — all cross-task dispatch uses `await .kiq()`
- [ ] No `run_async()` bridge in any task
- [ ] No `get_scoped_session()` calls
- [ ] `send_bulk_messages` uses `schedule_task_at()` for ETA dispatch
- [ ] `process_whatsapp_dlq` uses direct `await` for DLQHandler async methods
- [ ] `process_dlq_messages` uses sync session pragmatically (DLQService is sync-only)
- [ ] File passes `ast.parse()` check

## Verification

- `grep -c "@broker.task" backend-hormonia/app/tasks/messaging_taskiq.py` returns `9`
- `grep -c "schedule=" backend-hormonia/app/tasks/messaging_taskiq.py` returns `7`
- `grep "\.delay\b\|run_async\|get_scoped_session" backend-hormonia/app/tasks/messaging_taskiq.py` returns nothing
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/messaging_taskiq.py').read())"` passes

## Inputs

- `backend-hormonia/app/tasks/messaging_taskiq.py` — T02 output: module with `send_scheduled_message` Taskiq task already defined, imports established
- `backend-hormonia/app/tasks/messaging.py` — Reference implementation for all 9 Celery tasks. Key functions starting at: `process_scheduled_messages` (line 585), `retry_failed_messages` (line 635), `send_bulk_messages` (line 718), `cleanup_old_messages` (line 807), `generate_message_analytics` (line 907), `process_whatsapp_dlq` (line 1010), `process_dlq_messages` (line 1098), `retry_pending_welcome_messages` (line 1124)
- `backend-hormonia/app/tasks/taskiq_base.py` — `DbSession`, `log_task_start/success/error`, `schedule_task_at` (from T01)
- `app.domain.messaging.core.MessageService` — sync service used in process/retry tasks. Methods: `get_scheduled_messages()`, `get_messages_with_filters()`, `get_message_statistics()`.
- `app.integrations.whatsapp.queue.dlq.DLQHandler` — async class: `get_pending_review()`, `requeue_for_retry()` are async methods.
- `app.services.dlq.service.DLQService` — sync class: `process_scheduled_retries()` is sync, uses sync Session.
- `app.models.message_archive.MessageArchive` — used in `cleanup_old_messages` for archiving.
- Beat schedule mapping (Celery → Taskiq labels):
  - `process-scheduled-messages`: 60s interval → `schedule=[{"interval": {"seconds": 60}, "kwargs": {"limit": 60}}]`
  - `retry-failed-messages`: 300s interval → `schedule=[{"interval": {"seconds": 300}, "kwargs": {"limit": 50, "max_retries": 3}}]`
  - `retry-pending-welcome-messages`: 600s interval → `schedule=[{"interval": {"seconds": 600}, "kwargs": {"limit": 50, "min_age_minutes": 5, "max_age_hours": 24}}]`
  - `cleanup-old-messages`: 86400s interval → `schedule=[{"interval": {"seconds": 86400}, "kwargs": {"days_old": 90}}]`
  - `generate-message-analytics`: 3600s interval → `schedule=[{"interval": {"seconds": 3600}, "kwargs": {"days_back": 7}}]`
  - `process-whatsapp-dlq`: 600s interval → `schedule=[{"interval": {"seconds": 600}, "kwargs": {"limit": 50}}]`
  - `process-dlq-scheduled-retries`: crontab(*/5) → `schedule=[{"cron": "*/5 * * * *", "kwargs": {"limit": 100}}]`

## Expected Output

- `backend-hormonia/app/tasks/messaging_taskiq.py` — Updated with all 9 Taskiq tasks, 7 schedule labels, ~600-800 lines total

## Observability Impact

- **New structured log events**: Each of the 8 new tasks emits `log_task_start` / `log_task_success` / `log_task_error` with `task_name`, `event`, `duration_ms`, and task-specific context keys (e.g. `processed_count`, `retry_count`, `archived_count`).
- **Schedule visibility**: 7 schedule labels appear in LabelScheduleSource — visible via `GET /api/v2/health/ready` → `checks.taskiq_broker.scheduler_sources`.
- **Worker log search**: Filter by `task_name=process_scheduled_messages|retry_failed_messages|…` + `event=task_start|task_success|task_error`.
- **SmartRetryMiddleware**: Logs "Retrying N/M in X.XX seconds" for any task with `retry_on_error=True`.
- **DLQ routing**: `_route_to_dlq` entries include `error_message`, `error_type`, `payload.flow_context` for tracing failed messages.
- **Failure state**: `process_whatsapp_dlq` logs per-message processing outcome (auto-requeued vs manual review). `process_dlq_messages` returns `processed` count.
- **No new metrics endpoints** — observability is log-based. Future M010 may add Prometheus counters.
