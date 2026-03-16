# S02: Messaging tasks migradas — Research

**Date:** 2026-03-16
**Depth:** Targeted — known Taskiq patterns (established in S01) applied to messaging domain with one critical unknown (ETA/delayed dispatch).

## Summary

S02 migrates the 9 Celery messaging tasks (1231 lines in `app/tasks/messaging.py`) to Taskiq async-native tasks. The core win is eliminating the `run_async()` bridge in `send_scheduled_message` — the hot path — where a sync Celery task wraps an inner `async def _send_message_async()`. With Taskiq, that inner function _becomes_ the task body directly, using `AsyncSession` via `DbSession` dependency instead of manually calling `get_async_session_factory()`.

The three non-trivial translation challenges are: (1) `self.retry()` manual control in `send_scheduled_message` needs mapping to SmartRetryMiddleware labels + `Context` for retry count access, (2) `send_bulk_messages` uses `.apply_async(eta=datetime)` which requires a `ListRedisScheduleSource` for dynamic one-shot scheduling (the `LabelScheduleSource` from S01 does NOT support `add_schedule`), and (3) coexistence — external callers in `flow_automation.py` and `batch_tasks.py` still use `.delay()` which doesn't exist on Taskiq tasks, so Celery tasks must remain as thin wrappers during the migration period.

The recommended approach: create `app/tasks/messaging_taskiq.py` with all 9 Taskiq tasks, keep `app/tasks/messaging.py` as-is for backward-compat `.delay()` from non-messaging callers, update in-scope call sites (API routes, domain/messaging/ schedulers) to import from the new module and use `.kiq()`. The 7 beat schedule entries for messaging move to Taskiq task labels (cron/interval).

## Recommendation

**New module approach** — create `app/tasks/messaging_taskiq.py` alongside existing `messaging.py`.

Why: The slice scope explicitly states "Celery e Taskiq coexistem — apenas messaging usa Taskiq." External call sites in `flow_automation.py`, `batch_tasks.py` (S03 scope) still call `send_scheduled_message.delay()`. If we replace the Celery task in-place, those `.delay()` calls break. A parallel module keeps Celery tasks alive for non-messaging callers while messaging-domain callers switch to `.kiq()`. S03 will migrate flow callers to import from the Taskiq module; S05 deletes the Celery versions.

For `send_bulk_messages`'s `.apply_async(eta=)` pattern, add a `ListRedisScheduleSource` instance to `app/taskiq_broker.py`. This source supports `add_schedule()` (unlike `LabelScheduleSource`), enabling `task.kicker().schedule_by_time(source, delivery_time, *args)`. The SmartRetryMiddleware can also use this source for delayed retries via its `schedule_source` parameter.

## Implementation Landscape

### Key Files

- `backend-hormonia/app/tasks/messaging.py` (1231 lines) — Current Celery tasks. 9 tasks total: `send_scheduled_message`, `process_scheduled_messages`, `retry_failed_messages`, `send_bulk_messages`, `cleanup_old_messages`, `generate_message_analytics`, `process_whatsapp_dlq`, `process_dlq_messages`, `retry_pending_welcome_messages`. Stays intact for backward compat.
- `backend-hormonia/app/tasks/messaging_taskiq.py` — **NEW**. Taskiq versions of all 9 tasks. Async-native, uses `DbSession` from `taskiq_base.py`, `Context` for retry count access.
- `backend-hormonia/app/taskiq_broker.py` — Needs `ListRedisScheduleSource` instance added for dynamic scheduling (ETA replacement). SmartRetryMiddleware may need `schedule_source` parameter pointed to this source for delayed retries.
- `backend-hormonia/app/tasks/taskiq_base.py` — May need a helper for retry-count access via `Context` + convenience wrapper.
- `backend-hormonia/app/api/v2/messages/retry.py` — Call site: `send_scheduled_message.delay()` and `retry_failed_messages_task.delay()` → switch to `.kiq()` from taskiq module.
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py` — Call site: `send_scheduled_message.apply_async(eta=)` → switch to `schedule_by_time()`.
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py` — Call site: `send_scheduled_message.apply_async(eta=)` → switch to `schedule_by_time()`.
- `backend-hormonia/app/celery_app.py` lines 83-104, 178-188 — 7 messaging beat schedule entries. These stay (Celery still runs for non-messaging tasks) but are superseded by Taskiq task labels.
- `backend-hormonia/app/tasks/__init__.py` — Imports all messaging tasks from `messaging.py`. No change needed (keeps backward compat for non-messaging importers).

### Pure helper functions (no migration needed, reused by Taskiq tasks)

These functions in `messaging.py` are pure logic with no Celery dependency — import directly into `messaging_taskiq.py`:
- `_build_idempotency_key()` (line 42)
- `_parse_time_str()` (line 52)
- `_add_months()` (line 64)
- `_compute_next_reminder_time()` (line 68)
- `_schedule_next_reminder()` (line 118) — async, uses `db` parameter, no Celery tie

### Call Sites to Migrate in S02

| File | Current Pattern | New Pattern | Notes |
|------|----------------|-------------|-------|
| `messaging.py` internal (3x) | `send_scheduled_message.delay(str(id))` | `await send_scheduled_message.kiq(str(id))` | Inside `process_scheduled_messages`, `retry_failed_messages`, `retry_pending_welcome_messages` |
| `api/v2/messages/retry.py` | `send_scheduled_message.delay(str(id))` | `await send_scheduled_message.kiq(str(id))` | API route is already `async def` |
| `api/v2/messages/retry.py` | `retry_failed_messages_task.delay(limit=...)` | `await retry_failed_messages.kiq(limit=...)` | Returns `task_result.id` for response |
| `domain/messaging/.../task_scheduler.py` | `.apply_async(args=[...], eta=delivery_time)` | `.kicker().schedule_by_time(source, delivery_time, str(id))` | ETA replacement |
| `domain/messaging/.../retry_handler.py` | `.apply_async(args=[...], eta=retry_time)` | `.kicker().schedule_by_time(source, retry_time, str(id))` | ETA replacement |
| `messaging.py` `send_bulk_messages` | `.apply_async(args=[...], eta=eta)` | `.kicker().schedule_by_time(source, eta, str(id))` | Only ETA usage inside messaging.py |

### Call Sites NOT in S02 Scope (remain on Celery `.delay()`)

| File | Call | Migrated In |
|------|------|-------------|
| `tasks/flow_automation.py:265` | `send_scheduled_message.delay()` | S03 |
| `tasks/flows/batch_tasks.py:348` | `send_scheduled_message.delay()` | S03 |
| `tasks/__init__.py` | Re-exports from `messaging.py` | S05 (cleanup) |

### Task-by-Task Translation Map

| Celery Task | Complexity | Key Changes |
|-------------|-----------|-------------|
| `send_scheduled_message` | HIGH | Eliminate `run_async()` bridge. Inner `_send_message_async()` becomes task body. Replace `self.retry()` with raise-to-SmartRetryMiddleware. Replace sync DLQ `get_db_session()` with async. Access retry count via `Context.message.labels['_retries']`. |
| `process_scheduled_messages` | LOW | Replace `get_db_session()` with `DbSession`. Replace `send_scheduled_message.delay()` with `await send_scheduled_message.kiq()`. |
| `retry_failed_messages` | LOW | Replace `get_db_session()` with `DbSession`. Replace `.delay()` with `.kiq()`. |
| `send_bulk_messages` | MEDIUM | Replace `get_scoped_session()` with `DbSession`. Replace `.apply_async(eta=)` with `schedule_by_time()`. |
| `cleanup_old_messages` | LOW | Replace `get_scoped_session()` with `DbSession`. Straightforward port. |
| `generate_message_analytics` | LOW | Replace `get_scoped_session()` with `DbSession`. Sync ORM queries → async. |
| `process_whatsapp_dlq` | MEDIUM | Replace `get_scoped_session()` with `DbSession`. Eliminate `run_async()` for DLQHandler async calls — direct `await`. |
| `process_dlq_messages` | LOW | Replace `get_db_session()` with `DbSession`. DLQService is sync — wrap or convert. |
| `retry_pending_welcome_messages` | LOW | Replace `get_db_session()` with `DbSession`. Replace `.delay()` with `.kiq()`. |

### Beat Schedule → Taskiq Labels

| Schedule Entry | Interval | Taskiq Label |
|----------------|----------|-------------|
| `process-scheduled-messages` | 60s | `schedule=[{"interval": {"seconds": 60}, "kwargs": {"limit": 60}}]` |
| `retry-failed-messages` | 300s | `schedule=[{"interval": {"seconds": 300}, "kwargs": {"limit": 50, "max_retries": 3}}]` |
| `retry-pending-welcome-messages` | 600s | `schedule=[{"interval": {"seconds": 600}, "kwargs": {"limit": 50, "min_age_minutes": 5, "max_age_hours": 24}}]` |
| `cleanup-old-messages` | 86400s | `schedule=[{"interval": {"seconds": 86400}, "kwargs": {"days_old": 90}}]` |
| `generate-message-analytics` | 3600s | `schedule=[{"interval": {"seconds": 3600}, "kwargs": {"days_back": 7}}]` |
| `process-whatsapp-dlq` | 600s | `schedule=[{"interval": {"seconds": 600}, "kwargs": {"limit": 50}}]` |
| `process-dlq-scheduled-retries` | crontab(*/5) | `schedule=[{"cron": "*/5 * * * *", "kwargs": {"limit": 100}}]` |

### Build Order

1. **Add `ListRedisScheduleSource` to `taskiq_broker.py`** — unblocks ETA replacement for `send_bulk_messages`, `task_scheduler.py`, `retry_handler.py`. Pass it to `SmartRetryMiddleware(schedule_source=...)` so retry delays use scheduled dispatch instead of immediate re-queue with sleep label.

2. **Create `messaging_taskiq.py` with `send_scheduled_message`** — the hardest task, most complex retry logic, most call sites. Proves the pattern for all other tasks. Extract `_send_message_async()` as the async task body. Replace `self.retry(countdown=...)` for "not found" race condition with `Context.requeue()` or explicit raise + SmartRetryMiddleware. Replace sync DLQ `get_db_session()` blocks with async DLQ handling using the task's `DbSession`.

3. **Add remaining 8 tasks to `messaging_taskiq.py`** — follow the pattern from step 2. Each task: replace sync session with `DbSession`, replace Celery helpers (`self.log_task_start`, `self.create_success_result`, etc.) with taskiq_base equivalents, add schedule labels.

4. **Update call sites within messaging domain** — `api/v2/messages/retry.py`, `domain/messaging/.../task_scheduler.py`, `domain/messaging/.../retry_handler.py`. Switch imports and dispatch calls.

5. **Verify** — dispatch `send_scheduled_message.kiq()` against Dragonfly, confirm retry behavior, confirm schedule labels fire via scheduler.

### Verification Approach

1. **Dispatch proof**: `send_scheduled_message.kiq(message_id)` executes on Taskiq worker against Dragonfly → message status updated in DB.
2. **Retry proof**: Trigger `send_scheduled_message` with a message that doesn't exist yet (race condition) → SmartRetryMiddleware retries with exponential backoff → succeeds when message appears. Log shows "Retrying 1/3 in Xs".
3. **Schedule proof**: Run `taskiq scheduler` alongside worker → `process_scheduled_messages` fires every 60s, picks up due messages. Verify via worker logs.
4. **ETA proof**: `send_bulk_messages.kiq()` with future ETA → message dispatched after ETA via `ListRedisScheduleSource`. Verify via Redis key inspection or worker execution time.
5. **DLQ proof**: Trigger `send_scheduled_message` for a patient without phone → DLQ entry created via async path (no sync `get_db_session` fallback).
6. **Coexistence proof**: `flow_automation.py` still successfully calls `send_scheduled_message.delay()` from the Celery version (import from `app.tasks.messaging` not broken).
7. **AST parse check**: All modified/created files pass `python3 -c "import ast; ast.parse(open('file').read())"`.

## Constraints

- **`LabelScheduleSource` cannot do dynamic scheduling** — `add_schedule()` raises `NotImplementedError`. Must use `ListRedisScheduleSource` from `taskiq-redis` for ETA/delayed dispatch. This means the broker module needs a second schedule source instance.
- **`SmartRetryMiddleware` tracks retry count in `message.labels['_retries']`** — not on the task instance like Celery's `self.request.retries`. Tasks that need retry count must inject `Context` via `TaskiqDepends` and read `context.message.labels.get('_retries', 0)`.
- **`send_scheduled_message` uses sync `get_db_session()` (Celery sync Session) for DLQ routing in the exception handler** — this MUST be converted to async. The DLQ service (`DLQService`) is sync (uses sync `Session`). Two options: (a) create async DLQ operations, or (b) wrap sync DLQ calls. Prefer (a) since we're async-native now, but the DLQService refactor is out of scope — use a fresh async session for the specific DLQ writes needed.
- **`process_whatsapp_dlq` uses `run_async()` to call async `DLQHandler` methods from sync Celery** — with Taskiq, just `await` directly. But the handler uses the same sync `db` session passed in. Need to pass async session instead — verify `DLQHandler` works with `AsyncSession`.
- **`generate_message_analytics` uses raw sync SQLAlchemy queries** (`db.query(Message).filter(...)`) — must convert to async `select()` statements.
- **`.kiq()` is async** — call sites in sync contexts (if any) need `asyncio.run()` or must be in async functions. All identified call sites (`api/v2/messages/retry.py`, `task_scheduler.py`, `retry_handler.py`) are already async.
- **`app/tasks/__init__.py` imports from `app.tasks.messaging`** — do NOT change this; it's the Celery import chain for non-messaging consumers. The new Taskiq tasks live in `messaging_taskiq.py` with separate imports.

## Common Pitfalls

- **`send_scheduled_message` DLQ routing in exception handler uses a SEPARATE sync session** — The current code opens `with get_db_session() as db:` inside the except block to query the Message again and write to DLQ. In Taskiq, the `DbSession` is the main async session. The DLQ write should use this same session (or a new async session) — do NOT try to use sync `get_db_session()` which requires the Celery worker's sync event loop context.

- **SmartRetryMiddleware replaces `self.handle_retry(exc)` — do NOT re-raise the exception after explicit retry handling** — In Celery, `self.retry()` raises a `Retry` exception that Celery catches. In Taskiq, just `raise` the original exception and SmartRetryMiddleware handles retry automatically. The "not found" manual retry in `send_scheduled_message` (lines 385-397) needs special handling: either use `Context.requeue()` or raise a specific exception type that SmartRetryMiddleware catches.

- **`send_bulk_messages` returns `task.id` from `.apply_async()`** — Taskiq's `schedule_by_time()` returns a `CreatedSchedule` not an `AsyncTaskiqTask`. The `schedule_id` serves a similar purpose but it's not the same as Celery's task ID. Code that stores `task_result.id` for status checking needs adjustment.

- **`retry_failed_messages_task.delay(...)` in `api/v2/messages/retry.py` returns a result with `.id`** — The API route returns `{"task_id": task_result.id}`. Taskiq's `.kiq()` returns `AsyncTaskiqTask` which has `task_id`. This works but the attribute name differs.

- **`DLQHandler.get_pending_review()` and `DLQHandler.requeue_for_retry()` are async** — Currently called via `run_async()` bridge. In Taskiq task, call with `await` directly. But verify the handler's internal DB operations work with the async session we provide.

## Open Risks

- **`DLQService` is sync-only** — `process_dlq_messages` uses `DLQService(db)` with a sync session. In a Taskiq async task, we have an `AsyncSession`. Either: (a) create a sync session just for DLQ calls (ugly but works), (b) make DLQ calls async (out of S02 scope), or (c) use `run_in_executor` for the sync DLQ call. Recommend (a) as pragmatic solution — the DLQService.process_scheduled_retries() is lightweight and already has its own transaction management.

- **`DLQHandler` session compatibility** — `DLQHandler(db)` is initialized with whatever `db` is passed. In `process_whatsapp_dlq`, it's currently a sync session. We need to verify it works with AsyncSession or provide the right type.

- **`ListRedisScheduleSource` needs the scheduler process running to fire time-based schedules** — If the scheduler process isn't running, `schedule_by_time()` stores the schedule in Redis but nothing picks it up. This is the same as Celery beat not running — operational requirement, not a code issue.

## Sources

- Taskiq `AsyncKicker.schedule_by_time()` — confirmed by source inspection: creates `ScheduledTask` with `time` field, calls `source.add_schedule()`. Requires a `ScheduleSource` that implements `add_schedule()`.
- `ListRedisScheduleSource.add_schedule()` — confirmed implemented (stores in Redis with time-keyed lists). Unlike `LabelScheduleSource` which raises `NotImplementedError`.
- `SmartRetryMiddleware.on_error()` — tracks `_retries` in `message.labels`, compares to `max_retries` label or default. When retry scheduled, re-kiq's with incremented `_retries`.
- `Context` class — provides `message` (TaskiqMessage with `.labels` dict) and `.requeue()` method. Accessible via `TaskiqDepends`.
