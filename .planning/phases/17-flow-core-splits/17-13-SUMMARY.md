---
phase: 17-flow-core-splits
plan: 13
subsystem: testing
tags: [pytest, dlq, fixtures, postgres, foreign-key]

requires:
  - phase: 17-flow-core-splits
    provides: Flow split contracts and prior fail-fast blocker history through 17-12
provides:
  - DLQ admin extension fixtures now insert FailedMessage rows with FK-safe patient references
  - Fresh fail-fast rerun evidence documenting DLQ blocker closure and the next distinct blocker
affects: [phase-17-verification, backend-test-fixtures, fail-fast-gate]

tech-stack:
  added: []
  patterns: [Fixture-created child rows must reference real parent rows for FK integrity]

key-files:
  created: [.planning/phases/17-flow-core-splits/17-13-SUMMARY.md]
  modified:
    - backend-hormonia/tests/api/v2/test_admin_extensions.py
    - .planning/phases/17-flow-core-splits/deferred-items.md

key-decisions:
  - "Create a dedicated test_patient fixture and wire DLQ fixtures/tests to test_patient.id rather than random UUIDs."
  - "Treat the alerts UndefinedColumn failure as a new distinct fail-fast blocker and log it in deferred-items instead of expanding 17-13 scope."

patterns-established:
  - "FK-safe test fixtures: create and persist required parent rows before child inserts."
  - "Fail-fast closure tracking: each plan records closed blocker and newly exposed first failure."

requirements-completed: [SPLIT-05, SPLIT-06, SPLIT-07]
duration: 27 min
completed: 2026-02-26
---

# Phase 17 Plan 13: Flow Core Splits Summary

**DLQ admin extension fixtures now use a real Patient FK anchor, removing the whatsapp_delivery_failures FK violation and advancing fail-fast to the next unrelated alerts schema blocker.**

## Performance

- **Duration:** 27 min
- **Started:** 2026-02-26T04:17:53Z
- **Completed:** 2026-02-26T04:45:34Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `test_patient` fixture in admin extensions API tests and bound it to `admin_user.id` for a valid parent row.
- Rewired both `dlq_items` and `test_purge_dlq_items_actual` to use `test_patient.id`, eliminating random-UUID FK violations.
- Re-ran split contracts, targeted DLQ gate, and full fail-fast; recorded DLQ blocker closure and new first failing node evidence in deferred tracking.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add test_patient fixture and wire DLQ fixtures to use real patient_id** - `f715f865` (fix)
2. **Task 2: Run full fail-fast suite and record Phase 17 closure evidence** - `655c956c` (docs)

## Files Created/Modified
- `backend-hormonia/tests/api/v2/test_admin_extensions.py` - adds `test_patient` fixture and replaces DLQ `patient_id=uuid4()` references with `test_patient.id`.
- `.planning/phases/17-flow-core-splits/deferred-items.md` - appends timestamped 17-13 gate results, marks DLQ FK blocker closed, and records new alerts schema blocker.
- `.planning/phases/17-flow-core-splits/17-13-SUMMARY.md` - captures execution outcomes, decisions, and verification status for plan 17-13.

## Decisions Made
- Introduced a local `Patient` import only inside the new test fixture to keep production imports untouched and scope changes to test setup.
- Preserved plan scope by logging the newly surfaced `alerts.type` schema mismatch as a deferred blocker instead of editing unrelated alert fixtures/models.

## Deviations from Plan

None - plan tasks executed as written; full fail-fast rerun exposed a new distinct blocker and was documented per plan instructions.

## Issues Encountered
- `python3 -m pytest -x --tb=short` is not fully green yet; first failure is `tests/api/v2/test_alerts.py::TestListAlerts::test_list_alerts_basic` with `sqlalchemy.exc.ProgrammingError` (`psycopg.errors.UndefinedColumn: alerts.type`).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- DLQ patient FK blocker is closed and evidenced for verifier review.
- Phase 17 truth #13 remains blocked by the new alerts schema mismatch; next plan should address `alerts.type` test/runtime contract alignment.

---
*Phase: 17-flow-core-splits*
*Completed: 2026-02-26*

## Self-Check: PASSED

- FOUND: `.planning/phases/17-flow-core-splits/17-13-SUMMARY.md`
- FOUND: `f715f865`
- FOUND: `655c956c`
