---
estimated_steps: 4
estimated_files: 4
---

# T02: Resolve TODO(S05) call sites — trigger_service.py and recovery.py

**Slice:** S05 — Celery removal + bridge cleanup
**Milestone:** M009

## Description

3 call sites still dispatch via Celery `.apply_async(eta=)` and `.delay()`:
- `trigger_service.py` line 724: `send_quiz_link_reminder_task.apply_async(args=[str(quiz_session_id), 24], eta=reminder_1_time)`
- `trigger_service.py` line 732: `send_quiz_link_reminder_task.apply_async(args=[str(quiz_session_id), 6], eta=reminder_2_time)`
- `recovery.py` line 214: `retry_failed_flow_send.delay(prompt_message_id, flow_context=...)`

These must be converted to Taskiq dispatch before Celery files are deleted in T03.

## Steps

1. **Convert trigger_service.py (2 call sites)** — File: `backend-hormonia/app/domain/quizzes/integration/flow_integration/trigger_service.py`
   
   The function `_schedule_link_reminders` at line 700 is already `async def`, so `await` works directly.
   
   - Remove the Celery import: `from app.tasks.quiz_flow.trigger_tasks import send_quiz_link_reminder_task` (line 711)
   - Add Taskiq imports at top of function (lazy import pattern, same as existing):
     ```python
     from app.tasks.quiz_link_taskiq import send_quiz_reminder
     from app.tasks.taskiq_base import schedule_task_at
     ```
   - Replace line 724-727:
     ```python
     # Old: task_1 = send_quiz_link_reminder_task.apply_async(args=[str(quiz_session_id), 24], eta=reminder_1_time)
     # New:
     schedule_result_1 = await schedule_task_at(send_quiz_reminder, reminder_1_time, str(quiz_session_id), 24)
     logger.info(f"Scheduled first reminder for quiz {quiz_session_id} at {reminder_1_time} (schedule: {schedule_result_1.schedule_id})")
     ```
   - Replace line 732-735 similarly for the second reminder
   - Remove the TODO(S05) comments
   - Update the `session_metadata["reminders_scheduled"]` section if it references `task_1.id`/`task_2.id` — use `schedule_result_1.schedule_id`/`schedule_result_2.schedule_id` instead

2. **Convert recovery.py** — File: `backend-hormonia/app/services/flow/recovery.py`
   
   `attempt_recovery()` at line 128 is currently sync. It must become `async def` because:
   - Line 198 uses `async_to_sync(flow_manager.advance_patient_flow)(...)` → replace with `await flow_manager.advance_patient_flow(...)`
   - Line 214 uses `retry_failed_flow_send.delay(...)` → replace with `await retry_failed_flow_send.kiq(...)`
   
   Changes:
   - Remove `from asgiref.sync import async_to_sync` (line 9)
   - Change `def attempt_recovery(db, flow_state, redis_client) -> dict:` to `async def attempt_recovery(db, flow_state, redis_client) -> dict:`
   - Line 198: Replace `async_to_sync(flow_manager.advance_patient_flow)(latest_flow.patient_id, force_day=force_day)` with `await flow_manager.advance_patient_flow(latest_flow.patient_id, force_day=force_day)`
   - Line 211-214: Replace Celery import and `.delay()`:
     ```python
     # Old:
     from app.tasks.flows.send_retry import retry_failed_flow_send
     retry_failed_flow_send.delay(prompt_message_id, flow_context=...)
     # New:
     from app.tasks.flows_taskiq import retry_failed_flow_send
     await retry_failed_flow_send.kiq(prompt_message_id, _build_flow_context(latest_flow, updated_step_data))
     ```
   - Remove all TODO(S05) comments from this file

3. **Update detect_stuck_flows caller in flows_taskiq.py** — File: `backend-hormonia/app/tasks/flows_taskiq.py`
   
   The `detect_stuck_flows` Taskiq task calls `attempt_recovery()`. Since it's now async, the call must use `await`. Find the call site in `detect_stuck_flows` and update:
   - If it currently does `attempt_recovery(db, flow_state, redis_client)` → change to `await attempt_recovery(db, flow_state, redis_client)`
   - The task is already `async def`, so `await` works directly

4. **Verify all 3 files parse and have no Celery dispatch**

## Must-Haves

- [ ] trigger_service.py uses `await schedule_task_at(send_quiz_reminder, ...)` instead of `.apply_async(eta=)`
- [ ] recovery.py is `async def attempt_recovery(...)` using `await .kiq()` instead of `.delay()`
- [ ] recovery.py has no `from asgiref.sync import async_to_sync`
- [ ] flows_taskiq.py calls `await attempt_recovery(...)` 
- [ ] Zero TODO(S05) markers in the codebase
- [ ] All 3 files pass `ast.parse()`

## Verification

```bash
# 1. Zero TODO(S05)
! grep -rn 'TODO(S05)' backend-hormonia/app/ --include='*.py' && echo "PASS — No TODO(S05)" || echo "FAIL"

# 2. All files parse
python3 -c "
import ast, sys
files = [
    'backend-hormonia/app/domain/quizzes/integration/flow_integration/trigger_service.py',
    'backend-hormonia/app/services/flow/recovery.py',
    'backend-hormonia/app/tasks/flows_taskiq.py',
]
for f in files:
    try: ast.parse(open(f).read())
    except SyntaxError as e:
        print(f'FAIL: {f}: {e}')
        sys.exit(1)
print('PASS — All 3 files parse OK')
"

# 3. No Celery dispatch in trigger_service.py or recovery.py
! grep -n '\.delay\(\|\.apply_async\(\|from app\.tasks\.flows\.send_retry\|from app\.tasks\.quiz_flow' \
  backend-hormonia/app/domain/quizzes/integration/flow_integration/trigger_service.py \
  backend-hormonia/app/services/flow/recovery.py && echo "PASS — No Celery dispatch" || echo "FAIL"

# 4. No asgiref in recovery.py
! grep 'asgiref' backend-hormonia/app/services/flow/recovery.py && echo "PASS — No asgiref" || echo "FAIL"
```

## Inputs

- `backend-hormonia/app/domain/quizzes/integration/flow_integration/trigger_service.py` — lines 700-745 have the TODO(S05) Celery dispatch
- `backend-hormonia/app/services/flow/recovery.py` — lines 128-230 have `attempt_recovery()` with Celery dispatch
- `backend-hormonia/app/tasks/flows_taskiq.py` — `detect_stuck_flows` task calls `attempt_recovery()`
- `backend-hormonia/app/tasks/quiz_link_taskiq.py` — has `send_quiz_reminder` task to import
- `backend-hormonia/app/tasks/taskiq_base.py` — has `schedule_task_at()` helper

## Expected Output

- `trigger_service.py` — 2 call sites converted from `.apply_async(eta=)` to `await schedule_task_at()`
- `recovery.py` — `attempt_recovery()` is now async, uses `await .kiq()`, no asgiref
- `flows_taskiq.py` — `detect_stuck_flows` uses `await attempt_recovery()`

## Observability Impact

- **trigger_service.py**: Logger output changes from `task: {task_1.id}` (Celery task ID) to `schedule: {schedule_result_1.schedule_id}` (Taskiq schedule ID). Same `logger.info` call, same structured context — only the ID source changes.
- **recovery.py**: `logger.info("Recovered stuck flow", extra={...})` unchanged — still emits `flow_state_id`, `patient_id`, `action`, `attempt`. Failure path: `ValueError` on missing prompt_message_id surfaces via `log_task_error` in the calling Taskiq task.
- **flows_taskiq.py**: `detect_stuck_flows` structured return dict unchanged (`detected_count`, `recovered_count`, `skipped_count`, `failed_count`). `log_task_start/success/error` calls unchanged.
- **How to inspect**: `grep "Recovered stuck flow" <logs>` for recovery events. `grep "detect_stuck_flows" <logs>` for periodic run summaries. `schedule_id` values in trigger_service logs can be correlated against Taskiq's `ListRedisScheduleSource` in Redis/Dragonfly.
