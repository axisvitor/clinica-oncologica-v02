---
id: T02
parent: S03
milestone: M009
provides:
  - 6 additional async-native Taskiq flow tasks (detect_stuck_flows, monitor_flow_task_health, evaluate_flow_alerts, cleanup_old_flow_data, retry_failed_flow_send, retry_failed_followup_send)
  - 4 new schedule labels (10 total in flows_taskiq.py)
  - SmartRetryMiddleware-based retry for flow/followup send tasks with DLQ routing
key_files:
  - backend-hormonia/app/tasks/flows_taskiq.py
key_decisions:
  - detect_stuck_flows uses get_scoped_session() (sync) because find_stuck_flows and attempt_recovery are sync-only services; attempt_recovery internally calls Celery .delay() — intentionally left for coexistence (S05 cleans up)
  - retry_failed_flow_send/retry_failed_followup_send use context.message.labels.get('_retries', 0) to read retry count and raise on ExternalServiceError to let SmartRetryMiddleware schedule retries; permanent failure check done in task body before raise
  - monitor_flow_task_health converts sync db.query() to async select() and replaces run_async_in_sync/run_async_in_thread with direct await for Gemini health check
  - evaluate_flow_alerts uses DbSession (AsyncSession) since FlowAlertsService accepts Any session type
patterns_established:
  - SmartRetryMiddleware DLQ pattern: check retries >= max_retries in task body, finalize permanent failure state, log with dlq_routed=True, then return dict with permanently_failed=True
  - Context-based retry count: `context.message.labels.get('_retries', 0)` replaces Celery `self.request.retries`
  - Sync-only services in async tasks: get_scoped_session() context manager for sync ORM, no DbSession (AsyncSession)
observability_surfaces:
  - log_task_start/success/error for all 6 new tasks with structured fields (task_name, event, duration_ms)
  - retry_failed_flow_send/retry_failed_followup_send log retry attempts with attempt count and dlq_routed=True on permanent failure
  - detect_stuck_flows returns summary dict with detected/recovered/skipped/failed counts
  - monitor_flow_task_health returns overall_healthy boolean + component health status
duration: 8 minutes
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T02: Added stuck_detection, monitoring, cleanup, and retry tasks to flows_taskiq.py (6 tasks)

**Appended 6 async-native Taskiq tasks (detect_stuck_flows, monitor_flow_task_health, evaluate_flow_alerts, cleanup_old_flow_data, retry_failed_flow_send, retry_failed_followup_send) bringing flows_taskiq.py to 14 total @broker.task with 10 schedule labels, zero bridge code, and SmartRetryMiddleware-based DLQ routing on retry tasks.**

## What Happened

Read all 5 Celery source files (stuck_detection, monitoring, cleanup_tasks, send_retry, followup_retry) and confirmed recovery.py's `attempt_recovery()` is sync and calls `retry_failed_flow_send.delay()` at line 211 (stays as-is for coexistence).

Appended 6 tasks to flows_taskiq.py:

1. **detect_stuck_flows** (900s interval) — Uses `get_scoped_session()` for sync `find_stuck_flows()` + `attempt_recovery()`. Does NOT modify `attempt_recovery()` — its internal Celery `.delay()` remains for coexistence.

2. **monitor_flow_task_health** (300s interval) — Converted sync `db.query()` to async `select()`. Replaced `run_async_in_sync()`/`run_async_in_thread()` Gemini health check with `await asyncio.wait_for(gemini_client.health_check(), timeout=...)`.

3. **evaluate_flow_alerts** (900s interval) — Replaced `run_async_in_sync(service.evaluate_alerts())` with `await service.evaluate_alerts()`. FlowAlertsService accepts Any session.

4. **cleanup_old_flow_data** (86400s interval) — Translated sync ORM `db.query()` to async `select()` with DbSession. Archives to Redis before deletion.

5. **retry_failed_flow_send** (on-demand, max_retries=5, delay=60) — SmartRetryMiddleware replaces `self.retry(countdown=)`. Uses `context.message.labels.get('_retries', 0)` for retry count. Direct `await whatsapp_service.send_message()` instead of `async_to_sync()`. DLQ routing on permanent failure.

6. **retry_failed_followup_send** (on-demand, max_retries=3, delay=30) — Same SmartRetryMiddleware pattern. Direct await for service methods. DLQ routing on permanent failure.

Updated module docstring to reflect 14 tasks and 10 schedule labels.

## Verification

All 5 plan-specified checks pass:

| Check | Expected | Actual |
|-------|----------|--------|
| `ast.parse()` | OK | ✅ OK |
| `grep -c "@broker.task"` | 14 | ✅ 14 |
| `grep -c "schedule="` | 10 | ✅ 10 |
| AST bridge check (async_to_sync/run_async_in_sync/run_async_in_thread) | 0 | ✅ 0 |
| AST dispatch check (.delay()/.apply_async()) | 0 | ✅ 0 |

Note: `grep -c` returns higher counts because docstrings mention bridge names in "replaced X with Y" context. AST analysis confirms zero actual bridge/dispatch calls in code.

Celery originals verified intact — all 9 source files have unchanged `@celery_app.task` counts.

### Slice-level verification (partial — T02 is intermediate):
- ✅ `flows_taskiq.py` passes `ast.parse()` → 14 @broker.task, 10 schedule entries
- ❌ `saga_retry_taskiq.py` — not created yet (T03)
- ✅ Zero bridge code in `flows_taskiq.py`
- ✅ Zero Celery dispatch in `flows_taskiq.py`
- ✅ Celery originals intact

## Diagnostics

- Task inventory: `grep "@broker.task" backend-hormonia/app/tasks/flows_taskiq.py`
- Schedule entries: `grep "schedule=" backend-hormonia/app/tasks/flows_taskiq.py`
- Zero-bridge AST check: `python3 -c "import ast; [walk tree for async_to_sync/run_async/delay calls]"`
- Stuck flow detection: `grep "task_name=detect_stuck_flows" <worker-logs>` — returns detected/recovered/skipped/failed counts
- Retry tracing: `grep "task_name=retry_failed_flow_send" <worker-logs>` — shows attempt count, dlq_routed flag
- Health monitoring: `grep "task_name=monitor_flow_task_health" <worker-logs>` — returns overall_healthy boolean

## Deviations

None. All 6 tasks implemented per plan.

## Known Issues

- `grep -c "async_to_sync|run_async_in_sync|run_async_in_thread"` returns 10 (docstring mentions) — AST analysis returns 0 (correct). Verification scripts should use AST analysis for definitive results.
- `attempt_recovery()` in recovery.py still calls `retry_failed_flow_send.delay()` (Celery) — expected coexistence behavior, tracked for S05 cleanup.

## Files Created/Modified

- `backend-hormonia/app/tasks/flows_taskiq.py` — Appended 6 new @broker.task async tasks (detect_stuck_flows, monitor_flow_task_health, evaluate_flow_alerts, cleanup_old_flow_data, retry_failed_flow_send, retry_failed_followup_send), updated module docstring to reflect 14 tasks / 10 schedules
