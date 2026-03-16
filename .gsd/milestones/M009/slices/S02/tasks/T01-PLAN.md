---
estimated_steps: 4
estimated_files: 2
---

# T01: Add ListRedisScheduleSource and ETA dispatch helpers to broker

**Slice:** S02 — Messaging tasks migradas
**Milestone:** M009

## Description

Taskiq's `LabelScheduleSource` (used in S01 for cron/interval periodic tasks) does NOT support `add_schedule()` — it raises `NotImplementedError`. For ETA/delayed dispatch (replacing Celery's `.apply_async(eta=datetime)` pattern), we need `ListRedisScheduleSource` from `taskiq-redis`, which stores one-shot schedules in Redis and fires them at the specified time.

Three call sites need this: `send_bulk_messages` (inside messaging tasks), `task_scheduler.py`, and `retry_handler.py`. This task adds the schedule source and a convenience helper before the messaging tasks are created.

## Steps

1. **Add `ListRedisScheduleSource` to `app/taskiq_broker.py`**:
   - Import `ListRedisScheduleSource` from `taskiq_redis`
   - Create instance: `dynamic_schedule_source = ListRedisScheduleSource(url=_broker_url)` — uses same Dragonfly URL
   - Add it to the scheduler's sources list: `scheduler = TaskiqScheduler(broker, sources=[schedule_source, dynamic_schedule_source])`
   - Export `dynamic_schedule_source` so task modules and call sites can import it
   - Add a comment explaining: LabelScheduleSource handles cron/interval (static), ListRedisScheduleSource handles one-shot delayed dispatch (dynamic)

2. **Add `schedule_by_time` helper to `app/tasks/taskiq_base.py`**:
   - Create async helper function: `async def schedule_task_at(task, scheduled_time: datetime, *args, **kwargs)` that wraps `task.kicker().schedule_by_time(dynamic_schedule_source, scheduled_time, *args, **kwargs)`
   - Import `dynamic_schedule_source` from `app.taskiq_broker` inside the function body (lazy import to avoid circular)
   - Return the `CreatedSchedule` result for callers that need the schedule ID
   - Add docstring explaining this replaces Celery's `.apply_async(eta=datetime)` pattern

3. **Verify both files parse cleanly**:
   - `python3 -c "import ast; ast.parse(open('backend-hormonia/app/taskiq_broker.py').read())"`
   - `python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/taskiq_base.py').read())"`

4. **Verify exports exist**:
   - `grep "dynamic_schedule_source" backend-hormonia/app/taskiq_broker.py` shows the instance
   - `grep "schedule_task_at" backend-hormonia/app/tasks/taskiq_base.py` shows the helper

## Must-Haves

- [ ] `ListRedisScheduleSource` instance created in `taskiq_broker.py` using same Dragonfly URL
- [ ] `dynamic_schedule_source` is a module-level name importable from `app.taskiq_broker`
- [ ] Scheduler includes both `LabelScheduleSource` (static) and `ListRedisScheduleSource` (dynamic)
- [ ] `schedule_task_at` async helper in `taskiq_base.py`
- [ ] Both files pass `ast.parse()` check

## Verification

- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/taskiq_broker.py').read())"` passes
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/taskiq_base.py').read())"` passes
- `grep "dynamic_schedule_source" backend-hormonia/app/taskiq_broker.py` returns at least 2 lines (definition + scheduler usage)
- `grep "schedule_task_at" backend-hormonia/app/tasks/taskiq_base.py` returns at least 1 line

## Inputs

- `backend-hormonia/app/taskiq_broker.py` — S01 output: broker, SmartRetryMiddleware, LabelScheduleSource, scheduler. `_broker_url` is the Dragonfly connection string. `schedule_source` is the LabelScheduleSource. `scheduler` is the TaskiqScheduler.
- `backend-hormonia/app/tasks/taskiq_base.py` — S01 output: DbSession, log_task_start/success/error helpers.
- The `ListRedisScheduleSource` class is imported from `taskiq_redis` (already in requirements.txt from S01).
- `ListRedisScheduleSource` constructor signature: `ListRedisScheduleSource(url: str)` — takes the Redis URL directly.
- `AsyncKicker.schedule_by_time(source, time, *args, **kwargs)` — creates a `ScheduledTask` with the given time, calls `source.add_schedule()`, returns `CreatedSchedule`.

## Expected Output

- `backend-hormonia/app/taskiq_broker.py` — Modified: has `dynamic_schedule_source = ListRedisScheduleSource(url=_broker_url)`, scheduler includes both sources
- `backend-hormonia/app/tasks/taskiq_base.py` — Modified: has `schedule_task_at()` async helper function
