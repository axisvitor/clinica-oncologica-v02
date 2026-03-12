---
id: S02
parent: M001
milestone: M001
provides:
  - bounded stuck-flow detection over awaiting_response flows
  - automatic recovery via prompt resend or day advancement
  - periodic Celery beat execution for stalled flow recovery
  - admin flow reset endpoint for clearing waiting and mismatch state
  - admin flow advance endpoint for forcing the next flow day
  - admin flow unstick endpoint for clearing recovery counters
  - failed-flow operations query over persisted flow-state markers
requires: []
affects: []
key_files: []
key_decisions:
  - "Used Redis idempotency keys plus a re-read of the flow state before acting so concurrent patient replies do not trigger duplicate recovery work."
  - "Classified max-attempt, already-recovering, and no-longer-stuck results as skipped outcomes in the detector summary instead of hard failures."
  - "Used direct AsyncSession queries inside the router instead of FlowStateRepository to avoid sync-session/AsyncSession mismatches on admin endpoints."
  - "Surfaced failed flow operations from PatientFlowState.step_data markers instead of introducing a new persistence layer or DLQ subtype."
patterns_established:
  - "Stalled flow recovery is now a bounded periodic sweep: detect stale awaiting_response flows, attempt recovery once per beat window, escalate after repeated attempts."
  - "Flow recovery tasks use sync DB + Redis primitives inside Celery workers while delegating message resend and day advancement to existing flow services."
  - "Admin recovery endpoints follow the existing admin_extensions pattern: admin auth, rate limits, request context, and AuditService logging."
  - "Operator-visible flow failures are derived from persisted flow-state markers such as delivery_failures and last_mismatch_reset_at."
observability_surfaces: []
drill_down_paths: []
duration: 6 min
verification_result: passed
completed_at: 2026-03-06
blocker_discovered: false
---
# S02: Flow Recovery

**# Phase 51 Plan 01: Stuck Flow Recovery Summary**

## What Happened

# Phase 51 Plan 01: Stuck Flow Recovery Summary

**Stuck awaiting-response flows now get detected every 15 minutes and recovered through bounded resend/day-advance logic with Redis-backed idempotency**

## Performance

- **Duration:** 15m
- **Started:** 2026-03-06T18:40:18-03:00
- **Completed:** 2026-03-06T18:55:34-03:00
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added `app.services.flow.recovery` with stale-flow detection, recovery-action selection, bounded retry metadata, manual-escalation markers, and Redis idempotency protection.
- Added `detect_stuck_flows` as a periodic Celery task that batches recovery attempts, isolates per-flow failures, and reports recovered/skipped/failed counts.
- Wired the task into `app.tasks.flows` autodiscovery plus a 900-second beat schedule and covered both the service and the detector with focused unit tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create flow recovery service with detection and auto-recovery logic**
   - `a77a55d6` (`test`) RED: added failing tests for recovery service behavior
   - `64ee8db7` (`feat`) GREEN: implemented detection settings and recovery service logic
2. **Task 2: Create Celery Beat task for stuck flow detection and wire into schedule**
   - `e8682f4b` (`test`) RED: added failing tests for the detector batch summary and beat schedule
   - `5baf976d` (`feat`) GREEN: implemented the detector task, exports, and 15-minute beat entry

## Files Created/Modified

- `backend-hormonia/app/services/flow/recovery.py` - Detects stale awaiting-response flows and performs bounded resend/day-advance recovery.
- `backend-hormonia/app/tasks/flows/stuck_detection.py` - Executes periodic stalled-flow detection and aggregates recovery outcomes.
- `backend-hormonia/app/config/settings/tasks.py` - Adds configurable stuck-flow detection thresholds, attempt bounds, and Redis TTL.
- `backend-hormonia/app/tasks/flows/__init__.py` - Exports the detector task for Celery autodiscovery.
- `backend-hormonia/app/celery_app.py` - Schedules `detect-stuck-flows` every 900 seconds.
- `backend-hormonia/tests/unit/services/flow/test_flow_recovery.py` - Covers detection queries, action selection, idempotency, and recovery branches.
- `backend-hormonia/tests/unit/tasks/test_stuck_detection.py` - Covers batch summaries, skipped statuses, per-flow failure isolation, and beat registration.

## Decisions Made

- Reused the existing `retry_failed_flow_send` and day-advancement services instead of creating a new recovery transport, keeping auto-recovery aligned with the flow pipeline built in Phase 50.
- Counted bounded/manual-intervention outcomes as skipped rather than failed in the detector summary so operators can distinguish expected escalations from real task errors.

## Deviations from Plan

- The delegated executor stalled after creating the RED coverage for task 2, so the detector implementation and final verification were completed locally against the existing TDD baseline without changing scope.

## Issues Encountered

- The shell does not expose `python` on `PATH`, so verification used `./.venv/bin/python -m pytest ...` instead of `python -m pytest`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 51 now covers both automatic and manual recovery paths for stalled flows.
- Phase 52 can build observability and alerting on top of the new recovery markers and admin controls.

## Self-Check: PASSED

- Verified `backend-hormonia/tests/unit/services/flow/test_flow_recovery.py` passes.
- Verified `backend-hormonia/tests/unit/tasks/test_stuck_detection.py` passes.
- Verified commits `a77a55d6`, `64ee8db7`, `e8682f4b`, and `5baf976d` exist in git history.

---
*Phase: 51-flow-recovery*
*Completed: 2026-03-06*

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
