---
id: T01
parent: S03
milestone: M009
provides:
  - flows_taskiq.py with 8 async-native Taskiq flow tasks
  - 6 schedule labels (2 cron, 4 interval)
  - Cross-task dispatch via send_scheduled_message.kiq()
key_files:
  - backend-hormonia/app/tasks/flows_taskiq.py
key_decisions:
  - process_daily_flows uses sync get_scoped_session for FlowStateRepository (sync ORM) then async batch via _process_single_patient_flow_by_id
  - resume_paused_flows and send_flow_day_for_patient use sync sessions for FlowManagementService and SequentialMessageHandler (sync ORM services)
  - process_monthly_quizzes and generate_quiz_report use sync sessions for quiz services (sync ORM)
patterns_established:
  - Sync ORM services (FlowStateRepository, FlowManagementService, SequentialMessageHandler) wrapped in get_scoped_session() context manager within async Taskiq tasks
  - Pure helpers imported from Celery modules (_determine_template_for_patient, _get_reminder_message, _is_auto_resume_due, _process_single_patient_flow_by_id) without duplication
observability_surfaces:
  - log_task_start/success/error with structured fields (task_name, event, duration_ms, error_type) for all 8 tasks
duration: 12m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: Created flows_taskiq.py with 8 async-native Taskiq flow tasks

**Created `backend-hormonia/app/tasks/flows_taskiq.py` with 8 `@broker.task` async tasks, 6 schedule labels, zero bridge code, and `send_daily_reminders` dispatching via `await send_scheduled_message.kiq()` from messaging_taskiq.**

## What Happened

Created the first 8 flow-domain Taskiq tasks following the exact pattern proven in S02's `messaging_taskiq.py`:

1. **process_daily_flows** — cron 08:00 BRT (11:00 UTC). Inlined `process_daily_flows_async()` logic directly as async task body. Uses `get_scoped_session()` for sync FlowStateRepository, delegates per-patient to `_process_single_patient_flow_by_id` (which manages its own sync session).
2. **check_and_start_pending_flows** — 900s interval. Direct async DB queries via DbSession, enrolls via EnhancedFlowEngine.
3. **send_daily_reminders** — cron 09:00 BRT (12:00 UTC). Critical change: `send_scheduled_message.delay()` → `await send_scheduled_message.kiq()` imported from `messaging_taskiq`.
4. **resume_paused_flows** — 3600s interval. Uses sync session for FlowManagementService (sync ORM).
5. **cleanup_expired_quiz_links** — 86400s interval. Pure async SQL cleanup.
6. **send_flow_day_for_patient** — on-demand with retry. Async DB queries + sync SequentialMessageHandler.
7. **process_monthly_quizzes** — 3600s interval. Sync session for quiz trigger service.
8. **generate_quiz_report** — on-demand with retry. Sync session for report generator.

Pure helpers imported from Celery modules without duplication: `_process_single_patient_flow_by_id`, `_determine_template_for_patient`, `_get_reminder_message`, `_is_auto_resume_due`.

## Verification

All task-level checks passed:

| Check | Expected | Actual | Status |
|---|---|---|---|
| `ast.parse()` | OK | OK | ✅ |
| `@broker.task` count | 8 | 8 | ✅ |
| `schedule=` count | 6 | 6 | ✅ |
| AST-level `async_to_sync`/`run_async` calls | 0 | 0 | ✅ |
| AST-level `.delay()`/`.apply_async()` calls | 0 | 0 | ✅ |
| Celery originals intact | unchanged | flow_automation:5, flow_tasks:1, monthly_tasks:2 | ✅ |

Slice-level checks (partial — T01 is intermediate):

| Check | Expected (slice end) | Current | Status |
|---|---|---|---|
| `@broker.task` in flows_taskiq.py | 14 | 8 | 🟡 (T02 adds 6) |
| saga_retry_taskiq.py exists | yes | no | 🟡 (T03) |
| External call sites wired | yes | no | 🟡 (T04) |

## Diagnostics

- Task inventory: `grep "@broker.task" backend-hormonia/app/tasks/flows_taskiq.py`
- Schedule entries: `grep "schedule=" backend-hormonia/app/tasks/flows_taskiq.py`
- Zero-bridge check: `python3 -c "import ast; [check AST for async_to_sync/run_async calls]"`
- Runtime: `grep "task_name=process_daily_flows" <worker-logs>` for execution tracing

## Deviations

- `resume_paused_flows`: Uses both async DbSession (for initial query) and sync `get_scoped_session()` (for FlowManagementService resume) — the Celery original used only sync. The initial query was converted to async for consistency but resume stays sync because FlowManagementService uses sync ORM.
- `send_flow_day_for_patient`: Patient/flow lookups converted to async queries, but SequentialMessageHandler call kept in sync session context.
- Constants (`_MAX_SAFE_DAILY_FLOW_LIMIT`, etc.) duplicated from `flow_tasks.py` to avoid importing the Celery module entirely.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/tasks/flows_taskiq.py` — NEW: 8 `@broker.task` async tasks with 6 schedule labels, structured logging, zero bridge code
