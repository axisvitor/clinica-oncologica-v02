---
estimated_steps: 10
estimated_files: 19
---

# T04: Clean infrastructure Celery references, update requirements, docker-compose, Makefile

**Slice:** S05 — Celery removal + bridge cleanup
**Milestone:** M009

## Description

After T03 deleted all Celery task files, infrastructure code still references Celery in health checks, settings, metrics, Sentry, task API, and build configs. This task cleans all remaining references so the AST zero-import scan passes. This fulfills R085 (Celery deps removed from requirements.txt).

## Steps

1. **Clean `app/task_queue.py`** (238 lines):
   - Remove the `TaskQueue` class (wraps `celery_app`)
   - Remove `task_queue` singleton instance
   - Remove `ensure_task_registry_loaded()` function (loads Celery modules)
   - Remove all Celery imports (`from app.celery_app import ...`, `from celery import ...`)
   - **Keep**: `store_task()`, `update_task()`, `get_task()`, `list_tasks()`, `append_task_log()`, `delete_task()` — these are pure Redis functions, Celery-independent
   - **Keep**: `get_taskiq_broker()` and `get_taskiq_broker_health()` if present
   - Update any code that references the deleted `task_queue` singleton — in the files below, look for `from app.task_queue import task_queue` and replace with appropriate alternatives

2. **Clean health endpoints**:
   - `app/api/v2/routers/health/core.py`: Remove the Celery inspect block (lines ~126-139 and ~145-146 that import `task_queue as celery_app` and call `celery_app.control.inspect()`). Keep the Taskiq health check. The `checks["workers"]` line should use only `taskiq_ok`, not `taskiq_ok or checks.get("celery_workers", False)`.
   - `app/api/v2/routers/health/service_health.py`: Remove `_read_avg_task_duration()` Redis read of `celery:metrics:avg_task_duration` (line 86) — either remove the function or make it return 0.0. Remove the Celery inspect block (lines 116-130) that imports `task_queue` and calls `celery_app.control.inspect()`. Keep any Taskiq-based worker health checks.

3. **Delete `app/api/v2/routers/tasks/utils/celery_integration.py`** (141 lines) — entire file is Celery-specific (`AsyncResult`, `celery.states`).

4. **Delete `app/utils/task_monitoring.py`** (320 lines) — `TaskMonitor` class wrapping Celery `State()` and `control.inspect()`.

5. **Clean task API endpoints**:
   - `app/api/v2/routers/tasks/dependencies.py`: Remove imports from `celery_integration.py`. If functions from celery_integration are used in dependencies, either stub them (return empty dict/None) or remove the dependency entirely.
   - `app/api/v2/routers/tasks/endpoints/operations.py`: Remove `from app.task_queue import task_queue as celery_app`. Replace `celery_app.control.revoke(celery_task_id, terminate=True)` (line 78) with a logged no-op:
     ```python
     # Task revocation not supported in Taskiq — log and continue
     logger.warning("Task revocation requested but not supported", extra={"task_id": celery_task_id})
     ```
     Remove import of `_get_task_with_celery_data` if it comes from celery_integration.py.
   - `app/api/v2/routers/tasks/endpoints/bulk.py`: Same treatment — replace `celery_app.control.revoke()` (line 101) with logged no-op. Remove celery_app import.
   - `app/api/v2/routers/tasks/endpoints/crud.py`: Replace `celery_app.send_task(task_name, ...)` (line 332) with a logged no-op or stub. Remove `from app.task_queue import task_queue as celery_app`. Note: this endpoint dispatches tasks by string name — Taskiq doesn't support this natively. Stub it with a logger warning for now. The task API is admin-only and rarely used.

6. **Clean `app/services/flow/management/pause_resume.py`** (lines 227-240):
   - Remove `from celery.result import AsyncResult` and `from app.celery_app import celery_app as celery_instance`
   - Replace the `AsyncResult(task_id, app=celery_instance).revoke(terminate=False)` block with a logged no-op:
     ```python
     # Pending message cancellation — Taskiq doesn't support task revocation
     # The message will be sent but the flow is paused, so it will be ignored
     logger.info("Skipping pending message cancel (no revocation in Taskiq)", extra={"task_id": task_id})
     ```

7. **Clean Sentry integration**:
   - `app/core/setup/sentry.py` line 38,63: Remove `from sentry_sdk.integrations.celery import CeleryIntegration` and remove `CeleryIntegration(...)` from the integrations list
   - `app/core/monitoring_config.py` line 94: Same treatment — remove `CeleryIntegration` import and usage

8. **Clean settings**:
   - `app/config/settings/integrations.py` lines 283-322: Remove all `CELERY_*` field definitions. **Keep** the class otherwise intact.
   - `app/config/settings/__init__.py` lines 148-151: Remove the `CELERY_*` boolean field names from the boolean handling list.
   - `app/config/settings/performance.py`: Remove `CELERY_WORKER_*` fields (lines 232-244).

9. **Clean metrics**:
   - `app/core/metrics.py`: Remove `app_celery_task_duration_seconds` histogram (lines 70-78), `app_celery_queue_size` gauge (lines 77-78), `track_celery_task_metrics` function (lines 217-229), `update_celery_queue_size` function (lines 319-321). Verify no other code imports these (research confirmed: zero external importers).

10. **Update build/deploy configs**:
    - `requirements.txt`: Remove these 4 lines:
      - `celery>=5.6.2,<6.0.0`
      - `celery[redis]>=5.6.2,<6.0.0  # Celery with Redis broker support`
      - `asgiref>=3.11.0,<4.0.0  # Async utilities for Celery tasks (async_to_sync)`
      - `flower==2.0.1  # Web-based Celery monitoring UI`
    - `docker-compose.yml`: 
      - Worker service (line 42): Change `command: celery -A app.celery_app worker --loglevel=info --concurrency=4` to `command: taskiq worker app.taskiq_broker:broker`
      - Beat service (line 59): Change `command: celery -A app.celery_app beat --loglevel=info` to `command: taskiq scheduler app.taskiq_broker:scheduler`
      - **Keep** `CELERY_BROKER_URL` env var — Taskiq broker reads it as fallback (per D003: broker reads `TASKIQ_BROKER_URL → CELERY_BROKER_URL → REDIS_URL → default`)
      - Rename the services from `worker`/`beat` to `taskiq-worker`/`taskiq-scheduler` (or keep as `worker`/`beat` — preference for keeping existing names to not break any external references)
    - `Makefile`: Replace all celery targets:
      - Line 22: `celery` help → `worker` or `taskiq-worker`
      - Lines 38,41: Worker/beat commands → `taskiq worker app.taskiq_broker:broker` / `taskiq scheduler app.taskiq_broker:scheduler`
      - Lines 92-101: `celery:`, `beat:`, `flower:` targets → `taskiq-worker:`, `taskiq-scheduler:` (remove flower target entirely)
      - Lines 183-185: Background worker/beat → `taskiq` commands

## Must-Haves

- [ ] Zero Celery imports in AST scan of entire `app/` directory
- [ ] `celery_integration.py` deleted
- [ ] `task_monitoring.py` deleted
- [ ] `requirements.txt` has no celery, celery[redis], asgiref, flower
- [ ] `docker-compose.yml` uses `taskiq` commands for worker and scheduler
- [ ] `Makefile` uses `taskiq` commands (no `celery` targets)
- [ ] Health endpoints have no Celery inspect blocks
- [ ] Settings have no `CELERY_*` fields
- [ ] Sentry has no `CeleryIntegration`
- [ ] Task API endpoints have no Celery dispatch/revoke (stubbed with log)
- [ ] All modified `.py` files pass `ast.parse()`

## Verification

```bash
# 1. AST zero-import scan (the definitive check)
python3 -c "
import ast, sys, os
errors = []
for root, dirs, files in os.walk('backend-hormonia/app'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if not f.endswith('.py'): continue
        path = os.path.join(root, f)
        try:
            tree = ast.parse(open(path).read())
        except: continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, 'module', '') or ''
                names = [a.name for a in node.names]
                for name in [mod] + names:
                    if 'celery' in name.lower():
                        errors.append(f'{path}:{node.lineno}: {name}')
if errors:
    print('FAIL — Celery imports found:')
    for e in errors: print(f'  {e}')
    sys.exit(1)
else:
    print('PASS — Zero Celery imports')
"

# 2. Requirements clean
! grep -iE 'celery|kombu|amqp|billiard|flower|asgiref' backend-hormonia/requirements.txt && echo "PASS — Requirements clean" || echo "FAIL"

# 3. Docker-compose uses taskiq
grep -q 'taskiq worker' backend-hormonia/docker-compose.yml && echo "PASS — Docker worker" || echo "FAIL"
grep -q 'taskiq scheduler' backend-hormonia/docker-compose.yml && echo "PASS — Docker scheduler" || echo "FAIL"

# 4. Deleted files confirmed
test ! -f backend-hormonia/app/api/v2/routers/tasks/utils/celery_integration.py && echo PASS || echo "FAIL: celery_integration"
test ! -f backend-hormonia/app/utils/task_monitoring.py && echo PASS || echo "FAIL: task_monitoring"

# 5. All modified Python files parse
python3 -c "
import ast, sys
files = [
    'backend-hormonia/app/task_queue.py',
    'backend-hormonia/app/api/v2/routers/health/core.py',
    'backend-hormonia/app/api/v2/routers/health/service_health.py',
    'backend-hormonia/app/api/v2/routers/tasks/dependencies.py',
    'backend-hormonia/app/api/v2/routers/tasks/endpoints/operations.py',
    'backend-hormonia/app/api/v2/routers/tasks/endpoints/bulk.py',
    'backend-hormonia/app/api/v2/routers/tasks/endpoints/crud.py',
    'backend-hormonia/app/services/flow/management/pause_resume.py',
    'backend-hormonia/app/core/setup/sentry.py',
    'backend-hormonia/app/core/monitoring_config.py',
    'backend-hormonia/app/core/metrics.py',
    'backend-hormonia/app/config/settings/integrations.py',
    'backend-hormonia/app/config/settings/__init__.py',
    'backend-hormonia/app/config/settings/performance.py',
]
for f in files:
    try: ast.parse(open(f).read())
    except SyntaxError as e:
        print(f'FAIL: {f}: {e}')
        sys.exit(1)
print(f'PASS — All {len(files)} infrastructure files parse OK')
"
```

## Inputs

- T03 completed: All Celery task files and bridge code deleted
- Research doc sections on non-task infrastructure files (detailed line numbers and what to change)
- D003: Taskiq broker reads `TASKIQ_BROKER_URL → CELERY_BROKER_URL → REDIS_URL → default` — keep `CELERY_BROKER_URL` env var in docker-compose

## Expected Output

- `celery_integration.py` and `task_monitoring.py` deleted
- `task_queue.py` — cleaned, only Redis store functions remain
- Health endpoints — Taskiq-only checks
- Task API — Celery dispatch/revoke replaced with logged no-ops
- `pause_resume.py` — AsyncResult.revoke() replaced with logged no-op
- Sentry/monitoring_config — no CeleryIntegration
- Settings — no CELERY_* fields
- Metrics — no Celery histograms/gauges
- `requirements.txt` — no celery/asgiref/flower deps
- `docker-compose.yml` — taskiq worker/scheduler commands
- `Makefile` — taskiq targets
