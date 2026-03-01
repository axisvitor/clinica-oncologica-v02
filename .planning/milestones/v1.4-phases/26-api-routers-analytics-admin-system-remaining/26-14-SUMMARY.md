---
phase: 26-api-routers-analytics-admin-system-remaining
plan: 14
subsystem: api
tags: [fastapi, sqlalchemy, asyncsession, routers, health, localization, webhooks, ai]

# Dependency graph
requires:
  - phase: 21-async-foundation
    provides: get_async_db request-scope AsyncSession dependency
  - phase: 26-api-routers-analytics-admin-system-remaining
    provides: prior router AsyncSession migration patterns
provides:
  - AsyncSession-backed system and health routers (7 files)
  - AsyncSession-backed localization, webhooks, and AI insights routers (3 files)
  - Removal of remaining Depends(get_db) in this 10-file plan scope
affects: [phase-26-remaining-plans, phase-27-test-stability, api-router-async-guards]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Replace Depends(get_db) with Depends(get_async_db) plus AsyncSession typing
    - Replace db.query(...) with await db.execute(select(...)) in async handlers
    - Await DB execute calls in health/system checks while preserving endpoint contracts

key-files:
  created:
    - .planning/phases/26-api-routers-analytics-admin-system-remaining/26-14-SUMMARY.md
  modified:
    - backend-hormonia/app/api/v2/routers/system/metrics.py
    - backend-hormonia/app/api/v2/routers/system/initialization.py
    - backend-hormonia/app/api/v2/routers/system/components.py
    - backend-hormonia/app/api/v2/routers/system/health.py
    - backend-hormonia/app/api/v2/routers/health/metrics.py
    - backend-hormonia/app/api/v2/routers/health/core.py
    - backend-hormonia/app/api/v2/routers/health/test.py
    - backend-hormonia/app/api/v2/routers/localization.py
    - backend-hormonia/app/api/v2/routers/webhooks.py
    - backend-hormonia/app/api/v2/routers/ai/insights.py

key-decisions:
  - Keep API contracts unchanged and limit migration to dependency/DB-execution semantics.
  - Convert health metrics and AI insights router-level sync queries to async select/execute patterns.
  - Keep webhooks service factory contract intact while injecting AsyncSession via get_async_db.

patterns-established:
  - "Router migration pattern: AsyncSession annotation + Depends(get_async_db) in every handler signature"
  - "Health compatibility pattern: resolve patched DB targets but await execute when awaitable"

requirements-completed: [API-06, API-08, API-09]

# Metrics
duration: 2 min
completed: 2026-02-27
---

# Phase 26 Plan 14: System/Health/Localization/Webhooks/AI AsyncSession Summary

**Ten remaining routers now use AsyncSession DI with awaited query execution, including health metrics count queries and AI insights patient lookup conversion.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-27T22:18:05Z
- **Completed:** 2026-02-27T22:20:28Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Migrated all 7 plan-scoped `system/*` and `health/*` routers from `Depends(get_db)` to `Depends(get_async_db)` with `AsyncSession` typing.
- Converted synchronous DB operations in `health/metrics.py` and `ai/insights.py` to awaited async execution (`await db.execute(select(...))`).
- Migrated `localization.py`, `webhooks.py`, and `ai/insights.py` dependencies to async DI while preserving request/response contracts.
- Verified all 10 files compile and source checks pass: zero `Depends(get_db)` in scope and zero `db.query(` in `health/metrics.py`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate system/ and health/ sub-routers to AsyncSession** - `16e3c439` (feat)
2. **Task 2: Migrate localization.py, webhooks.py, and ai/insights.py to AsyncSession** - `a62f1540` (feat)

**Plan metadata:** pending metadata commit

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/system/metrics.py` - async DB dependency and awaited session-count query
- `backend-hormonia/app/api/v2/routers/system/initialization.py` - async DB dependency and awaited DB probe
- `backend-hormonia/app/api/v2/routers/system/components.py` - async DB dependency updates for both handlers
- `backend-hormonia/app/api/v2/routers/system/health.py` - async DB dependency update for component checks
- `backend-hormonia/app/api/v2/routers/health/metrics.py` - async DB dependency in all handlers and async count queries
- `backend-hormonia/app/api/v2/routers/health/core.py` - async DB dependency in readiness/detailed handlers with awaitable execute compatibility
- `backend-hormonia/app/api/v2/routers/health/test.py` - async DB dependency update
- `backend-hormonia/app/api/v2/routers/localization.py` - async DB dependency in all three affected signatures
- `backend-hormonia/app/api/v2/routers/webhooks.py` - async webhook service factory dependency
- `backend-hormonia/app/api/v2/routers/ai/insights.py` - async DB dependencies and patient lookup conversion to async select

## Decisions Made

- Preserved all route paths and payload contracts; only dependency injection and DB execution mechanics changed.
- Used `select(func.count(...))` async aggregation in health metrics to eliminate remaining sync query patterns.
- Kept webhooks service delegation unchanged to avoid service-layer scope expansion in this plan.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 26-14 async migration scope is complete with source-level guards satisfied.
- Phase 26 remains in progress with plans 26-11/12/13/15/16 still open on disk.

## Self-Check: PASSED

- FOUND: .planning/phases/26-api-routers-analytics-admin-system-remaining/26-14-SUMMARY.md
- FOUND: 16e3c439
- FOUND: a62f1540

---
*Phase: 26-api-routers-analytics-admin-system-remaining*
*Completed: 2026-02-27*
