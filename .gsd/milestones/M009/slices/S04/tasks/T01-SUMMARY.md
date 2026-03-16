---
id: T01
parent: S04
milestone: M009
provides:
  - 4 Taskiq modules (audit, lgpd, reports, saga_monitoring) with 11 tasks and 9 schedule labels
  - LGPD middleware migrated from Celery .delay() to Taskiq await .kiq()
key_files:
  - backend-hormonia/app/tasks/audit_taskiq.py
  - backend-hormonia/app/tasks/lgpd_taskiq.py
  - backend-hormonia/app/tasks/reports_taskiq.py
  - backend-hormonia/app/tasks/saga_monitoring_taskiq.py
  - backend-hormonia/app/middleware/lgpd_middleware.py
key_decisions:
  - Saga monitoring helpers (_alert_orphaned_saga, _generate_orphan_summary) replicated inline rather than imported — they're tightly coupled to ORM session, not pure stateless helpers
patterns_established:
  - Sync ORM Taskiq pattern: async def wraps get_scoped_session() context manager for services that haven't been converted to async
  - LGPD helper import pattern: import 13 pure helpers from Celery module to avoid duplication
observability_surfaces:
  - 11 tasks emit log_task_start/success/error with structured task_name, event, duration_ms, error_type, error_message
  - 9 schedule labels readable by taskiq scheduler at startup
  - LGPD middleware logs warning on Taskiq dispatch failure (request never blocked)
duration: 15min
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: Migrate simple sync-ORM modules + LGPD middleware call site

**Created 4 Taskiq modules (11 tasks, 9 schedule labels) for audit/lgpd/reports/saga_monitoring and migrated LGPD middleware from .delay() to await .kiq()**

## What Happened

Created 4 parallel `*_taskiq.py` modules alongside existing Celery modules following the D007 coexistence pattern:

1. **audit_taskiq.py** — 4 tasks (cleanup_expired_logs, refresh_ai_performance_metrics, generate_daily_report, check_hipaa_compliance) with 4 schedule labels (3 cron UTC-converted, 1 interval). Uses get_scoped_session() for sync AuditService calls.

2. **lgpd_taskiq.py** — 2 tasks (persist_lgpd_audit_log, cleanup_expired_lgpd_audit_logs) with 1 schedule label (cron). Imports 13 pure helper functions from Celery module — zero logic duplication.

3. **reports_taskiq.py** — 2 tasks (generate_patient_report, generate_scheduled_reports) with 1 schedule label (interval). Cross-dispatch via `.kiq()` for report fanout. Removed `run_async()` bridge — calls ReportService.generate_report() with await directly.

4. **saga_monitoring_taskiq.py** — 3 tasks (check_orphaned_sagas, check_long_running_sagas, generate_saga_metrics) with 3 schedule labels (all interval). Pure sync ORM — no bridges to remove.

5. **LGPD middleware migration** — `_enqueue_lgpd_audit` changed from sync `def` calling `.delay()` to `async def` calling `await .kiq()`. Caller in `__call__` updated to `await`. Error-resilient fallback preserved.

All cron schedules converted BRT → UTC (+3h): 02:00→05:00, 02:15→05:15, 02:30→05:30, 02:45→05:45.

## Verification

All task-level checks passed:
- `ast.parse()` — all 4 modules + middleware parse cleanly ✅
- `@broker.task` counts: audit=4, lgpd=2, reports=2, saga_monitoring=3 (total 11) ✅
- `schedule=` counts: audit=4, lgpd=1, reports=1, saga_monitoring=3 (total 9) ✅
- Middleware imports from `lgpd_taskiq` ✅
- Zero `.delay(` in middleware ✅
- `await .kiq(` present in middleware ✅

Slice-level checks (partial — T01 is task 1 of 4):
- All `*_taskiq.py` modules parse: ✅ (7 modules so far including S02/S03)
- Total `@broker.task` across all modules: 37 (target ≥46 by T04)
- All taskiq modules have error logging: 7/7 ✅
- External `.delay()/.apply_async()` audit: remaining calls in quiz_flow/, flows/, trigger_service.py, recovery.py — these are handled by T02-T04

## Diagnostics

- **Task failures:** `grep "event.*task_error" <log>` — all 11 tasks log structured errors with error_type and error_message
- **Schedule inspection:** schedule labels on `@broker.task()` decorators; `taskiq scheduler --dump` reads all labels at startup
- **Retry visibility:** SmartRetryMiddleware logs retry attempts with count/delay for all retry-enabled tasks
- **LGPD dispatch failures:** `grep "LGPD: Failed to enqueue" <log>` — middleware catches dispatch errors and logs warning without blocking requests

## Deviations

- Plan step 2 listed helper names that don't exist in the Celery module (e.g., `_normalize_action_type`, `_build_safe_audit_record`). Imported the actual 13 helpers available: `_is_patient_context`, `_normalize_action`, `_normalize_data_category`, etc.
- Saga monitoring helpers (`_alert_orphaned_saga`, `_generate_orphan_summary`) were replicated inline instead of imported — they require the ORM `db` session parameter and perform writes, making them non-pure. The plan's guidance to "import pure helpers" doesn't apply to these stateful helpers.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/tasks/audit_taskiq.py` — new: 4 Taskiq tasks with schedule labels
- `backend-hormonia/app/tasks/lgpd_taskiq.py` — new: 2 Taskiq tasks, 13 helpers imported from Celery
- `backend-hormonia/app/tasks/reports_taskiq.py` — new: 2 Taskiq tasks, .kiq() cross-dispatch
- `backend-hormonia/app/tasks/saga_monitoring_taskiq.py` — new: 3 Taskiq tasks, pure sync ORM
- `backend-hormonia/app/middleware/lgpd_middleware.py` — modified: async _enqueue_lgpd_audit + await .kiq()
- `.gsd/milestones/M009/slices/S04/S04-PLAN.md` — T01 marked done, added diagnostic check
- `.gsd/milestones/M009/slices/S04/tasks/T01-PLAN.md` — added Observability Impact section
- `.gsd/STATE.md` — next action updated to T02
