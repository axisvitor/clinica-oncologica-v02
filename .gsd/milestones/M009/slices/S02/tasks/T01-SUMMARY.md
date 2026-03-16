---
id: T01
parent: S02
milestone: M009
provides:
  - ListRedisScheduleSource instance for dynamic one-shot scheduling (ETA replacement)
  - schedule_task_at async helper for delayed task dispatch
key_files:
  - backend-hormonia/app/taskiq_broker.py
  - backend-hormonia/app/tasks/taskiq_base.py
key_decisions:
  - ListRedisScheduleSource uses same Dragonfly URL as broker (_broker_url)
  - schedule_task_at uses lazy import to avoid circular dependency with taskiq_broker
patterns_established:
  - ETA dispatch via schedule_task_at(task, datetime, *args) replaces Celery .apply_async(eta=)
observability_surfaces:
  - get_broker_status() now reports scheduler_sources list including ListRedisScheduleSource
duration: 5m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: Add ListRedisScheduleSource and ETA dispatch helpers to broker

**Added `ListRedisScheduleSource` for dynamic one-shot scheduling and `schedule_task_at` helper for ETA dispatch**

## What Happened

Added `ListRedisScheduleSource` from `taskiq_redis` to the broker module alongside the existing `LabelScheduleSource`. The scheduler now includes both sources: Label for static cron/interval, ListRedis for dynamic one-shot delayed dispatch. Created `schedule_task_at()` async helper in `taskiq_base.py` that wraps `task.kicker().schedule_by_time()` — this is the direct replacement for Celery's `.apply_async(eta=datetime)` pattern used by task_scheduler.py, retry_handler.py, and send_bulk_messages. Updated `get_broker_status()` to report both scheduler sources.

## Verification

- `ast.parse(broker)` — PASS
- `ast.parse(base)` — PASS
- `grep dynamic_schedule_source broker` — 2 lines (definition + scheduler usage) — PASS
- `grep schedule_task_at base` — 4 lines (docstring, def, example) — PASS
- Slice check: `grep -c "@celery_app.task" messaging.py` returns 9 — Celery tasks intact — PASS

## Diagnostics

- `get_broker_status()` returns `scheduler_sources: ["LabelScheduleSource", "ListRedisScheduleSource"]`
- Pending dynamic schedules visible in Dragonfly via `redis-cli -p 6380 KEYS "taskiq:schedule:*"`
- If ListRedisScheduleSource can't reach Dragonfly, `schedule_task_at()` raises Redis connection error — propagated by callers

## Deviations

- Found file corruption during editing (duplicated tail in both files). Rewrote both files cleanly using `write` instead of incremental `edit`. Content matches plan exactly.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/taskiq_broker.py` — Added ListRedisScheduleSource import, dynamic_schedule_source instance, updated scheduler to include both sources, updated get_broker_status() output
- `backend-hormonia/app/tasks/taskiq_base.py` — Added schedule_task_at() async helper with lazy import, added datetime import
- `.gsd/milestones/M009/slices/S02/tasks/T01-PLAN.md` — Added Observability Impact section (pre-flight fix)
