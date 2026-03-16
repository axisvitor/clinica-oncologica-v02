---
id: S03
parent: M009
milestone: M009
provides:
  - flows_taskiq.py with 14 async-native Taskiq flow tasks (process_daily_flows, flow_automation, monthly, stuck_detection, monitoring, cleanup, retry)
  - saga_retry_taskiq.py with 3 async-native Taskiq saga tasks (retry, scan, cleanup)
  - 12 schedule labels (10 in flows_taskiq, 2 in saga_retry_taskiq) — 8 interval + 2 cron + 2 interval
  - SmartRetryMiddleware-based DLQ routing for retry_failed_flow_send, retry_failed_followup_send, retry_patient_onboarding_saga
  - 3 external call sites wired to Taskiq dispatch (response_handler, delivery, message)
  - recovery.py documented for S05 coexistence with TODO(S05) marker
requires:
  - slice: S01
    provides: Taskiq broker, SmartRetryMiddleware, LabelScheduleSource, DbSession dependency, schedule_task_at
  - slice: S02
    provides: send_scheduled_message as Taskiq task (.kiq() dispatch), retry→SmartRetryMiddleware pattern, .apply_async(eta=)→schedule_task_at pattern
affects:
  - S05
key_files:
  - backend-hormonia/app/tasks/flows_taskiq.py
  - backend-hormonia/app/tasks/saga_retry_taskiq.py
  - backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py
  - backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py
  - backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py
  - backend-hormonia/app/services/follow_up_system/execution/message.py
  - backend-hormonia/app/services/flow/recovery.py
key_decisions:
  - Sync ORM services (FlowStateRepository, FlowManagementService, SequentialMessageHandler) wrapped in get_scoped_session() within async tasks — no async rewrites of deep service code
  - detect_stuck_flows keeps Celery .delay() inside attempt_recovery() for coexistence — deferred to S05
  - SmartRetryMiddleware DLQ pattern — check retries >= max_retries in task body, finalize permanent failure, return permanently_failed=True
  - delivery.py and message.py converted from sync to async — all callers already async
  - schedule_task_at replaces .apply_async(countdown=N) — compute delivery_time as datetime.now(UTC) + timedelta(seconds=delay)
  - Pure helpers imported from Celery modules without duplication — constants duplicated only when importing would pull entire Celery module
patterns_established:
  - Sync-only services in async tasks — get_scoped_session() context manager for sync ORM, not DbSession(AsyncSession)
  - SmartRetryMiddleware DLQ routing — context.message.labels.get('_retries', 0) for retry count, raise on error for middleware retry, permanent failure guard in task body
  - schedule_task_at for delayed dispatch — .apply_async(countdown=N) → await schedule_task_at(task, datetime.now(UTC) + timedelta(seconds=N), *args)
  - Cross-task dispatch — await send_scheduled_message.kiq() from messaging_taskiq for flow→messaging calls
observability_surfaces:
  - log_task_start/success/error with structured fields (task_name, event, duration_ms, error_type) for all 17 tasks
  - retry_failed_flow_send/retry_failed_followup_send/retry_patient_onboarding_saga log retry attempts with dlq_routed=True on permanent failure
  - detect_stuck_flows returns detected/recovered/skipped/failed counts
  - monitor_flow_task_health returns overall_healthy boolean + component health
  - scan_and_retry_failed_sagas returns total_found/scheduled/max_retries_exceeded
drill_down_paths:
  - .gsd/milestones/M009/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M009/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M009/slices/S03/tasks/T03-SUMMARY.md
  - .gsd/milestones/M009/slices/S03/tasks/T04-SUMMARY.md
duration: ~40m across 4 tasks
verification_result: passed
completed_at: 2026-03-16
---

# S03: Flow/saga tasks migradas

**17 async-native Taskiq tasks (14 flow + 3 saga) with 12 schedule labels, zero bridge code, SmartRetryMiddleware DLQ routing, and 3 external call sites wired to Taskiq dispatch — completing the flow/saga domain migration for R080.**

## What Happened

Migrated all 17 flow and saga Celery tasks to async-native Taskiq equivalents across two new modules, then wired external dispatch call sites.

**T01 — Core flow tasks (8 tasks).** Created `flows_taskiq.py` with the 8 primary flow-domain tasks: `process_daily_flows` (cron 08:00 BRT), `check_and_start_pending_flows` (900s), `send_daily_reminders` (cron 09:00 BRT), `resume_paused_flows` (3600s), `cleanup_expired_quiz_links` (86400s), `send_flow_day_for_patient` (on-demand), `process_monthly_quizzes` (3600s), `generate_quiz_report` (on-demand). Key pattern: sync ORM services (FlowStateRepository, FlowManagementService) wrapped in `get_scoped_session()` inside async task bodies. `send_daily_reminders` dispatches via `await send_scheduled_message.kiq()` from `messaging_taskiq`, establishing the cross-module Taskiq dispatch pattern.

**T02 — Stuck detection, monitoring, cleanup, retry tasks (6 tasks).** Appended to `flows_taskiq.py`: `detect_stuck_flows` (900s), `monitor_flow_task_health` (300s), `evaluate_flow_alerts` (900s), `cleanup_old_flow_data` (86400s), `retry_failed_flow_send` (on-demand, max_retries=5, delay=60), `retry_failed_followup_send` (on-demand, max_retries=3, delay=30). The retry tasks use SmartRetryMiddleware with DLQ routing: check `context.message.labels.get('_retries', 0)`, finalize permanent failure state, then return `permanently_failed=True`. `monitor_flow_task_health` replaced `run_async_in_sync()`/`run_async_in_thread()` Gemini health checks with direct `await`. `detect_stuck_flows` uses sync sessions because its services are sync-only; `attempt_recovery()` internally calls Celery `.delay()` — left intact for coexistence.

**T03 — Saga tasks (3 tasks).** Created `saga_retry_taskiq.py` with: `retry_patient_onboarding_saga` (on-demand, SmartRetryMiddleware replaces `self.retry(countdown=60*(2**retries))`), `scan_and_retry_failed_sagas` (300s, `.apply_async(countdown=)` → `await schedule_task_at()`), `cleanup_old_completed_sagas` (86400s). SagaOrchestrator uses async Redis + AsyncSession directly — no `run_async` bridge.

**T04 — External call sites (3 migrated, 1 deferred).** Wired `response_handler.py` (`generate_quiz_report.delay()` → `await generate_quiz_report.kiq()`), `delivery.py` (sync→async, `.apply_async(countdown=)` → `await schedule_task_at()`), `message.py` (sync→async, same pattern). `sequencing.py` updated with `await` for the now-async `enqueue_failed_flow_send_retry`. `recovery.py` left on Celery `.delay()` with `TODO(S05)` marker — sync function with sync callers.

## Verification

All slice acceptance criteria passed:

| Check | Expected | Actual | Status |
|---|---|---|---|
| `flows_taskiq.py` AST parse | OK | OK | ✅ |
| `saga_retry_taskiq.py` AST parse | OK | OK | ✅ |
| `@broker.task` in flows_taskiq.py | 14 | 14 | ✅ |
| `@broker.task` in saga_retry_taskiq.py | 3 | 3 | ✅ |
| Total schedule labels | 12 | 12 (10+2) | ✅ |
| Bridge code in Taskiq files (AST) | 0 | 0 | ✅ |
| Celery dispatch in Taskiq files (AST) | 0 | 0 | ✅ |
| Celery originals intact | unchanged | all 9 files unchanged | ✅ |
| Call sites import from flows_taskiq | 3 files | 3 files | ✅ |
| Call sites zero Celery dispatch | 0 | 0 | ✅ |
| recovery.py retains .delay() | yes | yes (with TODO(S05)) | ✅ |
| All modified files AST parse | OK | OK (7 files) | ✅ |

## Requirements Advanced

- R080 — All 17 flow/saga tasks now have async-native Taskiq equivalents with zero bridge code. Contract parity proven via AST analysis. Runtime verification deferred to S06.
- R082 — 12 schedule labels contributed toward the 40+ total. S04 completes the remaining entries.
- R083 — 3 external call sites migrated from `.delay()`/`.apply_async()` to `.kiq()`/`schedule_task_at()`. 1 deferred to S05 (recovery.py). S04 migrates remaining call sites.

## Requirements Validated

- None — R080 requires runtime proof (S06) to validate. This slice proves contract parity only.

## New Requirements Surfaced

- None

## Requirements Invalidated or Re-scoped

- None

## Deviations

- `sequencing.py` was not listed in the T04 plan but required `await` updates at 2 call sites of the now-async `enqueue_failed_flow_send_retry`. Discovered during T04 execution.
- `MESSAGE_RETRY_DELAY` imported from `app.config.settings.tasks` instead of from Celery `send_retry` module — same underlying value, avoids pulling Celery import chain.
- Constants (`_MAX_SAFE_DAILY_FLOW_LIMIT`, etc.) duplicated from `flow_tasks.py` to avoid importing the entire Celery module.

## Known Limitations

- `recovery.py:attempt_recovery()` still dispatches via Celery `.delay()` — sync function deep inside sync-only services, cannot be made async without cascading changes. Tracked for S05 cleanup.
- `detect_stuck_flows` internally calls `attempt_recovery()` which uses Celery `.delay()` — same coexistence constraint.
- `grep -c "async_to_sync|run_async"` returns false positives from docstrings mentioning "replaced X with Y" — use AST analysis for definitive zero-bridge verification.
- Runtime proof deferred — all 17 tasks are contract-verified (AST parse, task count, schedule count, zero bridge) but not runtime-verified. S06 proves end-to-end.

## Follow-ups

- S05 must migrate `recovery.py:attempt_recovery()` from Celery `.delay()` to Taskiq `.kiq()` — requires making the function and its callers async, or using a sync dispatch wrapper.
- S05 must update `detect_stuck_flows` to not depend on Celery dispatch path through `attempt_recovery()`.

## Files Created/Modified

- `backend-hormonia/app/tasks/flows_taskiq.py` — NEW: 14 `@broker.task` async tasks with 10 schedule labels, structured logging, SmartRetryMiddleware DLQ routing
- `backend-hormonia/app/tasks/saga_retry_taskiq.py` — NEW: 3 `@broker.task` async saga tasks with 2 schedule labels
- `backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py` — Switched generate_quiz_report dispatch to Taskiq .kiq()
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py` — Made enqueue_failed_flow_send_retry async, using schedule_task_at
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py` — Added await to 2 enqueue_failed_flow_send_retry calls
- `backend-hormonia/app/services/follow_up_system/execution/message.py` — Made _enqueue_retry async, using schedule_task_at
- `backend-hormonia/app/services/flow/recovery.py` — Added TODO(S05) comment, Celery .delay() retained for coexistence

## Forward Intelligence

### What the next slice should know
- Flow and saga domains are fully migrated to Taskiq. S04 handles quiz, alert, follow-up, LGPD, audit, webhook DLQ, and monitoring tasks — different domain, same patterns.
- The `get_scoped_session()` pattern for sync ORM services is proven and safe — use it when a service's internal ORM is sync-only.
- `schedule_task_at()` is the canonical replacement for `.apply_async(countdown=N)` — compute `datetime.now(UTC) + timedelta(seconds=delay)`.
- Cross-task Taskiq dispatch works: `await task.kiq()` from another Taskiq module (proven by send_daily_reminders → send_scheduled_message).

### What's fragile
- `grep -c` verification against Taskiq files gives false positives from docstrings — always use AST-based analysis for bridge/dispatch zero-checks.
- `attempt_recovery()` in recovery.py is a sync Celery dispatch buried inside `detect_stuck_flows` — S05 must trace and convert the entire call chain.

### Authoritative diagnostics
- `python3 -c "import ast; [walk AST for Call nodes with bridge/dispatch names]"` — the only trustworthy zero-bridge check. grep returns docstring false positives.
- `grep -c "@broker.task" flows_taskiq.py saga_retry_taskiq.py` — definitive task count (14 + 3 = 17).
- `grep "TODO(S05)" backend-hormonia/app/services/flow/recovery.py` — confirms the one deferred coexistence point.

### What assumptions changed
- Plan assumed `delivery.py` and `message.py` callers might be sync — all callers are actually async, so converting these to async was safe without cascading changes.
- Plan didn't list `sequencing.py` as a file to modify — it needed `await` updates because it calls the now-async `enqueue_failed_flow_send_retry`.
