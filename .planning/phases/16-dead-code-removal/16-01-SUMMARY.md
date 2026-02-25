---
phase: 16-dead-code-removal
plan: 01
subsystem: api
tags: [dead-code, tombstone, flow]
requires:
  - phase: 15-data-integrity-fixes
    provides: canonical flow constants and cycle helpers
provides:
  - Tombstoned sentinels for `app.services.flow.constants` and `app.services.flow.template_lookup`
  - Verified zero production imports referencing both tombstoned modules
affects: [phase-16, phase-17, flow-services]
tech-stack:
  added: []
  patterns: [ImportError tombstone sentinel, migration-hint messaging]
key-files:
  created:
    - .planning/phases/16-dead-code-removal/deferred-items.md
  modified:
    - backend-hormonia/app/services/flow/constants.py
    - backend-hormonia/app/services/flow/template_lookup.py
key-decisions:
  - "Use Phase 12 tombstone sentinel pattern verbatim for dead flow modules"
  - "Keep out-of-scope package import blocker deferred instead of broadening plan scope"
patterns-established:
  - "Tombstoned modules raise immediate ImportError with explicit migration target"
requirements-completed: [DEAD-01, DEAD-02]
duration: 22 min
completed: 2026-02-24
---

# Phase 16 Plan 01: Dead Code Tombstones Summary

**Flow constants/template lookup dead paths now fail fast with explicit tombstone ImportError guidance to canonical modules.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-02-24T22:54:00Z
- **Completed:** 2026-02-24T23:16:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Replaced `app/services/flow/constants.py` with a tombstone sentinel pointing to `app.agents.patient.flow_coordinator.constants`
- Replaced `app/services/flow/template_lookup.py` with a tombstone sentinel describing local replacement guidance
- Verified no production import statements reference either tombstoned module in `backend-hormonia/app/`

## Task Commits

Each task was committed atomically:

1. **Task 1: Tombstone flow/constants.py and flow/template_lookup.py** - `c5dcc45e` (refactor)
2. **Task 2: Verify no production imports remain for tombstoned files** - `7e9f2a24` (chore)

## Files Created/Modified
- `.planning/phases/16-dead-code-removal/deferred-items.md` - Logs out-of-scope pre-existing blocker found during verification
- `backend-hormonia/app/services/flow/constants.py` - Tombstone sentinel with migration hint to canonical constants module
- `backend-hormonia/app/services/flow/template_lookup.py` - Tombstone sentinel for removed helper

## Decisions Made
- Kept tombstone messaging consistent with prior sentinel style from `app/ai/langgraph/__init__.py` for discoverability
- Logged unrelated package-level import interception as deferred instead of widening this plan's scope

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Python executable mismatch in verification environment**
- **Found during:** Task 1 (tombstone verification)
- **Issue:** `python` command is unavailable in this environment
- **Fix:** Switched verification commands to `python3`
- **Files modified:** None
- **Verification:** Both module sentinel checks pass with expected ImportError assertions
- **Committed in:** `c5dcc45e` (task commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep; fix was environment-only and required for task verification.

## Issues Encountered
- Pre-existing `app.services.flow.__init__` import chain currently raises from tombstoned `.analytics` before submodule import resolution; documented in `.planning/phases/16-dead-code-removal/deferred-items.md` and kept out of scope.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 16-01 goals achieved and verified for DEAD-01/DEAD-02 tombstones.
- Ready for `16-02-PLAN.md` tombstoning remaining dead flow package modules.

---
*Phase: 16-dead-code-removal*
*Completed: 2026-02-24*

## Self-Check: PASSED

- FOUND: `.planning/phases/16-dead-code-removal/16-01-SUMMARY.md`
- FOUND: `.planning/phases/16-dead-code-removal/deferred-items.md`
- FOUND: `c5dcc45e`
- FOUND: `7e9f2a24`
