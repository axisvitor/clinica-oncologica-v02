---
estimated_steps: 6
estimated_files: 8
---

# T03: Fix flow, batch, and simple service test files

**Slice:** S06 — Verificação integrada ponta-a-ponta
**Milestone:** M009

## Description

Fix 8 test files that import from deleted flow subdirectories (`app.tasks.flows.*`) or `app.tasks.messaging`/`app.tasks.flow_automation`. Helper functions were moved to `app/tasks/helpers/flow_helpers.py`, task functions to `app/tasks/flows_taskiq.py`. `process_daily_flows_async` no longer exists — replaced by `process_daily_flows` in `flows_taskiq.py`.

## Steps

1. **`test_batch_processing.py`** (424 lines): All 12 imports `from app.tasks.flows.batch_tasks import X` → `from app.tasks.helpers.flow_helpers import X`. Functions: `_update_scheduling`, `_get_message_template_for_day`, `_process_single_patient_flow`, `_process_single_patient_flow_by_id`. Update all `@patch('app.tasks.flows.batch_tasks.X')` → `@patch('app.tasks.helpers.flow_helpers.X')`.

2. **`test_flow_tasks_hardening.py`** (97 lines): `from app.tasks.flows.flow_tasks import process_daily_flows_async` → `from app.tasks.flows_taskiq import process_daily_flows`. Update all references from `process_daily_flows_async` to `process_daily_flows`. Update `@patch` targets.

3. **`test_monitoring_health_task.py`** (68 lines): `from app.tasks.flows.monitoring import monitor_flow_task_health` → `from app.tasks.flows_taskiq import monitor_flow_task_health`. Convert `.run()` call (line 60) to async: either `asyncio.run(monitor_flow_task_health.fn())` or `@pytest.mark.asyncio` + `await`. Update `@patch` targets.

4. **`test_monthly_tasks_async_bridge.py`** (89 lines): `from app.tasks.flows.monthly_tasks import process_monthly_quizzes` → `from app.tasks.flows_taskiq import process_monthly_quizzes`; same for `generate_quiz_report`. Update `@patch` targets.

5. **`test_auto_resume_flows.py`** (90 lines): `from app.tasks.flow_automation import resume_paused_flows` → `from app.tasks.flows_taskiq import resume_paused_flows`. Convert `.run()` (line 32) to async. Update `@patch` targets.

6. **`test_flow_pause_detection.py`** (125 lines): `from app.tasks.flows.flow_tasks import process_daily_flows_async` → `from app.tasks.flows_taskiq import process_daily_flows`. Update references. Update `@patch` targets.

7. **`test_sanity_with_import.py`** (30 lines): `from app.tasks.messaging import send_scheduled_message` → `from app.tasks.messaging_taskiq import send_scheduled_message`.

8. **`test_patient_deletion.py`** (112 lines): `from app.tasks.messaging import send_scheduled_message` → `from app.tasks.messaging_taskiq import send_scheduled_message`. Update any `@patch('app.tasks.messaging.X')` → `@patch('app.tasks.messaging_taskiq.X')`.

## Must-Haves

- [ ] Zero imports from `app.tasks.flows.*`, `app.tasks.flow_automation`, `app.tasks.messaging` (without _taskiq suffix) in these 8 files
- [ ] All 8 files collect without import errors
- [ ] No references to `process_daily_flows_async` remain

## Verification

- `cd backend-hormonia && python3 -m pytest tests/tasks/flows/ tests/unit/tasks/test_auto_resume_flows.py tests/unit/services/test_flow_pause_detection.py tests/services/test_sanity_with_import.py tests/services/test_patient_deletion.py --collect-only 2>&1 | grep ERROR` — empty

## Inputs

- T01 and T02 complete
- `app/tasks/helpers/flow_helpers.py` contains: `_update_scheduling`, `_get_message_template_for_day`, `_process_single_patient_flow`, `_process_single_patient_flow_by_id`, `SEND_RETRY_MAX_RETRIES`, `FOLLOWUP_RETRY_MAX`, and 15+ other helpers extracted from 4 Celery sources
- `app/tasks/flows_taskiq.py` contains: `process_daily_flows` (replaces old `process_daily_flows_async`), `monitor_flow_task_health`, `process_monthly_quizzes`, `generate_quiz_report`, `resume_paused_flows`, `detect_stuck_flows`, etc.
- `app/tasks/messaging_taskiq.py` contains: `send_scheduled_message`, etc.

## Expected Output

- 8 test files with corrected imports, all collecting successfully

## Observability Impact

- **Signal changed:** `pytest --collect-only` error count drops by ~8 (these 8 files no longer produce `ModuleNotFoundError`/`ImportError`)
- **Inspection:** `grep -rn "app\.tasks\.flows\.\|app\.tasks\.flow_automation\|app\.tasks\.messaging[^_]"` on these 8 files returns empty
- **Failure visibility:** Any regression re-introducing old imports will surface as `ModuleNotFoundError` at collection time with exact file:line
- **AST scan:** The reusable AST zero-import scanner (see S06 verification) covers these files
