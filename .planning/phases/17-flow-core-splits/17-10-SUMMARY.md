---
phase: 17-flow-core-splits
plan: 10
subsystem: api
tags: [saga, patient-onboarding, sqlalchemy, pytest]
requires:
  - phase: 17-09
    provides: root get_async_db override and fail-fast baseline for saga payload blocker
provides:
  - Saga patient payload filter that only passes Patient model-supported kwargs
  - Preservation of schema-only clinical fields in metadata custom_fields.clinical_info
  - Fresh fail-fast rerun evidence proving saga payload mismatch blocker is closed
affects: [patient-onboarding, saga-orchestrator, phase-17-verification]
tech-stack:
  added: []
  patterns: [model-kwarg allowlist filtering, metadata custom_fields preservation]
key-files:
  created: [.planning/phases/17-flow-core-splits/17-10-SUMMARY.md]
  modified:
    - backend-hormonia/app/orchestration/saga_orchestrator/steps.py
    - .planning/phases/17-flow-core-splits/deferred-items.md
key-decisions:
  - "Use module-level _PATIENT_MODEL_FIELDS frozenset in saga step to filter constructor kwargs before Patient(**filtered_dict)."
  - "Store schema-only clinical extras in metadata custom_fields.clinical_info to satisfy JSONB schema validation while preserving data."
patterns-established:
  - "Saga payloads from Pydantic schemas must be filtered against model constructor contract before SQLAlchemy entity construction."
requirements-completed: [SPLIT-05, SPLIT-06, SPLIT-07]
duration: 17 min
completed: 2026-02-26
---

# Phase 17 Plan 10: Saga Payload Filter Summary

**Patient onboarding saga now filters schema-only clinical fields out of Patient constructor kwargs and preserves those fields in metadata custom_fields.clinical_info, removing the prior invalid-kwarg create failure.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-02-26T00:24:19Z
- **Completed:** 2026-02-26T00:41:37Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `_PATIENT_MODEL_FIELDS` allowlist in saga step module and switched patient creation to `Patient(**filtered_dict)`.
- Routed schema-only clinical fields into `metadata["custom_fields"]["clinical_info"]` so data is preserved without violating metadata schema constraints.
- Re-ran `python3 -m pytest -x --tb=short` and logged fresh evidence showing the saga payload/model mismatch blocker is closed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Filter saga patient_dict to valid Patient model fields and route clinical extras into metadata** - `cd1270a1` (fix)
2. **Task 2: Run full fail-fast suite and record final Phase 17 closure evidence** - `c630ccfa` (docs)

## Files Created/Modified
- `backend-hormonia/app/orchestration/saga_orchestrator/steps.py` - Added patient kwarg allowlist filter and clinical extras metadata routing.
- `.planning/phases/17-flow-core-splits/deferred-items.md` - Added timestamped fail-fast rerun evidence for post-fix state.

## Decisions Made
- Introduced a module-level allowlist (`_PATIENT_MODEL_FIELDS`) to enforce Patient constructor input compatibility in saga step 1.
- Preserved clinical fields under `custom_fields.clinical_info` (instead of root metadata) because root metadata schema rejects unknown top-level keys.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Prevented metadata schema validation failure from root clinical_info key**
- **Found during:** Task 1 (targeted patient create test rerun)
- **Issue:** Initial fix stored `clinical_info` at root metadata level, but JSONB schema has `additionalProperties: false`, causing `ValueError` during Patient creation.
- **Fix:** Stored clinical extras under `metadata["custom_fields"]["clinical_info"]` to preserve data within schema-allowed structure.
- **Files modified:** `backend-hormonia/app/orchestration/saga_orchestrator/steps.py`
- **Verification:** `python3 -m pytest tests/api/test_patients_endpoints.py::TestPatientCRUDEndpoints::test_create_patient_success -x --tb=short` passed.
- **Committed in:** `cd1270a1`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix was required for correctness and to keep the payload-filter strategy functional with existing metadata validation constraints.

## Issues Encountered
- Full fail-fast gate remains red at a new node: `tests/api/test_patients_endpoints.py::TestPatientCRUDEndpoints::test_list_patients_pagination` (`AssertionError: assert 4 >= 5`), documented as a distinct blocker from the now-closed saga payload mismatch.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Saga payload/model mismatch blocker is closed with fresh evidence.
- Remaining work should address patient list pagination expectation mismatch to reach full green fail-fast.

## Self-Check
PASSED

---
*Phase: 17-flow-core-splits*
*Completed: 2026-02-26*
