# T01: Taskiq broker setup + dependencies + test task

**Slice:** S01
**Milestone:** M009

## Goal
Install Taskiq ecosystem, create the broker module with SmartRetryMiddleware and scheduler, and prove task dispatch/execution works against Dragonfly.

## Must-Haves

### Truths
- `pip install taskiq taskiq-redis taskiq-fastapi` succeeds
- `taskiq worker app.taskiq_broker:broker` starts and connects to Dragonfly on port 6380
- A test task dispatched via `.kiq()` executes in the worker and returns a result
- SmartRetryMiddleware retries a deliberately failing task (confirmed by log or retry count)
- `taskiq scheduler app.taskiq_broker:scheduler` starts and fires a label-scheduled test task

### Artifacts
- `backend-hormonia/app/taskiq_broker.py` — broker instance, SmartRetryMiddleware, RedisAsyncResultBackend, TaskiqScheduler, LabelScheduleSource
- `backend-hormonia/app/tasks/smoke_test.py` — test task that exercises dispatch + retry + schedule
- `backend-hormonia/requirements.txt` — taskiq, taskiq-redis, taskiq-fastapi added

### Key Links
- `smoke_test.py` → `taskiq_broker.py` via `from app.taskiq_broker import broker`
- `taskiq_broker.py` → Dragonfly via `redis://localhost:6380`

## Steps
1. Add `taskiq`, `taskiq-redis`, `taskiq-fastapi` to requirements.txt and install
2. Create `app/taskiq_broker.py`:
   - `ListQueueBroker` configured with `redis://localhost:6380/0`
   - `.with_middlewares(SmartRetryMiddleware(...))` for retry
   - `.with_result_backend(RedisAsyncResultBackend(...))` for results
   - `LabelScheduleSource(broker)` as schedule source
   - `TaskiqScheduler(broker, sources=[...])` as scheduler
3. Create `app/tasks/smoke_test.py` with:
   - A simple async test task decorated with `@broker.task`
   - A deliberately failing task with `retry_on_error=True, max_retries=3` labels
   - A scheduled task with `schedule=[{"cron": "* * * * *"}]` label
4. Start Dragonfly (should already be running on 6380)
5. Start worker: `taskiq worker app.taskiq_broker:broker`
6. Dispatch test task from Python and verify result
7. Verify retry task actually retries (check worker logs)
8. Start scheduler: `taskiq scheduler app.taskiq_broker:scheduler`
9. Verify scheduled task fires

## Context
- Dragonfly runs on port 6380 (not 6379) — decision #63 from M008
- ListQueueBroker preferred over RedisStreamBroker for simplicity — open question from M009-CONTEXT, validate here
- Taskiq SmartRetryMiddleware supports: max_retries, delay, use_jitter, use_delay_exponent, max_delay_exponent
- LabelScheduleSource reads schedule from task decorator labels — no separate beat config file
- Worker command: `taskiq worker module:broker_variable`
