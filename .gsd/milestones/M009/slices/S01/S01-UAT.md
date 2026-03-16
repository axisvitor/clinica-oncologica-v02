# S01: Taskiq broker + base task + FastAPI integration — UAT

**Milestone:** M009
**Written:** 2026-03-16

## UAT Type

- UAT mode: mixed (artifact-driven for code structure + live-runtime for broker/health verification)
- Why this mode is sufficient: The slice builds infrastructure (broker, middleware, health checks) that must be verified both structurally (correct wiring, imports, patterns) and at runtime (Dragonfly connectivity, task dispatch, retry behavior). Artifact checks cover wiring correctness; runtime checks cover actual broker/worker behavior.

## Preconditions

- Dragonfly running on `localhost:6380` (or `REDIS_URL` / `CELERY_BROKER_URL` / `TASKIQ_BROKER_URL` pointing to it)
- PostgreSQL running (for `smoke_test_db_query`)
- `taskiq`, `taskiq-redis`, `taskiq-fastapi` installed (`pip install -r requirements.txt`)
- Working directory: `backend-hormonia/`
- Environment variables: `DATABASE_URL` set for DB session tests

## Smoke Test

Start the Taskiq worker and dispatch `smoke_test_echo`:
```bash
# Terminal 1: Start worker
taskiq worker app.taskiq_broker:broker app.tasks.smoke_test

# Terminal 2: Dispatch task
python -c "
import asyncio
from app.tasks.smoke_test import smoke_test_echo
asyncio.run(smoke_test_echo.kiq('UAT smoke'))
"
```
**Expected:** Worker terminal shows task execution with `smoke_test_echo received: UAT smoke`. Result includes `{status: ok, message: 'UAT smoke', worker: 'taskiq'}`.

## Test Cases

### 1. Broker connects to Dragonfly and dispatches task

1. Start Taskiq worker: `taskiq worker app.taskiq_broker:broker app.tasks.smoke_test`
2. Observe worker startup logs
3. In a separate terminal, dispatch: `python -c "import asyncio; from app.tasks.smoke_test import smoke_test_echo; asyncio.run(smoke_test_echo.kiq('test-dispatch'))"`
4. **Expected:** Worker logs show `smoke_test_echo received: test-dispatch`. Worker started with 2 processes.

### 2. SmartRetryMiddleware retries with exponential backoff

1. With worker running, dispatch retry task: `python -c "import asyncio; from app.tasks.smoke_test import smoke_test_retry; asyncio.run(smoke_test_retry.kiq('retry-test'))"`
2. Observe worker logs for retry attempts
3. **Expected:** Logs show "Retrying 1/3 in X.XX seconds" → "Retrying 2/3 in X.XX seconds" with increasing delay (exponential backoff + jitter). After max retries: "Maximum retries count is reached".

### 3. DB session injection via TaskiqDepends

1. Ensure DATABASE_URL is set and PostgreSQL is running
2. Start worker with full env: `taskiq worker app.taskiq_broker:broker app.tasks.smoke_test`
3. Dispatch DB task: `python -c "import asyncio; from app.tasks.smoke_test import smoke_test_db_query; asyncio.run(smoke_test_db_query.kiq())"`
4. **Expected:** Worker logs show `Task started: smoke_test_db_query` → `Task completed: smoke_test_db_query (Xms)`. Result includes `db_connected: True`, `pg_version: PostgreSQL ...`, `echo: taskiq_db_ok`.

### 4. Health check — broker healthy

1. Start the FastAPI backend: `uvicorn app.main:app --port 8000`
2. `curl http://localhost:8000/api/v2/health/ready`
3. **Expected:** Response includes `checks.taskiq_broker: true`. If a Celery worker is also running, `checks.celery_workers: true`. `checks.workers: true` (passes if either healthy).

### 5. Health check — broker unreachable (failure path)

1. Stop Dragonfly (or point `TASKIQ_BROKER_URL` to unreachable host)
2. Run: `python -c "import asyncio; from app.taskiq_broker import check_broker_health; print(asyncio.run(check_broker_health()))"`
3. **Expected:** Returns `{taskiq_broker: 'unhealthy', dragonfly_reachable: False, error: '...'}` — NOT a crash or unhandled exception.

### 6. FastAPI lifespan manages broker lifecycle

1. Start the backend with `uvicorn app.main:app --port 8000`
2. Observe startup logs
3. Stop the backend (Ctrl+C)
4. Observe shutdown logs
5. **Expected:** Startup logs include `✓ Taskiq broker started (X.XXs)`. Shutdown logs include `✓ Taskiq broker shut down`. No errors or unhandled exceptions.

### 7. Broker status helper

1. `python -c "from app.taskiq_broker import get_broker_status; import json; print(json.dumps(get_broker_status(), indent=2))"`
2. **Expected:** Returns dict with `taskiq.status: configured`, `broker_type: ListQueueBroker`, `queue_name: hormonia`, `result_backend: RedisAsyncResultBackend`, `retry_middleware: SmartRetryMiddleware`, `scheduler: LabelScheduleSource`.

### 8. task_queue.py Taskiq coexistence access

1. `python -c "from app.task_queue import get_taskiq_broker; b = get_taskiq_broker(); print(type(b).__name__)"`
2. `python -c "import asyncio; from app.task_queue import get_taskiq_broker_health; print(asyncio.run(get_taskiq_broker_health()))"`
3. **Expected:** First returns `ListQueueBroker`. Second returns `{taskiq_broker: 'healthy', dragonfly_reachable: True}` (with Dragonfly running).

## Edge Cases

### Broker module import without full env vars

1. Unset DATABASE_URL, WUZAPI_TOKEN, etc.
2. `python -c "from app.taskiq_broker import broker; print(type(broker).__name__)"`
3. **Expected:** Returns `ListQueueBroker` — broker imports without triggering settings validation chain.

### Worker startup without Dragonfly

1. Stop Dragonfly
2. Start worker: `taskiq worker app.taskiq_broker:broker app.tasks.smoke_test`
3. **Expected:** Worker starts but connection attempts fail with logged errors. No unhandled crash.

### Direct import of smoke_test module (not through app.tasks)

1. `python -c "from app.tasks.smoke_test import smoke_test_echo; print(smoke_test_echo)"`
2. **Expected:** Imports successfully without requiring DATABASE_URL or other env vars (imports through taskiq_broker, not app.tasks.__init__).

## Failure Signals

- Worker startup crashes with import error → check requirements.txt for taskiq packages
- `check_broker_health()` raises unhandled exception → failure path not properly wrapped
- Health endpoint returns 500 instead of degraded status → exception handling missing in readiness probe
- `smoke_test_db_query` fails with "no session" → TaskiqDepends wiring broken, check taskiq_fastapi.init() order
- `smoke_test_retry` doesn't retry → SmartRetryMiddleware not attached to broker, check `.with_middlewares()` chain
- `from app.taskiq_broker import broker` requires DATABASE_URL → settings import leaked into broker module

## Requirements Proved By This UAT

- R077 — Taskiq broker connected to Dragonfly, worker processes tasks, FastAPI lifespan integration, health check reports status
- R078 — SmartRetryMiddleware proven, DB session via TaskiqDepends, structured task logging

## Not Proven By This UAT

- Scheduler end-to-end firing (LabelScheduleSource → TaskiqScheduler → periodic task dispatch) — requires running scheduler process alongside worker in Docker
- Real production task migration (S02-S04 scope)
- Celery removal and bridge cleanup (S05 scope)

## Notes for Tester

- The smoke test tasks are intentionally simple — they exist to prove infrastructure, not business logic.
- `smoke_test_retry` in-memory fail counter may not work as expected with multi-worker setup (each worker has its own counter). The retry middleware behavior itself is correctly proven.
- The scheduler test (`smoke_test_scheduled` with `* * * * *` cron) requires running `taskiq scheduler app.taskiq_broker:scheduler` in addition to the worker. This is a separate verification step.
- Health check coexistence: if no Celery worker is running, `checks.celery_workers` will be `false` but `checks.workers` will be `true` as long as Taskiq broker is healthy — this is correct behavior during migration.
