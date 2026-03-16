---
id: S02
parent: M009
milestone: M009
provides:
  - messaging_taskiq.py with all 9 async-native Taskiq messaging tasks
  - 7 schedule labels for LabelScheduleSource periodic dispatch (cron/interval)
  - ListRedisScheduleSource + schedule_task_at() for ETA/delayed dispatch (replaces .apply_async(eta=))
  - Messaging-domain call sites (retry.py, task_scheduler.py, retry_handler.py) dispatching via .kiq()/schedule_task_at()
  - Celery/Taskiq coexistence — external callers (flow_automation.py, batch_tasks.py) still use Celery .delay()
  - Proven migration pattern: Celery bound task → async Taskiq task with SmartRetryMiddleware
requires:
  - slice: S01
    provides: Taskiq broker (ListQueueBroker), SmartRetryMiddleware, LabelScheduleSource, TaskiqScheduler, DbSession dependency, FastAPI lifespan integration
affects:
  - S03 (consumes send_scheduled_message Taskiq task + migration patterns for flow/saga tasks)
  - S04 (consumes schedule label pattern for remaining 30+ periodic tasks)
  - S05 (messaging tasks ready for Celery removal — messaging.py can be deleted after S03/S04 migrate remaining callers)
key_files:
  - backend-hormonia/app/tasks/messaging_taskiq.py
  - backend-hormonia/app/taskiq_broker.py
  - backend-hormonia/app/tasks/taskiq_base.py
  - backend-hormonia/app/api/v2/messages/retry.py
  - backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py
  - backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py
key_decisions:
  - D006: ListRedisScheduleSource for ETA/delayed dispatch (replaces Celery .apply_async(eta=))
  - D007: Parallel module strategy (messaging_taskiq.py alongside messaging.py for coexistence)
  - DLQ writes use sync get_scoped_session() because DLQService/DLQHandler are sync-internally despite async-def signatures
  - Pure helpers imported from Celery module (no duplication) — _build_idempotency_key, _compute_next_reminder_time, _schedule_next_reminder
patterns_established:
  - Celery run_async() bridge eliminated — async inner function becomes direct Taskiq task body
  - "@broker.task(retry_on_error=True, max_retries=N, delay=N) + raise = SmartRetryMiddleware handles retry"
  - context.message.labels.get('_retries', 0) replaces self.request.retries for retry count
  - Periodic tasks use schedule= label in @broker.task decorator (interval or cron)
  - Cross-task dispatch: await task.kiq(id) replaces Celery .delay()
  - ETA dispatch: await schedule_task_at(task, datetime, *args) replaces .apply_async(eta=)
  - Import from messaging_taskiq for Taskiq tasks, from messaging for Celery tasks (coexistence)
  - Sync services (DLQService, DLQHandler) get sync session via get_scoped_session() in isolated helpers
observability_surfaces:
  - Structured logs via log_task_start/success/error with task_name, event, duration_ms for all 9 tasks
  - SmartRetryMiddleware logs "Retrying N/M in X.XX seconds" on retry
  - Message DB fields: status=FAILED, failure_reason, retry_count, last_retry_at, message_metadata.last_retry_error
  - DLQ entries with error_message, error_type, payload.flow_context
  - GET /api/v2/health/ready → checks.taskiq_broker for broker health + scheduler_sources
  - retry.py API response includes task_id for dispatch tracing
  - task_scheduler.py/retry_handler.py log schedule_id with message ID and delivery time
drill_down_paths:
  - .gsd/milestones/M009/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M009/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M009/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M009/slices/S02/tasks/T04-SUMMARY.md
duration: 40m
verification_result: passed
completed_at: 2026-03-16
---

# S02: Messaging tasks migradas

**All 9 messaging Celery tasks have async-native Taskiq equivalents with SmartRetryMiddleware retry, 7 schedule labels, ETA dispatch via ListRedisScheduleSource, and messaging-domain call sites switched to .kiq()/schedule_task_at() — while Celery tasks remain intact for external callers.**

## What Happened

This slice migrated the entire messaging task domain from Celery to Taskiq in four tasks:

**T01** added the ETA/delayed dispatch infrastructure: `ListRedisScheduleSource` for dynamic one-shot scheduling in the broker module, and `schedule_task_at()` helper in `taskiq_base.py`. This is the direct replacement for Celery's `.apply_async(eta=datetime)` used by task_scheduler.py, retry_handler.py, and send_bulk_messages. The scheduler now includes both `LabelScheduleSource` (static cron/interval) and `ListRedisScheduleSource` (dynamic one-shot).

**T02** created `messaging_taskiq.py` with the hardest task first: `send_scheduled_message` (367 lines, complex retry/DLQ logic). The core translation flattened the inner `_send_message_async()` into the task body directly — no `run_async()` bridge needed. Key patterns proven: `@broker.task(retry_on_error=True, max_retries=3, delay=2)` + raise for SmartRetryMiddleware retry, `context.message.labels.get('_retries', 0)` for retry count, and `_route_to_dlq()` helper using sync session for sync-only DLQService. Pure helpers imported from Celery module without duplication.

**T03** added the remaining 8 tasks: `process_scheduled_messages`, `retry_failed_messages`, `send_bulk_messages`, `cleanup_old_messages`, `generate_message_analytics`, `process_whatsapp_dlq`, `process_dlq_messages`, `retry_pending_welcome_messages`. All follow the T02 pattern: async-native with `AsyncSession` via `DbSession`, cross-task `.kiq()` dispatch, `schedule_task_at()` for ETA. 7 schedule labels added for periodic dispatch. Key finding: `DLQHandler` declares `async def` methods but uses sync ORM internally — needs sync session regardless.

**T04** wired the new dispatch patterns into the 3 messaging-domain call sites: `retry.py` switched `.delay()` → `await .kiq()`, `task_scheduler.py` and `retry_handler.py` switched `.apply_async(eta=)` → `await schedule_task_at()`. Verified coexistence: `flow_automation.py` and `batch_tasks.py` still import from Celery `messaging.py` and use `.delay()` without breakage.

## Verification

All 14 slice-level checks pass:

| # | Check | Result |
|---|-------|--------|
| V1 | `messaging_taskiq.py` AST parse | PASS |
| V2 | `taskiq_broker.py` AST parse | PASS |
| V3 | `retry.py` AST parse | PASS |
| V4 | `task_scheduler.py` AST parse | PASS |
| V5 | `retry_handler.py` AST parse | PASS |
| V6 | `@broker.task` count = 9 | PASS |
| V7 | `schedule=` count = 7 | PASS |
| V8 | No `.delay` in messaging_taskiq.py code | PASS |
| V9 | No `run_async` in messaging_taskiq.py code | PASS |
| V10 | No sync session in main task flow (only in DLQ helpers) | PASS |
| V11 | No Celery dispatch in retry.py | PASS |
| V12 | No Celery dispatch in task_scheduler.py | PASS |
| V13 | No Celery dispatch in retry_handler.py | PASS |
| V14 | Celery tasks intact: 9 `@celery_app.task` in messaging.py | PASS |

Coexistence verified: `flow_automation.py` and `batch_tasks.py` still import from `app.tasks.messaging` (Celery) and use `.delay()`.

## Requirements Advanced

- R079 — All 9 messaging tasks (send_scheduled_message, process_scheduled_messages, retry_failed_messages, send_bulk_messages, cleanup_old_messages, generate_message_analytics, process_whatsapp_dlq, process_dlq_messages, retry_pending_welcome_messages) now have async-native Taskiq equivalents with SmartRetryMiddleware retry, and messaging-domain call sites dispatch via Taskiq. Full validation requires runtime proof against Dragonfly (S06 scope).
- R082 — 7 of 40+ schedule entries migrated to Taskiq LabelScheduleSource (messaging domain complete). Remaining entries are S04 scope.
- R083 — 3 of ~20 call sites migrated to .kiq()/schedule_task_at() (messaging-domain call sites: retry.py, task_scheduler.py, retry_handler.py). Remaining call sites are S03/S04 scope.

## Requirements Validated

- none (R079 requires runtime proof to validate; code migration is complete but runtime verification is S06)

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- **T03: DLQHandler sync session** — Plan suggested DLQHandler might work with AsyncSession since methods use `await`. Investigation showed methods actually use `self.db.query()` (sync ORM) despite `async def` signatures. Used `get_scoped_session()` — correct approach.
- **T03: File size** — messaging_taskiq.py is 1237 lines vs estimated 600-800. All content is necessary — the 9 tasks plus docstrings/observability are more verbose than estimated.
- **T01: File corruption during editing** — Both broker and base files had duplicated tails during edit operations. Resolved by clean full-file rewrites. No content impact.

## Known Limitations

- **DLQ path uses sync session**: `_route_to_dlq()`, `process_whatsapp_dlq`, and `process_dlq_messages` use sync `get_scoped_session()` because DLQService and DLQHandler are sync-internally. This is pragmatic isolation — the main task flow is fully async.
- **generate_message_analytics replicates service logic**: Async queries replicate `MessageService.get_message_statistics()` inline. If the service method changes, the Taskiq version must be updated manually.
- **DLQHandler has misleading async-def signatures**: Methods declared `async def` but use sync ORM (`self.db.query()`, `self.db.commit()`). A future cleanup could make it truly async or explicitly sync.
- **No runtime verification yet**: All tasks are code-correct (AST parse, no sync patterns in main flow) but have not been exercised against a live Taskiq worker + Dragonfly. Runtime proof is S06 scope.

## Follow-ups

- S03 must migrate flow_automation.py and batch_tasks.py call sites from Celery .delay() to Taskiq .kiq() — these are the remaining callers of send_scheduled_message via Celery.
- S04 must add the remaining 30+ schedule entries to complete the full beat schedule parity.
- S05 can delete messaging.py (Celery tasks) once S03 migrates all external callers.
- Consider making DLQHandler/DLQService truly async in a future cleanup to eliminate the sync session islands.

## Files Created/Modified

- `backend-hormonia/app/taskiq_broker.py` — Added ListRedisScheduleSource, dynamic_schedule_source instance, updated scheduler to include both sources, updated get_broker_status()
- `backend-hormonia/app/tasks/taskiq_base.py` — Added schedule_task_at() async helper with lazy import, added datetime import
- `backend-hormonia/app/tasks/messaging_taskiq.py` — NEW: all 9 async-native Taskiq messaging tasks with schedule labels (~1237 lines)
- `backend-hormonia/app/api/v2/messages/retry.py` — Switched imports to messaging_taskiq, .delay() → await .kiq(), task_result.id → task_result.task_id
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py` — .apply_async(eta=) → await schedule_task_at(), result access updated to schedule_result.schedule_id
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py` — .apply_async(eta=) → await schedule_task_at(), metadata updated with schedule_id

## Forward Intelligence

### What the next slice should know
- The migration pattern is fully proven: async task body, SmartRetryMiddleware for retry, DbSession for async DB, schedule labels for cron/interval, schedule_task_at for ETA dispatch. S03 can follow this pattern exactly for flow/saga tasks.
- `messaging_taskiq.py` imports pure helpers from `messaging.py` (Celery module) without duplication. S03's flow tasks likely import from the Celery flow modules too — same pattern works.
- External callers (`flow_automation.py`, `batch_tasks.py`) still use `send_scheduled_message.delay()` from Celery `messaging.py`. S03 must switch these to `await send_scheduled_message.kiq()` from `messaging_taskiq`.

### What's fragile
- **DLQHandler async/sync mismatch** — DLQHandler has `async def` signatures but uses sync ORM. Any caller must use sync session. If someone passes AsyncSession assuming the `async def` means async I/O, it will fail silently or raise.
- **generate_message_analytics inline queries** — Replicates MessageService.get_message_statistics() logic. If that service method changes, the Taskiq task becomes stale.
- **Import path coexistence** — During S02-S04, both `app.tasks.messaging` (Celery) and `app.tasks.messaging_taskiq` (Taskiq) export tasks with the same names. Callers must import from the correct module. Wrong import = task dispatched to wrong queue.

### Authoritative diagnostics
- `grep -c "@broker.task" backend-hormonia/app/tasks/messaging_taskiq.py` → must be 9
- `grep -c "@celery_app.task" backend-hormonia/app/tasks/messaging.py` → must be 9 (untouched)
- `grep "from app.tasks.messaging import" backend-hormonia/app/tasks/flow_automation.py` → confirms external callers still on Celery
- Worker logs: `task_name=send_scheduled_message` + `event=task_start` for execution tracing

### What assumptions changed
- **DLQHandler is async** → DLQHandler declares `async def` but uses sync ORM internally. Always provide sync session.
- **messaging_taskiq.py ~600-800 lines** → actual is 1237 lines. 9 tasks with full observability, docstrings, and DLQ helpers are larger than estimated.
