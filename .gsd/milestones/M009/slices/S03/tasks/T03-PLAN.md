---
estimated_steps: 4
estimated_files: 3
---

# T03: Create saga_retry_taskiq.py with 3 saga tasks

**Slice:** S03 — Flow/saga tasks migradas
**Milestone:** M009

## Description

Create `backend-hormonia/app/tasks/saga_retry_taskiq.py` with 3 saga domain tasks. Saga is a separate domain (patient onboarding orchestration) justifying its own file. The key translations: `retry_patient_onboarding_saga` replaces `self.retry(countdown=60*(2**retries))` with SmartRetryMiddleware, `scan_and_retry_failed_sagas` replaces `.apply_async(countdown=)` with `await schedule_task_at()`, and `SagaOrchestrator.resume_saga()` is called with `await` directly (no `run_async` bridge).

## Steps

1. Read `backend-hormonia/app/tasks/saga_retry.py` (567 lines) to understand all 3 Celery tasks:
   - `retry_patient_onboarding_saga` — bound task with `self.retry(countdown=60*(2**self.request.retries), max_retries=5)`, calls `SagaOrchestrator.resume_saga()` via `run_async()` bridge
   - `scan_and_retry_failed_sagas` — schedule=300s interval, queries DB for failed sagas, dispatches `retry_patient_onboarding_saga.apply_async(countdown=delay)` for each
   - `cleanup_old_completed_sagas` — schedule=86400s interval, pure DB cleanup of old completed sagas

2. Create `backend-hormonia/app/tasks/saga_retry_taskiq.py` with:
   - Module docstring listing all 3 tasks
   - Standard imports: `broker` from `app.taskiq_broker`, `DbSession`, `log_task_start/success/error`, `schedule_task_at` from `app.tasks.taskiq_base`
   - Import `SagaOrchestrator` and related domain types
   - Import pure helpers from Celery `saga_retry.py` (e.g., `_calculate_exponential_backoff` if exists)

3. Translate the 3 tasks:

   **3a. `retry_patient_onboarding_saga`** — on-demand with retry. SmartRetryMiddleware replaces `self.retry()`. Labels: `retry_on_error=True, max_retries=5, delay=60`. Call `await SagaOrchestrator(db, redis_client).resume_saga(saga_id)` directly — the orchestrator accepts `Any` session and has async methods.

   **3b. `scan_and_retry_failed_sagas`** — schedule=300s interval. Query DB for failed/stuck sagas. For each, dispatch via `await schedule_task_at(retry_patient_onboarding_saga, delivery_time, saga_id)` instead of `.apply_async(countdown=)`. Calculate `delivery_time` as `datetime.now(UTC) + timedelta(seconds=delay)`.

   **3c. `cleanup_old_completed_sagas`** — schedule=86400s interval. Simple async DB cleanup — delete sagas older than retention period. Direct SQL via DbSession.

4. Verify:
   - `python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/saga_retry_taskiq.py').read()); print('OK')"`
   - `grep -c "@broker.task" backend-hormonia/app/tasks/saga_retry_taskiq.py` = 3
   - `grep -c "schedule=" backend-hormonia/app/tasks/saga_retry_taskiq.py` = 2
   - `grep -c "run_async\|async_to_sync" backend-hormonia/app/tasks/saga_retry_taskiq.py` = 0
   - `grep -c "\.delay(\|\.apply_async(" backend-hormonia/app/tasks/saga_retry_taskiq.py` = 0

## Must-Haves

- [ ] 3 `@broker.task` decorated async tasks in saga_retry_taskiq.py
- [ ] 2 schedule labels (scan_and_retry_failed_sagas 300s, cleanup_old_completed_sagas 86400s)
- [ ] `retry_patient_onboarding_saga` uses SmartRetryMiddleware labels (not `self.retry()`)
- [ ] `scan_and_retry_failed_sagas` dispatches via `await schedule_task_at()` (not `.apply_async(countdown=)`)
- [ ] `SagaOrchestrator.resume_saga()` called with `await` directly (no `run_async` bridge)
- [ ] Zero bridge code, zero Celery dispatch
- [ ] File passes `ast.parse()`

## Verification

- `python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/saga_retry_taskiq.py').read()); print('OK')"` → OK
- `grep -c "@broker.task" backend-hormonia/app/tasks/saga_retry_taskiq.py` → 3
- `grep -c "schedule=" backend-hormonia/app/tasks/saga_retry_taskiq.py` → 2
- `grep -c "run_async\|async_to_sync" backend-hormonia/app/tasks/saga_retry_taskiq.py` → 0
- `grep -c "\.delay(\|\.apply_async(" backend-hormonia/app/tasks/saga_retry_taskiq.py` → 0

## Observability Impact

- Signals added: `log_task_start/success/error` for 3 saga tasks; `scan_and_retry_failed_sagas` logs count of sagas dispatched; `retry_patient_onboarding_saga` logs saga_id and retry count
- How a future agent inspects: `grep "task_name=scan_and_retry_failed_sagas" <logs>` for scan cycle; `grep "task_name=retry_patient_onboarding_saga" <logs>` for individual saga retries
- Failure state exposed: SmartRetryMiddleware retry count; saga status in DB after retry; cleanup task reports deleted count

## Inputs

- `backend-hormonia/app/tasks/saga_retry.py` (567 lines) — Celery saga tasks (3 tasks)
- `backend-hormonia/app/tasks/taskiq_base.py` — DbSession, log helpers, schedule_task_at
- `backend-hormonia/app/taskiq_broker.py` — broker instance

### Key patterns:
- `self.retry(countdown=60*(2**self.request.retries))` → `@broker.task(retry_on_error=True, max_retries=5, delay=60)` + just `raise` on error
- `.apply_async(countdown=N)` → `await schedule_task_at(task, datetime.now(UTC) + timedelta(seconds=N), *args)`
- `run_async(SagaOrchestrator(...).resume_saga(saga_id))` → `await SagaOrchestrator(db, redis_client).resume_saga(saga_id)`
- SagaOrchestrator accepts `Any` session — can use AsyncSession from DbSession

## Expected Output

- `backend-hormonia/app/tasks/saga_retry_taskiq.py` — NEW file with 3 `@broker.task` async tasks, 2 schedule labels, zero bridge code
