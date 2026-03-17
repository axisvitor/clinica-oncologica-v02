---
estimated_steps: 8
estimated_files: 7
---

# T04: Fix retry, exception, and Celery-deep test files

**Slice:** S06 — Verificação integrada ponta-a-ponta
**Milestone:** M009

## Description

Fix 7 test files with deep Celery dependencies: `celery.exceptions.MaxRetriesExceededError`, `from app.celery_app`, `.run()` on Celery bound tasks, `celery.result.AsyncResult`, and the deleted `celery_integration` utility module.

## Steps

1. **`test_followup_retry_task.py`** (190 lines):
   - Remove `from celery.exceptions import MaxRetriesExceededError` — define `class MaxRetriesExceededError(Exception): pass` locally or just use `Exception` in the test
   - `from app.tasks.flows.followup_retry import X` → `from app.tasks.flows_taskiq import retry_failed_followup_send` and `from app.tasks.helpers.flow_helpers import FOLLOWUP_RETRY_MAX`
   - Remove `.apply_async` mock (line 184-185) — Taskiq tasks use `.kiq()`, but if the test is checking retry dispatch, mock at service level instead
   - Update all `@patch('app.tasks.flows.followup_retry.X')` targets

2. **`test_send_retry_task.py`** (299 lines):
   - Remove `from celery.exceptions import MaxRetriesExceededError` — same local class pattern
   - `from app.tasks.flows.send_retry import X` → `from app.tasks.flows_taskiq import retry_failed_flow_send` and `from app.tasks.helpers.flow_helpers import SEND_RETRY_MAX_RETRIES, retry_send_message, should_retry_send, handle_send_retry_failure` (check exact function locations)
   - Update all `@patch` targets from `app.tasks.flows.send_retry.*` to correct module

3. **`test_stuck_detection.py`** (147 lines):
   - Remove `from app.celery_app import celery_app` (deleted module)
   - `from app.tasks.flows.stuck_detection import detect_stuck_flows` → `from app.tasks.flows_taskiq import detect_stuck_flows`
   - Remove any beat_schedule assertions (Taskiq uses LabelScheduleSource, not beat_schedule dict)
   - Convert 4× `.run()` calls to async: `@pytest.mark.asyncio` + `await detect_stuck_flows.fn()` or `asyncio.run()`
   - Update `@patch` targets

4. **`test_flow_recovery_retry_e2e.py`** (641 lines — largest file):
   - Remove `from celery.exceptions import MaxRetriesExceededError`
   - Replace 3 module imports:
     - `from app.tasks.flows import followup_retry as followup_retry_task` → `from app.tasks import flows_taskiq as followup_retry_task` (or restructure)
     - `from app.tasks.flows import send_retry as send_retry_task` → similar
     - `from app.tasks.flows import stuck_detection as stuck_detection_task` → similar
   - `from app.tasks.flows.followup_retry import FOLLOWUP_RETRY_MAX, retry_failed_followup_send` → `from app.tasks.helpers.flow_helpers import FOLLOWUP_RETRY_MAX` + `from app.tasks.flows_taskiq import retry_failed_followup_send`
   - `from app.tasks.flows.send_retry import SEND_RETRY_MAX_RETRIES, retry_failed_flow_send, ...` → from helpers + flows_taskiq
   - `from app.tasks.flows.stuck_detection import detect_stuck_flows` → `from app.tasks.flows_taskiq import detect_stuck_flows`
   - Convert `.run()` to async
   - Replace MaxRetriesExceededError with local class
   - Update all `@patch` targets

5. **`test_messaging_dlq_wiring.py`** (175 lines):
   - `from app.tasks.messaging import send_scheduled_message` → `from app.tasks.messaging_taskiq import send_scheduled_message`
   - Update `@patch` targets

6. **`test_flow_cancel.py`** (138 lines):
   - Remove `with patch("celery.result.AsyncResult", ...)` — per D013, revoke is now a logged no-op
   - The test verifies task cancellation behavior. Since Taskiq doesn't support revoke, update the test to verify the no-op/logging behavior instead, or remove the revoke-specific assertion
   - Update any import paths if needed

7. **`test_task_registry_dragonfly_fallback.py`** (67 lines):
   - `from app.api.v2.routers.tasks.utils import celery_integration` — this module was deleted by S05
   - The `test_register_task_persists_metadata_to_store` test (uses `celery_integration._register_task` and `celery_integration.store_task`) must be deleted — the function no longer exists
   - Keep the 2 `tasks_dependencies` tests (`test_find_task_in_registry_uses_stored_task_fallback`, `test_find_task_in_registry_ignores_invalid_stored_payload`) — they import from `app.api.v2.routers.tasks.dependencies` which still exists

## Must-Haves

- [ ] Zero imports from `celery.*`, `app.celery_app`, `app.tasks.flows.*` (deleted subpackage), deleted modules
- [ ] All 7 files collect without errors
- [ ] No `.run()` calls on Taskiq tasks remain

## Verification

- `cd backend-hormonia && python3 -m pytest tests/unit/tasks/test_followup_retry_task.py tests/unit/tasks/test_send_retry_task.py tests/unit/tasks/test_stuck_detection.py tests/integration/test_flow_recovery_retry_e2e.py tests/unit/tasks/test_messaging_dlq_wiring.py tests/unit/services/test_flow_cancel.py tests/unit/api/v2/test_task_registry_dragonfly_fallback.py --collect-only 2>&1 | grep ERROR` — empty

## Inputs

- T01-T03 complete
- `app/tasks/helpers/flow_helpers.py` contains: `FOLLOWUP_RETRY_MAX` (line 54), `SEND_RETRY_MAX_RETRIES` (line 42), `FOLLOWUP_RETRY_MAX_JITTER` (line 57), and helper functions from deleted send_retry/followup_retry modules
- `app/tasks/flows_taskiq.py` contains: `retry_failed_followup_send`, `retry_failed_flow_send`, `detect_stuck_flows`
- D013: Celery revoke → logged no-op (relevant for test_flow_cancel.py)
- `celery_integration` module was deleted by S05 — `_register_task` function no longer exists

## Expected Output

- 7 test files with corrected imports, zero Celery dependencies, all collecting successfully
