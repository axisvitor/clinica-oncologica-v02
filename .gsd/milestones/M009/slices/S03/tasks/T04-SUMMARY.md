---
id: T04
parent: S03
milestone: M009
provides:
  - 3 external call sites wired to Taskiq dispatch (response_handler, delivery, message)
  - recovery.py documented for S05 coexistence (TODO comment added)
  - Full slice verification passed (17 tasks, 12 schedules, 0 bridges, 0 Celery dispatch in Taskiq files)
key_files:
  - backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py
  - backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py
  - backend-hormonia/app/services/follow_up_system/execution/message.py
  - backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py
  - backend-hormonia/app/services/flow/recovery.py
key_decisions:
  - delivery.py enqueue_failed_flow_send_retry made async — all callers (SequencingMixin._send_flow_message) are already async
  - message.py _enqueue_retry made async — caller _execute_message_action is already async
  - recovery.py attempt_recovery keeps Celery .delay() — sync function with sync callers, S05 migration deferred
  - FOLLOWUP_RETRY_BASE_DELAY (30s) defined locally in message.py to avoid importing from Celery module
  - MESSAGE_RETRY_DELAY imported from config/settings/tasks.py (canonical source) instead of from Celery send_retry module
patterns_established:
  - ".apply_async(args=[...], kwargs={...}, countdown=N)" → "await schedule_task_at(task, datetime.now(UTC) + timedelta(seconds=N), *args, **kwargs)"
  - ".delay(arg)" → "await task.kiq(arg)" in async contexts
  - "result.id" → "result.task_id" for Taskiq AsyncTaskiqDecoratedTask results
  - Sync call sites that cannot be made async keep Celery dispatch with TODO(S05) marker
observability_surfaces:
  - response_handler.py logs Taskiq task_id on quiz report dispatch
  - delivery.py logs retry enqueue with message_id/patient_id structured fields
  - message.py sets execution_result with retry_enqueued flag
  - recovery.py TODO(S05) marker visible via grep
duration: 12m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T04: Wired 3 external call sites to Taskiq dispatch and passed all slice verification

**Migrated generate_quiz_report, retry_failed_flow_send, and retry_failed_followup_send dispatch from Celery .delay()/.apply_async() to Taskiq .kiq()/schedule_task_at() in 3 async call sites; documented recovery.py for S05 coexistence; all slice verification checks passed.**

## What Happened

Wired 4 external call sites that dispatched flow tasks via Celery:

1. **response_handler.py** (async `_complete_quiz_session`): Changed `generate_quiz_report.delay(session_id)` → `await generate_quiz_report.kiq(session_id)` from `flows_taskiq`. Updated `report_task.id` → `report_task.task_id`.

2. **delivery.py** (`enqueue_failed_flow_send_retry`): Converted from sync to `async def`. Replaced `retry_failed_flow_send.apply_async(args=..., countdown=SEND_RETRY_BASE_DELAY)` → `await schedule_task_at(retry_failed_flow_send, datetime.now(UTC) + timedelta(seconds=MESSAGE_RETRY_DELAY), ...)`. Updated both callers in `sequencing.py` to `await`.

3. **message.py** (`_enqueue_retry`): Converted from sync to `async def`. Replaced `retry_failed_followup_send.apply_async(args=..., countdown=FOLLOWUP_RETRY_BASE_DELAY)` → `await schedule_task_at(retry_failed_followup_send, ...)`. Updated caller `_execute_message_action` to `await self._enqueue_retry(action)`.

4. **recovery.py** (`attempt_recovery`): Left Celery `.delay()` intact — sync function with sync callers. Added TODO(S05) comment explaining the coexistence constraint.

## Verification

All slice-level acceptance criteria passed:

```
AST parse: flows_taskiq OK, saga_retry_taskiq OK, response_handler OK, delivery OK, message OK, sequencing OK, recovery OK
Task counts: flows_taskiq=14, saga_retry_taskiq=3 (17 total)
Schedule counts: flows_taskiq=10, saga_retry_taskiq=2 (12 total)
Bridge code in Taskiq files: 0 (all matches in comments/docstrings only)
Celery dispatch in Taskiq files: 0 (all matches in comments/docstrings only)
Celery originals intact: flow_automation=5, saga_retry=3, flow_tasks=1, stuck_detection=1, monitoring=2, monthly_tasks=2, cleanup_tasks=1, followup_retry=1, send_retry=1
Call sites migrated: all 3 show "from app.tasks.flows_taskiq import"
Call sites zero Celery dispatch: response_handler=0, delivery=0, message=0
recovery.py retained: retry_failed_flow_send.delay() present (intentional)
```

## Diagnostics

- Taskiq imports in call sites: `grep "from app.tasks.flows_taskiq import" response_handler.py delivery.py message.py`
- Zero Celery dispatch: `grep -c "\.delay(\|\.apply_async(" response_handler.py delivery.py message.py` = 0
- Coexistence marker: `grep "TODO(S05)" backend-hormonia/app/services/flow/recovery.py`
- Task inventory: `grep -c "@broker.task" flows_taskiq.py` = 14, `saga_retry_taskiq.py` = 3

## Deviations

- `sequencing.py` was not listed in the task plan as a file to modify, but required `await` updates at 2 call sites of `enqueue_failed_flow_send_retry` (now async). This was implied by the plan's "update any callers" instruction.
- `MESSAGE_RETRY_DELAY` imported from `app.config.settings.tasks` instead of `SEND_RETRY_BASE_DELAY` from Celery module — same underlying value (env-driven, default 60s), avoids importing from Celery task module.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/domain/quizzes/integration/flow_integration/response_handler.py` — Switched generate_quiz_report dispatch to Taskiq .kiq()
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py` — Made enqueue_failed_flow_send_retry async, using schedule_task_at
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py` — Added await to 2 enqueue_failed_flow_send_retry calls
- `backend-hormonia/app/services/follow_up_system/execution/message.py` — Made _enqueue_retry async, using schedule_task_at
- `backend-hormonia/app/services/flow/recovery.py` — Added TODO(S05) comment, Celery .delay() retained
- `.gsd/milestones/M009/slices/S03/tasks/T04-PLAN.md` — Added Observability Impact section
