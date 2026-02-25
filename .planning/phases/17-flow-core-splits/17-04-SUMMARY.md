---
phase: 17-flow-core-splits
plan: 04
subsystem: testing
tags: [pytest, postgres, schema-guard, critical-api]

# Dependency graph
requires:
  - phase: 17-flow-core-splits
    provides: split-module baseline and deferred full-suite failure context from plans 17-01 to 17-03
provides:
  - Idempotent Postgres test-fixture schema guard for patients.messaging_stopped_at in root and critical test suites
  - Fresh phase-level full-suite regression evidence after schema sync attempt
  - Updated deferred blocker record with new first-failure node and error class
affects: [phase-17 verification closure, backend regression gating, critical API security tests]

# Tech tracking
tech-stack:
  added: []
  patterns: [fixture bootstrap schema guard, additive postgres ALTER TABLE patching, CI-visible schema patch logging]

key-files:
  created: []
  modified:
    - backend-hormonia/tests/conftest.py
    - backend-hormonia/tests/api/critical/conftest.py
    - .planning/phases/17-flow-core-splits/deferred-items.md

key-decisions:
  - "Apply non-destructive fixture-time Postgres schema patching (ALTER TABLE ... IF NOT EXISTS) instead of table rebuilds"
  - "Treat new AssertionError (422 vs 403) as the next deferred blocker after removing the original UndefinedColumn failure"

patterns-established:
  - "Regression Guardrails: critical-suite fixtures must enforce required additive schema columns before session yield"
  - "Deferred Handoff: when pytest -x still fails after blocker fix, log exact node + error class + UTC timestamp"

requirements-completed: [SPLIT-05, SPLIT-06, SPLIT-07]

# Metrics
duration: 5 min
completed: 2026-02-25
---

# Phase 17 Plan 04: Schema Guard Closure Summary

**Root and critical pytest fixtures now idempotently enforce `patients.messaging_stopped_at`, clearing the missing-column failure path and producing fresh full-suite blocker evidence for handoff.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25T17:29:04Z
- **Completed:** 2026-02-25T17:34:53Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added Postgres-only fixture guards in both test bootstrap paths to patch `patients.messaging_stopped_at` and index when missing.
- Confirmed the targeted critical security test no longer fails with `UndefinedColumn` and reaches assertion/authorization flow.
- Re-ran full `python3 -m pytest -x` and recorded the new first blocker (`AssertionError` 422 vs 403) in deferred notes with UTC timestamp.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add idempotent schema bootstrap guard for patients.messaging_stopped_at in test fixtures** - `332acc6f` (fix)
2. **Task 2: Re-run full backend gate and record closure of Phase 17 deferred blocker** - `29ff91d7` (docs)

## Files Created/Modified
- `backend-hormonia/tests/conftest.py` - adds session-level Postgres schema guard for `patients.messaging_stopped_at` and index patching.
- `backend-hormonia/tests/api/critical/conftest.py` - adds critical-suite Postgres schema guard before yielding test engine.
- `.planning/phases/17-flow-core-splits/deferred-items.md` - logs schema-blocker closure and new first regression blocker details.

## Decisions Made
- Enforced schema sync at fixture bootstrap using additive SQL patches to keep test setup non-destructive and idempotent.
- Preserved scope boundary by documenting the new full-suite failure rather than reopening Phase 17 split implementation work.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `python3 -m pytest -x` still fails at `tests/api/critical/test_patient_security_fixes.py::TestPatientSecurityFixes::test_idempotency_rbac_denies_other_doctor`, now with `AssertionError` (`422 != 403`) and logged `AsyncSession` query incompatibility in validation services.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 17 schema-sync blocker is advanced: `messaging_stopped_at` missing-column failure path is closed.
- Next owner can focus directly on the newly exposed authorization/validation behavior regression in the same critical test node.

---
*Phase: 17-flow-core-splits*
*Completed: 2026-02-25*

## Self-Check: PASSED

- FOUND: `.planning/phases/17-flow-core-splits/17-04-SUMMARY.md`
- FOUND: `332acc6f`
- FOUND: `29ff91d7`
