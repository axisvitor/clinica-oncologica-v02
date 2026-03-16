# S03 — Research

**Date:** 2026-03-16

## Summary

S03 migrates all flow/saga Celery tasks to Taskiq — 17 tasks across 9 source files (~3300 lines). The migration pattern is fully proven by S02: async task body with `@broker.task`, `DbSession` for async DB, SmartRetryMiddleware for retry, schedule labels for periodic dispatch, and `schedule_task_at()` for ETA/delayed dispatch. No new technology or unknown patterns are involved.

The main complexity is volume (17 tasks) and two structural constraints: (1) several flow services (`FlowStateRepository`, `find_stuck_flows`, `attempt_recovery`) are sync-only and require `get_scoped_session()` even in Taskiq tasks, and (2) `process_daily_flows_async()` is already a well-structured async function that can become the Taskiq task body directly, but its internal helper `_process_single_patient_flow` calls `send_scheduled_message.delay()` which must switch to `await send_scheduled_message.kiq()` from `messaging_taskiq`. Four external service call sites also need to switch imports from Celery flow tasks to Taskiq flow tasks.

## Recommendation

Follow the D007 parallel-module strategy from S02: create `flows_taskiq.py` (all flow/batch/monitoring/cleanup/retry tasks) and `saga_retry_taskiq.py` (saga tasks) alongside existing Celery modules, then wire external call sites. Build process_daily_flows first (the core daily loop and most complex task), then the simpler periodic/on-demand tasks, then the saga domain, then external call sites.

## Implementation Landscape

### Key Files — Source (Celery tasks to translate)

- `backend-hormonia/app/tasks/flows/flow_tasks.py` (379 lines) — `process_daily_flows` Celery wrapper + `process_daily_flows_async()` (the async function that does real work). Uses `async_to_sync` bridge, `get_scoped_session()`, delegates to `_process_single_patient_flow_by_id`.
- `backend-hormonia/app/tasks/flows/batch_tasks.py` (637 lines) — Helper functions `_process_single_patient_flow_by_id`, `_process_single_patient_flow`, `_get_message_template_for_day`, `_update_scheduling`. All use `get_scoped_session()` sync sessions. `_process_single_patient_flow` calls `send_scheduled_message.delay()` at line 348.
- `backend-hormonia/app/tasks/flow_automation.py` (637 lines) — 5 Celery tasks: `check_and_start_pending_flows`, `send_daily_reminders`, `resume_paused_flows`, `cleanup_expired_quiz_links`, `send_flow_day_for_patient`. All use `async_to_sync(_process)()` pattern with sync sessions inside. `send_daily_reminders` calls `send_scheduled_message.delay()` at line 265.
- `backend-hormonia/app/tasks/saga_retry.py` (567 lines) — 3 Celery tasks: `retry_patient_onboarding_saga` (bound with self.retry), `scan_and_retry_failed_sagas`, `cleanup_old_completed_sagas`. Uses `run_async()` bridge for `SagaOrchestrator.resume_saga()`. `scan_and_retry_failed_sagas` uses `.apply_async(countdown=)` for delayed dispatch.
- `backend-hormonia/app/tasks/flows/stuck_detection.py` (86 lines) — `detect_stuck_flows` task. Uses `get_scoped_session()` + sync `find_stuck_flows(db)` + sync `attempt_recovery(db)`.
- `backend-hormonia/app/tasks/flows/monitoring.py` (189 lines) — `monitor_flow_task_health`, `evaluate_flow_alerts`. Uses `run_async_in_sync()`/`run_async_in_thread()` bridges.
- `backend-hormonia/app/tasks/flows/monthly_tasks.py` (168 lines) — `process_monthly_quizzes`, `generate_quiz_report`. Uses `run_async()` bridge.
- `backend-hormonia/app/tasks/flows/cleanup_tasks.py` (131 lines) — `cleanup_old_flow_data`. Pure sync DB operations.
- `backend-hormonia/app/tasks/flows/followup_retry.py` (151 lines) — `retry_failed_followup_send`. Bound task with `self.retry(countdown=)` + `MaxRetriesExceededError` handling. Uses `async_to_sync()`.
- `backend-hormonia/app/tasks/flows/send_retry.py` (210 lines) — `retry_failed_flow_send`. Bound task with `self.retry(countdown=)` + `MaxRetriesExceededError` handling. Uses `async_to_sync()`.
- `backend-hormonia/app/tasks/flows/base.py` (149 lines) — `FlowTaskBase` (Celery Task subclass with Redis result tracking), `send_critical_alert_sync`. Not needed in Taskiq — SmartRetryMiddleware + result backend replace this.

### Key Files — Target (new Taskiq modules to create)

- `backend-hormonia/app/tasks/flows_taskiq.py` — NEW: All 14 flow domain Taskiq tasks (process_daily_flows, flow_automation tasks, monitoring, cleanup, stuck detection, monthly, send_retry, followup_retry). Single file following S02 pattern.
- `backend-hormonia/app/tasks/saga_retry_taskiq.py` — NEW: 3 saga Taskiq tasks (retry_patient_onboarding_saga, scan_and_retry_failed_sagas, cleanup_old_completed_sagas).

### Key Files — Call sites to update

- `backend-hormonia/app/services/flow/recovery.py:211` — `retry_failed_flow_send.delay(prompt_message_id, ...)` → import from Taskiq module, use `await .kiq()`
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py:92` — `retry_failed_flow_send.apply_async(args=[...], countdown=...)` → `await schedule_task_at()`
- `backend-hormonia/app/services/follow_up_system/execution/message.py:81` — `retry_failed_followup_send.apply_async(...)` → `await schedule_task_at()`
- `backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py:470` — `generate_quiz_report.delay(...)` → `await .kiq()`

### Key Files — Reference (established patterns)

- `backend-hormonia/app/tasks/messaging_taskiq.py` (1237 lines) — S02 reference for all translation patterns
- `backend-hormonia/app/tasks/taskiq_base.py` — `DbSession`, `log_task_start/success/error`, `schedule_task_at()`
- `backend-hormonia/app/taskiq_broker.py` — broker instance, `dynamic_schedule_source`

### Complete Task Inventory (17 tasks)

**12 scheduled (periodic):**

| # | Task Name | Source File | Schedule | Bridge Pattern |
|---|-----------|-------------|----------|---------------|
| 1 | `process_daily_flows` | flows/flow_tasks.py | cron 8:00 | async_to_sync wrapping process_daily_flows_async |
| 2 | `check_and_start_pending_flows` | flow_automation.py | 900s interval | async_to_sync + sync DB |
| 3 | `send_daily_reminders` | flow_automation.py | cron 9:00 | async_to_sync + sync DB, calls send_scheduled_message.delay |
| 4 | `resume_paused_flows` | flow_automation.py | 3600s interval | async_to_sync + sync DB |
| 5 | `cleanup_expired_quiz_links` | flow_automation.py | 86400s interval | async_to_sync + sync DB (pure SQL) |
| 6 | `detect_stuck_flows` | flows/stuck_detection.py | 900s interval | sync only (find_stuck_flows + attempt_recovery are sync) |
| 7 | `monitor_flow_task_health` | flows/monitoring.py | 300s interval | run_async_in_sync/thread for Gemini health check |
| 8 | `evaluate_flow_alerts` | flows/monitoring.py | 900s interval | run_async_in_sync for FlowAlertsService |
| 9 | `process_monthly_quizzes` | flows/monthly_tasks.py | 3600s interval | run_async bridge |
| 10 | `cleanup_old_flow_data` | flows/cleanup_tasks.py | 86400s interval | pure sync DB |
| 11 | `scan_and_retry_failed_sagas` | saga_retry.py | 300s interval | sync DB, dispatches via .apply_async(countdown=) |
| 12 | `cleanup_old_completed_sagas` | saga_retry.py | 86400s interval | sync DB |

**5 on-demand (dispatched by other code):**

| # | Task Name | Source File | Retry Pattern | Dispatched By |
|---|-----------|-------------|---------------|---------------|
| 13 | `send_flow_day_for_patient` | flow_automation.py | autoretry_for (via task options) | Manual/API |
| 14 | `retry_patient_onboarding_saga` | saga_retry.py | self.retry(countdown=60*(2^retries)) | scan_and_retry_failed_sagas |
| 15 | `generate_quiz_report` | flows/monthly_tasks.py | self.retry(countdown=) | response_handler.py |
| 16 | `retry_failed_flow_send` | flows/send_retry.py | self.retry(countdown=) + MaxRetriesExceededError | recovery.py, delivery.py |
| 17 | `retry_failed_followup_send` | flows/followup_retry.py | self.retry(countdown=) + MaxRetriesExceededError | message.py |

### Sync Service Constraints

These services/functions are **sync-only** and require `get_scoped_session()` even in Taskiq tasks:

- `find_stuck_flows(db: Session)` in `app/services/flow/recovery.py` — sync ORM queries
- `attempt_recovery(db: Session, ...)` in `app/services/flow/recovery.py` — sync ORM, calls `retry_failed_flow_send.delay()` internally (this call site also needs migration)
- `FlowStateRepository(db: Session)` in `app/repositories/flow.py` — inherits BaseRepository with sync Session
- `batch_tasks._get_message_template_for_day(db: Session, ...)` — sync ORM queries
- `FlowManagementService(flow_repo, db)` — sync

These services accept `Any` and work with both sync/async sessions:

- `EnhancedFlowEngine(db: Any)` — `get_enhanced_flow_engine(db)` factory
- `SagaOrchestrator(db: Any, redis_client=)` — designed for both paths
- `FlowAlertsService(db: Any)` — has async methods, accepts Any
- `UnifiedWhatsAppService(db)` — accepts Any

### Build Order

**Phase 1: Core flow task + batch helpers** — Create `flows_taskiq.py` starting with `process_daily_flows`. The key transformation: `process_daily_flows_async()` becomes the Taskiq task body directly (no `async_to_sync` wrapper). `_process_single_patient_flow_by_id` already creates its own session via `get_scoped_session()` — this stays sync because `FlowStateRepository` and `_get_message_template_for_day` are sync. The critical change: `send_scheduled_message.delay()` at line 348 of `batch_tasks.py` must switch to `await send_scheduled_message.kiq()` from `messaging_taskiq`. Same for line 265 of `flow_automation.py`. Since helpers are shared, import them from the Celery module (same pattern as S02 importing pure helpers from `messaging.py`).

**Phase 2: Remaining flow tasks** — Add the remaining 11 flow tasks to `flows_taskiq.py`: flow_automation tasks (5), stuck_detection (1), monitoring (2), cleanup (1), send_retry (1), followup_retry (1), monthly_tasks (2). Translation pattern: remove `async_to_sync`/`run_async` bridges, make task body directly async, replace `self.retry()` with SmartRetryMiddleware labels + raise, add schedule labels for periodic tasks.

**Phase 3: Saga tasks** — Create `saga_retry_taskiq.py` with 3 saga tasks. Key changes: `retry_patient_onboarding_saga` loses `self.retry()` (SmartRetryMiddleware handles it), `scan_and_retry_failed_sagas` switches `.apply_async(countdown=)` to `await schedule_task_at()`, `SagaOrchestrator.resume_saga()` is called with `await` directly (no `run_async` bridge).

**Phase 4: External call sites** — Wire 4 external service call sites to import from Taskiq modules and use `await .kiq()`/`schedule_task_at()`.

### Verification Approach

1. **AST parse** all new files — confirms no syntax errors
2. **Task count**: `grep -c "@broker.task" flows_taskiq.py` = 14, `saga_retry_taskiq.py` = 3 (total 17)
3. **Schedule count**: `grep -c "schedule=" flows_taskiq.py saga_retry_taskiq.py` = 12
4. **No bridge code**: `grep -c "async_to_sync\|run_async\|run_async_in_sync\|run_async_in_thread" flows_taskiq.py saga_retry_taskiq.py` = 0
5. **No Celery dispatch**: `grep -c "\.delay(\|\.apply_async(" flows_taskiq.py saga_retry_taskiq.py` = 0
6. **Celery originals intact**: `grep -c "@celery_app.task" flow_automation.py saga_retry.py flows/flow_tasks.py flows/stuck_detection.py flows/monitoring.py flows/monthly_tasks.py flows/cleanup_tasks.py flows/followup_retry.py flows/send_retry.py` = unchanged (17 total)
7. **External call sites**: No `.delay()` or `.apply_async()` in the 4 updated service files for flow task calls
8. **Coexistence**: Celery tasks remain intact for any callers not yet migrated (S05 deletes them)

## Constraints

- `find_stuck_flows(db)` and `attempt_recovery(db, ...)` in `recovery.py` are sync functions that accept `Session`. The `detect_stuck_flows` Taskiq task must use `get_scoped_session()` for these, not `DbSession` (AsyncSession). Same isolation pattern as DLQ in S02.
- `FlowStateRepository` and `_get_message_template_for_day` are sync-Session-only. `_process_single_patient_flow_by_id` (called by process_daily_flows) already creates its own sync session — this pattern stays.
- `attempt_recovery()` internally calls `retry_failed_flow_send.delay()` at line 211 of `recovery.py`. This is an external call site that S03 must update to Taskiq dispatch, BUT `attempt_recovery` is a sync function. Converting `.delay()` to `await .kiq()` requires making it async or using a sync dispatch helper. This needs careful handling.
- Pure helper functions (`_determine_template_for_patient`, `_get_reminder_message`, `_is_auto_resume_due`, `_calculate_exponential_backoff`, `_normalize_template_day`, etc.) should be imported from the Celery modules — no duplication (same as S02 pattern).

## Common Pitfalls

- **batch_tasks helpers are shared between process_daily_flows (Taskiq) and flow_automation tasks (Celery during coexistence)** — Don't modify the Celery batch_tasks.py file. Import helpers from it into Taskiq tasks. Only the `send_scheduled_message.delay()` call inside `_process_single_patient_flow` needs a Taskiq equivalent (create a separate async version of the dispatch path or pass a dispatch callback).
- **attempt_recovery() is sync but calls .delay()** — This function is called by `detect_stuck_flows` (being migrated) and possibly other sync code. Changing it to async would break other callers. Instead, for the Taskiq version of stuck_detection, wrap the dispatch in the Taskiq task level (override the dispatch after calling attempt_recovery, or accept that this particular call stays Celery during coexistence and gets cleaned up in S05).
- **self.retry() with custom countdown formulas** — `retry_patient_onboarding_saga` uses `countdown=60 * (2**self.request.retries)`, `retry_failed_flow_send` uses `countdown = base * (backoff ** retries) + jitter`. SmartRetryMiddleware applies its own backoff. For tasks needing custom countdown (saga), use `retry_on_error=True` + configure `delay` and `max_retries` labels. The exact countdown will differ slightly from Celery (SmartRetryMiddleware applies its own jitter) — functionally equivalent, not identical.
- **process_daily_flows_async creates its own sessions per patient** — The function already spawns per-patient sessions via `_process_single_patient_flow_by_id`. The Taskiq DbSession should NOT be passed down to these helpers — they manage their own lifecycle. The task-level DbSession is only for the initial `FlowStateRepository(db)` call to fetch active flows.

## Open Risks

- **process_daily_flows batch helper session model** — `_process_single_patient_flow_by_id` uses sync `get_scoped_session()`. With Taskiq, the outer task has AsyncSession, but inner helpers use sync sessions independently. This works but means process_daily_flows cannot be fully async-native end-to-end. Acceptable for S03 — full async conversion of FlowStateRepository and batch helpers is out of scope.
- **Volume risk** — 17 tasks is the largest single migration batch. Estimated output file size: ~1800-2200 lines for flows_taskiq.py, ~400-500 lines for saga_retry_taskiq.py. May need to be split into sub-tasks for manageable execution.
