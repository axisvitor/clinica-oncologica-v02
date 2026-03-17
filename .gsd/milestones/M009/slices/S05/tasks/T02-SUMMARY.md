---
id: T02
parent: S05
milestone: M009
provides:
  - trigger_service.py uses Taskiq schedule_task_at() for quiz reminders instead of Celery .apply_async(eta=)
  - recovery.py is async, dispatches via await .kiq() instead of Celery .delay()
  - detect_stuck_flows in flows_taskiq.py uses await attempt_recovery()
  - Zero TODO(S05) markers remaining in codebase
key_files:
  - backend-hormonia/app/domain/quizzes/integration/flow_integration/trigger_service.py
  - backend-hormonia/app/services/flow/recovery.py
  - backend-hormonia/app/tasks/flows_taskiq.py
key_decisions:
  - recovery.py attempt_recovery() converted from sync to async def — this is safe because its only caller (detect_stuck_flows in flows_taskiq.py) is already an async Taskiq task
patterns_established:
  - ETA-scheduled task dispatch uses schedule_task_at(task, time, *args) from taskiq_base — returns CreatedSchedule with schedule_id for tracking
  - On-demand task dispatch uses await task.kiq(*args, **kwargs) — direct Taskiq async kick
observability_surfaces:
  - trigger_service.py logs schedule_id from Taskiq schedule source (replacing Celery task_id)
  - recovery.py structured logger.info("Recovered stuck flow") unchanged — emits flow_state_id, patient_id, action, attempt
  - detect_stuck_flows return dict (detected/recovered/skipped/failed counts) unchanged
duration: 8m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T02: Resolve TODO(S05) call sites — trigger_service.py and recovery.py

**Converted 3 Celery dispatch call sites to Taskiq: 2 `.apply_async(eta=)` in trigger_service.py → `schedule_task_at()`, 1 `.delay()` in recovery.py → `await .kiq()`, plus made `attempt_recovery()` async.**

## What Happened

Three Celery dispatch call sites were the last remaining TODO(S05) markers in the codebase:

1. **trigger_service.py** (`_schedule_link_reminders`): Two `.apply_async(args=[...], eta=time)` calls for quiz link reminders replaced with `await schedule_task_at(send_quiz_reminder, time, ...)`. Import changed from `app.tasks.quiz_flow.trigger_tasks` (Celery) to `app.tasks.quiz_link_taskiq` + `app.tasks.taskiq_base`. Logger output now shows `schedule_id` instead of Celery `task_id`.

2. **recovery.py** (`attempt_recovery`): Converted from sync `def` to `async def`. Removed `from asgiref.sync import async_to_sync`. The `async_to_sync(flow_manager.advance_patient_flow)(...)` bridge became `await flow_manager.advance_patient_flow(...)`. The `retry_failed_flow_send.delay(...)` Celery dispatch became `await retry_failed_flow_send.kiq(...)` importing from `flows_taskiq`.

3. **flows_taskiq.py** (`detect_stuck_flows`): Updated the `attempt_recovery(db, flow_state, redis_client)` call to `await attempt_recovery(...)`. Cleaned up the docstring noting Celery coexistence.

## Verification

All task-level checks passed:
- `ast.parse()` on all 3 files: **PASS**
- Zero `TODO(S05)` in `backend-hormonia/app/`: **PASS**
- No `.delay()` or `.apply_async()` in trigger_service.py or recovery.py: **PASS**
- No `asgiref` import in recovery.py: **PASS**

Slice-level checks (intermediate — T03/T04 still pending):
- V2 (13 Taskiq modules parse): **PASS**
- V6 (47 schedule labels): **PASS**
- V7 (10 helper modules parse): **PASS**
- V8 (no TODO(S05)): **PASS**
- V1, V3, V4, V5, V9: Not yet applicable (depend on T03 Celery file deletions)

## Diagnostics

- `grep "Scheduled first reminder" <logs>` — shows quiz reminder scheduling with `schedule:` field (Taskiq schedule_id)
- `grep "Recovered stuck flow" <logs>` — shows recovery events with flow_state_id, patient_id, action, attempt
- `detect_stuck_flows` return dict reports `recovered_count`/`failed_count` per run
- `ValueError` on missing prompt_message_id in recovery surfaces via `log_task_error` + Sentry

## Deviations

None — plan followed exactly.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/domain/quizzes/integration/flow_integration/trigger_service.py` — 2 `.apply_async(eta=)` → `await schedule_task_at()`, import swapped from Celery to Taskiq
- `backend-hormonia/app/services/flow/recovery.py` — sync→async, removed asgiref, `.delay()` → `await .kiq()`, import from flows_taskiq
- `backend-hormonia/app/tasks/flows_taskiq.py` — `await attempt_recovery()`, cleaned coexistence docstring
- `.gsd/milestones/M009/slices/S05/S05-PLAN.md` — T02 marked done, added failure-path diagnostic to observability
- `.gsd/milestones/M009/slices/S05/tasks/T02-PLAN.md` — added Observability Impact section
