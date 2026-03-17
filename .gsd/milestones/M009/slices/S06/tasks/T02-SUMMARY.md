---
id: T02
parent: S06
milestone: M009
provides:
  - 6 test files rewritten with Taskiq imports (alerts, audit, reports, webhook_dlq, follow_up, flow_automation)
  - 1 test file updated with quiz_flow_taskiq imports (cleanup_expired_quiz_sessions)
  - 1 dead test file deleted (test_reencrypt_patients.py — batch_reencrypt_patients never migrated to Taskiq)
  - Pre-existing syntax bug fixed in flows_taskiq.py (stray `ise` at EOF)
  - 33 tests collected, 0 errors across all 7 remaining files
key_files:
  - backend-hormonia/tests/tasks/test_alerts_tasks.py (rewritten — async, alerts_taskiq)
  - backend-hormonia/tests/tasks/test_audit_cleanup_tasks.py (rewritten — async, audit_taskiq)
  - backend-hormonia/tests/tasks/test_reports_tasks.py (rewritten — async, reports_taskiq + helpers)
  - backend-hormonia/tests/tasks/test_webhook_dlq_tasks.py (rewritten — async, webhook_dlq_taskiq)
  - backend-hormonia/tests/tasks/test_follow_up_tasks.py (rewritten — async, follow_up_taskiq)
  - backend-hormonia/tests/tasks/test_flow_automation_retry_config.py (rewritten — flows_taskiq)
  - backend-hormonia/tests/test_cleanup_expired_quiz_sessions_task.py (updated — quiz_flow_taskiq)
  - backend-hormonia/app/tasks/flows_taskiq.py (bugfix — removed stray `ise` at line 1781)
key_decisions:
  - Deleted test_reencrypt_patients.py — batch_reencrypt_patients was never migrated to Taskiq (only persist_lgpd_audit_log and cleanup_expired_lgpd_audit_logs exist in lgpd_taskiq.py)
  - Removed .retry() mock tests entirely — Taskiq uses SmartRetryMiddleware; tasks just raise exceptions
  - Converted .apply_async mocks to .kiq mocks for Taskiq dispatch pattern
  - Made all test functions async — Taskiq tasks are async def; pyproject.toml has asyncio_mode=auto
patterns_established:
  - Taskiq test pattern: async test functions, await task directly, patch `app.tasks.X_taskiq.dep` targets, mock .kiq for cross-dispatch
  - Retry test pattern: verify exception propagation instead of .retry() mock (SmartRetryMiddleware handles retries)
observability_surfaces:
  - "`pytest --collect-only` on these 7 files → 33 collected, 0 errors"
  - "AST scan on 7 files → zero imports from deleted modules"
duration: 25m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T02: Fix domain task test imports (alerts, audit, reports, webhook, follow-up, LGPD, quiz)

**Rewrote 6 test files and updated 1 to use Taskiq imports; deleted 1 dead test file (batch_reencrypt_patients never migrated); fixed stray syntax bug in flows_taskiq.py. 33 tests collect with 0 errors.**

## What Happened

Converted all 8 test files from the plan from Celery imports to Taskiq equivalents:

1. **test_alerts_tasks.py** — `app.tasks.alerts` → `app.tasks.alerts_taskiq`; `.run()` → `await fn()`; removed `.retry()` mock tests (Taskiq uses SmartRetryMiddleware)
2. **test_audit_cleanup_tasks.py** — `app.tasks.audit_cleanup` → `app.tasks.audit_taskiq`; function renames: `cleanup_expired_audit_logs` → `cleanup_expired_logs`, `generate_daily_audit_report` → `generate_daily_report`
3. **test_reports_tasks.py** — `_get_system_actor_uuid` → `app.tasks.helpers.reports_helpers`; task fns → `app.tasks.reports_taskiq`; `.apply_async` mock → `.kiq` mock
4. **test_webhook_dlq_tasks.py** — `app.tasks.webhook_dlq` → `app.tasks.webhook_dlq_taskiq`; removed `.retry()` mock test; `run_async` bridge calls removed (tasks are natively async)
5. **test_follow_up_tasks.py** — `app.tasks.follow_up` → `app.tasks.follow_up_taskiq`; `_execute_follow_up_action` → `_execute_follow_up_action_async`; `get_db_session` → `get_scoped_session`
6. **test_flow_automation_retry_config.py** — `app.tasks.flow_automation` → `app.tasks.flows_taskiq`; removed Celery-specific attribute tests (max_retries, retry_backoff, autoretry_for, time_limit) that don't exist on Taskiq tasks
7. **test_cleanup_expired_quiz_sessions_task.py** — `app.tasks.quiz_flow.cleanup_tasks` → `app.tasks.quiz_flow_taskiq`; `cleanup_expired_quiz_sessions_task` → `cleanup_expired_quiz_sessions`; made test methods async
8. **test_reencrypt_patients.py** — DELETED. `batch_reencrypt_patients` was never migrated to Taskiq (`lgpd_taskiq.py` only has `persist_lgpd_audit_log` and `cleanup_expired_lgpd_audit_logs`). The original `app.tasks.lgpd.reencrypt_patients` module was deleted. This is dead test code.

Also fixed pre-existing bug: `flows_taskiq.py:1781` had a stray `ise` (truncated `raise`) causing `NameError` on import of any module that transitively imports `app.tasks`.

## Verification

- **Syntax check**: All 7 files pass `ast.parse()` — PASS
- **Collection**: `pytest --collect-only` → 33 tests collected, 0 errors — PASS
- **AST zero-import scan**: Zero imports from deleted modules in all 7 files — PASS

### Slice-level checks (partial — T02 is task 2 of 5):
- Collection of these 7 files: PASS (33 collected, 0 errors)
- AST scan on these 7 files: PASS
- Full workspace collection: NOT YET (remaining files in T03–T05 still import deleted modules)
- Full pytest run: NOT YET

## Diagnostics

- `DATABASE_URL="..." QUIZ_TOKEN_SECRET="..." pytest tests/tasks/test_alerts_tasks.py tests/tasks/test_audit_cleanup_tasks.py tests/tasks/test_reports_tasks.py tests/tasks/test_webhook_dlq_tasks.py tests/tasks/test_follow_up_tasks.py tests/tasks/test_flow_automation_retry_config.py tests/test_cleanup_expired_quiz_sessions_task.py --collect-only` → should show 33 collected, 0 errors
- `QUIZ_TOKEN_SECRET` env var required for follow_up import chain (MonthlyQuizConfig pydantic validation)

## Deviations

- **Deleted test_reencrypt_patients.py instead of fixing** — Plan said to remap imports to `lgpd_taskiq`, but `batch_reencrypt_patients` was never migrated. No Taskiq equivalent exists. File tests dead code.
- **Fixed flows_taskiq.py:1781 stray `ise`** — Pre-existing syntax bug blocked import of any module importing from `app.tasks`. Not in plan but required for any tests to collect.
- **Removed Celery-specific attribute tests in flow_automation_retry_config** — `max_retries`, `retry_backoff`, `autoretry_for`, `time_limit`, `soft_time_limit` are Celery task attributes that don't exist on Taskiq tasks. Replaced with callable check and async propagation test.

## Known Issues

- `QUIZ_TOKEN_SECRET` env var must be set for follow_up test collection (indirect import chain through app factory). This is a pre-existing project configuration requirement, not introduced by this task.

## Files Created/Modified

- `backend-hormonia/tests/tasks/test_alerts_tasks.py` — rewritten (Celery → Taskiq async)
- `backend-hormonia/tests/tasks/test_audit_cleanup_tasks.py` — rewritten (Celery → Taskiq async)
- `backend-hormonia/tests/tasks/test_reports_tasks.py` — rewritten (Celery → Taskiq async, helpers split)
- `backend-hormonia/tests/tasks/test_webhook_dlq_tasks.py` — rewritten (Celery → Taskiq async)
- `backend-hormonia/tests/tasks/test_follow_up_tasks.py` — rewritten (Celery → Taskiq async)
- `backend-hormonia/tests/tasks/test_flow_automation_retry_config.py` — rewritten (Celery attrs → Taskiq pattern)
- `backend-hormonia/tests/test_cleanup_expired_quiz_sessions_task.py` — updated (imports + async)
- `backend-hormonia/tests/tasks/test_reencrypt_patients.py` — deleted (dead code, no Taskiq equivalent)
- `backend-hormonia/app/tasks/flows_taskiq.py` — bugfix (removed stray `ise` at EOF)
