# S01: Taskiq broker + base task + FastAPI integration

**Goal:** Stand up the Taskiq infrastructure — broker, scheduler, retry middleware, FastAPI integration, DB session dependency, health check — and prove it works against Dragonfly with a real test task.
**Demo:** `taskiq worker` processes a test task via Dragonfly, retry middleware catches errors and retries with backoff, scheduler fires a periodic task, FastAPI lifespan manages broker lifecycle, health check reports Taskiq worker status.

## Must-Haves

- Taskiq broker connects to Dragonfly (6380) and processes tasks
- SmartRetryMiddleware retries failed tasks with exponential backoff + jitter
- LabelScheduleSource + TaskiqScheduler fires periodic tasks on cron/interval
- FastAPI lifespan integrates broker startup/shutdown
- DB session available to tasks via TaskiqDepends
- Health check endpoint reports Taskiq worker status (replaces Celery inspect)
- A real test task (not stub) executes end-to-end: dispatch → worker → result
- `taskiq`, `taskiq-redis`, `taskiq-fastapi` in requirements.txt
- Worker starts via `taskiq worker app.taskiq_broker:broker`
- Scheduler starts via `taskiq scheduler app.taskiq_broker:scheduler`

## Tasks

- [x] **T01: Taskiq broker setup + dependencies + test task**
  Install taskiq + taskiq-redis + taskiq-fastapi. Create `app/taskiq_broker.py` with broker, SmartRetryMiddleware, result backend, scheduler. Create a smoke-test task. Prove broker sends/receives via Dragonfly.

- [ ] **T02: FastAPI integration + DB dependency + health check + base patterns**
  Integrate taskiq-fastapi into lifespan. Create TaskiqDepends-based DB session provider. Replace health check Celery inspect with Taskiq liveness probe. Establish base task patterns (retry labels, logging, config).

## Files Likely Touched

- `backend-hormonia/app/taskiq_broker.py` — NEW: broker, middleware, scheduler, schedule source
- `backend-hormonia/app/tasks/taskiq_base.py` — NEW: base task patterns and DB dependency
- `backend-hormonia/app/tasks/smoke_test.py` — NEW: test task for end-to-end verification
- `backend-hormonia/app/core/lifespan.py` — Add taskiq-fastapi broker lifecycle
- `backend-hormonia/app/api/v2/routers/health/core.py` — Replace Celery inspect with Taskiq probe
- `backend-hormonia/app/api/v2/routers/health/service_health.py` — Replace Celery inspect
- `backend-hormonia/requirements.txt` — Add taskiq, taskiq-redis, taskiq-fastapi

## Observability / Diagnostics

- `taskiq worker app.taskiq_broker:broker` logs show task execution
- Health check endpoint returns Taskiq worker status
- Test task result retrievable via result backend
- Scheduler logs show periodic task dispatch
