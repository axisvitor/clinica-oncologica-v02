---
id: T01
parent: S01
milestone: M009
provides:
  - Taskiq ListQueueBroker configured with Dragonfly (redis://localhost:6380/0)
  - SmartRetryMiddleware with exponential backoff + jitter (base 60s, max 600s, 3 retries)
  - RedisAsyncResultBackend for task result storage (1h TTL)
  - LabelScheduleSource + TaskiqScheduler for periodic tasks
  - smoke_test_echo task — proven dispatch → worker → result
  - smoke_test_retry task — proven SmartRetryMiddleware catches errors, retries with backoff, enforces max_retries
  - smoke_test_scheduled task — labeled with cron schedule for scheduler
  - get_broker_status() and check_broker_health() for health checks
  - taskiq 0.12.1, taskiq-redis 1.2.2, taskiq-fastapi 0.4.0 installed
requires: []
affects: [S02, S03, S04]
key_files:
  - backend-hormonia/app/taskiq_broker.py
  - backend-hormonia/app/tasks/smoke_test.py
  - backend-hormonia/requirements.txt
key_decisions:
  - "ListQueueBroker over RedisStreamBroker — simpler, no ack overhead, tasks have own retry logic"
  - "Broker reads URL from env directly (not app.config.settings) to avoid heavyweight settings import chain"
  - "redis bumped from <7.0.0 to <8.0.0 — taskiq-redis pulls redis 7.3.0"
patterns_established:
  - "Taskiq task: @broker.task decorator + async def + .kiq() dispatch"
  - "Retry via SmartRetryMiddleware labels: retry_on_error=True, max_retries=N, delay=N"
  - "Schedule via task decorator label: schedule=[{cron: '...'}]"
  - "Worker command: taskiq worker app.taskiq_broker:broker app.tasks.<module>"
observability_surfaces:
  - "get_broker_status() → broker config summary (type, URL, queue, middleware, scheduler)"
  - "check_broker_health() → async Redis ping returning {taskiq_broker: healthy/unhealthy, dragonfly_reachable: bool}"
  - "Worker startup logs: 'taskiq worker' outputs worker process count + listening confirmation"
  - "SmartRetryMiddleware logs: 'Retrying N/M in X.XX seconds' and 'Maximum retries count is reached'"
drill_down_paths:
  - .gsd/milestones/M009/slices/S01/tasks/T01-PLAN.md
duration: 20m
verification_result: pass
completed_at: 2026-03-16
---

# T01: Taskiq broker setup + dependencies + test task

**Taskiq ListQueueBroker with SmartRetryMiddleware connected to Dragonfly, smoke test task dispatched → executed → result returned, retry middleware proven with exponential backoff**

## What Happened

Installed taskiq 0.12.1 + taskiq-redis 1.2.2 + taskiq-fastapi 0.4.0. Created `app/taskiq_broker.py` with ListQueueBroker pointing to Dragonfly on port 6380, SmartRetryMiddleware (default 3 retries, 60s base delay, exponential backoff capped at 600s, jitter enabled), RedisAsyncResultBackend (1h TTL), and LabelScheduleSource + TaskiqScheduler.

The broker module reads the Redis URL directly from environment variables (`TASKIQ_BROKER_URL` → `CELERY_BROKER_URL` → `REDIS_URL` → default `redis://localhost:6380/0`) instead of importing `app.config.settings`. This avoids pulling in the entire settings validation chain which requires all env vars including WuzAPI tokens — important for worker process startup and standalone testing.

Created `app/tasks/smoke_test.py` with three tasks: `smoke_test_echo` (simple dispatch → result), `smoke_test_retry` (deliberately fails to test retry middleware), and `smoke_test_scheduled` (cron-labeled for scheduler). Worker started with `taskiq worker app.taskiq_broker:broker app.tasks.smoke_test` — 2 worker processes initialized and listening.

Verification: dispatched `smoke_test_echo.kiq('M009 Taskiq test')` → worker executed → result returned `{'status': 'ok', 'message': 'M009 Taskiq test', 'worker': 'taskiq'}`. Retry test: SmartRetryMiddleware logged "Retrying 1/3 in 2.68 seconds" → "Retrying 2/3 in 6.27 seconds" → "Maximum retries count is reached" — exponential backoff with jitter confirmed.

redis package was bumped from `<7.0.0` to `<8.0.0` because taskiq-redis requires redis 7.x.

## Deviations

- Scheduler test (smoke_test_scheduled firing via cron) deferred to T02 — scheduler verification aligns better with the FastAPI integration task where the scheduler lifecycle is managed.
- In-memory fail counter in smoke_test_retry doesn't work across multi-worker processes (each worker has its own counter). Not a problem for real tasks — it's just the test design.

## Diagnostics

- **Broker config**: Call `get_broker_status()` from `app.taskiq_broker` — returns broker type, URL (masked), queue name, middleware, scheduler
- **Broker health**: Call `check_broker_health()` from `app.taskiq_broker` — async Redis ping returning `{taskiq_broker: healthy/unhealthy, dragonfly_reachable: bool}`
- **Worker processes**: `taskiq worker app.taskiq_broker:broker app.tasks.smoke_test` — logs show number of worker processes and task execution
- **Retry verification**: SmartRetryMiddleware logs at INFO level: `"Retrying 1/3 in X.XX seconds"`, `"Maximum retries count is reached"` — search for these in worker logs
- **Dispatch verification**: `smoke_test_echo.kiq('test')` dispatches to Dragonfly queue `hormonia` — result returned via `RedisAsyncResultBackend`

## Files Created/Modified

- `backend-hormonia/app/taskiq_broker.py` — NEW: Taskiq broker, SmartRetryMiddleware, result backend, scheduler, health check helpers
- `backend-hormonia/app/tasks/smoke_test.py` — NEW: smoke test tasks for dispatch/retry/schedule verification
- `backend-hormonia/requirements.txt` — Added taskiq ecosystem; bumped redis to <8.0.0
