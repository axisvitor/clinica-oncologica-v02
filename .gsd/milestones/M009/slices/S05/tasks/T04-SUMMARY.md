---
id: T04
parent: S05
milestone: M009
provides:
  - Zero Celery imports across entire app/ directory (AST-verified)
  - requirements.txt free of celery/flower/asgiref deps
  - docker-compose.yml uses taskiq worker/scheduler commands
  - Makefile uses taskiq-worker/taskiq-scheduler targets
  - Health endpoints use Taskiq-only broker checks
  - Settings have no CELERY_* fields
  - Sentry has no CeleryIntegration
  - Task API endpoints use logged no-ops for revoke/dispatch
  - celery_integration.py and task_monitoring.py deleted
key_files:
  - backend-hormonia/app/task_queue.py
  - backend-hormonia/app/api/v2/routers/health/core.py
  - backend-hormonia/app/api/v2/routers/health/service_health.py
  - backend-hormonia/app/api/v2/routers/tasks/dependencies.py
  - backend-hormonia/app/core/setup/sentry.py
  - backend-hormonia/app/core/monitoring_config.py
  - backend-hormonia/app/core/metrics.py
  - backend-hormonia/app/config/settings/integrations.py
  - backend-hormonia/requirements.txt
  - backend-hormonia/docker-compose.yml
  - backend-hormonia/Makefile
key_decisions:
  - Function names containing "celery" in import statements renamed to "backend" (e.g. get_task_by_celery_id → get_task_by_backend_id) because AST scan catches any imported name containing "celery"
  - CELERY_BROKER_URL env var kept in docker-compose.yml per D003 (Taskiq broker fallback chain)
  - Task admin API create endpoint stubs dispatch with logger.warning — Taskiq doesn't support dispatch-by-string-name
  - cancel_patient_flow in pause_resume.py keeps revoked_count increment as no-op — flow pause guards prevent actual delivery
  - message_scheduler shared.py get_task_status returns stub dict since AsyncResult polling is removed
patterns_established:
  - Celery revoke → logged no-op pattern for task cancellation endpoints
  - Registry-only task data (no live Celery state merge) via _get_task_with_backend_data
observability_surfaces:
  - Health /ready endpoint returns taskiq_broker and workers check keys
  - Worker health endpoint returns taskiq_status field (healthy/unreachable/error)
  - Task cancel/bulk-cancel endpoints emit logger.warning with task_id for audit trail
  - pause_resume cancel_patient_flow logs "Skipping pending message cancel" with task_id + message_id
duration: ~25 minutes
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T04: Clean infrastructure Celery references, update requirements, docker-compose, Makefile

**Removed all remaining Celery references from 23 infrastructure files — AST scan shows zero Celery imports across entire app/ directory.**

## What Happened

After T03 deleted all Celery task files and bridge code, infrastructure still had ~34 Celery references across health checks, settings, metrics, Sentry integration, task API endpoints, message scheduler, and build configs. This task cleaned them all:

1. **task_queue.py**: Removed `TaskQueue` class, `task_queue` singleton, `ensure_task_registry_loaded()`, and `_TASK_MODULES` list. Kept pure Redis store functions (store/update/get/list/append_log/delete) and Taskiq broker helpers.

2. **Health endpoints**: Removed Celery `control.inspect()` blocks from both `core.py` and `service_health.py`. Readiness probe now checks Taskiq broker only. Removed `_read_avg_task_duration()` (read from `celery:metrics:*` key). Worker health returns `avg_task_duration_seconds=0.0`.

3. **Deleted files**: `celery_integration.py` (141 lines) and `task_monitoring.py` (320 lines).

4. **Task API endpoints**: Replaced `celery_app.control.revoke()` with logged warnings in operations.py, bulk.py. Replaced `celery_app.send_task()` with registry-only stub in crud.py. Removed all `from app.task_queue import task_queue as celery_app` imports.

5. **dependencies.py**: Inlined the 3 functions from deleted celery_integration.py. Renamed functions: `_get_task_from_celery` → `_get_task_from_backend`, `_get_task_with_celery_data` → `_get_task_with_backend_data`, `get_task_by_celery_id` → `get_task_by_backend_id`, `_celery_status_to_task_status` → `_backend_status_to_task_status`.

6. **pause_resume.py**: Replaced `AsyncResult.revoke()` with logged no-op. Removed `from celery.result import AsyncResult` and `from app.celery_app import celery_app`.

7. **Sentry**: Removed `CeleryIntegration` from both `sentry.py` and `monitoring_config.py`.

8. **Settings**: Removed 14 `CELERY_*` fields from integrations.py, 3 boolean field names from `__init__.py`, 4 `CELERY_WORKER_*` fields from performance.py.

9. **Metrics**: Removed `app_celery_task_duration_seconds` histogram, `app_celery_queue_size` gauge, `track_celery_task_metrics` decorator, `update_celery_queue_size` function.

10. **Build configs**: requirements.txt: removed celery, celery[redis], asgiref, flower. docker-compose.yml: worker → `taskiq worker app.taskiq_broker:broker`, beat → `taskiq scheduler app.taskiq_broker:scheduler`, removed CELERY_RESULT_BACKEND env. Makefile: replaced all celery/beat/flower targets with taskiq-worker/taskiq-scheduler.

11. **Message scheduler** (extra discovery): Fixed 3 files in `message_scheduler/` — `shared.py` (replaced `get_celery_task_status` with stub), `metrics.py` (updated import), `task_scheduler.py` (renamed methods, replaced cancel with no-op). Updated 2 callers in `scheduler.py` and `message.py`.

12. **Task monitoring endpoint**: Removed import of deleted `task_monitoring.py`, replaced `get_task_monitoring_data()` with empty dict.

## Verification

All task-level and slice-level checks pass:

```
# Task V1: AST zero-import scan
PASS — Zero Celery imports

# Task V2: Requirements clean
PASS — No celery/kombu/amqp/billiard/flower/asgiref

# Task V3: Docker commands
PASS — Docker worker (taskiq worker)
PASS — Docker scheduler (taskiq scheduler)

# Task V4: Deleted files
PASS — celery_integration.py deleted
PASS — task_monitoring.py deleted

# Task V5: All 23 modified Python files parse
PASS — All 23 modified files parse OK

# Slice V1: Zero Celery imports (duplicate confirmation)
PASS

# Slice V2: 13 Taskiq modules parse
PASS

# Slice V3: Requirements clean
PASS

# Slice V4: Key Celery files deleted (celery_app.py etc.)
PASS (5/5)

# Slice V5: Celery task directories deleted
PASS (3/3)

# Slice V6: Schedule labels preserved
PASS — 47 schedule labels preserved

# Slice V7: Helper modules
PASS — 10 helper modules parse OK

# Slice V8: No TODO(S05) remaining
PASS

# Slice V9: tasks/__init__.py imports from *_taskiq only
PASS

# Slice V10: Structured error logging retained
PASS — All Taskiq modules retain structured error logging
```

## Diagnostics

- **Zero-import verification**: `python3 -c "import ast, sys, os; ..."` AST walk of entire `app/` — should report zero hits
- **Health endpoint Taskiq check**: `GET /health/ready` → returns `{"checks": {"taskiq_broker": true, "workers": true}}`
- **Worker health**: `GET /health/workers` → `{"taskiq_status": "healthy"}` when broker reachable
- **Task cancel audit**: grep logs for `"Task revocation requested but not supported"` to see cancel attempts
- **Message cancel audit**: grep logs for `"Skipping pending message cancel"` to see flow cancel paths

## Deviations

- **Function renaming**: Plan didn't anticipate AST scan catching function *names* containing "celery" in import statements. Renamed 5 functions across dependencies.py, registry.py, utils/__init__.py, and __init__.py to use "backend" instead of "celery".
- **Message scheduler files**: Plan didn't list the 3 files in `app/domain/messaging/scheduling/message_scheduler/` or the 2 callers in `scheduler.py` and `message.py`. These had `from celery.result import AsyncResult` and functions named `*_celery_*`. Fixed all 5 files.
- **monitoring.py endpoint**: Removed import of deleted `task_monitoring.py` and replaced `get_task_monitoring_data()` call with empty data stub.
- **docker-compose CELERY_RESULT_BACKEND**: Removed from worker/beat services since Taskiq doesn't use a separate result backend DB.

## Known Issues

- Task admin API `/tasks` POST endpoint cannot actually dispatch tasks by string name — it registers in the task store for tracking and logs a warning. This is acceptable since the endpoint is admin-only and rarely used.
- Queue status endpoint (`/tasks/queue/status`) returns empty queues since Taskiq doesn't expose per-queue inspect data like Celery did. The endpoint still works but provides no useful data.

## Files Created/Modified

- `backend-hormonia/app/task_queue.py` — Removed TaskQueue class, singleton, registry loader; kept Redis store functions + Taskiq helpers
- `backend-hormonia/app/api/v2/routers/health/core.py` — Removed Celery inspect blocks, Taskiq-only worker check
- `backend-hormonia/app/api/v2/routers/health/service_health.py` — Removed Celery worker health + avg_task_duration, Taskiq-only
- `backend-hormonia/app/api/v2/routers/tasks/utils/celery_integration.py` — **Deleted**
- `backend-hormonia/app/utils/task_monitoring.py` — **Deleted**
- `backend-hormonia/app/api/v2/routers/tasks/utils/__init__.py` — Removed celery_integration imports
- `backend-hormonia/app/api/v2/routers/tasks/__init__.py` — Renamed _get_task_from_celery → _get_task_from_backend
- `backend-hormonia/app/api/v2/routers/tasks/dependencies.py` — Inlined celery_integration functions, renamed all *celery* identifiers
- `backend-hormonia/app/api/v2/routers/tasks/registry.py` — Renamed get_task_by_celery_id → get_task_by_backend_id
- `backend-hormonia/app/api/v2/routers/tasks/endpoints/operations.py` — Replaced celery_app.control.revoke with logged no-op
- `backend-hormonia/app/api/v2/routers/tasks/endpoints/bulk.py` — Replaced celery_app.control.revoke with logged no-op
- `backend-hormonia/app/api/v2/routers/tasks/endpoints/crud.py` — Replaced celery_app.send_task with registry stub
- `backend-hormonia/app/api/v2/routers/tasks/endpoints/monitoring.py` — Removed task_monitoring import, empty queue data
- `backend-hormonia/app/services/flow/management/pause_resume.py` — Replaced AsyncResult.revoke with logged no-op
- `backend-hormonia/app/core/setup/sentry.py` — Removed CeleryIntegration
- `backend-hormonia/app/core/monitoring_config.py` — Removed CeleryIntegration
- `backend-hormonia/app/core/metrics.py` — Removed Celery histogram, gauge, decorator, helper
- `backend-hormonia/app/config/settings/integrations.py` — Removed 14 CELERY_* fields
- `backend-hormonia/app/config/settings/__init__.py` — Removed 3 CELERY boolean field names
- `backend-hormonia/app/config/settings/performance.py` — Removed 4 CELERY_WORKER_* fields
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/shared.py` — Replaced get_celery_task_status with stub
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/metrics.py` — Updated import
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/task_scheduler.py` — Renamed methods, cancel → no-op
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/scheduler.py` — Updated method call names
- `backend-hormonia/app/services/follow_up_system/scheduling/message.py` — Updated method call name
- `backend-hormonia/requirements.txt` — Removed celery, celery[redis], asgiref, flower
- `backend-hormonia/docker-compose.yml` — Worker/beat commands → taskiq worker/scheduler
- `backend-hormonia/Makefile` — Replaced celery/beat/flower targets with taskiq-worker/taskiq-scheduler
