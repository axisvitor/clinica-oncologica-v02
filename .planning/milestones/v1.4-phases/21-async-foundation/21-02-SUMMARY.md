---
phase: 21-async-foundation
plan: 02
subsystem: infra
tags: [ci, celery, lint, sqlalchemy]

# Dependency graph
requires:
  - phase: 21-async-foundation
    provides: Plan 01 runtime async guard for non-async contexts
provides:
  - CI lint guard that blocks get_async_db and AsyncSession usage in app/tasks
  - Verified failure/pass behavior through synthetic task-file violations
affects: [phase-22, phase-23, celery, ci]

# Tech tracking
tech-stack:
  added: []
  patterns: [regex-based CI guard, docstring/comment skipping in static scans]

key-files:
  created: [backend-hormonia/scripts/check_async_isolation.py]
  modified: [backend-hormonia/scripts/check_async_isolation.py]

key-decisions:
  - "Guard targets get_async_db and AsyncSession while allowing get_async_session_factory usage in tasks"
  - "AsyncSession violations are enforced on import lines to avoid noisy false positives"

patterns-established:
  - "CI lint scripts for migration safety follow check_agent_run_calls structure"

requirements-completed: [FOUND-03]

# Metrics
duration: 3 min
completed: 2026-02-26
---

# Phase 21 Plan 02: Async Isolation Guard Summary

**Celery task isolation is now enforced by a CI lint script that blocks get_async_db and AsyncSession usage under app/tasks while keeping legitimate get_async_session_factory patterns allowed.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-26T23:14:43Z
- **Completed:** 2026-02-26T23:17:58Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Added `scripts/check_async_isolation.py` with the same scan structure as `scripts/check_agent_run_calls.py`.
- Implemented docstring/comment skipping, recursive `app/tasks/**/*.py` scanning, and violation output with path:line snippets.
- Verified clean baseline run exits `0`, and synthetic `get_async_db`/`AsyncSession` imports in task files exit `1`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create scripts/check_async_isolation.py CI lint guard** - `d6bb7354` (feat)
2. **Task 2: Verify CI guard catches violations with a synthetic test** - `d812b3ad` (fix)

## Files Created/Modified
- `backend-hormonia/scripts/check_async_isolation.py` - CI check for async DB isolation in Celery task code.

## Decisions Made
- Reused the existing CI lint pattern (`check_agent_run_calls.py`) for consistency and maintainability.
- Kept detection focused on `get_async_db` and `AsyncSession`, explicitly not flagging `get_async_session_factory`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- FOUND-03 now has both runtime and CI guardrails for Celery sync-session isolation.
- Ready for next Phase 21 plans that migrate DI/factories with this guard active.

## Self-Check: PASSED

- FOUND: `.planning/phases/21-async-foundation/21-02-SUMMARY.md`
- FOUND: `d6bb7354`
- FOUND: `d812b3ad`

---
*Phase: 21-async-foundation*
*Completed: 2026-02-26*
