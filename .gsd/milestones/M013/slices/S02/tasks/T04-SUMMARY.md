---
id: T04
parent: S02
milestone: M013
key_files:
  - backend-hormonia/app/api/v2/routers/patients/flow_responses.py
  - backend-hormonia/app/api/v2/routers/patients/flow_overrides.py
  - backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py
key_decisions:
  - Flow response and override routes now rely on the centralized `load_patient_with_access` helper before patient-bound queries to preserve the shared ID-only deny diagnostics and fail-closed ownership semantics.
  - Flow override PUT audit attribution resolves the actor UUID via shared auth utilities instead of direct `.id` access so dict-backed session users are compatible and malformed actors fail closed.
duration: 
verification_result: passed
completed_at: 2026-05-12T19:35:14.453Z
blocker_discovered: false
---

# T04: Protected patient flow responses and flow override schedules with the shared patient ownership boundary and UUID-safe override audit attribution.

**Protected patient flow responses and flow override schedules with the shared patient ownership boundary and UUID-safe override audit attribution.**

## What Happened

Wired `flow_responses.py` to call `load_patient_with_access` before constructing any `PatientFlowResponse` query, replacing the prior patient-existence-only lookup. Wired both GET and PUT flow override routes to call `load_patient_with_access` before active-flow-state lookup so foreign doctors receive the shared 403 boundary result before flow-state or override details can be inferred. Added UUID-safe PUT audit attribution through `get_user_uuid(current_user)`, which supports dict-backed session users and model users and fails closed with 403 if no actor UUID is resolvable. Extended the patient ownership boundary API tests with minimal flow response/state/template/override fixtures covering foreign flow-response read denial with free-text non-disclosure, foreign override GET denial, foreign override PUT denial without row mutation, assigned-doctor success including dict-session `created_by`, and admin read access.

## Verification

Ran the task verification from inside `backend-hormonia`: `pytest tests/api/v2/test_patient_ownership_boundary.py -q` passed with 18 tests. Also reran the verification gate command that previously failed from the repository root using the corrected working directory: `pytest tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py -q -k "message_mutation or read_state or bulk or send_message"` passed with 9 selected tests and 1 expected skip.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py -q` | 0 | ✅ pass | 25916ms |
| 2 | `cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py -q -k "message_mutation or read_state or bulk or send_message"` | 0 | ✅ pass | 25864ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py`
- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`
