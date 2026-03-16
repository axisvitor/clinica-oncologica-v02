---
estimated_steps: 5
estimated_files: 5
---

# T04: Wire external call sites and run slice verification

**Slice:** S03 — Flow/saga tasks migradas
**Milestone:** M009

## Description

Update external service files that dispatch flow tasks via Celery `.delay()`/`.apply_async()` to use Taskiq `.kiq()`/`schedule_task_at()`. There are 4 call sites — 3 can be migrated (they're in async contexts or can be made async), 1 stays on Celery during coexistence (`recovery.py:211` is deep inside a sync function). Then run comprehensive slice-level verification.

## Steps

1. **Wire `response_handler.py:470`** — This is inside an `async def _complete_quiz_session()` method. Change:
   - Import: `from app.tasks.flows import generate_quiz_report` → `from app.tasks.flows_taskiq import generate_quiz_report`
   - Dispatch: `report_task = generate_quiz_report.delay(str(session.id))` → `report_task = await generate_quiz_report.kiq(str(session.id))`
   - Result access: `report_task.id` → `report_task.task_id`
   - File: `backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py`

2. **Wire `delivery.py:92`** — This is inside a sync function `_enqueue_flow_send_retry()`. The function must become `async def` to use `await schedule_task_at()`. Check all callers of this function — if they're already async (likely, since it's in a message handler pipeline), this is safe. Change:
   - Import: `from app.tasks.flows.send_retry import SEND_RETRY_BASE_DELAY, retry_failed_flow_send` → `from app.tasks.flows_taskiq import retry_failed_flow_send` + define base delay locally or import from the Celery module
   - Function: `def _enqueue_flow_send_retry(...)` → `async def _enqueue_flow_send_retry(...)`
   - Dispatch: `retry_failed_flow_send.apply_async(args=[...], kwargs={...}, countdown=SEND_RETRY_BASE_DELAY)` → `await schedule_task_at(retry_failed_flow_send, datetime.now(UTC) + timedelta(seconds=SEND_RETRY_BASE_DELAY), str(message_id), flow_context=flow_context)`
   - Update any callers of this function to use `await` if they aren't already
   - File: `backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py`

3. **Wire `message.py:81`** — This is inside `_enqueue_retry()` method of a class. Check if it can be made async. Change:
   - Import: `from app.tasks.flows.followup_retry import FOLLOWUP_RETRY_BASE_DELAY, retry_failed_followup_send` → `from app.tasks.flows_taskiq import retry_failed_followup_send` + import base delay
   - Method: `def _enqueue_retry(...)` → `async def _enqueue_retry(...)`
   - Dispatch: `retry_failed_followup_send.apply_async(args=[...], kwargs={...}, countdown=FOLLOWUP_RETRY_BASE_DELAY)` → `await schedule_task_at(retry_failed_followup_send, datetime.now(UTC) + timedelta(seconds=FOLLOWUP_RETRY_BASE_DELAY), ...)`
   - Update callers to use `await` if needed
   - File: `backend-hormonia/app/services/follow_up_system/execution/message.py`

4. **Document `recovery.py:211` for S05** — `attempt_recovery()` is a sync function that calls `retry_failed_flow_send.delay(...)`. Converting to async would break `detect_stuck_flows` and other sync callers. Leave as-is. Add a comment: `# TODO(S05): migrate to flows_taskiq.retry_failed_flow_send.kiq() after Celery removal`.

5. **Run comprehensive slice verification:**
   ```bash
   # AST parse all new/modified files
   python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/flows_taskiq.py').read()); print('flows_taskiq: OK')"
   python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/saga_retry_taskiq.py').read()); print('saga_retry_taskiq: OK')"
   python -c "import ast; [ast.parse(open(f).read()) for f in ['backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py', 'backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py', 'backend-hormonia/app/services/follow_up_system/execution/message.py']]; print('call sites: OK')"

   # Task counts
   grep -c "@broker.task" backend-hormonia/app/tasks/flows_taskiq.py  # = 14
   grep -c "@broker.task" backend-hormonia/app/tasks/saga_retry_taskiq.py  # = 3

   # Schedule counts
   grep -c "schedule=" backend-hormonia/app/tasks/flows_taskiq.py backend-hormonia/app/tasks/saga_retry_taskiq.py  # = 12 total (10+2)

   # Zero bridge code
   grep -c "async_to_sync\|run_async\|run_async_in_sync\|run_async_in_thread" backend-hormonia/app/tasks/flows_taskiq.py backend-hormonia/app/tasks/saga_retry_taskiq.py  # = 0

   # Zero Celery dispatch in Taskiq files
   grep -c "\.delay(\|\.apply_async(" backend-hormonia/app/tasks/flows_taskiq.py backend-hormonia/app/tasks/saga_retry_taskiq.py  # = 0

   # Celery originals intact
   grep -c "@celery_app.task" backend-hormonia/app/tasks/flow_automation.py backend-hormonia/app/tasks/saga_retry.py backend-hormonia/app/tasks/flows/flow_tasks.py backend-hormonia/app/tasks/flows/stuck_detection.py backend-hormonia/app/tasks/flows/monitoring.py backend-hormonia/app/tasks/flows/monthly_tasks.py backend-hormonia/app/tasks/flows/cleanup_tasks.py backend-hormonia/app/tasks/flows/followup_retry.py backend-hormonia/app/tasks/flows/send_retry.py  # unchanged

   # Call sites migrated
   grep "from app.tasks.flows_taskiq import" backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py
   grep "from app.tasks.flows_taskiq import" backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py
   grep "from app.tasks.flows_taskiq import" backend-hormonia/app/services/follow_up_system/execution/message.py

   # recovery.py still has Celery .delay() (intentional coexistence)
   grep "retry_failed_flow_send.delay" backend-hormonia/app/services/flow/recovery.py
   ```

## Must-Haves

- [ ] `response_handler.py` dispatches `generate_quiz_report` via `await .kiq()` from `flows_taskiq`
- [ ] `delivery.py` dispatches `retry_failed_flow_send` via `await schedule_task_at()` from `flows_taskiq`
- [ ] `message.py` dispatches `retry_failed_followup_send` via `await schedule_task_at()` from `flows_taskiq`
- [ ] `recovery.py:211` stays on Celery `.delay()` with TODO comment for S05
- [ ] All modified files pass `ast.parse()`
- [ ] All slice-level verification checks pass (17 tasks, 12 schedules, 0 bridges, 0 Celery dispatch in Taskiq files)

## Verification

- All 4 external call-site files pass `ast.parse()`
- `grep "from app.tasks.flows_taskiq import" response_handler.py delivery.py message.py` → shows Taskiq imports in all 3
- `grep "\.delay\|\.apply_async" response_handler.py delivery.py message.py` for flow task calls → 0 matches
- `recovery.py` still has `.delay()` → confirmed (intentional)
- All slice verification checks pass (listed in step 5 above)

## Inputs

- `backend-hormonia/app/tasks/flows_taskiq.py` — T01+T02 output (14 tasks)
- `backend-hormonia/app/tasks/saga_retry_taskiq.py` — T03 output (3 tasks)
- `backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py:470` — async method, `generate_quiz_report.delay()`
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py:92` — sync function, `.apply_async(countdown=)`
- `backend-hormonia/app/services/follow_up_system/execution/message.py:81` — sync method, `.apply_async(countdown=)`
- `backend-hormonia/app/services/flow/recovery.py:211` — sync function, `.delay()` — KEEP for coexistence

### Key patterns:
- `.delay(arg)` → `await task.kiq(arg)` (async context)
- `.apply_async(args=[...], kwargs={...}, countdown=N)` → `await schedule_task_at(task, datetime.now(UTC) + timedelta(seconds=N), *args, **kwargs)`
- `result.id` → `result.task_id` for Taskiq task results
- Sync callers of `.delay()` that cannot become async → keep Celery during coexistence, add S05 TODO

## Expected Output

- `backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py` — Updated import + `.kiq()` dispatch
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py` — Updated import + `schedule_task_at()` dispatch
- `backend-hormonia/app/services/follow_up_system/execution/message.py` — Updated import + `schedule_task_at()` dispatch
- `backend-hormonia/app/services/flow/recovery.py` — TODO comment added, `.delay()` stays
- Verification script output confirming all slice acceptance criteria pass
