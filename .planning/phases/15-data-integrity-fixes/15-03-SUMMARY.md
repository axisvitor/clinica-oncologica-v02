---
phase: 15-data-integrity-fixes
plan: 03
subsystem: messaging
tags: [celery, dlq, retry, whatsapp, integrity]
requires:
  - phase: 14-flow-control-fixes
    provides: stable pause/resume/cancel flow lifecycle before integrity hardening
provides:
  - DLQ routing for scheduled-message final failures and deterministic non-retriable failures
  - SQL-backed DLQ retry processing task wired into Celery Beat
  - Unit coverage for DLQ routing behavior and flow retry config values
affects: [flow-monitoring, messaging-reliability, phase-16-cleanup]
tech-stack:
  added: []
  patterns: [non-fatal DLQ write path, explicit DLQ context payload for failed flow messages]
key-files:
  created: [backend-hormonia/tests/unit/tasks/test_messaging_dlq_wiring.py]
  modified:
    [
      backend-hormonia/app/tasks/messaging.py,
      backend-hormonia/app/services/dlq/base.py,
      backend-hormonia/app/celery_app.py,
    ]
key-decisions:
  - "Use existing FailureReason enum values (MAX_RETRIES_EXCEEDED/UNKNOWN) to avoid DB enum drift."
  - "Keep DLQ routing non-fatal so delivery-task failure reporting still returns predictable error results."
patterns-established:
  - "Task failure path now persists retry context and flow_context into DLQ payload."
  - "DLQ scheduled retry processing is handled by dedicated Celery beat entry every 5 minutes."
requirements-completed: [FIX-07]
duration: 7 min
completed: 2026-02-24
---

# Phase 15 Plan 03: DLQ Wiring Summary

**Scheduled flow-message delivery failures now land in the SQL-backed DLQ with flow context and are processed by automated retry scheduling.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-24T23:49:00Z
- **Completed:** 2026-02-24T23:55:48Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added DLQ routing in `send_scheduled_message` for both final retry exhaustion and deterministic non-retriable failures.
- Added `FlowMessageRetryConfig` with the requested 30s/120s/600s policy constants for flow-message retries.
- Added `process_dlq_messages` Celery task and beat schedule wiring for periodic SQL-DLQ retry processing.
- Added six unit tests validating DLQ routing behavior, non-fatal DLQ write failures, retry policy values, and payload flow context.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire send_scheduled_message final failure path to DLQ** - `66c1b208` (feat)
2. **Task 2: Add unit tests for messaging DLQ wiring** - `74a5f1d4` (test)

**Plan metadata:** Pending

## Files Created/Modified
- `backend-hormonia/app/tasks/messaging.py` - DLQ routing in failure paths plus scheduled DLQ retry task.
- `backend-hormonia/app/services/dlq/base.py` - flow-message retry policy class with 3-step backoff values.
- `backend-hormonia/app/celery_app.py` - beat schedule entry for `process_dlq_messages` every 5 minutes.
- `backend-hormonia/tests/unit/tasks/test_messaging_dlq_wiring.py` - six focused unit tests for DLQ wiring behavior.

## Decisions Made
- Reused existing `FailureReason` values to avoid introducing new enum values without schema migration.
- Treated DLQ write failure as non-fatal so task callers still receive deterministic error responses.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adjusted failure reason constants to existing enum set**
- **Found during:** Task 1 (DLQ routing implementation)
- **Issue:** Plan example referenced `FailureReason.DELIVERY_FAILED` and `FailureReason.PERMANENT_ERROR`, which do not exist in current model enum.
- **Fix:** Mapped final-exhaustion failures to `FailureReason.MAX_RETRIES_EXCEEDED` and non-retriable failures to `FailureReason.UNKNOWN` with explicit payload context.
- **Files modified:** `backend-hormonia/app/tasks/messaging.py`
- **Verification:** `python3 -m pytest tests/unit/tasks/test_messaging_dlq_wiring.py -x -v`
- **Committed in:** `66c1b208`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Change preserves plan behavior while remaining schema-compatible with the existing DLQ enum.

## Authentication Gates

None.

## Issues Encountered

- Initial `git commit` attempt hit transient `.git/index.lock` contention; retry succeeded without data loss.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- FIX-07 implementation is complete for this plan; flow message failures are now visible and operable via DLQ paths.
- Phase 15 has earlier plans still open in this repository state, but Plan 15-03 is ready for transition.

## Self-Check: PASSED
- FOUND: `.planning/phases/15-data-integrity-fixes/15-03-SUMMARY.md`
- FOUND: `66c1b208`
- FOUND: `74a5f1d4`

---
*Phase: 15-data-integrity-fixes*
*Completed: 2026-02-24*
