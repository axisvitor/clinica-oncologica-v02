---
phase: 03-operational-stability
plan: 01
subsystem: infra
tags: [celery, asyncio, asgiref, async_to_sync, task-queue, memory-leak]

# Dependency graph
requires: []
provides:
  - "Celery flow tasks using async_to_sync instead of asyncio.run() — zero asyncio.run() calls in app/tasks/"
  - "send_critical_alert_sync collapsed from 18-line loop-detection boilerplate to 1-line async_to_sync call"
affects: [04-saga-async, 06-async-migration]

# Tech tracking
tech-stack:
  added: [asgiref.sync.async_to_sync (already in project, now used in flow tasks)]
  patterns: [async_to_sync wrapper pattern for all Celery sync-to-async bridging]

key-files:
  created: []
  modified:
    - backend-hormonia/app/tasks/flows/flow_tasks.py
    - backend-hormonia/app/tasks/flows/base.py

key-decisions:
  - "asyncio import retained in flow_tasks.py — still needed by process_daily_flows_async (Semaphore, gather, sleep, TimeoutError)"
  - "asyncio import removed from base.py — used only in the removed loop-detection block"
  - "ThreadPoolExecutor in send_critical_alert_sync eliminated — async_to_sync handles event loop threading correctly"

patterns-established:
  - "async_to_sync pattern: all Celery tasks bridging sync→async use async_to_sync(coro_fn)(args) — matches 15+ existing task files"

requirements-completed: [ASYNC-04]

# Metrics
duration: 5min
completed: 2026-02-22
---

# Phase 3 Plan 01: Operational Stability — asyncio.run() Elimination Summary

**Replaced `asyncio.run()` and 18-line loop-detection boilerplate with `async_to_sync` in both remaining Celery flow task files, closing memory leak risk from per-invocation event loop creation**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-22T18:25:42Z
- **Completed:** 2026-02-22T18:30:45Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Eliminated `asyncio.run()` from `flow_tasks.py` — `process_daily_flows` Celery task now uses `async_to_sync(process_daily_flows_async)(limit)`
- Eliminated `get_event_loop` / `run_until_complete` / `ThreadPoolExecutor` boilerplate from `base.py` — `send_critical_alert_sync` collapsed from ~18 lines to 1 line
- Zero `asyncio.run()` actual code calls remain in `app/tasks/` (only comments referencing old pattern)
- Both files confirmed to import cleanly; full symbol import test passes

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace asyncio.run() with async_to_sync in flow_tasks.py** - `6cbaf58e` (fix)
2. **Task 2: Replace asyncio.run() and loop detection in base.py send_critical_alert_sync** - `7e92df44` (fix)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `backend-hormonia/app/tasks/flows/flow_tasks.py` - Added `from asgiref.sync import async_to_sync`; replaced `asyncio.run(process_daily_flows_async(limit))` with `async_to_sync(process_daily_flows_async)(limit)`
- `backend-hormonia/app/tasks/flows/base.py` - Added `from asgiref.sync import async_to_sync`; removed `import asyncio`; collapsed 18-line loop-detection block in `send_critical_alert_sync` into single `async_to_sync(manager.process_alert)(alert)` call

## Decisions Made

- asyncio import retained in `flow_tasks.py` — the `process_daily_flows_async` function still uses `asyncio.Semaphore`, `asyncio.gather`, `asyncio.sleep`, and `asyncio.TimeoutError` internally; only the sync entry point changed
- asyncio import removed from `base.py` — it was used exclusively in the loop-detection block that was deleted; no other code in the file needed it
- ThreadPoolExecutor pattern eliminated — the old code used a ThreadPoolExecutor as a fallback when the event loop was already running, which itself called `asyncio.run()` inside the thread; `async_to_sync` handles this correctly without manual threading

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. The `grep -rn "asyncio.run(" app/tasks/` check after completion showed three matches, all in comment lines (not code), in `quiz_flow/helpers.py`, `quiz_flow/response_tasks.py`, and `quiz_flow/trigger_tasks.py` — those comments reference the old pattern to explain why it was replaced. The actual code call count is zero.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ASYNC-04 requirement fully satisfied: zero `asyncio.run()` calls in `app/tasks/`
- Pattern is consistent with the 15+ other task files already using `async_to_sync`
- No blockers for subsequent plans in Phase 3

---
*Phase: 03-operational-stability*
*Completed: 2026-02-22*
