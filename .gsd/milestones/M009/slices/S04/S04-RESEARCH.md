# S04 — Research

**Date:** 2026-03-16
**Depth:** Targeted (known pattern from S02/S03, moderate volume — 28 periodic + ~18 on-demand tasks across 10 modules)

## Summary

S04 migrates all remaining Celery tasks to Taskiq and delivers the **complete schedule** with all 47 beat_schedule entries covered. S02 migrated 7 messaging tasks (9 total with non-periodic) and S03 migrated 12 flow/saga tasks (17 total). S04 covers the remaining **28 periodic entries** plus all associated on-demand tasks — spanning 10 Celery modules: `alerts.py`, `quiz_link_tasks.py`, `quiz_flow/` (4 files), `follow_up.py`, `webhook_dlq.py`, `monitoring.py`, `audit_cleanup.py`, `lgpd_tasks.py`, `reports.py`, and `saga_monitoring.py`.

The established pattern from S02/S03 is clear: create `*_taskiq.py` parallel modules with `@broker.task()` async functions, schedule labels for periodic tasks, `DbSession` for async DB, `get_scoped_session()` for sync ORM services, and `log_task_start/success/error` for structured logging. The key migration translations are: `run_async()`/`async_to_sync()` bridges → direct `await`, `self.retry()` → raise + SmartRetryMiddleware, `.delay()` → `await .kiq()`, `.apply_async(eta=)` → `await schedule_task_at()`. One special case: `persist_lgpd_audit_log.delay()` is called from sync FastAPI middleware — needs an async dispatch pattern since `.kiq()` is a coroutine.

After S04, every task in the codebase has a Taskiq equivalent, every beat_schedule entry has a matching schedule label, and the `.delay()` → `.kiq()` migration of remaining call sites (middleware, trigger_service, recovery) is complete. Celery tasks remain alive for S05 to delete.

## Recommendation

**Create 10 parallel `*_taskiq.py` modules** following the exact S02/S03 coexistence pattern (D007). Import pure helper functions from Celery modules to avoid duplication. Use `get_scoped_session()` for tasks with sync ORM services (monitoring, saga_monitoring, quiz_flow, follow_up) per D009. Build simple modules first (audit, LGPD, reports, saga_monitoring), then medium (alerts, webhook_dlq, monitoring), then complex (quiz_link, quiz_flow, follow_up). Finish with call site migration and schedule parity verification.

For the LGPD middleware call site, use `asyncio.get_event_loop().create_task()` or `asyncio.ensure_future()` inside the async middleware to dispatch `.kiq()` without blocking.

## Implementation Landscape

### Key Files — Source (Celery tasks to migrate)

- `backend-hormonia/app/tasks/alerts.py` (582 lines, 7 tasks) — check_patient_alerts, periodic_alert_check, process_alert_notification, process_alert_escalation, periodic_escalation_check, cleanup_resolved_alerts, generate_alert_metrics. Uses `async_to_sync` for alert_manager. Internal cross-dispatch: `process_alert_escalation.delay()` from `periodic_escalation_check`.
- `backend-hormonia/app/tasks/quiz_link_tasks.py` (693 lines, 6 tasks) — check_expired_links, rotate_expired_token, send_quiz_reminder, fallback_to_whatsapp, process_dead_letter_queue, monitor_resilience_metrics. Complex retry: `send_quiz_reminder` uses `self.request.retries` + `.apply_async(countdown=)` for manual retry scheduling. Import pure helpers: `_sanitize_limit`, `_token_fingerprint`, `_sanitize_error_message`, `_sanitize_dlq_record`, `QuizLinkTask` (base class — not needed in Taskiq).
- `backend-hormonia/app/tasks/quiz_flow/cleanup_tasks.py` (328 lines, 1 task) — cleanup_expired_quiz_sessions_task. Uses sync ORM.
- `backend-hormonia/app/tasks/quiz_flow/trigger_tasks.py` (428 lines, 3 tasks) — check_quiz_triggers_task, send_quiz_link_reminder_task, monitor_quiz_links_task. Uses `async_to_sync` for quiz service. Has `.delay()` and `.apply_async()` cross-dispatch to send_quiz_reminder.
- `backend-hormonia/app/tasks/quiz_flow/response_tasks.py` (294 lines, 2 tasks) — process_quiz_response_task, generate_quiz_report_task. Uses `async_to_sync` and `run_async`.
- `backend-hormonia/app/tasks/quiz_flow/question_tasks.py` (309 lines, 2 tasks) — send_quiz_question_task, send_quiz_progress_update_task. Uses `async_to_sync` and `run_async`.
- `backend-hormonia/app/tasks/follow_up.py` (895 lines, 3 tasks) — execute_pending_follow_ups, process_escalation_alerts, cleanup_old_contexts. Heaviest bridge usage: 15+ `async_to_sync()` calls for FollowUpSystemService + Redis store. Many helper functions (pure, can import). Dispatches `process_alert_notification.delay()`.
- `backend-hormonia/app/tasks/webhook_dlq.py` (329 lines, 3 tasks) — process_webhook_dlq, cleanup_old_dlq_events, monitor_dlq_health. Uses `run_async()` for async DLQ service. `_retry_or_raise` helper can be dropped (SmartRetryMiddleware handles it).
- `backend-hormonia/app/tasks/monitoring.py` (614 lines, 8 tasks) — 8 MonitoringTask subclasses wrapping `run_async()`. Needs flattening from class hierarchy to `@broker.task()` functions. All use sync `get_db_session()` + `get_sync_redis_client()` + `run_async()` for async services.
- `backend-hormonia/app/tasks/audit_cleanup.py` (251 lines, 4 tasks) — cleanup_expired_logs, refresh_ai_performance_metrics, generate_daily_report, check_hipaa_compliance. All use `get_scoped_session()` sync ORM. Simplest migration — just wrap in async, use `get_scoped_session()` per D009.
- `backend-hormonia/app/tasks/lgpd_tasks.py` (624 lines, 2 tasks) — persist_lgpd_audit_log (on-demand, from middleware), cleanup_expired_lgpd_audit_logs. Lots of pure helper functions (normalization, sanitization) — import them.
- `backend-hormonia/app/tasks/reports.py` (127 lines, 2 tasks) — generate_patient_report, generate_scheduled_reports. Uses `self.retry(exc=, countdown=)` and `run_async()` + `.apply_async()`.
- `backend-hormonia/app/tasks/saga_monitoring.py` (396 lines, 3 tasks) — check_orphaned_sagas, check_long_running_sagas, generate_saga_metrics. All sync ORM with `get_scoped_session()`.

### Key Files — Target (new Taskiq modules to create)

- `backend-hormonia/app/tasks/alerts_taskiq.py` — 7 tasks (1 periodic in beat_schedule: check_patient_alerts 300s)
- `backend-hormonia/app/tasks/quiz_link_taskiq.py` — 6 tasks (3 periodic: check_expired_links 1800s, monitor_resilience_metrics 3600s, process_dead_letter_queue 7200s)
- `backend-hormonia/app/tasks/quiz_flow_taskiq.py` — 8 tasks from 4 subpackage files (1 periodic: cleanup_expired_quiz_sessions 7200s)
- `backend-hormonia/app/tasks/follow_up_taskiq.py` — 3 tasks (3 periodic: execute_pending_follow_ups 300s, process_escalation_alerts 600s, cleanup_old_contexts cron 06:00 UTC)
- `backend-hormonia/app/tasks/webhook_dlq_taskiq.py` — 3 tasks (3 periodic: process_webhook_dlq 60s, cleanup_old_dlq_events cron 06:00 UTC, monitor_dlq_health 300s)
- `backend-hormonia/app/tasks/monitoring_taskiq.py` — 8 tasks (8 periodic: system_health_check 300s, performance_metrics_collection 600s, bottleneck_detection 900s, alert_monitoring 300s, escalation_check 1800s, automated_recovery 3600s, data_integrity_guardrails 900s, cleanup_old_data 86400s)
- `backend-hormonia/app/tasks/audit_taskiq.py` — 4 tasks (4 periodic: cleanup_expired_logs cron 05:00 UTC, refresh_performance_metrics 3600s, generate_daily_report cron 05:15 UTC, check_hipaa_compliance cron 05:45 UTC)
- `backend-hormonia/app/tasks/lgpd_taskiq.py` — 2 tasks (1 periodic: cleanup_expired_lgpd_audit_logs cron 05:30 UTC)
- `backend-hormonia/app/tasks/reports_taskiq.py` — 2 tasks (1 periodic: generate_scheduled_reports 3600s)
- `backend-hormonia/app/tasks/saga_monitoring_taskiq.py` — 3 tasks (3 periodic: check_orphaned_sagas 3600s, check_long_running_sagas 900s, generate_saga_metrics 3600s)

### Key Files — Call sites to migrate

- `backend-hormonia/app/middleware/lgpd_middleware.py:170` — `persist_lgpd_audit_log.delay()` → async `.kiq()` dispatch from async middleware
- `backend-hormonia/app/tasks/follow_up.py:692,726` → Will be in `follow_up_taskiq.py`, calls `process_alert_notification` — needs import from `alerts_taskiq.py`
- `backend-hormonia/app/domain/quizzes/integration/flow_integration/trigger_service.py:724,732` — `send_quiz_link_reminder_task.apply_async()` → needs async `.kiq()` call. This is a sync service method — needs pattern consideration.
- `backend-hormonia/app/services/flow/recovery.py:214` — `retry_failed_flow_send.delay()` — already migrated in S03 `flows_taskiq.py`, but the call site in `recovery.py` still uses Celery .delay(). Marked with TODO(S05) in D010.

### Files NOT to migrate (Celery infrastructure, deleted in S05)

- `celery_metrics.py` — Celery Prometheus signals (698 lines)
- `queue_monitor.py` — Celery queue length monitor (258 lines)
- `base.py` — Celery BaseTask / DatabaseTask / MonitoringTask classes
- `config.py` — Celery TaskConfig dataclasses
- `celery_app.py` — Celery instance + beat_schedule + run_async_in_celery

### Build Order

**Phase 1: Simple sync-ORM tasks (4 modules, ~20 tasks, low risk)**
1. `audit_taskiq.py` — 4 tasks, pure sync ORM, no bridges. Simplest possible migration.
2. `lgpd_taskiq.py` — 2 tasks, sync ORM + many pure helpers (import from lgpd_tasks.py). Middleware call site migration.
3. `reports_taskiq.py` — 2 tasks, `run_async()` → direct `await`. `generate_scheduled_reports` dispatches `generate_patient_report` — both must be Taskiq.
4. `saga_monitoring_taskiq.py` — 3 tasks, pure sync ORM with `get_scoped_session()`.

**Phase 2: Medium complexity (3 modules, ~18 tasks)**
5. `alerts_taskiq.py` — 7 tasks, `async_to_sync` → direct `await`. Internal cross-dispatch (`process_alert_escalation`).
6. `webhook_dlq_taskiq.py` — 3 tasks, `run_async()` → direct `await`. Async DLQ service can be called natively.
7. `monitoring_taskiq.py` — 8 tasks, flatten MonitoringTask class hierarchy into `@broker.task()` functions. `run_async()` → direct `await` for async services; sync ORM services use `get_scoped_session()`.

**Phase 3: Complex tasks (3 modules, ~17 tasks)**
8. `quiz_link_taskiq.py` — 6 tasks. `send_quiz_reminder` has custom retry-with-countdown pattern → SmartRetryMiddleware. Cross-task dispatch chain (check_expired → rotate → send_quiz_reminder/fallback).
9. `quiz_flow_taskiq.py` — 8 tasks from 4 subpackage files. `async_to_sync` → direct `await`. Cross-dispatch to `send_quiz_reminder` from quiz_link_taskiq.
10. `follow_up_taskiq.py` — 3 tasks, 895 lines source. Heaviest bridge usage (15+ `async_to_sync`). With Taskiq async, `follow_up_service` methods can be called with `await` directly. Dispatches `process_alert_notification` from `alerts_taskiq.py`.

**Phase 4: Call sites + schedule verification**
11. Migrate remaining `.delay()` / `.apply_async()` call sites to `.kiq()`:
    - `middleware/lgpd_middleware.py` — async dispatch pattern
    - `domain/quizzes/.../trigger_service.py` — sync caller, needs pattern
12. **Schedule parity verification** — enumerate all schedule labels across all `*_taskiq.py` files, compare against the 47 beat_schedule entries, confirm 1:1 coverage.

### Verification Approach

1. **Syntax/import validation**: `python3 -c "import ast; ast.parse(open('file').read())"` for each new file
2. **Schedule parity audit**: Script that extracts all `schedule=[...]` labels from `*_taskiq.py` files and compares against 47 beat_schedule entries in `celery_app.py`
3. **Task count verification**: Count total `@broker.task` decorators across all `*_taskiq.py` files — should match total Celery tasks
4. **No orphaned call sites**: `rg "\.delay\(|\.apply_async\(" -g "*.py"` should only show results in Celery task modules (not in services, middleware, or domain code) — all external call sites migrated to `.kiq()`
5. **Module import chain**: Each `*_taskiq.py` must import from `app.taskiq_broker` (broker) and `app.tasks.taskiq_base` (DbSession, log helpers) — no import from `app.tasks.base` (Celery BaseTask)

## Constraints

- **D007 (coexistence)**: Celery tasks stay intact — create parallel `*_taskiq.py` modules. S05 deletes the Celery versions.
- **D009 (sync ORM services)**: Tasks that call sync services (FlowStateRepository, FollowUpSystemService, QuizLinkResilienceService, MonitoringTask classes) wrap them in `get_scoped_session()` context manager. Don't rewrite services to async.
- **D005 (AsyncSession)**: Tasks that do direct DB queries use `DbSession` (AsyncSession via TaskiqDepends).
- **Cron timezone**: Celery beat_schedule uses `America/Sao_Paulo` timezone (UTC-3). Taskiq LabelScheduleSource cron is UTC. Convert: `cron(hour=2)` BRT → `cron(hour=5)` UTC, `cron(hour=3)` BRT → `cron(hour=6)` UTC, `cron(hour=8)` → already in S03 as `cron(hour=11)`.
- **KNOWLEDGE Rule 1**: Never import `from app.tasks.xxx` through `app.tasks` package init — import `*_taskiq.py` modules directly.
- **KNOWLEDGE Rule 2**: Never import `app.config.settings` in broker module.

## Common Pitfalls

- **Timezone conversion for cron schedules** — All BRT cron times must be converted to UTC in Taskiq schedule labels. BRT is UTC-3: `02:00 BRT = 05:00 UTC`, `02:15 BRT = 05:15 UTC`, `02:30 BRT = 05:30 UTC`, `02:45 BRT = 05:45 UTC`, `03:00 BRT = 06:00 UTC`. Missing this makes tasks fire 3 hours early.
- **LGPD middleware sync→async dispatch** — `persist_lgpd_audit_log.delay()` is called from sync code path in middleware, but `.kiq()` returns a coroutine. The middleware is async (FastAPI), so `await persist_lgpd_audit_log.kiq(...)` works directly. Verify the middleware function is `async def`.
- **Cross-task import ordering** — `follow_up_taskiq.py` dispatches `process_alert_notification` from `alerts_taskiq.py`. Import must use the Taskiq version, not the Celery version. Same for `quiz_flow_taskiq.py` → `send_quiz_reminder` from `quiz_link_taskiq.py`.
- **MonitoringTask flattening** — `monitoring.py` uses `run_async()` to call async service methods from sync task body. In Taskiq async tasks, call services directly with `await`. But services that construct sync objects (get_sync_redis_client, FlowStateRepository(db)) need sync session — use `get_scoped_session()` for the sync session passed to constructors, then `await` the async method.
- **quiz_link_tasks.py send_quiz_reminder custom retry** — Uses `send_quiz_reminder.apply_async(countdown=retry_delay)` for manual retry with escalating delays [3600, 7200, 14400]. In Taskiq, SmartRetryMiddleware handles retry automatically. If specific delay escalation is needed, use `schedule_task_at` with computed future time, or accept SmartRetryMiddleware's exponential backoff (simpler).
- **reports.py generate_scheduled_reports** — Calls `generate_patient_report.apply_async(args=[pid, rtype])`. This is immediate dispatch (no ETA), so it maps to `await generate_patient_report.kiq(pid, rtype)`. The `task.id` return value changes: Celery returns `AsyncResult` with `.id`, Taskiq `.kiq()` returns `TaskiqResult`.
- **trigger_service.py sync caller** — `send_quiz_link_reminder_task.apply_async(countdown=...)` is called from sync `QuizTriggerService`. This is a domain service, not a task — with Taskiq `.kiq()` being async, the sync caller needs `asyncio.get_event_loop().run_until_complete()` or must stay on Celery `.delay()` until S05. Best approach: keep Celery `.delay()` in trigger_service.py during coexistence and add `TODO(S05)` marker.

## Open Risks

- **follow_up.py complexity (895 lines)** — The most complex task file with 15+ `async_to_sync` calls, Redis store interactions, distributed locks, deduplication, and Prometheus metrics. Translating all bridges to native async is mechanical but error-prone due to volume. Helper functions (~20) should be imported from the Celery module to avoid duplication.
- **Domain service call sites** — `trigger_service.py` and `recovery.py` call `.delay()` / `.apply_async()` from sync service code. These can't easily switch to async `.kiq()` without making the calling chain async. During coexistence, the safest approach is to keep Celery dispatch in these sync callers and mark them `TODO(S05)`. This means S04 achieves schedule parity and task migration, but not 100% call site migration — the remaining sync call sites are resolved when Celery is removed.
