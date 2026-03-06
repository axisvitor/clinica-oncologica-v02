---
phase: 51-flow-recovery
plan: 02
subsystem: api
tags: [fastapi, sqlalchemy, admin, flow-recovery]
requires:
  - phase: 50-pipeline-reliability
    provides: delivery failure and mismatch reset markers persisted in PatientFlowState.step_data
  - phase: 51-flow-recovery
    provides: recovery attempt markers that the unstick endpoint clears when operators intervene
provides:
  - admin flow reset endpoint for clearing waiting and mismatch state
  - admin flow advance endpoint for forcing the next flow day
  - admin flow unstick endpoint for clearing recovery counters
  - failed-flow operations query over persisted flow-state markers
affects: [admin-extensions, flow-recovery, operator-triage]
tech-stack:
  added: []
  patterns: [async admin router queries, audit-logged flow recovery operations, flow failure visibility via step_data markers]
key-files:
  created:
    - backend-hormonia/app/api/v2/routers/admin_extensions/flow_ops.py
  modified:
    - backend-hormonia/app/api/v2/routers/admin_extensions/__init__.py
    - backend-hormonia/app/schemas/v2/admin_extensions.py
    - backend-hormonia/tests/unit/api/test_admin_flow_ops.py
key-decisions:
  - "Used direct AsyncSession queries inside the router instead of FlowStateRepository to avoid sync-session/AsyncSession mismatches on admin endpoints."
  - "Surfaced failed flow operations from PatientFlowState.step_data markers instead of introducing a new persistence layer or DLQ subtype."
patterns-established:
  - "Admin recovery endpoints follow the existing admin_extensions pattern: admin auth, rate limits, request context, and AuditService logging."
  - "Operator-visible flow failures are derived from persisted flow-state markers such as delivery_failures and last_mismatch_reset_at."
requirements-completed: [RECV-03, RECV-04]
duration: 6 min
completed: 2026-03-06
---

# Phase 51 Plan 02: Admin Flow Ops Summary

**Admin flow reset, advance, and unstick endpoints with failed-flow visibility over persisted step_data recovery markers**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-06T21:39:12Z
- **Completed:** 2026-03-06T21:45:34Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments
- Added a dedicated `flow_ops` admin router with `reset`, `advance`, `unstick`, and `failed` endpoints under `/admin-ext/flow-ops`.
- Added Flow Ops response schemas so the new admin endpoints have explicit contracts in the v2 schema module.
- Covered the router registration, mutating endpoint audit logging, and failed-ops pagination/mapping with unit tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create admin flow ops router with reset, advance, unstick, and failed-ops endpoints**
   - `9b4edf19` (`test`) RED: added failing admin flow ops tests
   - `a3e455e8` (`feat`) GREEN: added the `flow_ops.py` router implementation
   - `039dd49e` (`feat`) GREEN: wired schemas, router registration, and green-path test expectations

## Files Created/Modified
- `backend-hormonia/app/api/v2/routers/admin_extensions/flow_ops.py` - Async admin flow recovery endpoints and failed-op query mapping.
- `backend-hormonia/app/api/v2/routers/admin_extensions/__init__.py` - Registers the new flow ops router under `/flow-ops`.
- `backend-hormonia/app/schemas/v2/admin_extensions.py` - Adds reset/advance/unstick and failed-flow response models.
- `backend-hormonia/tests/unit/api/test_admin_flow_ops.py` - TDD coverage for reset/advance/unstick behaviors, failed-op visibility, pagination, and audit logging.

## Decisions Made
- Kept the admin flow endpoints async-native and queried `PatientFlowState` directly with `AsyncSession` so the router matches the project’s API-side async database contract.
- Implemented failed-flow visibility as a read over `step_data` markers already written by prior flow reliability work, which keeps this plan migration-free and aligned with the research guidance.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- The shell does not expose `python` on `PATH`, so verification used `./.venv/bin/python -m pytest ...` instead of `python -m pytest`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan `51-02` is complete and the admin flow recovery surface is ready for operator use.
- Phase 51 still needs the separate `51-01` summary path to finish before the phase can be closed as complete.

## Self-Check: PASSED
- Found `.planning/phases/51-flow-recovery/51-02-SUMMARY.md`
- Found commit `9b4edf19`
- Found commit `a3e455e8`
- Found commit `039dd49e`

---
*Phase: 51-flow-recovery*
*Completed: 2026-03-06*
