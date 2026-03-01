---
phase: 14-flow-control-fixes
plan: 02
subsystem: api
tags: [python, celery, flow-control, scheduling, pytest]
requires:
  - phase: 14-01
    provides: state_data.paused pause contract used by FlowManagement resume path
provides:
  - Auto-resume only triggers for paused flows with expired state_data.auto_resume_at
  - Hourly Celery Beat schedule for responsive timestamp-based auto-resume checks
  - Unit coverage for expired/future/indefinite/conflict auto-resume behavior
affects: [phase-14-plan-03, flow-automation, pause-resume]
tech-stack:
  added: []
  patterns: ["timestamp-gated auto-resume", "FlowManagementService resume path in Celery automation"]
key-files:
  created:
    - backend-hormonia/tests/unit/tasks/test_auto_resume_flows.py
  modified:
    - backend-hormonia/app/tasks/flow_automation.py
    - backend-hormonia/app/celery_app.py
key-decisions:
  - "Auto-resume query now requires state_data.auto_resume_at and expired timestamp instead of updated_at age"
  - "resume_paused_flows uses FlowManagementService.resume_patient_flow to keep state_data pause semantics consistent"
patterns-established:
  - "Celery auto-resume jobs should guard on explicit auto_resume_at and handle already-resumed conflicts without failing batch"
requirements-completed: [FIX-02]
duration: 1 min
completed: 2026-02-24
---

# Phase 14 Plan 02: Auto-Resume Timestamp Gating Summary

**Paused flows now auto-resume strictly from expired `state_data.auto_resume_at` timestamps, with hourly beat checks and conflict-safe resume handling via `FlowManagementService`.**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-24T19:42:21-03:00
- **Completed:** 2026-02-24T22:43:55Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Replaced blanket 48-hour pause heuristic with explicit `auto_resume_at` timestamp filtering in `resume_paused_flows`
- Switched resume execution to `FlowManagementService.resume_patient_flow(patient_id=...)` to preserve `state_data.paused` contract from Plan 01
- Added structured audit logs for successful auto-resume and warning logs for already-resumed conflicts
- Updated `resume-paused-flows` Celery Beat interval from 6 hours to 1 hour with descriptive scheduling comment
- Added four focused unit tests for expired, future, indefinite, and conflict auto-resume paths

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite resume_paused_flows to check auto_resume_at timestamps** - `81e888a8` (fix)
2. **Task 2: Add unit tests for auto-resume logic** - `5fba2001` (test)

## Files Created/Modified
- `backend-hormonia/app/tasks/flow_automation.py` - Rewrote paused-flow query and resume loop around `auto_resume_at` with conflict-safe handling
- `backend-hormonia/app/celery_app.py` - Changed `resume-paused-flows` beat schedule to hourly
- `backend-hormonia/tests/unit/tasks/test_auto_resume_flows.py` - Added four unit tests for auto-resume contract

## Decisions Made
- Enforced explicit auto-resume intent by requiring non-null, expired `state_data.auto_resume_at` in the task query.
- Standardized auto-resume execution on `FlowManagementService` to avoid the legacy flow-engine path that bypasses `state_data` semantics.

## Deviations from Plan

None - plan executed exactly as written.

## Authentication Gates

None.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 14 Plan 02 scope is complete and verified.
- Ready for `14-03-PLAN.md`.

---
*Phase: 14-flow-control-fixes*
*Completed: 2026-02-24*

## Self-Check: PASSED
