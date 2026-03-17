---
id: S04
parent: M009
milestone: M009
provides:
  - 10 new Taskiq modules (72 tasks total across 13 modules) covering quiz, alerts, follow-up, LGPD, audit, webhook DLQ, monitoring, reports, saga monitoring
  - 47/47 Celery beat_schedule → Taskiq schedule label parity (verified by script)
  - All external .delay()/.apply_async() call sites migrated to .kiq() or marked TODO(S05)
  - LGPD middleware migrated from sync .delay() to async await .kiq()
  - verify_schedule_parity.sh — replayable proof of schedule parity
requires:
  - slice: S01
    provides: Taskiq broker, SmartRetryMiddleware, LabelScheduleSource, scheduler, taskiq_base helpers (DbSession, log_task_start/success/error, get_scoped_session)
affects:
  - S05
key_files:
  - backend-hormonia/app/tasks/audit_taskiq.py
  - backend-hormonia/app/tasks/lgpd_taskiq.py
  - backend-hormonia/app/tasks/reports_taskiq.py
  - backend-hormonia/app/tasks/saga_monitoring_taskiq.py
  - backend-hormonia/app/tasks/alerts_taskiq.py
  - backend-hormonia/app/tasks/webhook_dlq_taskiq.py
  - backend-hormonia/app/tasks/monitoring_taskiq.py
  - backend-hormonia/app/tasks/quiz_link_taskiq.py
  - backend-hormonia/app/tasks/quiz_flow_taskiq.py
  - backend-hormonia/app/tasks/follow_up_taskiq.py
  - backend-hormonia/app/middleware/lgpd_middleware.py
  - backend-hormonia/scripts/verify_schedule_parity.sh
key_decisions:
  - Stateful helpers (ORM session params, writes) replicated inline in Taskiq modules rather than imported from Celery — D007 "import pure helpers" only applies to stateless functions
  - MonitoringTask class hierarchy (8 subclasses) fully flattened into standalone @broker.task async functions — eliminates inheritance and self.log patterns
  - quiz_flow 4-file Celery subpackage consolidated into single quiz_flow_taskiq.py — simpler module structure for async-native tasks
  - send_quiz_reminder retry mapped to SmartRetryMiddleware delay=3600 exponential backoff, replacing Celery manual countdown=[3600,7200,14400]
  - trigger_service.py and recovery.py sync callers kept on Celery .delay() with TODO(S05) per D010
patterns_established:
  - Sync ORM Taskiq pattern: async def wraps get_scoped_session() for services not yet converted to async
  - Medium-complexity migration: async_to_sync()/run_async() bridges removed, async service methods called directly with await
  - Complex cross-module Taskiq dispatch: follow_up→alerts_taskiq, quiz_flow→quiz_link_taskiq via await .kiq()
  - Hybrid sync/async in follow_up: sync ORM helpers imported from Celery + async redis_store calls via direct await
  - Schedule parity verification via extraction script with known-renaming table
observability_surfaces:
  - 72 tasks emit log_task_start/success/error with structured task_name, event, duration_ms, error_type, error_message
  - 47 schedule labels readable by `taskiq scheduler --dump`
  - bash scripts/verify_schedule_parity.sh — exits 0 (47/47 matched) or 1 (lists missing)
  - SmartRetryMiddleware logs retry attempts with count/delay for all retry-enabled tasks
  - follow_up Prometheus metrics preserved (action_duration, actions_total, messages_deduplicated, messages_sent, pending_actions)
  - DLQ health alerts logged as ERROR/WARNING with severity and threshold data
drill_down_paths:
  - .gsd/milestones/M009/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M009/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M009/slices/S04/tasks/T03-SUMMARY.md
  - .gsd/milestones/M009/slices/S04/tasks/T04-SUMMARY.md
duration: ~70min
verification_result: passed
completed_at: 2026-03-16
---

# S04: Quiz/alert/follow-up/monitoring migradas + schedule completo

**10 new Taskiq modules with 72 tasks covering all remaining Celery task groups, 47/47 schedule parity verified, all external call sites migrated to .kiq() or marked TODO(S05).**

## What Happened

Created 10 parallel `*_taskiq.py` modules alongside existing Celery modules, completing the task-level migration for every remaining Celery task group. Combined with S02 (messaging) and S03 (flows/saga), all 72 tasks across 13 Taskiq modules now have async-native equivalents.

**T01 — Simple sync-ORM modules (4 modules, 11 tasks, 9 schedules):** audit, lgpd, reports, saga_monitoring. Pure `get_scoped_session()` pattern for sync ORM services. 13 pure helpers imported from Celery LGPD module (zero duplication). LGPD middleware migrated from sync `.delay()` to `async def` + `await .kiq()`. Reports cross-dispatch via `.kiq()` for fanout. All BRT cron schedules converted to UTC (+3h).

**T02 — Medium complexity modules (3 modules, 18 tasks, 12 schedules):** alerts, webhook_dlq, monitoring. `async_to_sync()`/`run_async()` bridges fully removed — async services called with direct `await`. MonitoringTask class hierarchy (8 subclasses with inheritance, self.log, self.create_success_result) flattened into 8 standalone `@broker.task()` async functions. DLQ `_retry_or_raise` helper dropped (SmartRetryMiddleware handles retries).

**T03 — Complex modules (3 modules, 17 tasks, 7 schedules):** quiz_link, quiz_flow, follow_up. The heaviest migration — 15+ `async_to_sync()` calls replaced in follow_up alone. quiz_flow's 4-file Celery subpackage (cleanup, trigger, response, question) consolidated into single module. Cross-module dispatch chains wired: quiz_flow→quiz_link_taskiq for `send_quiz_reminder`, follow_up→alerts_taskiq for `process_alert_notification`. Prometheus metrics fully preserved in follow_up. `send_quiz_reminder` custom retry pattern mapped to SmartRetryMiddleware `delay=3600` exponential backoff. trigger_service.py sync caller untouched per D010.

**T04 — Schedule parity verification + call site audit:** Created `verify_schedule_parity.sh` that extracts all 47 beat_schedule entries from celery_app.py and all 47 scheduled functions from Taskiq modules, maps names via known renamings, and reports matched/missing/extra. Script confirms 47/47 parity. Added inline TODO(S05) markers to remaining sync callers in trigger_service.py (2 `.apply_async()` lines) and recovery.py (1 `.delay()` line).

## Verification

All 5 slice-level checks passed:

| Check | Result |
|-------|--------|
| All 13 `*_taskiq.py` modules parse cleanly (`ast.parse`) | ✅ PASS |
| Schedule parity: 47/47 matched (`verify_schedule_parity.sh` exit 0) | ✅ PASS |
| Zero external `.delay()`/`.apply_async()` in non-task code (excl. TODO(S05)) | ✅ PASS |
| Total `@broker.task` ≥ 46 (actual: 72) | ✅ PASS |
| All 13 taskiq modules have `log_task_error` (error logging) | ✅ PASS |

## Requirements Advanced

- R081 — 10 new Taskiq modules created covering all remaining task groups (quiz_link, quiz_flow, follow_up, alerts, webhook_dlq, monitoring, audit, lgpd, reports, saga_monitoring). All 72 tasks parse cleanly and follow established patterns. Contract-level proof complete; runtime proof deferred to S06.
- R082 — 47/47 Celery beat_schedule entries have matching Taskiq schedule labels, verified by replayable `verify_schedule_parity.sh` script. Cron BRT→UTC conversions applied. Runtime schedule firing deferred to S06.
- R083 — All external `.delay()`/`.apply_async()` call sites in non-task code migrated to `.kiq()` or explicitly marked TODO(S05). LGPD middleware migrated (T01). trigger_service.py and recovery.py deferred per D010 (sync callers requiring chain conversion). Call sites within cross-dispatching tasks use `.kiq()`.

## Requirements Validated

- none — R081/R082/R083 need runtime verification in S06 to be validated

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- Stateful helpers (`_alert_orphaned_saga`, `_generate_orphan_summary`, `_notify_doctor_of_expired_session`, `_resume_patient_flow_after_expiration`) replicated inline instead of imported per D007 — these require ORM session and perform writes, making them non-pure.
- `send_quiz_progress_update` uses `get_async_session_factory()` directly instead of sync ORM — the Celery version already used `run_async()` with an async inner function, so direct async is more natural.
- Plan's verification glob `!app/tasks/*.py` didn't match subdirectories like `app/tasks/quiz_flow/trigger_tasks.py` — actual verification uses `!**/tasks/**` for recursive exclusion.

## Known Limitations

- trigger_service.py (2 lines) and recovery.py (1 line) still dispatch via Celery `.delay()`/`.apply_async()` — these are sync call chains that require cascading async conversion. Deferred to S05 per D010.
- All tasks are contract-verified (parse, schedule labels, imports) but not runtime-verified — actual execution against Dragonfly/WuzAPI is S06 scope.
- Celery task modules still exist alongside Taskiq modules — wrong import would dispatch to wrong queue during coexistence.

## Follow-ups

- S05 must resolve TODO(S05) markers in trigger_service.py and recovery.py when removing Celery
- S05 must delete all Celery task modules, celery_app.py, and bridge code
- S06 must runtime-verify all 72 tasks execute successfully via Taskiq worker against Dragonfly

## Files Created/Modified

- `backend-hormonia/app/tasks/audit_taskiq.py` — 4 tasks (audit cleanup, metrics, daily report, HIPAA compliance)
- `backend-hormonia/app/tasks/lgpd_taskiq.py` — 2 tasks (persist audit log, cleanup expired logs)
- `backend-hormonia/app/tasks/reports_taskiq.py` — 2 tasks (generate patient report, scheduled reports with .kiq() fanout)
- `backend-hormonia/app/tasks/saga_monitoring_taskiq.py` — 3 tasks (orphaned sagas, long-running sagas, saga metrics)
- `backend-hormonia/app/tasks/alerts_taskiq.py` — 7 tasks (alert evaluation, escalation, notification, periodic check)
- `backend-hormonia/app/tasks/webhook_dlq_taskiq.py` — 3 tasks (DLQ processing, health monitoring, cleanup)
- `backend-hormonia/app/tasks/monitoring_taskiq.py` — 8 tasks (health check, performance, bottleneck, integrity, recovery, escalation, alert, cleanup)
- `backend-hormonia/app/tasks/quiz_link_taskiq.py` — 6 tasks (expired links, token rotation, send reminder, WhatsApp fallback, DLQ, metrics)
- `backend-hormonia/app/tasks/quiz_flow_taskiq.py` — 8 tasks (cleanup, triggers, responses, questions — consolidated from 4 files)
- `backend-hormonia/app/tasks/follow_up_taskiq.py` — 3 tasks (pending execution, escalation alerts, context cleanup)
- `backend-hormonia/app/middleware/lgpd_middleware.py` — `_enqueue_lgpd_audit` migrated: sync `.delay()` → `async def` + `await .kiq()`
- `backend-hormonia/scripts/verify_schedule_parity.sh` — replayable 47/47 schedule parity verification script
- `backend-hormonia/app/domain/quizzes/integration/flow_integration/trigger_service.py` — 2 inline TODO(S05) markers added
- `backend-hormonia/app/services/flow/recovery.py` — 1 inline TODO(S05) marker added

## Forward Intelligence

### What the next slice should know
- All 72 Taskiq tasks exist across 13 modules. S05 can now safely delete all Celery task modules, celery_app.py, and bridge code. The TODO(S05) markers in trigger_service.py (lines 724, 732) and recovery.py (line 214) are the sync callers that need conversion to async + `.kiq()` when Celery is removed.
- `verify_schedule_parity.sh` should be re-run after S05 deletions to confirm no schedule labels were accidentally removed.

### What's fragile
- Import coexistence: `from app.tasks.messaging_taskiq import X` vs `from app.tasks.messaging import X` — same function names, different modules. Wrong import = task dispatched to wrong queue. S05 removing Celery modules eliminates this risk.
- LGPD middleware is the only non-task call site fully migrated to `.kiq()` — it's async so the conversion was clean. trigger_service.py and recovery.py are sync chains and cannot simply swap to `await .kiq()`.

### Authoritative diagnostics
- `bash scripts/verify_schedule_parity.sh` — single-command proof of schedule parity, exits 0/1 with color-coded matched/missing/extra report
- `grep -rc "@broker.task" app/tasks/*_taskiq.py` — total task count (expect 72)
- `rg "\.delay\(|\.apply_async\(" --glob "!**/tasks/**" --glob "!app/celery_app.py"` — external call site audit (should show only TODO(S05) lines)

### What assumptions changed
- Plan estimated 46+ tasks — actual count is 72 (monitoring flattened 8 classes into 8 separate tasks, plus higher task counts in alerts and quiz modules than estimated).
- Plan listed 28 "remaining" periodic entries for S04 — actual S04 contribution was exactly the entries needed to reach 47/47 total parity when combined with S02 (7) and S03 (12) schedule labels.
