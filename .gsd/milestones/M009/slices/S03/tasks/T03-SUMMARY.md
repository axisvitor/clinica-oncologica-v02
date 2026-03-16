---
id: T03
parent: S03
milestone: M009
provides:
  - saga_retry_taskiq.py with 3 async-native Taskiq saga retry tasks
  - 2 schedule labels (scan_and_retry_failed_sagas 300s, cleanup_old_completed_sagas 86400s)
key_files:
  - backend-hormonia/app/tasks/saga_retry_taskiq.py
key_decisions:
  - retry_patient_onboarding_saga uses SmartRetryMiddleware (retry_on_error=True, max_retries=5, delay=60) and context.message.labels DLQ pattern instead of self.retry(countdown=60*(2**retries))
  - scan_and_retry_failed_sagas dispatches via await schedule_task_at() with UTC delivery_time instead of .apply_async(countdown=)
  - SagaOrchestrator instantiated with async redis (get_async_redis_client) and AsyncSession directly — no run_async bridge
  - Pure helpers (_calculate_exponential_backoff, _alert_admin_max_retries_exceeded) imported from Celery saga_retry.py without duplication
patterns_established:
  - schedule_task_at pattern for delayed dispatch replacing .apply_async(countdown=N) — compute delivery_time as datetime.now(UTC) + timedelta(seconds=delay)
  - Async Redis client (get_async_redis_client) for SagaOrchestrator in Taskiq tasks vs sync (get_sync_redis_client) in Celery
observability_surfaces:
  - log_task_start/success/error for all 3 saga tasks with structured fields (task_name, saga_id, attempt, retry_count)
  - scan_and_retry_failed_sagas logs total_found, scheduled, max_retries_exceeded counts
  - retry_patient_onboarding_saga logs DLQ routing (permanently_failed=True, dlq_routed=True) on exhausted retries
  - grep "task_name=scan_and_retry_failed_sagas" for scan cycle; grep "task_name=retry_patient_onboarding_saga" for retries
duration: fast
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T03: Created saga_retry_taskiq.py with 3 saga tasks

**Created `backend-hormonia/app/tasks/saga_retry_taskiq.py` with 3 `@broker.task` async tasks, 2 schedule labels, zero bridge code, and SmartRetryMiddleware-based retry/DLQ for saga retries.**

## What Happened

Created the saga_retry_taskiq.py file translating all 3 Celery saga retry tasks to async-native Taskiq equivalents:

1. **retry_patient_onboarding_saga** — on-demand with retry. `self.retry(countdown=60*(2**retries))` replaced by SmartRetryMiddleware labels. `run_async(orchestrator.resume_saga())` replaced by direct `await orchestrator.resume_saga()`. DLQ pattern checks `context.message.labels.get('_retries', 0)` for permanent failure routing.

2. **scan_and_retry_failed_sagas** — 300s interval. `.apply_async(countdown=N)` replaced by `await schedule_task_at(retry_patient_onboarding_saga, delivery_time, saga_id)` with UTC delivery_time computed from exponential backoff. Async DB queries replace sync ORM.

3. **cleanup_old_completed_sagas** — 86400s interval. Direct async DB cleanup via AsyncSession (TaskiqDepends), replacing sync `get_scoped_session()`.

Imported `_calculate_exponential_backoff` and `_alert_admin_max_retries_exceeded` from Celery module to avoid duplication. Used `get_async_redis_client` for SagaOrchestrator (since task body is async).

## Verification

All task-level checks passed:
- `python -c "import ast; ast.parse(...);"` → OK
- `grep -c "@broker.task" saga_retry_taskiq.py` → 3 ✓
- `grep -c "schedule=" saga_retry_taskiq.py` → 2 ✓
- AST-based zero-bridge check → 0 run_async/async_to_sync calls ✓
- AST-based zero-Celery-dispatch check → 0 .delay()/.apply_async() calls ✓

Slice-level checks (all passing as of T03, the final task):
- flows_taskiq.py AST parse → OK ✓
- saga_retry_taskiq.py AST parse → OK ✓
- `grep -c "@broker.task" flows_taskiq.py` → 14 ✓
- `grep -c "@broker.task" saga_retry_taskiq.py` → 3 ✓
- Total schedule labels: 10 + 2 = 12 ✓
- Zero bridge code (AST-verified across both files) ✓
- Zero Celery dispatch (AST-verified across both files) ✓
- Celery originals intact: saga_retry.py still has 3 @celery_app.task ✓

## Diagnostics

- Task inventory: `grep "@broker.task" backend-hormonia/app/tasks/saga_retry_taskiq.py`
- Schedule entries: `grep "schedule=" backend-hormonia/app/tasks/saga_retry_taskiq.py`
- Zero-bridge AST check: `python3 -c "import ast; [walk tree for run_async/async_to_sync calls]"`
- Scan cycle: `grep "task_name=scan_and_retry_failed_sagas" <worker-logs>` — returns total_found/scheduled/max_retries_exceeded
- Saga retries: `grep "task_name=retry_patient_onboarding_saga" <worker-logs>` — shows saga_id, attempt, dlq_routed
- Cleanup: `grep "task_name=cleanup_old_completed_sagas" <worker-logs>` — returns deleted_count

## Deviations

None — implementation followed plan exactly.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/tasks/saga_retry_taskiq.py` — NEW: 3 `@broker.task` async saga tasks (retry, scan, cleanup) with 2 schedule labels
