---
estimated_steps: 6
estimated_files: 3
---

# T02: Migrate medium complexity modules (alerts, webhook_dlq, monitoring)

**Slice:** S04 — Quiz/alert/follow-up/monitoring migradas + schedule completo
**Milestone:** M009

## Description

Create 3 Taskiq parallel modules for medium-complexity task groups: alerts (7 tasks), webhook DLQ (3 tasks), and monitoring (8 tasks). These modules have `async_to_sync()` and `run_async()` bridges that get removed since Taskiq tasks are async-native. The monitoring module requires flattening 8 `MonitoringTask` subclasses into plain `@broker.task()` functions.

## Steps

1. **Create `alerts_taskiq.py`** (7 tasks, 1 periodic):
   - Read source file: `app/tasks/alerts.py` (582 lines, 7 tasks).
   - Import from `app.taskiq_broker import broker`, `app.tasks.taskiq_base import DbSession, log_task_start, log_task_success, log_task_error`.
   - Create 7 `@broker.task()` async functions: `check_patient_alerts` (periodic 300s), `periodic_alert_check`, `process_alert_notification`, `process_alert_escalation`, `periodic_escalation_check`, `cleanup_resolved_alerts`, `generate_alert_metrics`.
   - Key translation: `async_to_sync(alert_manager.method)()` → `await alert_manager.method()` directly. The alert_manager methods are already async — the Celery version wraps them in `async_to_sync`.
   - Internal cross-dispatch: `periodic_escalation_check` calls `process_alert_escalation.delay()` → change to `await process_alert_escalation.kiq(...)`. Both are in the same module.
   - Import pure helpers from Celery module: `_ALERT_METADATA_REDACTED_FIELDS` and any sanitization helpers.
   - Only `check_patient_alerts` has a schedule label (interval 300s). The others are on-demand or dispatched internally.

2. **Create `webhook_dlq_taskiq.py`** (3 tasks, 3 periodic):
   - Read source file: `app/tasks/webhook_dlq.py` (329 lines, 3 tasks).
   - `process_webhook_dlq` — periodic 60s. Uses `run_async()` → call async DLQ service directly with `await`. Import `get_webhook_dlq` for async DLQ service.
   - `cleanup_old_dlq_events` — cron `cron("0 6 * * *")` (was 03:00 BRT → 06:00 UTC). Uses `get_scoped_session()` for sync cleanup.
   - `monitor_dlq_health` — interval 300s. Uses `run_async()` → call async service with `await`.
   - Drop `_retry_or_raise` helper entirely — SmartRetryMiddleware handles retries via `retry_on_error=True, max_retries=3`.
   - Import config values from `app.config.settings.tasks`: `QUIZ_DLQ_BATCH_SIZE`, `WEBHOOK_DLQ_PROCESSING_TIMEOUT`.

3. **Create `monitoring_taskiq.py`** (8 tasks, 8 periodic):
   - Read source file: `app/tasks/monitoring.py` (614 lines, 8 MonitoringTask subclasses).
   - **Flatten class hierarchy**: Each `MonitoringTask` subclass has a `run(self)` method that calls sync services or `run_async()` for async services. Convert each to a standalone `@broker.task()` async function.
   - 8 tasks with their schedules:
     - `system_health_check` — interval 300s. Checks DB connectivity, Redis, service health.
     - `performance_metrics_collection` — interval 600s. `run_async()` → `await` on PerformanceMonitoringService.
     - `bottleneck_detection` — interval 900s. `run_async()` → `await` on FlowMonitoringService.
     - `alert_monitoring` — interval 300s. `run_async()` → `await` on get_escalation_manager().
     - `escalation_check` — interval 1800s. `run_async()` → `await` on get_escalation_manager().
     - `automated_recovery` — interval 3600s. `run_async()` → `await` on AutomatedRecoveryService.
     - `data_integrity_guardrails` — interval 900s. Uses sync DataCorruptionDetector + ManualCorrectionService with `get_scoped_session()`.
     - `cleanup_old_data` — interval 86400s. Sync cleanup with `get_scoped_session()`.
   - For services needing sync session in constructors: `FlowStateRepository(db)`, `DataCorruptionDetector(db)`, `ErrorRecoveryService(db)` — use `get_scoped_session()` per D009.
   - For async service methods: call directly with `await` (no `run_async()` bridge needed).
   - Import service classes from their original locations (not from monitoring.py).

4. **Verify all 3 modules parse and have correct counts.**

## Must-Haves

- [ ] `alerts_taskiq.py` with 7 `@broker.task` functions, 1 schedule label, zero `async_to_sync` imports
- [ ] `webhook_dlq_taskiq.py` with 3 `@broker.task` functions, 3 schedule labels, zero `run_async` imports, no `_retry_or_raise`
- [ ] `monitoring_taskiq.py` with 8 `@broker.task` functions, 8 schedule labels, zero `MonitoringTask` class hierarchy, zero `run_async` imports
- [ ] Internal alerts cross-dispatch uses `.kiq()` not `.delay()`
- [ ] Cron conversion: 03:00 BRT → 06:00 UTC for `cleanup_old_dlq_events`
- [ ] All files pass `ast.parse()`

## Verification

- `python3 -c "import ast; ast.parse(open('app/tasks/alerts_taskiq.py').read()); ast.parse(open('app/tasks/webhook_dlq_taskiq.py').read()); ast.parse(open('app/tasks/monitoring_taskiq.py').read()); print('All 3 modules parse OK')"` from backend-hormonia/
- `grep -c "@broker.task" app/tasks/alerts_taskiq.py app/tasks/webhook_dlq_taskiq.py app/tasks/monitoring_taskiq.py` → 7 + 3 + 8 = 18
- `grep -c "schedule=" app/tasks/alerts_taskiq.py app/tasks/webhook_dlq_taskiq.py app/tasks/monitoring_taskiq.py` → 1 + 3 + 8 = 12
- `grep -c "async_to_sync\|run_async" app/tasks/alerts_taskiq.py app/tasks/webhook_dlq_taskiq.py app/tasks/monitoring_taskiq.py` → 0 + 0 + 0 (zero bridges)
- `grep -c "MonitoringTask" app/tasks/monitoring_taskiq.py` → 0 (class hierarchy flattened)

## Inputs

- `backend-hormonia/app/tasks/alerts.py` — Celery source: 7 tasks, `async_to_sync`, alert_manager
- `backend-hormonia/app/tasks/webhook_dlq.py` — Celery source: 3 tasks, `run_async`, DLQ service
- `backend-hormonia/app/tasks/monitoring.py` — Celery source: 8 MonitoringTask subclasses, `run_async`, sync constructors
- `backend-hormonia/app/tasks/taskiq_base.py` — DbSession, log helpers
- `backend-hormonia/app/taskiq_broker.py` — broker instance
- `backend-hormonia/app/celery_app.py` — beat_schedule entries for schedule reference
- T01 output: `audit_taskiq.py`, `lgpd_taskiq.py`, `reports_taskiq.py`, `saga_monitoring_taskiq.py` — established pattern for this slice

## Expected Output

- `backend-hormonia/app/tasks/alerts_taskiq.py` — 7 Taskiq tasks, async-native alert processing
- `backend-hormonia/app/tasks/webhook_dlq_taskiq.py` — 3 Taskiq tasks, async DLQ service calls
- `backend-hormonia/app/tasks/monitoring_taskiq.py` — 8 Taskiq tasks, flattened from class hierarchy

## Observability Impact

- **New structured log events**: 18 tasks emit `task_start`, `task_success`, `task_error` events via `log_task_start/success/error` with `task_name`, `event`, `duration_ms`, `error_type`, `error_message` fields
- **Schedule labels**: 12 schedule labels on `@broker.task()` decorators; `taskiq scheduler --dump` reads all labels at startup
- **Alert monitoring signals**: `alert_monitoring` and `system_health_check` log critical alerts at WARNING/CRITICAL level; `data_integrity_guardrails` logs non-zero counters as WARNING
- **DLQ health signals**: `monitor_dlq_health` emits `DLQ ALERT:` (critical) and `DLQ WARNING:` (warning) log lines when thresholds exceeded
- **Retry visibility**: SmartRetryMiddleware logs retry attempts with count/delay for all retry-enabled tasks (all 18)
- **Failure inspection**: `grep "event.*task_error" <log>` surfaces all 18 tasks; each includes `error_type` and `error_message`
- **Cross-dispatch tracing**: `periodic_escalation_check` dispatches `process_alert_escalation` via `.kiq()` — linkage visible in Taskiq result backend
