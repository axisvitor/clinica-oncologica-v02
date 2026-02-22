---
phase: 03-operational-stability
plan: 02
subsystem: infra
tags: [redis, lua, rate-limiting, concurrency, sliding-window]

# Dependency graph
requires:
  - phase: 01-security-hardening
    provides: "Distributed rate limiter split into rate_limit_core.py + distributed_rate_limiter.py"
provides:
  - "Atomic sliding window rate limiting via Redis Lua script — eliminates ZCARD/ZADD race condition"
  - "Module-level _SLIDING_WINDOW_LUA constant registered as a reusable Redis script"
  - "Branch-based check_rate_limit: Lua for increment=True, read-only pipeline for increment=False"
affects: [03-operational-stability]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lua script atomicity: register_script() at init, call with keys/args at use-site"
    - "Branching increment vs read-only for optimal Redis command strategy per operation type"

key-files:
  created: []
  modified:
    - "backend-hormonia/app/middleware/rate_limit_core.py"

key-decisions:
  - "increment=True path uses Lua script (atomic); increment=False path uses pipeline (no mutation, no race)"
  - "Script registered once at __init__ via register_script() — avoids re-registering per call"
  - "_sliding_window_script() called synchronously (no await) matching existing pipeline pattern in async method"
  - "tonumber() used for all ARGV values — Redis passes all script args as strings"

patterns-established:
  - "Lua atomicity pattern: define script as module constant, register in __init__, invoke with keys/args"

requirements-completed: [REL-01]

# Metrics
duration: 2min
completed: 2026-02-22
---

# Phase 03 Plan 02: Atomic Sliding Window Rate Limiter via Redis Lua Script Summary

**Replaced non-atomic Redis pipeline in DistributedRateLimiter with a Lua script that executes ZREMRANGEBYSCORE + ZCARD + conditional ZADD atomically on the Redis server, eliminating the documented ZCARD/ZADD race condition.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-22T18:25:42Z
- **Completed:** 2026-02-22T18:27:14Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added `_SLIDING_WINDOW_LUA` module-level constant containing the sliding window Lua script with `tonumber()` for all ARGV values
- Registered the script on the Redis client via `register_script()` in `DistributedRateLimiter.__init__` — one registration per limiter instance
- Replaced the non-atomic pipeline block in `check_rate_limit` with a branch: Lua script for `increment=True`, simpler read-only pipeline for `increment=False`
- Removed the TODO comment that described the unresolved race condition — the race condition is now fixed

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Lua script constant and register in DistributedRateLimiter.__init__** - `40a41b5a` (feat)
2. **Task 2: Replace pipeline with Lua script in check_rate_limit increment path** - `210740ec` (feat)

## Files Created/Modified

- `backend-hormonia/app/middleware/rate_limit_core.py` - Added `_SLIDING_WINDOW_LUA` constant, registered script in `__init__`, replaced pipeline with branching Lua/read-only approach in `check_rate_limit`

## Decisions Made

- `increment=True` path uses the Lua script for true atomicity; `increment=False` path uses a simpler pipeline because read-only ZCARD has no mutation race condition
- Script registered once at init via `register_script()` — avoids re-registration overhead on every request
- `_sliding_window_script()` called synchronously (no `await`) matching the existing pattern where `self.redis.pipeline()` is called synchronously inside the `async def check_rate_limit` method
- `tonumber()` wraps all ARGV values in Lua because Redis passes script arguments as strings regardless of Python type

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The Lua script is registered automatically when `DistributedRateLimiter` is instantiated; no Redis configuration changes needed.

## Next Phase Readiness

- Atomic rate limiting is now in place for Phase 3 operational stability goals
- The `DistributedRateLimiter` class is ready for concurrent load without burst-above-limit risk
- No blockers for remaining Phase 3 plans

## Self-Check: PASSED

- FOUND: `.planning/phases/03-operational-stability/03-02-SUMMARY.md`
- FOUND: commit `40a41b5a` (Task 1 — Lua constant + register_script)
- FOUND: commit `210740ec` (Task 2 — replace pipeline with Lua in check_rate_limit)

---
*Phase: 03-operational-stability*
*Completed: 2026-02-22*
