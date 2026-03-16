# S02: Messaging tasks migradas

**Goal:** All 9 messaging Celery tasks have Taskiq equivalents in `messaging_taskiq.py` with async-native implementations, SmartRetryMiddleware retry, schedule labels for all 7 beat entries, and messaging-domain call sites switched to `.kiq()` / `schedule_by_time()`. Celery tasks in `messaging.py` remain untouched for non-messaging callers (S03 scope).

**Demo:** `send_scheduled_message.kiq(message_id)` dispatches to Taskiq worker → processes via async DB + WuzAPI → retries with SmartRetryMiddleware on failure → DLQ routing works via async session. `process_scheduled_messages` fires every 60s via scheduler label. `task_scheduler.py` and `retry_handler.py` use `schedule_by_time()` instead of `.apply_async(eta=)`. External callers in `flow_automation.py` and `batch_tasks.py` still use Celery `.delay()` without breakage.

## Must-Haves

- `messaging_taskiq.py` with all 9 tasks as async Taskiq tasks using `DbSession` (AsyncSession)
- `send_scheduled_message` eliminates `run_async()` bridge — inner `_send_message_async()` becomes task body
- `self.retry()` pattern replaced by SmartRetryMiddleware labels + Context for retry count access
- `.apply_async(eta=datetime)` replaced by `schedule_by_time()` using `ListRedisScheduleSource`
- All 7 messaging beat schedule entries as Taskiq task labels (cron/interval)
- `api/v2/messages/retry.py` switches to `.kiq()` from Taskiq module
- `task_scheduler.py` and `retry_handler.py` switch to `schedule_by_time()`
- Celery `messaging.py` remains intact — `flow_automation.py` and `batch_tasks.py` `.delay()` still work
- DLQ routing uses async session (no sync `get_db_session()` fallback in Taskiq tasks)

## Proof Level

- This slice proves: integration
- Real runtime required: yes (Taskiq worker against Dragonfly for full proof; AST + import checks for code correctness)
- Human/UAT required: no

## Verification

- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/messaging_taskiq.py').read())"` — all 9 tasks parse
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/taskiq_broker.py').read())"` — broker with ListRedisScheduleSource parses
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/api/v2/messages/retry.py').read())"` — updated call sites parse
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py').read())"` — ETA replacement parses
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py').read())"` — ETA replacement parses
- `grep -c "@broker.task" backend-hormonia/app/tasks/messaging_taskiq.py` returns `9` — all tasks decorated
- `grep -c "schedule=" backend-hormonia/app/tasks/messaging_taskiq.py` returns `7` — all beat entries as labels
- `grep "\.delay\b" backend-hormonia/app/tasks/messaging_taskiq.py` returns nothing — no Celery dispatch in new module
- `grep "run_async" backend-hormonia/app/tasks/messaging_taskiq.py` returns nothing — no sync-async bridge
- `grep "get_scoped_session\|get_db_session" backend-hormonia/app/tasks/messaging_taskiq.py` returns nothing — no sync session
- `grep "send_scheduled_message\.\(delay\|apply_async\)" backend-hormonia/app/api/v2/messages/retry.py` returns nothing — call sites migrated
- `grep "send_scheduled_message\.\(delay\|apply_async\)" backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py` returns nothing
- `grep "send_scheduled_message\.\(delay\|apply_async\)" backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py` returns nothing
- Celery tasks intact: `grep -c "@celery_app.task" backend-hormonia/app/tasks/messaging.py` still returns `9`

## Observability / Diagnostics

- Runtime signals: Structured logs via `log_task_start/success/error` with `task_name`, `event`, `duration_ms`, `error_type` fields. SmartRetryMiddleware logs "Retrying N/M in X.XX seconds" on retry.
- Inspection surfaces: `GET /api/v2/health/ready` → `checks.taskiq_broker` for broker health. Worker logs with `task_name=send_scheduled_message` for execution tracing.
- Failure visibility: SmartRetryMiddleware tracks `_retries` in `message.labels`. DLQ entries created with `error_message`, `error_type`, `payload` including `flow_context`. Failed messages update `retry_count`, `last_retry_at`, `failure_reason`, `message_metadata.last_retry_error` in DB.
- Redaction constraints: Patient phone numbers logged only at DEBUG level. Message content never logged.

## Integration Closure

- Upstream surfaces consumed: `app/taskiq_broker.py` (broker, SmartRetryMiddleware), `app/tasks/taskiq_base.py` (DbSession, log helpers), `app/services/unified_whatsapp_service.py` (send_message), `app/domain/messaging/core.py` (MessageService), `app/services/dlq/service.py` (DLQService), `app/integrations/whatsapp/queue/dlq.py` (DLQHandler)
- New wiring introduced in this slice: `messaging_taskiq.py` task module, `ListRedisScheduleSource` in broker, `retry.py` / `task_scheduler.py` / `retry_handler.py` import rewiring
- What remains before the milestone is truly usable end-to-end: S03 migrates flow/saga tasks (flow_automation.py, batch_tasks.py call sites), S04 migrates remaining tasks + completes schedule, S05 removes Celery, S06 verifies pipeline

## Tasks

- [x] **T01: Add ListRedisScheduleSource and ETA dispatch helpers to broker** `est:30m`
  - Why: `.apply_async(eta=datetime)` is used in 3 files (send_bulk_messages, task_scheduler.py, retry_handler.py). Taskiq's `LabelScheduleSource` does NOT support `add_schedule()` — `ListRedisScheduleSource` from taskiq-redis does. This must be added before any task migration that needs delayed dispatch.
  - Files: `backend-hormonia/app/taskiq_broker.py`, `backend-hormonia/app/tasks/taskiq_base.py`
  - Do: Add `ListRedisScheduleSource` instance to broker module for dynamic one-shot scheduling. Add `schedule_by_time` helper to `taskiq_base.py` that wraps the `AsyncKicker.schedule_by_time()` pattern. Export the schedule source so call sites can import it. Update scheduler to include both sources.
  - Verify: `python3 -c "import ast; ast.parse(open('backend-hormonia/app/taskiq_broker.py').read())"` and `python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/taskiq_base.py').read())"`
  - Done when: `dynamic_schedule_source` is importable from `app.taskiq_broker`, `schedule_by_time` helper available in `taskiq_base.py`, both files parse clean

- [x] **T02: Create messaging_taskiq.py with send_scheduled_message task** `est:1h`
  - Why: `send_scheduled_message` is the hardest task (367 lines, complex retry/DLQ logic, `run_async()` bridge, `self.retry()` manual control). It proves the pattern that all other messaging tasks follow. The inner `_send_message_async()` becomes the direct task body in Taskiq — no bridge needed.
  - Files: `backend-hormonia/app/tasks/messaging_taskiq.py` (NEW)
  - Do: Create new module. Import pure helpers from `messaging.py` (`_build_idempotency_key`, `_parse_time_str`, `_add_months`, `_compute_next_reminder_time`, `_schedule_next_reminder`). Implement `send_scheduled_message` as `@broker.task(retry_on_error=True, max_retries=3, delay=2)` with async body. Replace sync `get_db_session()` DLQ routing with async DLQ operations using task's `DbSession`. Replace `self.request.retries` with `Context.message.labels.get('_retries', 0)`. Add schedule label for `process_scheduled_messages` interval (60s) as the first beat entry.
  - Verify: `python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/messaging_taskiq.py').read())"` and `grep -c "@broker.task" backend-hormonia/app/tasks/messaging_taskiq.py` returns at least `1`
  - Done when: `send_scheduled_message` Taskiq task defined in `messaging_taskiq.py`, no `run_async` or sync session, retry via SmartRetryMiddleware, DLQ via async session

- [ ] **T03: Migrate remaining 8 messaging tasks with schedule labels** `est:1h`
  - Why: Completes the full messaging task migration. All remaining tasks are LOW or MEDIUM complexity and follow the pattern proven in T02.
  - Files: `backend-hormonia/app/tasks/messaging_taskiq.py`
  - Do: Add 8 tasks: `process_scheduled_messages`, `retry_failed_messages`, `send_bulk_messages` (with `schedule_by_time()` for ETA), `cleanup_old_messages`, `generate_message_analytics` (convert sync ORM queries to async `select()`), `process_whatsapp_dlq` (direct `await` instead of `run_async()`), `process_dlq_messages` (sync DLQ service wrapped pragmatically), `retry_pending_welcome_messages`. Add all 7 schedule labels. Internal `.delay()` cross-calls become `await .kiq()`.
  - Verify: `grep -c "@broker.task" backend-hormonia/app/tasks/messaging_taskiq.py` returns `9`, `grep -c "schedule=" backend-hormonia/app/tasks/messaging_taskiq.py` returns `7`, `grep "\.delay\b\|run_async\|get_scoped_session\|get_db_session" backend-hormonia/app/tasks/messaging_taskiq.py` returns nothing
  - Done when: All 9 Taskiq messaging tasks defined, all 7 schedule labels present, no sync session or Celery dispatch patterns

- [ ] **T04: Update messaging-domain call sites and verify coexistence** `est:45m`
  - Why: The Taskiq tasks exist but nothing calls them yet from the messaging domain. This task wires the new dispatch patterns into `api/v2/messages/retry.py`, `task_scheduler.py`, and `retry_handler.py` — the three external call sites in S02 scope.
  - Files: `backend-hormonia/app/api/v2/messages/retry.py`, `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py`, `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py`
  - Do: In `retry.py`: change import to `from app.tasks.messaging_taskiq import send_scheduled_message, retry_failed_messages` (Taskiq versions), change `.delay()` to `await .kiq()`, adjust `task_result.id` to `task_result.task_id`. In `task_scheduler.py`: import Taskiq `send_scheduled_message` + `dynamic_schedule_source`, replace `.apply_async(eta=)` with `await send_scheduled_message.kicker().schedule_by_time(dynamic_schedule_source, delivery_time, str(message.id))`. In `retry_handler.py`: same ETA replacement pattern. Verify Celery tasks in `messaging.py` untouched. Verify external callers (`flow_automation.py`, `batch_tasks.py`) still import from `app.tasks.messaging` (Celery).
  - Verify: AST parse all 3 modified files. `grep "\.delay\|\.apply_async" backend-hormonia/app/api/v2/messages/retry.py backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py` returns nothing. `grep -c "@celery_app.task" backend-hormonia/app/tasks/messaging.py` still returns `9`. `grep "send_scheduled_message.delay" backend-hormonia/app/tasks/flow_automation.py backend-hormonia/app/tasks/flows/batch_tasks.py` still finds Celery calls (not broken).
  - Done when: All 3 messaging-domain call sites dispatch via Taskiq, Celery messaging tasks untouched, external callers still work

## Files Likely Touched

- `backend-hormonia/app/taskiq_broker.py` — Add ListRedisScheduleSource
- `backend-hormonia/app/tasks/taskiq_base.py` — Add schedule_by_time helper
- `backend-hormonia/app/tasks/messaging_taskiq.py` — NEW: all 9 Taskiq messaging tasks
- `backend-hormonia/app/api/v2/messages/retry.py` — Switch to Taskiq dispatch
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py` — ETA → schedule_by_time
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/retry_handler.py` — ETA → schedule_by_time
