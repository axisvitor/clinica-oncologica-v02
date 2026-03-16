# S03: Flow/saga tasks migradas

**Goal:** All 17 flow/saga Celery tasks have async-native Taskiq equivalents — process_daily_flows, flow_automation, saga_retry, stuck_detection, monitoring, cleanup, monthly, and retry tasks — with 12 schedule labels, no bridge code, and external call sites wired to Taskiq dispatch where safe.
**Demo:** `grep -c "@broker.task" flows_taskiq.py` = 14, `saga_retry_taskiq.py` = 3. `grep "async_to_sync\|run_async" flows_taskiq.py saga_retry_taskiq.py` = 0 matches. External callers (response_handler.py) dispatch via `await .kiq()`.

## Must-Haves

- `flows_taskiq.py` with 14 async-native Taskiq tasks (all flow domain tasks)
- `saga_retry_taskiq.py` with 3 async-native Taskiq saga tasks
- 12 schedule labels for periodic tasks (cron and interval)
- Zero bridge code (`async_to_sync`, `run_async`, `run_async_in_sync`, `run_async_in_thread`) in new files
- Zero Celery dispatch (`.delay()`, `.apply_async()`) in new Taskiq task files
- SmartRetryMiddleware labels for tasks that had `self.retry()`
- Pure helpers imported from Celery modules — no duplication
- External call sites in async contexts updated to Taskiq dispatch
- Celery originals intact for coexistence (S05 deletes them)

## Proof Level

- This slice proves: contract (code parity with Celery tasks, async-native, no bridges)
- Real runtime required: no (runtime proof deferred to S06)
- Human/UAT required: no

## Verification

- `python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/flows_taskiq.py').read()); print('OK')"` — passes
- `python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/saga_retry_taskiq.py').read()); print('OK')"` — passes
- `grep -c "@broker.task" backend-hormonia/app/tasks/flows_taskiq.py` = 14
- `grep -c "@broker.task" backend-hormonia/app/tasks/saga_retry_taskiq.py` = 3
- `grep -c "schedule=" backend-hormonia/app/tasks/flows_taskiq.py backend-hormonia/app/tasks/saga_retry_taskiq.py` = 12
- `grep -c "async_to_sync\|run_async\|run_async_in_sync\|run_async_in_thread" backend-hormonia/app/tasks/flows_taskiq.py backend-hormonia/app/tasks/saga_retry_taskiq.py` = 0
- `grep -c "\.delay(\|\.apply_async(" backend-hormonia/app/tasks/flows_taskiq.py backend-hormonia/app/tasks/saga_retry_taskiq.py` = 0
- Celery originals intact: `grep -c "@celery_app.task" backend-hormonia/app/tasks/flow_automation.py backend-hormonia/app/tasks/saga_retry.py backend-hormonia/app/tasks/flows/flow_tasks.py backend-hormonia/app/tasks/flows/stuck_detection.py backend-hormonia/app/tasks/flows/monitoring.py backend-hormonia/app/tasks/flows/monthly_tasks.py backend-hormonia/app/tasks/flows/cleanup_tasks.py backend-hormonia/app/tasks/flows/followup_retry.py backend-hormonia/app/tasks/flows/send_retry.py` = unchanged
- `response_handler.py:470` dispatches via Taskiq (no `.delay()`)
- All modified external call site files pass AST parse

## Observability / Diagnostics

- Runtime signals: `log_task_start/success/error` with structured fields (task_name, event, duration_ms, error_type) for all 17 tasks
- Inspection surfaces: `grep "@broker.task" flows_taskiq.py saga_retry_taskiq.py` for task inventory; `grep "schedule=" ...` for schedule entries
- Failure visibility: SmartRetryMiddleware logs "Retrying N/M in X.XX seconds" on retry; task error logs include error_type and traceback
- Redaction constraints: patient_id logged as UUID string only, no PII in task logs

## Integration Closure

- Upstream surfaces consumed: `app/taskiq_broker.py` (broker instance, dynamic_schedule_source), `app/tasks/taskiq_base.py` (DbSession, log_task_start/success/error, schedule_task_at), `app/tasks/messaging_taskiq.py` (send_scheduled_message for cross-task dispatch)
- New wiring introduced in this slice: `flows_taskiq.py` and `saga_retry_taskiq.py` as new task modules; `response_handler.py` import switched to Taskiq
- What remains before the milestone is truly usable end-to-end: S04 (remaining quiz/alert/monitoring tasks + complete schedule), S05 (Celery removal), S06 (e2e verification)

## Tasks

- [ ] **T01: Create flows_taskiq.py with process_daily_flows + flow_automation + monthly tasks (8 tasks)** `est:45m`
  - Why: These 8 tasks are the core flow domain — process_daily_flows is the daily patient loop, flow_automation handles pending/paused flows and reminders, monthly handles quizzes. This is the bulk of R080.
  - Files: `backend-hormonia/app/tasks/flows_taskiq.py` (NEW), `backend-hormonia/app/tasks/flows/flow_tasks.py` (read), `backend-hormonia/app/tasks/flow_automation.py` (read), `backend-hormonia/app/tasks/flows/monthly_tasks.py` (read), `backend-hormonia/app/tasks/flows/batch_tasks.py` (read), `backend-hormonia/app/tasks/messaging_taskiq.py` (reference)
  - Do: Create `flows_taskiq.py` following S02 pattern. Translate 8 Celery tasks to async Taskiq tasks with `@broker.task`, `DbSession`, schedule labels. `process_daily_flows` uses `process_daily_flows_async()` as task body directly (the function is already async). Import pure helpers from Celery modules without duplication. For `send_daily_reminders`, use `await send_scheduled_message.kiq()` from `messaging_taskiq` instead of Celery `.delay()`. Batch helpers (`_process_single_patient_flow_by_id`, etc.) are sync and manage their own sessions — import and call from Taskiq task without modification.
  - Verify: `python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/flows_taskiq.py').read())"` passes; `grep -c "@broker.task" flows_taskiq.py` = 8; `grep -c "schedule=" flows_taskiq.py` = 6; `grep -c "async_to_sync\|run_async" flows_taskiq.py` = 0
  - Done when: 8 `@broker.task` tasks with 6 schedule labels, zero bridge code, AST-valid Python

- [ ] **T02: Add stuck_detection, monitoring, cleanup, and retry tasks to flows_taskiq.py (6 tasks)** `est:35m`
  - Why: Completes the 14 flow-domain tasks in flows_taskiq.py. Covers stuck_detection (sync service constraint), monitoring (health/alerts), cleanup, and the retry tasks (send_retry, followup_retry) that translate self.retry() → SmartRetryMiddleware.
  - Files: `backend-hormonia/app/tasks/flows_taskiq.py` (append), `backend-hormonia/app/tasks/flows/stuck_detection.py` (read), `backend-hormonia/app/tasks/flows/monitoring.py` (read), `backend-hormonia/app/tasks/flows/cleanup_tasks.py` (read), `backend-hormonia/app/tasks/flows/send_retry.py` (read), `backend-hormonia/app/tasks/flows/followup_retry.py` (read)
  - Do: Append 6 tasks to flows_taskiq.py. `detect_stuck_flows` uses `get_scoped_session()` for sync `find_stuck_flows(db)` and `attempt_recovery(db)` — these are sync-only services. `attempt_recovery()` internally calls Celery `.delay()` — this stays during coexistence (S05 cleanup). `retry_failed_flow_send` and `retry_failed_followup_send` translate `self.retry(countdown=)` to `SmartRetryMiddleware` labels (`retry_on_error=True, max_retries=N, delay=N`). Monitoring tasks (`monitor_flow_task_health`, `evaluate_flow_alerts`) become direct async with no `run_async_in_sync/thread` bridge.
  - Verify: `grep -c "@broker.task" flows_taskiq.py` = 14; `grep -c "schedule=" flows_taskiq.py` = 10; `grep -c "async_to_sync\|run_async_in_sync\|run_async_in_thread" flows_taskiq.py` = 0; `grep -c "\.delay(\|\.apply_async(" flows_taskiq.py` = 0
  - Done when: 14 total `@broker.task` tasks, 10 schedule labels, zero bridge code, zero Celery dispatch in flows_taskiq.py, AST-valid

- [ ] **T03: Create saga_retry_taskiq.py with 3 saga tasks** `est:25m`
  - Why: Saga domain is a separate concern — 3 tasks in a separate file. `retry_patient_onboarding_saga` has custom exponential backoff, `scan_and_retry_failed_sagas` dispatches via `.apply_async(countdown=)` → `schedule_task_at()`.
  - Files: `backend-hormonia/app/tasks/saga_retry_taskiq.py` (NEW), `backend-hormonia/app/tasks/saga_retry.py` (read)
  - Do: Create `saga_retry_taskiq.py` with 3 tasks. `retry_patient_onboarding_saga`: SmartRetryMiddleware replaces `self.retry(countdown=60*(2**retries))`. `scan_and_retry_failed_sagas`: switch `.apply_async(countdown=)` to `await schedule_task_at()` for delayed dispatch of retry tasks. `cleanup_old_completed_sagas`: simple async DB cleanup. `SagaOrchestrator.resume_saga()` called with `await` directly (no `run_async` bridge).
  - Verify: `python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/saga_retry_taskiq.py').read())"` passes; `grep -c "@broker.task" saga_retry_taskiq.py` = 3; `grep -c "schedule=" saga_retry_taskiq.py` = 2; zero bridge code, zero Celery dispatch
  - Done when: 3 `@broker.task` tasks, 2 schedule labels, zero bridge code, AST-valid

- [ ] **T04: Wire external call sites and run slice verification** `est:20m`
  - Why: External service files dispatch flow tasks via Celery `.delay()`/`.apply_async()`. Async callers must switch to Taskiq. Sync callers (`recovery.py`) stay on Celery during coexistence. Final verification proves slice-level acceptance.
  - Files: `backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py`, `backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py`, `backend-hormonia/app/services/follow_up_system/execution/message.py`, `backend-hormonia/app/services/flow/recovery.py`
  - Do: (1) `response_handler.py:470` — async method, switch `generate_quiz_report.delay()` to `await generate_quiz_report.kiq()` from `flows_taskiq`. (2) `delivery.py:92` — sync function using `.apply_async(countdown=)`, convert to async and use `await schedule_task_at(retry_failed_flow_send, ...)` from `flows_taskiq`. (3) `message.py:81` — sync method using `.apply_async(countdown=)`, convert to async and use `await schedule_task_at(retry_failed_followup_send, ...)` from `flows_taskiq`. (4) `recovery.py:211` — sync function deep inside `attempt_recovery()`, KEEP Celery `.delay()` during coexistence (defer to S05). Run comprehensive verification script for all slice acceptance checks.
  - Verify: All 4 call-site files AST-parse; `grep "from app.tasks.flows_taskiq import" response_handler.py delivery.py message.py` shows Taskiq imports; `grep "\.delay\|\.apply_async" response_handler.py delivery.py message.py` = 0 for flow task calls; `recovery.py` still has `.delay()` (intentional coexistence); all slice-level checks pass (17 tasks, 12 schedules, 0 bridges, 0 Celery dispatch in Taskiq files)
  - Done when: 3 of 4 external call sites on Taskiq dispatch, recovery.py documented for S05, all slice verification checks pass

## Files Likely Touched

- `backend-hormonia/app/tasks/flows_taskiq.py` (NEW — ~1800-2200 lines, 14 tasks)
- `backend-hormonia/app/tasks/saga_retry_taskiq.py` (NEW — ~400-500 lines, 3 tasks)
- `backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py` (call site update)
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py` (call site update)
- `backend-hormonia/app/services/follow_up_system/execution/message.py` (call site update)
