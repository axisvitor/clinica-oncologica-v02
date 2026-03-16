---
estimated_steps: 6
estimated_files: 7
---

# T01: Create flows_taskiq.py with process_daily_flows + flow_automation + monthly tasks (8 tasks)

**Slice:** S03 — Flow/saga tasks migradas
**Milestone:** M009

## Description

Create `backend-hormonia/app/tasks/flows_taskiq.py` with the first 8 flow-domain Taskiq tasks, following the exact pattern proven in S02's `messaging_taskiq.py`. This covers the core daily loop (`process_daily_flows`), the 5 flow automation tasks, and 2 monthly tasks.

The key insight: `process_daily_flows_async()` in `flow_tasks.py` is already an async function — it becomes the Taskiq task body directly without any bridge. Batch helpers (`_process_single_patient_flow_by_id`, `_process_single_patient_flow`, `_get_message_template_for_day`) are sync and manage their own sessions via `get_scoped_session()` — import them from the Celery module without modification.

For `send_daily_reminders` (flow_automation.py), the Celery version calls `send_scheduled_message.delay()`. The Taskiq version must use `await send_scheduled_message.kiq()` imported from `messaging_taskiq`.

## Steps

1. Read source Celery tasks for understanding:
   - `backend-hormonia/app/tasks/flows/flow_tasks.py` — `process_daily_flows` + `process_daily_flows_async()`
   - `backend-hormonia/app/tasks/flow_automation.py` — 5 tasks: `check_and_start_pending_flows`, `send_daily_reminders`, `resume_paused_flows`, `cleanup_expired_quiz_links`, `send_flow_day_for_patient`
   - `backend-hormonia/app/tasks/flows/monthly_tasks.py` — 2 tasks: `process_monthly_quizzes`, `generate_quiz_report`
   - `backend-hormonia/app/tasks/flows/batch_tasks.py` — helper functions used by process_daily_flows

2. Read `backend-hormonia/app/tasks/messaging_taskiq.py` (first ~80 lines) for the exact module structure pattern: imports, broker import, module docstring, DbSession usage.

3. Create `backend-hormonia/app/tasks/flows_taskiq.py` with:
   - Module docstring listing all tasks (will be 14 when T02 completes, start with 8)
   - Standard imports: `broker` from `app.taskiq_broker`, `DbSession`, `log_task_start/success/error`, `schedule_task_at` from `app.tasks.taskiq_base`
   - Import `send_scheduled_message` from `app.tasks.messaging_taskiq` for cross-task dispatch
   - Import pure helpers from Celery modules: `_process_single_patient_flow_by_id` from `batch_tasks`, `_determine_template_for_patient`/`_get_reminder_message`/`_is_auto_resume_due`/`_normalize_template_day` from `flow_automation`, etc.
   - Import `get_scoped_session` from `app.database` for sync helpers that need it

4. Translate the 8 tasks following S02 pattern:

   **4a. `process_daily_flows`** — schedule=cron 8:00 BRT (11:00 UTC). The body IS `process_daily_flows_async()` flattened — create AsyncSession for initial FlowStateRepository queries, then delegate per-patient processing to `_process_single_patient_flow_by_id` (sync, manages own session). The Celery version wraps `process_daily_flows_async()` via `async_to_sync`. The Taskiq version calls it directly as async.

   **4b. `check_and_start_pending_flows`** — schedule=900s interval. Remove `async_to_sync` bridge, make async, use DbSession for async queries.

   **4c. `send_daily_reminders`** — schedule=cron 9:00 BRT (12:00 UTC). Remove bridge. Critical change: replace `send_scheduled_message.delay(str(message.id))` with `await send_scheduled_message.kiq(str(message.id))` importing from `messaging_taskiq`.

   **4d. `resume_paused_flows`** — schedule=3600s interval. Remove bridge, make async.

   **4e. `cleanup_expired_quiz_links`** — schedule=86400s interval. Remove bridge, pure SQL cleanup.

   **4f. `send_flow_day_for_patient`** — on-demand (no schedule). Uses `autoretry_for` in Celery → SmartRetryMiddleware labels.

   **4g. `process_monthly_quizzes`** — schedule=3600s interval. Remove `run_async` bridge, make async.

   **4h. `generate_quiz_report`** — on-demand with retry. Remove bridge, SmartRetryMiddleware for retry.

5. For each task, add:
   - `@broker.task(...)` with appropriate labels (retry_on_error, max_retries, delay for retry tasks; schedule for periodic)
   - `async def` body with `db: AsyncSession = DbSession` parameter
   - `log_task_start()` at entry, `log_task_success()` on success, `log_task_error()` on exception
   - Comprehensive docstring following S02 pattern

6. Verify:
   - `python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/flows_taskiq.py').read()); print('OK')"`
   - `grep -c "@broker.task" backend-hormonia/app/tasks/flows_taskiq.py` = 8
   - `grep -c "schedule=" backend-hormonia/app/tasks/flows_taskiq.py` = 6
   - `grep -c "async_to_sync\|run_async" backend-hormonia/app/tasks/flows_taskiq.py` = 0

## Must-Haves

- [ ] 8 `@broker.task` decorated async tasks in flows_taskiq.py
- [ ] 6 schedule labels (process_daily_flows cron 8:00, check_and_start_pending_flows 900s, send_daily_reminders cron 9:00, resume_paused_flows 3600s, cleanup_expired_quiz_links 86400s, process_monthly_quizzes 3600s)
- [ ] Zero `async_to_sync`, `run_async`, or other bridge patterns
- [ ] `send_daily_reminders` dispatches via `await send_scheduled_message.kiq()` from `messaging_taskiq`
- [ ] Pure helpers imported from Celery modules — no duplication
- [ ] File passes `ast.parse()` without errors

## Verification

- `python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/flows_taskiq.py').read()); print('OK')"` → prints OK
- `grep -c "@broker.task" backend-hormonia/app/tasks/flows_taskiq.py` → 8
- `grep -c "schedule=" backend-hormonia/app/tasks/flows_taskiq.py` → 6 (6 periodic tasks)
- `grep -c "async_to_sync\|run_async" backend-hormonia/app/tasks/flows_taskiq.py` → 0
- `grep -c "\.delay(\|\.apply_async(" backend-hormonia/app/tasks/flows_taskiq.py` → 0

## Observability Impact

- Signals added: `log_task_start/success/error` for 8 tasks with structured fields (task_name, event, duration_ms, error_type)
- How a future agent inspects this: `grep "task_name=process_daily_flows" <worker-logs>` for execution tracing
- Failure state exposed: SmartRetryMiddleware logs "Retrying N/M in X.XX seconds"; task error logs include full traceback with context

## Inputs

- `backend-hormonia/app/tasks/flows/flow_tasks.py` (379 lines) — Celery `process_daily_flows` + `process_daily_flows_async()`
- `backend-hormonia/app/tasks/flow_automation.py` (637 lines) — 5 Celery tasks with `async_to_sync` pattern
- `backend-hormonia/app/tasks/flows/monthly_tasks.py` (168 lines) — 2 Celery tasks with `run_async` bridge
- `backend-hormonia/app/tasks/flows/batch_tasks.py` (637 lines) — Helper functions used by process_daily_flows (sync, own sessions)
- `backend-hormonia/app/tasks/messaging_taskiq.py` (1237 lines) — S02 reference for all patterns
- `backend-hormonia/app/tasks/taskiq_base.py` — DbSession, log_task_start/success/error, schedule_task_at
- `backend-hormonia/app/taskiq_broker.py` — broker instance

### Critical patterns from S02 (messaging_taskiq.py):
- `from app.taskiq_broker import broker`
- `from app.tasks.taskiq_base import DbSession, log_task_start, log_task_success, log_task_error, schedule_task_at`
- `@broker.task(task_name="...", retry_on_error=True, max_retries=3, delay=60)`
- Schedule: `@broker.task(task_name="...", schedule=[{"cron": "0 11 * * *"}])` for cron (UTC)
- Schedule: `@broker.task(task_name="...", schedule=[{"every": "900"}])` for interval
- Cross-task dispatch: `await send_scheduled_message.kiq(str(message_id))`
- DB session: `async def my_task(db: AsyncSession = DbSession)`

### Key constraints from research:
- `_process_single_patient_flow_by_id` creates its own sync session via `get_scoped_session()` — do NOT pass task-level DbSession to it
- Pure helpers from Celery modules are imported without duplication
- `process_daily_flows_async()` is already async — becomes task body directly
- `send_scheduled_message.delay()` → `await send_scheduled_message.kiq()` from `messaging_taskiq`

## Expected Output

- `backend-hormonia/app/tasks/flows_taskiq.py` — NEW file with 8 `@broker.task` async tasks, 6 schedule labels, structured logging, no bridge code
