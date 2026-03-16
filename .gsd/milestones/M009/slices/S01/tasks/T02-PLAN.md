# T02: FastAPI integration + DB dependency + health check + base patterns

**Slice:** S01
**Milestone:** M009

## Goal
Wire Taskiq into FastAPI lifespan, create TaskiqDepends-based DB session provider, replace Celery health check with Taskiq liveness probe, and establish reusable base task patterns.

## Must-Haves

### Truths
- FastAPI starts with Taskiq broker startup in lifespan (logs confirm)
- FastAPI shutdown triggers broker shutdown cleanly
- A task can receive a DB session via `TaskiqDepends(get_db_session)` and execute a query
- `/api/v2/health` reports Taskiq worker status instead of Celery inspect
- `service_health` endpoint reports Taskiq connectivity
- TaskConfig dataclasses are reusable from tasks (not Celery-specific anymore)

### Artifacts
- `backend-hormonia/app/tasks/taskiq_base.py` — DB session dependency, task logging helpers, retry config patterns
- `backend-hormonia/app/core/lifespan.py` — Taskiq broker startup/shutdown in lifespan
- `backend-hormonia/app/api/v2/routers/health/core.py` — Taskiq worker status check
- `backend-hormonia/app/api/v2/routers/health/service_health.py` — Taskiq connectivity check
- `backend-hormonia/app/task_queue.py` — Updated to support both Celery and Taskiq (coexistence period)

### Key Links
- `lifespan.py` → `taskiq_broker.py` via `from app.taskiq_broker import broker` + `taskiq_fastapi.init(broker, app)`
- `taskiq_base.py` → `taskiq_broker.py` via `TaskiqDepends`
- `health/core.py` → `taskiq_broker.py` via Taskiq liveness mechanism (not Celery control.inspect)

## Steps
1. Add `taskiq_fastapi.init(broker, "app.main:app")` to broker module
2. Update `lifespan.py`:
   - Import broker
   - Add `await broker.startup()` in startup (with `if not broker.is_worker_process` guard)
   - Add `await broker.shutdown()` in shutdown
3. Create `app/tasks/taskiq_base.py`:
   - `get_db_session` dependency using AsyncSession (TaskiqDepends pattern)
   - Task logging helpers (log_start, log_success, log_error) as standalone functions
   - Retry config pattern documentation (how to set retry_on_error, max_retries, delay per task)
4. Create a DB-using test task in `smoke_test.py` that queries via the injected session
5. Update `health/core.py`:
   - Replace `celery_app.control.inspect(timeout=0.5)` with Taskiq worker liveness (Redis ping + broker state)
   - Keep backward compat: if Celery is still running (coexistence), report both
6. Update `health/service_health.py` similarly
7. Update `task_queue.py` to expose Taskiq broker alongside Celery (coexistence)
8. Verify: start backend + worker, confirm health check reports Taskiq status
9. Verify: dispatch DB-using task, confirm it queries and returns result

## Context
- `taskiq_fastapi.init(broker, "app.main:app")` must be called AFTER broker creation but BEFORE task definitions that use TaskiqDepends
- `broker.is_worker_process` prevents broker.startup() from running inside worker processes (would cause infinite loop)
- Health checks currently use `celery_app.control.inspect()` — need Taskiq equivalent
- During coexistence (S02-S04), both Celery and Taskiq may be running — health should report both
- DB sessions in Celery tasks used `get_scoped_session()` (sync) — Taskiq can use AsyncSession directly

## Observability Impact

### Signals Changed
- `/api/v2/health/ready` — `checks.workers` now reports Taskiq broker reachability (Redis ping) alongside Celery worker inspection during coexistence.
- `/api/v2/health/workers` — `WorkerHealth` includes `taskiq_status` field showing broker health: `healthy | unreachable | not_configured`.
- `/api/v2/health/detailed` — Aggregated status reflects Taskiq worker connectivity.
- FastAPI lifespan logs emit `Taskiq broker started` / `Taskiq broker shut down` at startup/shutdown boundaries.

### How to Inspect
- **Broker health:** `GET /api/v2/health/workers` → check `taskiq_status` field.
- **Lifespan integration:** Application logs contain `Taskiq broker started` and `Taskiq broker shut down`.
- **DB dependency in tasks:** Worker logs show `TaskiqDepends[get_db_session]` resolution when DB-using tasks execute.
- **Failure surfaces:** Health endpoints return `degraded` with `error` detail when Dragonfly is unreachable — never 500.

### Failure State Visibility
- If Dragonfly is down: health endpoints report `taskiq_broker: unreachable` with error string.
- If broker.startup() fails: lifespan logs `Taskiq broker startup failed: <error>` and continues (non-blocking).
- If DB session injection fails: task fails with structured error in result backend, logged at ERROR level.
