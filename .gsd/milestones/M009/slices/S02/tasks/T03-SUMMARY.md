---
id: T03
parent: S02
milestone: M009
provides:
  - All 9 Taskiq messaging tasks in messaging_taskiq.py (1 from T02 + 8 new)
  - 7 schedule labels for LabelScheduleSource periodic dispatch
  - ETA dispatch via schedule_task_at in send_bulk_messages
  - Direct await for DLQHandler async-def methods (process_whatsapp_dlq)
  - Pragmatic sync session for DLQService (process_dlq_messages)
key_files:
  - backend-hormonia/app/tasks/messaging_taskiq.py
key_decisions:
  - process_whatsapp_dlq uses sync get_scoped_session() because DLQHandler.get_pending_review/requeue_for_retry are async-def but use sync ORM internally (self.db.query(), self.db.commit())
  - process_dlq_messages uses sync get_scoped_session() because DLQService is sync-only
  - process_scheduled_messages uses direct async select() instead of sync MessageService.get_scheduled_messages() to avoid sync session dependency
  - send_bulk_messages creates Message objects directly via async ORM instead of sync MessageService.schedule_message()
  - generate_message_analytics replicates MessageService.get_message_statistics() logic with async select() queries
patterns_established:
  - Periodic tasks use schedule label in @broker.task decorator (interval or cron)
  - Cross-task dispatch uses await task.kiq(id) replacing Celery .delay()
  - ETA dispatch uses await schedule_task_at(task, datetime, *args) replacing Celery .apply_async(eta=)
  - Tasks needing sync services (DLQService, DLQHandler) import get_scoped_session locally and use sync context manager
observability_surfaces:
  - Structured logs: log_task_start/success/error with task_name, event, duration_ms for all 9 tasks
  - SmartRetryMiddleware logs "Retrying N/M in X.XX seconds" on retry for send_scheduled_message
  - DLQ entries with error_message, error_type, payload.flow_context
  - Worker logs filterable by task_name=process_scheduled_messages|retry_failed_messages|etc
duration: 15min
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T03: Migrate remaining 8 messaging tasks with schedule labels

**Added 8 async-native Taskiq tasks to messaging_taskiq.py with 7 schedule labels, completing all 9 messaging task migrations.**

## What Happened

Migrated all 8 remaining Celery messaging tasks to Taskiq in `messaging_taskiq.py`, building on the `send_scheduled_message` task from T02. Each task was converted to async-native Python with:

- **Sync ORM replaced**: All `db.query()` / `db.commit()` converted to `await db.execute(select(...))` / `await db.commit()` using injected `AsyncSession` via `DbSession`.
- **Cross-task dispatch migrated**: All `.delay()` calls → `await .kiq()`. `send_bulk_messages` uses `await schedule_task_at()` for ETA dispatch.
- **Sync bridges eliminated**: No `run_async()` wrapper anywhere. `process_whatsapp_dlq` calls `await dlq_handler.get_pending_review()` and `await dlq_handler.requeue_for_retry()` directly.
- **Pragmatic sync sessions**: `process_whatsapp_dlq` and `process_dlq_messages` use `get_scoped_session()` because their underlying services (DLQHandler, DLQService) use sync ORM internally. This is isolated and intentional.
- **Schedule labels**: 7 periodic tasks decorated with `schedule=[...]` for LabelScheduleSource.

Key finding: DLQHandler declares `async def` methods but internally uses sync ORM (`self.db.query()`, `self.db.commit()`). This means it needs a sync session regardless of being called with `await`. Both `process_whatsapp_dlq` and `_route_to_dlq` use the same `get_scoped_session()` pattern.

## Verification

All plan-specified checks pass:

```
@broker.task count:  9  ✓
schedule= count:     7  ✓
.delay() calls:      0  ✓ (only in docstring comments)
run_async calls:     0  ✓ (only in docstring comments)
AST parse:           OK ✓
Celery tasks intact: 9  ✓ (messaging.py unchanged)
```

Slice-level checks (T03 scope):
- `messaging_taskiq.py` AST parse: PASS
- `taskiq_broker.py` AST parse: PASS
- 9 @broker.task decorators: PASS
- 7 schedule= labels: PASS
- No .delay in code: PASS
- No run_async in code: PASS
- Celery tasks unchanged: PASS

Remaining slice checks (T04+ scope, not yet applicable):
- retry.py, task_scheduler.py, retry_handler.py call-site migration — pending T04

## Diagnostics

- Search worker logs for `task_name=<name>` + `event=task_start|task_success|task_error`
- Each task returns a dict with `success`, result-specific counts, and ISO timestamp
- DLQ routing visible via `_route_to_dlq` entries with `error_message`, `error_type`, `payload`
- `process_whatsapp_dlq` logs per-message outcome: auto-requeued vs manual review
- Schedule labels visible via `GET /api/v2/health/ready` → `checks.taskiq_broker.scheduler_sources`

## Deviations

- **process_whatsapp_dlq uses sync session**: Plan suggested DLQHandler might work with AsyncSession since methods use `await self.db.execute()`. Investigation showed methods actually use `self.db.query()` (sync ORM). Used `get_scoped_session()` instead of `DbSession` — this is the correct approach since DLQHandler is sync-internally despite async-def signatures.
- **File is 1237 lines vs estimated 600-800**: The 8 new tasks plus docstrings/comments are more verbose than estimated. All content is necessary.

## Known Issues

- DLQHandler has misleading `async def` signatures but uses sync ORM. A future cleanup could make it truly async or explicitly sync.
- `generate_message_analytics` replicates `MessageService.get_message_statistics()` logic inline as async queries. If the service method changes, the Taskiq version must be updated manually.

## Files Created/Modified

- `backend-hormonia/app/tasks/messaging_taskiq.py` — Added 8 new Taskiq tasks (process_scheduled_messages, retry_failed_messages, send_bulk_messages, cleanup_old_messages, generate_message_analytics, process_whatsapp_dlq, process_dlq_messages, retry_pending_welcome_messages) with schedule labels
- `.gsd/milestones/M009/slices/S02/tasks/T03-PLAN.md` — Added Observability Impact section (pre-flight fix)
