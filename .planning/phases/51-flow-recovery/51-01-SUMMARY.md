---
phase: 51-flow-recovery
plan: 01
subsystem: flow
tags: [celery, redis, flow-recovery, awaiting-response]
requires:
  - phase: 50-pipeline-reliability
    provides: retry_failed_flow_send and day_advance verification markers used during recovery
provides:
  - bounded stuck-flow detection over awaiting_response flows
  - automatic recovery via prompt resend or day advancement
  - periodic Celery beat execution for stalled flow recovery
affects: [flow-recovery, celery-beat, operator-triage]
tech-stack:
  added: []
  patterns: [bounded auto-recovery, Redis idempotency guards, periodic stalled-flow sweeps]
key-files:
  created:
    - backend-hormonia/app/services/flow/recovery.py
    - backend-hormonia/app/tasks/flows/stuck_detection.py
  modified:
    - backend-hormonia/app/config/settings/tasks.py
    - backend-hormonia/app/tasks/flows/__init__.py
    - backend-hormonia/app/celery_app.py
    - backend-hormonia/tests/unit/services/flow/test_flow_recovery.py
    - backend-hormonia/tests/unit/tasks/test_stuck_detection.py
key-decisions:
  - "Used Redis idempotency keys plus a re-read of the flow state before acting so concurrent patient replies do not trigger duplicate recovery work."
  - "Classified max-attempt, already-recovering, and no-longer-stuck results as skipped outcomes in the detector summary instead of hard failures."
patterns-established:
  - "Stalled flow recovery is now a bounded periodic sweep: detect stale awaiting_response flows, attempt recovery once per beat window, escalate after repeated attempts."
  - "Flow recovery tasks use sync DB + Redis primitives inside Celery workers while delegating message resend and day advancement to existing flow services."
requirements-completed: [RECV-01, RECV-02]
duration: 15m
completed: 2026-03-06
---

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
