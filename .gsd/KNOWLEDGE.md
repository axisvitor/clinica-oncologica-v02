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

## Lessons Learned

| # | What Happened | Root Cause | Fix | Scope |
|---|--------------|------------|-----|-------|
| 1 | `from app.tasks.smoke_test import ...` fails without DATABASE_URL in env | `app/tasks/__init__.py` has `from .base import ...` which triggers full settings chain | Import taskiq task modules directly, not through the `app.tasks` package init | backend/M009 |
