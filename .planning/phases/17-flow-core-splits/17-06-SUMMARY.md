---
phase: 17-flow-core-splits
plan: 06
subsystem: api
tags: [fastapi, pydantic, patient-schema, pytest]

requires:
  - phase: 17-05
    provides: async-session idempotency bridge and refreshed full-suite baseline
provides:
  - PatientV2Response tolerates persisted free-form treatment_phase values
  - Input schemas and treatment constants now include onboarding phase
  - Phase-17 blocker shifted from patients list validation to unrelated notifications schema
affects: [patient-listing, response-validation, onboarding-flow, phase-17-verification]

tech-stack:
  added: []
  patterns:
    - Keep strict treatment_phase regex on input models, lenient treatment_phase on response models
    - Track unrelated first-failure results in deferred-items.md when running full suite fail-fast

key-files:
  created: []
  modified:
    - backend-hormonia/app/schemas/v2/patient.py
    - backend-hormonia/app/schemas/patient.py
    - backend-hormonia/app/config/constants.py
    - .planning/phases/17-flow-core-splits/deferred-items.md

key-decisions:
  - "Override PatientV2Response.treatment_phase without regex while preserving regex constraints in input schemas"
  - "Treat unsupported pytest --timeout flag as an execution-environment blocker and rerun with supported fail-fast flags"

patterns-established:
  - "Response-vs-input split: persisted legacy/free-form values must not break API response validation"
  - "Out-of-scope full-suite first failures are logged as deferred blockers, not fixed in this plan"

requirements-completed: [SPLIT-05, SPLIT-06, SPLIT-07]

duration: 14 min
completed: 2026-02-25
---

# Phase 17 Plan 06: Treatment Phase Response Gap Closure Summary

**Patient list response serialization now accepts persisted onboarding/free-form treatment_phase values while input validation remains constrained and aligned with onboarding constants.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-02-25T19:23:30Z
- **Completed:** 2026-02-25T19:38:52Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Removed response-model pattern strictness for `PatientV2Response.treatment_phase` to prevent `ResponseValidationError` on persisted values.
- Added `onboarding` to v2/domain treatment_phase input regexes and `TreatmentPhase.ALL_PHASES` filter constants.
- Verified the critical failing endpoint test now passes (`test_list_patients_empty_or_existing`), and documented the new unrelated full-suite first failure.

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix treatment_phase response schema and input patterns** - `51d243b8` (fix)
2. **Task 2: Run full test suite fail-fast and capture green evidence** - `b03bccae` (chore)

**Plan metadata:** pending

## Files Created/Modified
- `backend-hormonia/app/schemas/v2/patient.py` - Added onboarding to input regexes and overrode response `treatment_phase` to lenient string field.
- `backend-hormonia/app/schemas/patient.py` - Added onboarding to domain create/update treatment_phase regex constraints.
- `backend-hormonia/app/config/constants.py` - Added `TreatmentPhase.ONBOARDING` and included it in `ALL_PHASES`.
- `.planning/phases/17-flow-core-splits/deferred-items.md` - Logged new unrelated full-suite notifications schema blocker.

## Decisions Made
- Kept strict regex validation for create/update schemas and made response schema tolerant of persisted database reality.
- Considered `--timeout` unsupported in this environment and reran fail-fast verification with supported pytest flags.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed unsupported pytest timeout flag from execution commands**
- **Found during:** Task 2 (full-suite fail-fast run)
- **Issue:** `python3 -m pytest ... --timeout=120` failed immediately because this environment's pytest setup does not accept `--timeout`.
- **Fix:** Re-ran verification using `python3 -m pytest -x --tb=short` and re-ran the critical target test with `-x --tb=short`.
- **Files modified:** None (execution command adjustment only)
- **Verification:** Full suite executed fail-fast and produced actionable first failure output; critical patient list test passed.
- **Committed in:** `b03bccae` (task evidence commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep; deviation was required to execute verification commands successfully in this runtime.

## Authentication Gates

None.

## Issues Encountered
- Full fail-fast suite did not go fully green: first failure moved to `tests/api/test_api_contract_fixes.py::TestNotificationsStructureFix::test_notifications_structure` with missing DB column `notifications.notification_type` (tracked in deferred items as out-of-scope for this plan).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 17 plan objective completed: patient list response no longer fails on `treatment_phase='onboarding'` and filter constants align.
- Remaining blocker for global suite is now outside this plan scope (notifications schema contract), documented for follow-up.

## Self-Check: PASSED

---
*Phase: 17-flow-core-splits*
*Completed: 2026-02-25*
