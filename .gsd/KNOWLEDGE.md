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
