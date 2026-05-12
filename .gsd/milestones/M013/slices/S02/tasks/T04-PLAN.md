---
estimated_steps: 12
estimated_files: 3
skills_used: []
---

# T04: Protect flow responses and flow overrides with patient ownership

Expected executor skills (`skills_used`): `security-review`, `tdd`, `test`, `verify-before-complete`.

Why: Free-text flow responses and personalized flow override schedules are PHI-bearing patient resources. Current endpoints only prove doctor/admin role, then query arbitrary `patient_id`; this task wires them to the shared ownership helper.

Do:
1. In `backend-hormonia/app/api/v2/routers/patients/flow_responses.py`, replace the standalone patient-existence query with `await load_patient_with_access(db, patient_id, current_user)` before building any `PatientFlowResponse` query.
2. In `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`, call `await load_patient_with_access(db, patient_id, current_user)` before `_get_active_flow_state` in both GET and PUT so foreign doctors do not learn whether a foreign patient has an active flow state.
3. Fix PUT audit attribution by replacing `created_by=current_user.id` with a helper-derived UUID that works for dict session users and model users; fail closed if the authenticated user id cannot be resolved.
4. Extend `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py` with flow tests: Doctor A cannot GET Doctor B's flow responses and the free-text response string is absent; Doctor A cannot GET or PUT Doctor B's flow overrides; denied PUT does not delete/insert override rows; assigned doctor succeeds; admin succeeds. Use the two-doctor helper from T02 and minimal `PatientFlowResponse`/`PatientFlowState`/template fixtures.
5. Keep date filtering, active-state behavior, current-day validation, cache invalidation, and merged-day response shape unchanged for authorized callers.

Failure Modes (Q5): nonexistent patient -> 404 from helper; foreign patient -> 403 before response/flow-state queries; no active flow for authorized patient -> existing 404; invalid/missing `created_by` actor -> 403 before insert; cache delete failure remains warning only after owned mutation.

Load Profile (Q6): one indexed patient lookup before existing flow queries; no new unbounded scans. PUT still uses existing delete+insert transaction only after authorization succeeds.

Negative Tests (Q7): foreign flow response read, free-text non-disclosure, foreign override GET, foreign override PUT with row-count unchanged, dict-session created_by compatibility, assigned/admin positive paths.

Done when: full focused boundary test file passes and flow endpoints deny before disclosing free text or active-state details.

## Inputs

- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py`
- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`
- `backend-hormonia/app/models/patient_flow_response.py`
- `backend-hormonia/app/models/flow.py`
- `backend-hormonia/app/schemas/v2/patient_overrides.py`
- `backend-hormonia/tests/api/v2/security_boundary_helpers.py`
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py`
- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py -q

## Observability Impact

Flow denials are observable through the centralized structured ownership-denied log while free-text response bodies and override content stay out of logs.
