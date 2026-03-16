---
id: T02
parent: S04
milestone: M009
provides:
  - 3 Taskiq modules (alerts, webhook_dlq, monitoring) with 18 tasks and 12 schedule labels
  - alerts_taskiq.py with 7 async-native alert tasks and .kiq() cross-dispatch
  - webhook_dlq_taskiq.py with 3 async DLQ tasks, no sync bridges
  - monitoring_taskiq.py with 8 tasks flattened from MonitoringTask class hierarchy
key_files:
  - backend-hormonia/app/tasks/alerts_taskiq.py
  - backend-hormonia/app/tasks/webhook_dlq_taskiq.py
  - backend-hormonia/app/tasks/monitoring_taskiq.py
key_decisions:
  - Monitoring class hierarchy (8 MonitoringTask subclasses) fully flattened into standalone async functions — eliminates inheritance and self.log/self.create_success_result patterns
  - DLQ cleanup uses inline async Redis SCAN rather than wrapping in run_async closure
patterns_established:
  - Medium-complexity Taskiq migration pattern: async_to_sync()/run_async() bridges removed, async service methods called directly with await
  - Internal cross-dispatch: .delay() → await .kiq() for task-to-task invocation within same module
  - Wall-clock timing separated from monotonic start_time: wall_clock_start = now_sao_paulo() for business-level execution_time, log helpers use time.monotonic for duration_ms
observability_surfaces:
  - 18 tasks emit task_start/task_success/task_error structured log events with task_name, event, duration_ms fields
  - 12 schedule labels readable via `taskiq scheduler --dump`
  - DLQ health alerts logged as ERROR (critical) and WARNING (warning) with severity and threshold data
  - Data integrity guardrails log non-zero counters as WARNING
  - SmartRetryMiddleware logs retry attempts with count/delay for all 18 tasks
duration: 15m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T02: Migrate medium complexity modules (alerts, webhook_dlq, monitoring)

**Created 3 Taskiq modules with 18 async-native tasks (7 alert + 3 DLQ + 8 monitoring) replacing Celery tasks with sync bridges removed and MonitoringTask class hierarchy flattened.**

## What Happened

Created three Taskiq parallel modules for medium-complexity task groups:

1. **alerts_taskiq.py** (7 tasks, 1 schedule label): Migrated all 7 alert tasks. Key change: `async_to_sync(alert_manager.evaluate_patient_alerts)()` → direct `await alert_manager.evaluate_patient_alerts()`. Internal cross-dispatch in `periodic_escalation_check` changed from `.delay()` to `await .kiq()`. Imported `_ALERT_METADATA_REDACTED_FIELDS` and `_sanitize_alert_metadata` from Celery module to avoid duplication.

2. **webhook_dlq_taskiq.py** (3 tasks, 3 schedule labels): Migrated all 3 DLQ tasks. Removed `run_async()` bridge — async DLQ service called directly with `await`. Dropped `_retry_or_raise` helper entirely (SmartRetryMiddleware handles retries). Cron for `cleanup_old_dlq_events` converted from 03:00 BRT → `cron("0 6 * * *")` UTC.

3. **monitoring_taskiq.py** (8 tasks, 8 schedule labels): Flattened 8 `MonitoringTask` subclasses into standalone `@broker.task()` async functions. Eliminated class hierarchy, `self.log_task_start/success/error()`, `self.create_success_result()`, and `self.get_task_logger()` patterns. All `run_async()` bridges removed — async service methods called directly with `await`. Sync services (DataCorruptionDetector, FlowStateRepository) still use `get_scoped_session()`.

## Verification

All 5 verification checks passed:

```
✅ ast.parse: All 3 modules parse OK
✅ @broker.task: alerts=7, webhook_dlq=3, monitoring=8 (total 18)
✅ schedule=: alerts=1, webhook_dlq=3, monitoring=8 (total 12)
✅ Zero bridges: async_to_sync|run_async = 0 across all 3 files
✅ Zero MonitoringTask: 0 references in monitoring_taskiq.py
```

Slice-level verification (partial — T02 is intermediate task):
- ✅ All 10 taskiq modules parse cleanly (`ast.parse` glob)
- ✅ Total @broker.task count: 55 across all modules (≥46 threshold)
- ✅ All 10 modules have `log_task_error` (error logging present)
- ⏳ Schedule parity script (T05+ — requires all modules)
- ⏳ External call site migration (T03/T04)

## Diagnostics

- **Task failures:** `grep "event.*task_error" <log>` — all 18 tasks log structured errors with error_type and error_message
- **Schedule inspection:** 12 schedule labels on `@broker.task()` decorators; `taskiq scheduler --dump` reads labels at startup
- **DLQ health:** `grep "DLQ ALERT\|DLQ WARNING" <log>` — monitor_dlq_health logs overflow and dead-letter-rate alerts
- **Data integrity:** `grep "Data integrity guardrails detected" <log>` — non-zero counters logged at WARNING
- **Retry visibility:** SmartRetryMiddleware logs retry attempts with count/delay for all retry-enabled tasks
- **Cross-dispatch tracing:** `periodic_escalation_check` → `process_alert_escalation` via `.kiq()` linkage visible in Taskiq result backend

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/tasks/alerts_taskiq.py` — 7 Taskiq alert tasks (1 periodic), async-native with .kiq() cross-dispatch
- `backend-hormonia/app/tasks/webhook_dlq_taskiq.py` — 3 Taskiq DLQ tasks (3 periodic), async service calls, no sync bridges
- `backend-hormonia/app/tasks/monitoring_taskiq.py` — 8 Taskiq monitoring tasks (8 periodic), flattened from class hierarchy
- `.gsd/milestones/M009/slices/S04/tasks/T02-PLAN.md` — Added Observability Impact section (pre-flight fix)
