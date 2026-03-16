---
estimated_steps: 5
estimated_files: 7
---

# T02: Add stuck_detection, monitoring, cleanup, and retry tasks to flows_taskiq.py (6 tasks)

**Slice:** S03 — Flow/saga tasks migradas
**Milestone:** M009

## Description

Append the remaining 6 flow-domain Taskiq tasks to `flows_taskiq.py`, bringing the total to 14. These tasks have specific constraints: `detect_stuck_flows` uses sync-only services (`find_stuck_flows`, `attempt_recovery`) requiring `get_scoped_session()`, retry tasks translate `self.retry(countdown=)` to SmartRetryMiddleware, and monitoring tasks eliminate `run_async_in_sync/thread` bridges.

Critical constraint: `attempt_recovery()` internally calls `retry_failed_flow_send.delay()` at line 211 of `recovery.py`. This is a sync function — it STAYS on Celery `.delay()` during coexistence. The Taskiq `detect_stuck_flows` task calls `attempt_recovery` but does not modify it. S05 handles this cleanup.

## Steps

1. Read source Celery tasks:
   - `backend-hormonia/app/tasks/flows/stuck_detection.py` (86 lines) — `detect_stuck_flows`, uses sync `find_stuck_flows(db)` + `attempt_recovery(db)`
   - `backend-hormonia/app/tasks/flows/monitoring.py` (189 lines) — `monitor_flow_task_health`, `evaluate_flow_alerts`, uses `run_async_in_sync()`/`run_async_in_thread()` bridges
   - `backend-hormonia/app/tasks/flows/cleanup_tasks.py` (131 lines) — `cleanup_old_flow_data`, pure sync DB
   - `backend-hormonia/app/tasks/flows/send_retry.py` (210 lines) — `retry_failed_flow_send` with `self.retry(countdown=)` + `MaxRetriesExceededError`
   - `backend-hormonia/app/tasks/flows/followup_retry.py` (151 lines) — `retry_failed_followup_send` with `self.retry(countdown=)` + `MaxRetriesExceededError`

2. Read `backend-hormonia/app/services/flow/recovery.py` lines 128-230 to understand `attempt_recovery()` — confirm it's sync and calls `retry_failed_flow_send.delay()`.

3. Append 6 tasks to `backend-hormonia/app/tasks/flows_taskiq.py`:

   **3a. `detect_stuck_flows`** — schedule=900s interval. Uses `get_scoped_session()` to get sync Session for `find_stuck_flows(db)` and `attempt_recovery(db, flow_state, redis_client)`. Do NOT use DbSession (AsyncSession) here. `attempt_recovery()` still calls Celery `.delay()` internally — accept this for coexistence.

   **3b. `monitor_flow_task_health`** — schedule=300s interval. Remove `run_async_in_sync()`/`run_async_in_thread()` bridge. Make async, call health check services directly with `await`.

   **3c. `evaluate_flow_alerts`** — schedule=900s interval. Remove `run_async_in_sync()` bridge. FlowAlertsService accepts `Any` session — use DbSession (AsyncSession).

   **3d. `cleanup_old_flow_data`** — schedule=86400s interval. Pure DB cleanup. Translate sync queries to async using DbSession.

   **3e. `retry_failed_flow_send`** — on-demand with retry. Replace `self.retry(countdown=base*(backoff**retries)+jitter)` with SmartRetryMiddleware labels: `retry_on_error=True, max_retries=5, delay=60`. Replace `MaxRetriesExceededError` handling with check `context.message.labels.get('_retries', 0) >= max_retries`. Include DLQ routing on final failure.

   **3f. `retry_failed_followup_send`** — on-demand with retry. Same pattern as retry_failed_flow_send.

4. Add necessary imports at top of file (append to existing import block):
   - `from app.database import get_scoped_session` for stuck_detection
   - `from app.services.flow.recovery import find_stuck_flows, attempt_recovery` for stuck_detection
   - Any additional service imports needed for monitoring tasks

5. Verify:
   - `python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/flows_taskiq.py').read()); print('OK')"`
   - `grep -c "@broker.task" backend-hormonia/app/tasks/flows_taskiq.py` = 14
   - `grep -c "schedule=" backend-hormonia/app/tasks/flows_taskiq.py` = 10
   - `grep -c "async_to_sync\|run_async_in_sync\|run_async_in_thread\|run_async_in_thread" backend-hormonia/app/tasks/flows_taskiq.py` = 0
   - `grep -c "\.delay(\|\.apply_async(" backend-hormonia/app/tasks/flows_taskiq.py` = 0

## Must-Haves

- [ ] 6 new `@broker.task` tasks appended (14 total in file)
- [ ] 4 new schedule labels (10 total in file): detect_stuck_flows 900s, monitor_flow_task_health 300s, evaluate_flow_alerts 900s, cleanup_old_flow_data 86400s
- [ ] `detect_stuck_flows` uses `get_scoped_session()` for sync services — NOT DbSession
- [ ] `attempt_recovery()` NOT modified — stays with Celery `.delay()` internally (coexistence)
- [ ] `retry_failed_flow_send` and `retry_failed_followup_send` use SmartRetryMiddleware labels instead of `self.retry()`
- [ ] Zero bridge code (`async_to_sync`, `run_async_in_sync`, `run_async_in_thread`) in the file
- [ ] Zero Celery dispatch (`.delay()`, `.apply_async()`) in the file
- [ ] File passes `ast.parse()`

## Verification

- `python -c "import ast; ast.parse(open('backend-hormonia/app/tasks/flows_taskiq.py').read()); print('OK')"` → OK
- `grep -c "@broker.task" backend-hormonia/app/tasks/flows_taskiq.py` → 14
- `grep -c "schedule=" backend-hormonia/app/tasks/flows_taskiq.py` → 10
- `grep -c "async_to_sync\|run_async_in_sync\|run_async_in_thread" backend-hormonia/app/tasks/flows_taskiq.py` → 0
- `grep -c "\.delay(\|\.apply_async(" backend-hormonia/app/tasks/flows_taskiq.py` → 0

## Observability Impact

- Signals added: `log_task_start/success/error` for 6 more tasks; retry tasks log retry count and DLQ routing
- How a future agent inspects: `grep "task_name=detect_stuck_flows" <logs>` for stuck flow detection; `grep "task_name=retry_failed_flow_send" <logs>` for retry tracing
- Failure state exposed: SmartRetryMiddleware retry logging; DLQ entries on max retries exceeded; stuck flow recovery status in task return value

## Inputs

- `backend-hormonia/app/tasks/flows_taskiq.py` — T01 output (8 tasks already in file)
- `backend-hormonia/app/tasks/flows/stuck_detection.py` (86 lines) — Celery detect_stuck_flows
- `backend-hormonia/app/tasks/flows/monitoring.py` (189 lines) — 2 Celery monitoring tasks
- `backend-hormonia/app/tasks/flows/cleanup_tasks.py` (131 lines) — Celery cleanup task
- `backend-hormonia/app/tasks/flows/send_retry.py` (210 lines) — Celery retry_failed_flow_send with self.retry
- `backend-hormonia/app/tasks/flows/followup_retry.py` (151 lines) — Celery retry_failed_followup_send with self.retry
- `backend-hormonia/app/services/flow/recovery.py` — sync `attempt_recovery()` that calls `.delay()` internally

### Key constraints:
- `find_stuck_flows(db: Session)` and `attempt_recovery(db: Session, ...)` are sync-only — MUST use `get_scoped_session()`, NOT DbSession
- `attempt_recovery()` calls `retry_failed_flow_send.delay()` at line 211 — this is sync code, keep Celery during coexistence
- `self.retry(countdown=base*(backoff**retries)+jitter)` → SmartRetryMiddleware labels: `retry_on_error=True, max_retries=N, delay=N` (middleware applies its own backoff + jitter)
- `context.message.labels.get('_retries', 0)` replaces `self.request.retries` for retry count
- `MaxRetriesExceededError` replaced by checking retry count against max in task body

## Expected Output

- `backend-hormonia/app/tasks/flows_taskiq.py` — Updated with 14 total @broker.task, 10 schedule labels, zero bridge code
