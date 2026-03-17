# Project Knowledge

Append-only register of project-specific rules, patterns, and lessons learned.
Agents read this before every unit. Add entries when you discover something worth remembering.

## Rules

| # | Scope | Rule | Why | Added |
|---|-------|------|-----|-------|
| 1 | backend | `app.tasks.__init__.py` imports the entire Celery chain → requires all env vars (DATABASE_URL etc). Never import `from app.tasks.xxx` in standalone/test scripts without the full env. Use `from app.tasks.taskiq_base import ...` directly or `importlib.util.spec_from_file_location` to bypass. | The Celery base module pulls `app.database` → `app.config.settings` which validates all required env vars at import time. | 2026-03-16 |
| 2 | backend | Taskiq broker module (`app.taskiq_broker`) reads Redis URL from env vars directly (not `app.config.settings`) to keep the import chain lightweight. Never add `from app.config import settings` to this module. | Worker processes and standalone tests need to import the broker without requiring the full settings validation chain. | 2026-03-16 |

## Patterns

| # | Pattern | Where | Notes |
|---|---------|-------|-------|
| 1 | `taskiq_fastapi.init(broker, "app.main:app")` must be called AFTER broker creation but BEFORE task definitions using TaskiqDepends | `app/taskiq_broker.py` | Order matters — move this if you reorganize broker module |
| 2 | DB session in Taskiq tasks: `db: AsyncSession = DbSession` where `DbSession = TaskiqDepends(get_db_session)` | `app/tasks/taskiq_base.py` | Replaces Celery's sync `get_scoped_session()` pattern |
| 3 | Health checks during Celery→Taskiq coexistence: try Taskiq first (Redis ping), then Celery (control.inspect), report both | `health/core.py`, `health/service_health.py` | Workers check passes if either is healthy |
| 4 | Celery `.delay()` → `await task.kiq()` for immediate dispatch; `.apply_async(eta=)` → `await schedule_task_at(task, datetime, *args)` for delayed dispatch | `app/tasks/messaging_taskiq.py`, call sites | Core translation pattern for all task migrations |
| 5 | Retry count in Taskiq: `context.message.labels.get('_retries', 0)` replaces Celery `self.request.retries` | `app/tasks/messaging_taskiq.py` | SmartRetryMiddleware stores retry count in message labels |
| 6 | Import coexistence: `from app.tasks.messaging_taskiq import X` for Taskiq, `from app.tasks.messaging import X` for Celery — same task names, different modules | `app/tasks/messaging_taskiq.py`, `app/tasks/messaging.py` | Wrong import = task dispatched to wrong queue. Active during S02-S04 coexistence. |

## Lessons Learned

| # | What Happened | Root Cause | Fix | Scope |
|---|--------------|------------|-----|-------|
| 1 | `from app.tasks.smoke_test import ...` fails without DATABASE_URL in env | `app/tasks/__init__.py` has `from .base import ...` which triggers full settings chain | Import taskiq task modules directly, not through the `app.tasks` package init | backend/M009 |
| 2 | DLQHandler declares `async def` methods (get_pending_review, requeue_for_retry) but uses sync ORM internally (self.db.query(), self.db.commit()) | Original Celery code used `run_async()` bridge, masking that the handler is sync-internally | Always provide sync session (get_scoped_session()) to DLQHandler; `await` works but no async I/O benefit. Don't pass AsyncSession. | backend/M009 |
| 3 | `batch_reencrypt_patients` not found in `lgpd_taskiq.py` during test migration | Function was never migrated from Celery to Taskiq — `lgpd_taskiq.py` only has `persist_lgpd_audit_log` and `cleanup_expired_lgpd_audit_logs` | Delete `test_reencrypt_patients.py` as dead test code. If reencryption is needed later, implement fresh in lgpd_taskiq. | backend/M009/S06 |
| 4 | `QUIZ_TOKEN_SECRET` env var required for `follow_up_taskiq` test collection | Import chain: `follow_up_taskiq` → `app.tasks.__init__` → app factory → `MonthlyQuizConfig` pydantic model validates `QUIZ_TOKEN_SECRET` | Set `QUIZ_TOKEN_SECRET="..."` alongside `DATABASE_URL` when running task tests | backend/M009 |
| 6 | `create_optimized_engine` passed sync `QueuePool` to `create_async_engine` → `ArgumentError: Pool class QueuePool cannot be used with asyncio engine` | `database_optimization.py` hardcoded `QueuePool` without checking if the URL is asyncpg | Auto-swap to `AsyncAdaptedQueuePool` when URL starts with `postgresql+asyncpg://`; register event listeners on `engine.sync_engine` for async engines | backend/M009/S06 |
| 7 | Taskiq task tests patching `app.tasks.flows_taskiq.get_scoped_session` had no effect — function still used real `get_scoped_session` | `process_daily_flows` does lazy `from app.database import get_scoped_session` inside function body — the name never exists in `flows_taskiq` module namespace | Patch at source module: `app.database.get_scoped_session`, not `app.tasks.flows_taskiq.get_scoped_session` | backend/M009/S06 |
| 8 | RetryHandler `schedule_retry` lazy-imports `schedule_task_at` from `app.tasks.taskiq_base` inside function body — monkeypatch on `retry_handler.schedule_task_at` fails with AttributeError | Lazy imports inside function body are not module-level attributes — they resolve at call time from the source module | Patch at `app.tasks.taskiq_base.schedule_task_at` (the defining module), not at the consuming module path | backend/M009/S06 |
