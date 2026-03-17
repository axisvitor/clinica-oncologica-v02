---
estimated_steps: 3
estimated_files: 7
---

# T01: Delete dead Celery test files

**Slice:** S06 — Verificação integrada ponta-a-ponta
**Milestone:** M009

## Description

Delete 7 test files that test Celery infrastructure deleted in S05. These files test `celery_app.py`, `celery_metrics`, `queue_monitor`, `monitoring.py` task registration, Celery beat schedule alignment, Celery `run_async_in_celery` bridge, and Celery async DB isolation. All tested modules are gone — there is no Taskiq equivalent because the infrastructure was replaced, not translated 1:1.

## Steps

1. Delete the 7 dead test files:
   - `backend-hormonia/tests/tasks/test_celery_app_async_helper.py` (34 lines — tests deleted `run_async_in_celery`)
   - `backend-hormonia/tests/tasks/test_celery_metrics_lifecycle.py` (111 lines — tests deleted `celery_metrics` module)
   - `backend-hormonia/tests/tasks/test_celery_schedule_alignment.py` (114 lines — tests deleted `celery_app.py` beat_schedule)
   - `backend-hormonia/tests/tasks/test_queue_monitor.py` (56 lines — tests deleted `QueueMonitor`)
   - `backend-hormonia/tests/tasks/test_monitoring_task_registration.py` (112 lines — tests deleted `monitoring.py` @task decorators)
   - `backend-hormonia/tests/validation/test_celery_ai_run_sync_path.py` (113 lines — tests deleted `batch_tasks.py`, `flow_automation.py`)
   - `backend-hormonia/tests/integration/test_celery_async_isolation.py` (108 lines — tests Celery async DB isolation)

2. Verify no other test file imports from these dead files:
   ```bash
   grep -r "test_celery_app_async_helper\|test_celery_metrics_lifecycle\|test_celery_schedule_alignment\|test_queue_monitor\|test_monitoring_task_registration\|test_celery_ai_run_sync_path\|test_celery_async_isolation" backend-hormonia/tests/ --include="*.py"
   ```
   Should return nothing.

3. Verify no test files with "celery" in the name remain:
   ```bash
   find backend-hormonia/tests -name "*celery*" -type f
   ```
   Should return nothing.

## Must-Haves

- [ ] All 7 files deleted
- [ ] No remaining test files with "celery" in the filename
- [ ] No dangling imports from other test files to deleted files

## Verification

- `ls backend-hormonia/tests/tasks/test_celery_app_async_helper.py 2>&1` → "No such file or directory" (repeat for all 7)
- `find backend-hormonia/tests -name "*celery*" -type f | wc -l` → 0

## Inputs

- S05 deleted all Celery infrastructure: `celery_app.py`, `async_context_manager.py`, `celery_metrics.py`, `queue_monitor.py`, `monitoring.py` (task file), `base.py`, `config.py`, etc.
- These 7 test files all import from modules that no longer exist

## Expected Output

- 7 files removed (~648 lines of dead test code)
- Clean filesystem: no test files referencing "celery" in filename
