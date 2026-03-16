# S04: Quiz/alert/follow-up/monitoring migradas + schedule completo

**Goal:** All remaining Celery tasks (quiz, alerts, follow-up, LGPD, audit, webhook DLQ, monitoring, reports, saga monitoring) have Taskiq equivalents, all 47 beat_schedule entries are covered by Taskiq schedule labels, and external call sites (.delay()/.apply_async()) are migrated to .kiq().

**Demo:** `grep -rc "@broker.task" app/tasks/*_taskiq.py` shows 46+ tasks across all modules; a schedule parity script confirms all 47 beat_schedule entries have matching Taskiq schedule labels; `rg "\.delay\(|\.apply_async\(" --glob "!**/tasks/*.py"` shows zero external call sites still using Celery dispatch (only Celery task modules themselves, which S05 deletes).

## Must-Haves

- 10 new `*_taskiq.py` modules created with all tasks from their Celery counterparts
- All 28 remaining periodic beat_schedule entries have matching Taskiq schedule labels
- Cron schedules correctly converted from BRT (America/Sao_Paulo) to UTC (+3 hours)
- `_enqueue_lgpd_audit` in LGPD middleware migrated from `.delay()` to `await .kiq()`
- Cross-task dispatch uses Taskiq imports: follow_up→alerts_taskiq, quiz_flow→quiz_link_taskiq, reports→reports_taskiq
- Sync ORM services wrapped in `get_scoped_session()` per D009 — no service rewrites
- Pure helper functions imported from Celery modules — no duplication per D007
- Sync call sites in trigger_service.py and recovery.py marked with `TODO(S05)` — kept on Celery per D010

## Proof Level

- This slice proves: contract (all tasks defined, all schedules mapped, all external call sites migrated)
- Real runtime required: no (syntax/import validation + schedule parity audit)
- Human/UAT required: no

## Verification

- `python3 -c "import ast; [ast.parse(open(f).read()) for f in __import__('glob').glob('app/tasks/*_taskiq.py')]"` — all 13 taskiq modules parse cleanly
- `bash scripts/verify_schedule_parity.sh` — script comparing all 47 beat_schedule entries against Taskiq schedule labels, outputting matched/missing/extra
- `rg "\.delay\(|\.apply_async\(" --glob "*.py" --glob "!app/tasks/*.py" --glob "!app/celery_app.py" --glob "!**/test*" backend-hormonia/` — zero matches in non-task code (middleware, services, domain)
- `grep -rc "@broker.task" app/tasks/*_taskiq.py | awk -F: '{s+=$2}END{print s}'` — total ≥ 46 tasks across all taskiq modules

## Observability / Diagnostics

- Runtime signals: Each task uses `log_task_start/success/error` with structured `task_name`, `event`, `duration_ms` fields
- Inspection surfaces: Schedule labels on `@broker.task()` decorators; `taskiq scheduler` reads all labels at startup
- Failure visibility: `SmartRetryMiddleware` logs retry attempts with count/delay; `log_task_error` captures error_type and error_message
- Redaction constraints: LGPD tasks redact PII fields; alert tasks redact `_ALERT_METADATA_REDACTED_FIELDS`

## Integration Closure

- Upstream surfaces consumed: `app/taskiq_broker.py` (broker, scheduler), `app/tasks/taskiq_base.py` (DbSession, log helpers, schedule_task_at), `app/tasks/messaging_taskiq.py` (send_scheduled_message for cross-dispatch)
- New wiring introduced in this slice: 10 new `*_taskiq.py` modules registered in scheduler via decorator labels; LGPD middleware wired to `lgpd_taskiq.py`
- What remains before the milestone is truly usable end-to-end: S05 removes Celery code, S06 verifies e2e pipeline

## Tasks

- [ ] **T01: Migrate simple sync-ORM modules (audit, lgpd, reports, saga_monitoring) + LGPD middleware call site** `est:1.5h`
  - Why: Covers 4 simplest modules (11 tasks, 9 periodic entries) using pure `get_scoped_session()` sync ORM. Establishes velocity with lowest-risk work. Includes LGPD middleware `.delay()` → `.kiq()` migration.
  - Files: `backend-hormonia/app/tasks/audit_taskiq.py` (new), `backend-hormonia/app/tasks/lgpd_taskiq.py` (new), `backend-hormonia/app/tasks/reports_taskiq.py` (new), `backend-hormonia/app/tasks/saga_monitoring_taskiq.py` (new), `backend-hormonia/app/middleware/lgpd_middleware.py`
  - Do: Create 4 parallel `*_taskiq.py` modules. Import pure helpers from Celery modules. Use `get_scoped_session()` for sync ORM services (D009). Convert BRT cron → UTC (+3h). Migrate `_enqueue_lgpd_audit` from `.delay()` to `await .kiq()` (middleware is async). For reports, `generate_scheduled_reports` dispatches `generate_patient_report` — both must be Taskiq tasks with `.kiq()` cross-dispatch.
  - Verify: `python3 -c "import ast; ast.parse(open('app/tasks/audit_taskiq.py').read()); ast.parse(open('app/tasks/lgpd_taskiq.py').read()); ast.parse(open('app/tasks/reports_taskiq.py').read()); ast.parse(open('app/tasks/saga_monitoring_taskiq.py').read())"` passes; 11 `@broker.task` decorators across 4 files; 9 `schedule=` entries present; middleware imports from `lgpd_taskiq` not `lgpd_tasks`
  - Done when: 4 new taskiq modules with 11 tasks, 9 schedule labels, LGPD middleware migrated to `.kiq()`, all files parse

- [ ] **T02: Migrate medium complexity modules (alerts, webhook_dlq, monitoring)** `est:2h`
  - Why: Covers 3 modules (18 tasks, 12 periodic entries) with `async_to_sync`/`run_async` bridge removal and MonitoringTask class flattening. Internal cross-dispatch in alerts (`process_alert_escalation`) handled within module.
  - Files: `backend-hormonia/app/tasks/alerts_taskiq.py` (new), `backend-hormonia/app/tasks/webhook_dlq_taskiq.py` (new), `backend-hormonia/app/tasks/monitoring_taskiq.py` (new)
  - Do: Create 3 parallel `*_taskiq.py` modules. Alerts: remove `async_to_sync` wrappers, call alert_manager methods with `await` directly. Webhook DLQ: remove `run_async()`, call async DLQ service directly, drop `_retry_or_raise` helper (SmartRetryMiddleware handles it). Monitoring: flatten 8 MonitoringTask subclasses into 8 `@broker.task()` async functions — remove `run_async()` for async services, use `get_scoped_session()` for sync constructors (FlowStateRepository, etc). All use structured logging from `taskiq_base`.
  - Verify: `python3 -c "import ast; ast.parse(open('app/tasks/alerts_taskiq.py').read()); ast.parse(open('app/tasks/webhook_dlq_taskiq.py').read()); ast.parse(open('app/tasks/monitoring_taskiq.py').read())"` passes; 18 `@broker.task` decorators across 3 files; 12 `schedule=` entries present; zero `async_to_sync` or `run_async` imports
  - Done when: 3 new taskiq modules with 18 tasks, 12 schedule labels, no sync-async bridges, monitoring classes flattened

- [ ] **T03: Migrate complex modules (quiz_link, quiz_flow, follow_up)** `est:2h`
  - Why: Covers 3 modules (17 tasks, 7 periodic entries) with the heaviest bridge usage, cross-module dispatch chains, and custom retry patterns. quiz_flow dispatches to quiz_link (send_quiz_reminder), follow_up dispatches to alerts_taskiq (process_alert_notification). Consolidates 4 quiz_flow subpackage files into single `quiz_flow_taskiq.py`.
  - Files: `backend-hormonia/app/tasks/quiz_link_taskiq.py` (new), `backend-hormonia/app/tasks/quiz_flow_taskiq.py` (new), `backend-hormonia/app/tasks/follow_up_taskiq.py` (new)
  - Do: Create 3 parallel `*_taskiq.py` modules. quiz_link: import pure helpers (`_sanitize_limit`, `_token_fingerprint`, `_sanitize_error_message`, `_sanitize_dlq_record`) from Celery module; `send_quiz_reminder` custom retry → SmartRetryMiddleware; distributed lock usage preserved. quiz_flow: consolidate 4 subpackage files (cleanup, trigger, response, question) into single module; cross-dispatch to `send_quiz_reminder` from `quiz_link_taskiq`; trigger_service.py sync caller keeps Celery `.apply_async()` with `TODO(S05)` marker per D010. follow_up: remove 15+ `async_to_sync()` calls → direct `await` on FollowUpSystemService; cross-dispatch to `process_alert_notification` from `alerts_taskiq.py`; import pure helpers from Celery module.
  - Verify: `python3 -c "import ast; ast.parse(open('app/tasks/quiz_link_taskiq.py').read()); ast.parse(open('app/tasks/quiz_flow_taskiq.py').read()); ast.parse(open('app/tasks/follow_up_taskiq.py').read())"` passes; 17 `@broker.task` decorators across 3 files; 7 `schedule=` entries present; cross-imports use `*_taskiq` modules; zero `async_to_sync` or `run_async` imports
  - Done when: 3 new taskiq modules with 17 tasks, 7 schedule labels, cross-module dispatch via Taskiq, no sync-async bridges

- [ ] **T04: Schedule parity verification + call site audit** `est:30m`
  - Why: Final validation that all 47 beat_schedule entries are covered and no external call sites still use Celery dispatch. This is the proof that R082 (schedule parity) is met.
  - Files: `backend-hormonia/scripts/verify_schedule_parity.sh` (new)
  - Do: Create verification script that: (1) extracts all 47 beat_schedule task names from celery_app.py, (2) extracts all schedule labels from `*_taskiq.py` files, (3) maps Celery task names to Taskiq function names, (4) reports matched/missing/extra. Run the script and fix any gaps. Run `rg "\.delay\(|\.apply_async\(" --glob "*.py"` to audit remaining call sites — external ones should be zero (except trigger_service.py and recovery.py marked `TODO(S05)`). Count total `@broker.task` across all modules.
  - Verify: `bash scripts/verify_schedule_parity.sh` exits 0 with 47/47 matched; `rg "\.delay\(|\.apply_async\(" --glob "*.py" --glob "!app/tasks/*.py" --glob "!app/celery_app.py"` shows only TODO(S05)-marked lines (trigger_service.py, recovery.py)
  - Done when: 47/47 schedule parity confirmed, all external call sites migrated or marked TODO(S05), verification script committed

## Files Likely Touched

- `backend-hormonia/app/tasks/audit_taskiq.py` (new)
- `backend-hormonia/app/tasks/lgpd_taskiq.py` (new)
- `backend-hormonia/app/tasks/reports_taskiq.py` (new)
- `backend-hormonia/app/tasks/saga_monitoring_taskiq.py` (new)
- `backend-hormonia/app/tasks/alerts_taskiq.py` (new)
- `backend-hormonia/app/tasks/webhook_dlq_taskiq.py` (new)
- `backend-hormonia/app/tasks/monitoring_taskiq.py` (new)
- `backend-hormonia/app/tasks/quiz_link_taskiq.py` (new)
- `backend-hormonia/app/tasks/quiz_flow_taskiq.py` (new)
- `backend-hormonia/app/tasks/follow_up_taskiq.py` (new)
- `backend-hormonia/app/middleware/lgpd_middleware.py` (modified — `.delay()` → `.kiq()`)
- `backend-hormonia/scripts/verify_schedule_parity.sh` (new)
