---
estimated_steps: 8
estimated_files: 5
---

# T01: Migrate simple sync-ORM modules (audit, lgpd, reports, saga_monitoring) + LGPD middleware call site

**Slice:** S04 — Quiz/alert/follow-up/monitoring migradas + schedule completo
**Milestone:** M009

## Description

Create 4 Taskiq parallel modules for the simplest Celery task groups: audit cleanup (4 tasks), LGPD (2 tasks), reports (2 tasks), and saga monitoring (3 tasks). These all use sync ORM via `get_scoped_session()` — the mechanical translation is straightforward. Also migrate the LGPD middleware call site from `.delay()` to `await .kiq()`.

All 4 modules follow the exact S02/S03 coexistence pattern (D007): create `*_taskiq.py` alongside existing Celery modules, import pure helpers from Celery modules to avoid duplication, and never import from `app.tasks` package init (KNOWLEDGE Rule 1).

## Steps

1. **Create `audit_taskiq.py`** (4 tasks, 4 periodic):
   - Import from `app.taskiq_broker import broker` and `app.tasks.taskiq_base import DbSession, log_task_start, log_task_success, log_task_error`
   - Import `get_scoped_session` from `app.database` for sync ORM services (AuditService)
   - Create 4 `@broker.task()` async functions: `cleanup_expired_logs`, `refresh_ai_performance_metrics`, `generate_daily_report`, `check_hipaa_compliance`
   - Each wraps the sync ORM logic in `with get_scoped_session() as db:` and calls AuditService methods
   - Cron timezone conversions (BRT → UTC, +3h): `cleanup_expired_logs` → `cron("0 5 * * *")` (was 02:00 BRT), `generate_daily_report` → `cron("15 5 * * *")` (was 02:15 BRT), `check_hipaa_compliance` → `cron("45 5 * * *")` (was 02:45 BRT)
   - `refresh_ai_performance_metrics` → interval 3600s
   - Add structured logging: `log_task_start/success/error` pattern
   - Use `retry_on_error=True, max_retries=3, delay=300` matching Celery's `_AUDIT_TASK_OPTIONS`

2. **Create `lgpd_taskiq.py`** (2 tasks, 1 periodic):
   - `persist_lgpd_audit_log` — on-demand task with retry. Import pure helper functions from `app.tasks.lgpd_tasks`: `_normalize_action_type`, `_resolve_data_category`, `_sanitize_context_data`, `_redact_sensitive_values`, `_redact_string_field`, `_validate_and_normalize_uuid`, `_build_safe_audit_record`. Use `get_scoped_session()` for sync ORM (LGPDAuditLog model).
   - `cleanup_expired_lgpd_audit_logs` — periodic at `cron("30 5 * * *")` (was 02:30 BRT). Import helpers from Celery module.
   - The Celery module's pure helpers are tested and stable — import, don't duplicate.

3. **Migrate LGPD middleware call site**:
   - In `app/middleware/lgpd_middleware.py`, the `_enqueue_lgpd_audit` function calls `persist_lgpd_audit_log.delay(...)`.
   - This is a plain (non-async) function called from within the async ASGI middleware `__call__`.
   - Change the import from `app.tasks.lgpd_tasks` to `app.tasks.lgpd_taskiq`.
   - Since `.kiq()` is a coroutine and `_enqueue_lgpd_audit` is sync, make it `async def _enqueue_lgpd_audit(...)` and change `.delay(...)` to `await persist_lgpd_audit_log.kiq(...)`.
   - Update the caller in the middleware `__call__` method (which is already async) to `await _enqueue_lgpd_audit(...)`.

4. **Create `reports_taskiq.py`** (2 tasks, 1 periodic):
   - `generate_patient_report` — on-demand with retry. Uses `run_async()` bridge in Celery version → in Taskiq, call `ReportService.generate_report()` with `await` directly (the service method is async).
   - `generate_scheduled_reports` — periodic at interval 3600s. Dispatches `generate_patient_report` for each patient. In Celery uses `.apply_async(args=[pid, rtype])` → in Taskiq use `await generate_patient_report.kiq(pid, rtype)`. Note: `.kiq()` returns `TaskiqResult`, not Celery's `AsyncResult`.
   - Import pure helpers from `app.tasks.reports`: `_get_system_actor_uuid`, `_sanitize_report_type`.

5. **Create `saga_monitoring_taskiq.py`** (3 tasks, 3 periodic):
   - `check_orphaned_sagas` — interval 3600s
   - `check_long_running_sagas` — interval 900s
   - `generate_saga_metrics` — interval 3600s
   - All use pure sync ORM with `get_scoped_session()`. Import `PatientOnboardingSaga`, `SagaStatus` models. No bridges to remove — these are already sync.

6. **Verify all 4 modules parse and have correct task/schedule counts.**

## Must-Haves

- [ ] `audit_taskiq.py` with 4 `@broker.task` functions, 4 schedule labels (3 cron UTC-converted, 1 interval)
- [ ] `lgpd_taskiq.py` with 2 `@broker.task` functions, 1 schedule label (cron UTC-converted)
- [ ] `reports_taskiq.py` with 2 `@broker.task` functions, 1 schedule label (interval), cross-dispatch via `.kiq()`
- [ ] `saga_monitoring_taskiq.py` with 3 `@broker.task` functions, 3 schedule labels (all interval)
- [ ] LGPD middleware `_enqueue_lgpd_audit` migrated from `.delay()` to `await .kiq()`
- [ ] Pure helpers imported from Celery modules — zero logic duplication
- [ ] All cron schedules correctly converted: 02:00 BRT→05:00 UTC, 02:15→05:15, 02:30→05:30, 02:45→05:45
- [ ] All files pass `ast.parse()`

## Verification

- `python3 -c "import ast; ast.parse(open('app/tasks/audit_taskiq.py').read()); ast.parse(open('app/tasks/lgpd_taskiq.py').read()); ast.parse(open('app/tasks/reports_taskiq.py').read()); ast.parse(open('app/tasks/saga_monitoring_taskiq.py').read()); print('All 4 modules parse OK')"` from backend-hormonia/
- `grep -c "@broker.task" app/tasks/audit_taskiq.py app/tasks/lgpd_taskiq.py app/tasks/reports_taskiq.py app/tasks/saga_monitoring_taskiq.py` → 4 + 2 + 2 + 3 = 11
- `grep -c "schedule=" app/tasks/audit_taskiq.py app/tasks/lgpd_taskiq.py app/tasks/reports_taskiq.py app/tasks/saga_monitoring_taskiq.py` → 4 + 1 + 1 + 3 = 9
- `grep "lgpd_taskiq" app/middleware/lgpd_middleware.py` shows import from Taskiq module
- `grep "\.delay(" app/middleware/lgpd_middleware.py` returns zero matches

## Inputs

- `backend-hormonia/app/tasks/taskiq_base.py` — DbSession, log_task_start/success/error, schedule_task_at
- `backend-hormonia/app/taskiq_broker.py` — broker instance for `@broker.task()` decorator
- `backend-hormonia/app/tasks/audit_cleanup.py` — Celery source: 4 tasks, `get_scoped_session()`, AuditService
- `backend-hormonia/app/tasks/lgpd_tasks.py` — Celery source: 2 tasks, pure helper functions, LGPDAuditLog model
- `backend-hormonia/app/tasks/reports.py` — Celery source: 2 tasks, `run_async()`, ReportService
- `backend-hormonia/app/tasks/saga_monitoring.py` — Celery source: 3 tasks, pure sync ORM
- `backend-hormonia/app/middleware/lgpd_middleware.py` — `_enqueue_lgpd_audit` call site (line ~170)
- `backend-hormonia/app/celery_app.py` — beat_schedule entries for cron time reference (lines 81-296)
- S02 pattern reference: `backend-hormonia/app/tasks/messaging_taskiq.py` — established task module structure

## Expected Output

- `backend-hormonia/app/tasks/audit_taskiq.py` — 4 Taskiq tasks with schedule labels, structured logging
- `backend-hormonia/app/tasks/lgpd_taskiq.py` — 2 Taskiq tasks, helpers imported from Celery module
- `backend-hormonia/app/tasks/reports_taskiq.py` — 2 Taskiq tasks, `.kiq()` cross-dispatch for report generation
- `backend-hormonia/app/tasks/saga_monitoring_taskiq.py` — 3 Taskiq tasks, pure sync ORM
- `backend-hormonia/app/middleware/lgpd_middleware.py` — modified to import from `lgpd_taskiq` and use `await .kiq()`

## Observability Impact

- **New signals:** 11 tasks emit `log_task_start`/`log_task_success`/`log_task_error` structured logs with `task_name`, `event`, `duration_ms`, `error_type`, `error_message` fields
- **Schedule labels:** 9 schedule labels (3 cron, 6 interval) readable by `taskiq scheduler` at startup
- **Failure visibility:** Each task re-raises exceptions → `SmartRetryMiddleware` logs retry attempts with count/delay. `log_task_error` captures `error_type` and `error_message` for all 11 tasks
- **LGPD middleware fallback:** `_enqueue_lgpd_audit` catches Taskiq dispatch errors and logs a warning (same resilience pattern as Celery version) — requests are never blocked by audit failures
- **Inspection:** `grep "event.*task_error" <log>` finds all task failures; schedule labels are inspectable via `taskiq scheduler --dump`
