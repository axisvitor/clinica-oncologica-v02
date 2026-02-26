---
phase: 17-flow-core-splits
plan: 12
subsystem: testing
tags: [pytest, postgres, audit-logs, flow-core-splits]

# Dependency graph
requires:
  - phase: 17-11
    provides: pagination stabilization and prior fail-fast evidence
provides:
  - audit log fixture uses constraint-compatible uppercase ADMIN category
  - updated fail-fast rerun evidence with closed audit_logs blocker and newly surfaced first failure
affects: [17-VERIFICATION, backend test-gates, v1.3 closure evidence]

# Tech tracking
tech-stack:
  added: []
  patterns: [test-fixture values must align with DB check constraints, fail-fast blocker handoff evidence]

key-files:
  created: [.planning/phases/17-flow-core-splits/17-12-SUMMARY.md]
  modified: [backend-hormonia/tests/api/v2/test_admin.py, .planning/phases/17-flow-core-splits/deferred-items.md]

key-decisions:
  - "Use uppercase ADMIN in the audit_logs fixture to match valid_event_category without altering migrations or production code."
  - "Record full fail-fast rerun as not green with explicit new blocker details instead of expanding 17-12 scope."

patterns-established:
  - "Constraint-compatible fixture data first: align test literals with canonical DB enum/check values."
  - "When fail-fast remains red, close prior blocker explicitly and hand off only the next distinct first failure."

requirements-completed: [SPLIT-05, SPLIT-06, SPLIT-07]

# Metrics
duration: 16 min
completed: 2026-02-26
---

# Phase 17 Plan 12: Audit Log Constraint Fixture Closure Summary

**Admin audit log fixture now uses `event_category="ADMIN"`, closing the `valid_event_category` blocker and producing fresh fail-fast rerun evidence with a newly surfaced DLQ foreign key gate.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-02-26T03:33:15Z
- **Completed:** 2026-02-26T03:50:06Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Updated `audit_logs` fixture in admin v2 tests from lowercase `admin` to uppercase `ADMIN` to satisfy the active check constraint.
- Verified split-contract regression gates remain intact (`9 passed`) and targeted admin audit logs test now passes (`1 passed`).
- Captured timestamped fail-fast rerun evidence showing prior audit_logs blocker closed and a new first blocker in admin extensions DLQ fixture setup.

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix audit_logs fixture event_category from lowercase "admin" to uppercase "ADMIN"** - `6bffff49` (fix)
2. **Task 2: Run full fail-fast suite and record Phase 17 closure evidence** - `9ae1552a` (fix)

## Files Created/Modified
- `backend-hormonia/tests/api/v2/test_admin.py` - Fixture literal updated to `event_category="ADMIN"` for constraint compatibility.
- `.planning/phases/17-flow-core-splits/deferred-items.md` - Added 2026-02-26 rerun section with three gate commands/results and new first-failure details.
- `.planning/phases/17-flow-core-splits/17-12-SUMMARY.md` - Plan execution summary and decision metadata.

## Decisions Made
- Kept the fix minimal and isolated to a single fixture literal change because the constraint guard already includes `ADMIN` and no schema change was required.
- Treated the new `whatsapp_delivery_failures_patient_id_fkey` failure as a distinct downstream blocker and documented it instead of broadening this plan.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Full fail-fast remained red at `tests/api/v2/test_admin_extensions.py::TestListDLQItems::test_list_dlq_items_basic` with `sqlalchemy.exc.IntegrityError` caused by `psycopg.errors.ForeignKeyViolation` (`whatsapp_delivery_failures_patient_id_fkey`). This was recorded as the new distinct blocker.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Audit logs `valid_event_category` blocker is closed with fresh evidence.
- Next action is to resolve the new DLQ fixture/patient FK blocker to achieve a fully green fail-fast gate for final Phase 17 verification truth closure.

---
*Phase: 17-flow-core-splits*
*Completed: 2026-02-26*

## Self-Check: PASSED

- FOUND: `.planning/phases/17-flow-core-splits/17-12-SUMMARY.md`
- FOUND: `6bffff49`
- FOUND: `9ae1552a`
