---
phase: 09-observability
plan: 01
subsystem: api
tags: [celery, redis, observability, health, metrics]

requires:
  - phase: 03-operational-stability
    provides: redis_manager singleton with sync and async client interfaces

provides:
  - Redis rolling list (celery:metrics:avg_task_duration) populated by Celery task_postrun signal
  - /health/workers endpoint avg_task_duration_seconds computed from real task data instead of hardcoded 2.5

affects:
  - future observability plans referencing /health/workers metrics
  - any dashboard or alerting that consumes avg_task_duration_seconds

tech-stack:
  added: []
  patterns:
    - "Celery signal handler pushes metrics to Redis via sync pipeline (LPUSH+LTRIM+EXPIRE) with silent except"
    - "FastAPI async health endpoint reads Redis rolling list via get_redis_manager().get_async_client()"
    - "Rolling window bounded to 100 samples with 24h TTL — prevents unbounded growth"

key-files:
  created: []
  modified:
    - backend-hormonia/app/tasks/celery_metrics.py
    - backend-hormonia/app/api/v2/routers/health/service_health.py

key-decisions:
  - "Use get_redis_manager() factory (not a non-existent redis_manager singleton) — matches actual module API"
  - "Sync pipeline in _push_duration_to_redis: LPUSH + LTRIM (0,99) + EXPIRE (86400) for atomicity and bounded growth"
  - "Silent except (pass) in write path so metrics never interfere with task execution"
  - "_read_avg_task_duration returns 0.0 on empty list or any error — health endpoint never crashes from Redis issues"
  - "round(..., 3) on computed average prevents floating-point noise in JSON response"

patterns-established:
  - "Redis metrics write in Celery signal handlers: always sync client, always silent except, always bounded list"
  - "Redis metrics read in async FastAPI: always return safe default on exception, never propagate errors"

requirements-completed: [OBS-01]

duration: 15min
completed: 2026-02-23
---

# Phase 09 Plan 01: Celery Task Duration Observability Summary

**Celery task durations pushed to Redis rolling list on every task completion; /health/workers endpoint now computes avg_task_duration_seconds from real data instead of hardcoded 2.5**

## Performance

- **Duration:** 15 min
- **Started:** 2026-02-23T13:26:00Z
- **Completed:** 2026-02-23T13:41:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Every Celery task that completes with a measured duration now pushes that duration to Redis key `celery:metrics:avg_task_duration` (max 100 samples, 24h TTL) using a sync pipeline
- The /health/workers endpoint reads the rolling list and computes a real average with `round(..., 3)` precision, returning 0.0 when no data is available
- Both write and read paths are fully wrapped in try/except — Redis failures never affect task execution or health endpoint availability

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Redis rolling duration write to task_postrun_handler** - `683a5385` (feat)
2. **Task 2: Replace hardcoded 2.5 with Redis rolling average read in check_worker_health** - `2f873869` (feat)

**Plan metadata:** (this commit) (docs: complete plan)

## Files Created/Modified

- `backend-hormonia/app/tasks/celery_metrics.py` - Added `get_redis_manager` import, `_DURATION_REDIS_KEY` constant, `_push_duration_to_redis()` helper, and call inside `_finalize_task_metadata`
- `backend-hormonia/app/api/v2/routers/health/service_health.py` - Added `get_redis_manager` import, `_read_avg_task_duration()` async helper, replaced hardcoded `2.5` with `await _read_avg_task_duration()`

## Decisions Made

- Used `get_redis_manager()` factory function (not a `redis_manager` module-level singleton) because the `app.core.redis_manager` package exports the factory, not a pre-built instance
- Sync client (`get_sync_client()`) in the Celery signal handler: signal handlers are synchronous callbacks, using `await` or `asyncio.run()` would be incorrect
- Async client (`get_async_client()`) in the health endpoint: `check_worker_health` is already `async def`, so `await` is appropriate
- `round(..., 3)` on the computed average prevents floating-point noise (e.g., 1.2999999999999998) in JSON responses

## Deviations from Plan

None - plan executed exactly as written. The only adaptation was using `get_redis_manager()` factory instead of a non-existent `redis_manager` singleton, which is consistent with the plan's intent and the codebase's actual API.

## Issues Encountered

None - both imports succeeded cleanly. The `_NullRedisManager` in test environments means this code is also safe in unit test contexts.

## User Setup Required

None - no external service configuration required. The Redis key is automatically created on first task completion.

## Next Phase Readiness

- OBS-01 is satisfied: `avg_task_duration_seconds` in /health/workers now reflects real Celery task performance
- The Redis key `celery:metrics:avg_task_duration` is ready for any future observability plans that want to extend or visualize this metric
- No blockers

## Self-Check

- [x] `backend-hormonia/app/tasks/celery_metrics.py` modified — verified via grep and import test
- [x] `backend-hormonia/app/api/v2/routers/health/service_health.py` modified — verified via grep and import test
- [x] No hardcoded `2.5` remains in service_health.py
- [x] Both commits exist: `683a5385`, `2f873869`
- [x] Import tests passed for both `_push_duration_to_redis` and `_read_avg_task_duration`

## Self-Check: PASSED

---
*Phase: 09-observability*
*Completed: 2026-02-23*
