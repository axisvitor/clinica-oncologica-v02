# S02: Patient Ownership Boundary

**Goal:** Establish a reusable patient ownership boundary so authenticated Doctor A cannot read or mutate Doctor B's patient-bound messages, flow responses, or flow override schedules, while assigned-doctor and admin flows remain functional.
**Demo:** Doctor A cannot access Doctor B’s messages, free-text flow responses or flow override schedules; assigned doctor/admin access still passes.

## Must-Haves

- R003: Active `/api/v2/messages` routes that query or mutate patient-bound message data enforce admin-or-assigned-doctor scope before returning cached data, listing conversations, exposing unread/read state, sending, bulk-sending, marking read, or deleting/cancelling.
- R009: `/api/v2/patients/{patient_id}/flow-responses` and `/api/v2/patients/{patient_id}/flow-overrides` GET/PUT require admin or assigned doctor before response/override queries and before mutation.
- R010 support: A reusable two-doctor/two-patient negative authorization fixture pattern exists in focused API tests for reuse by S03/S05.
- R011 support: Ownership denials fail closed with generic 403/404 responses and structured diagnostics that contain IDs/reason only, never message content, response text, patient names, phones, tokens, or secrets.
- Focused and regression commands pass:
- `cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py -q`
- `cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py -q`
- `cd backend-hormonia && pytest tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py -q`
- `cd backend-hormonia && pytest tests/api/v2/test_phase25_messages_quiz_async.py -q`
- Threat Surface (Q3): parameter tampering with patient/message UUIDs, cached cross-user responses, read-state mutation, bulk-send IDs, and flow override PUT payloads can expose or alter PHI if ownership is not checked before DB/cache/service work.
- Requirement Impact (Q4): touches R003, R009, supports R010/R011; follows D002/D003 and new D008. Existing legitimate doctor-owned/admin message and patient flows must be re-verified.

## Proof Level

- This slice proves: Integration proof with real pytest/FastAPI TestClient route coverage plus helper unit tests. Runtime server and human/UAT are not required for this slice.

## Integration Closure

Consumes existing session dependencies, `User`/`Patient` models, active monolithic `app/api/v2/routers/messages.py`, and patient subrouters. Introduces shared patient access helpers in `app/api/v2/patients_shared_helpers.py` and focused negative authorization fixtures/tests. Leaves quiz session/link hardening to S03 and report/private-file ownership to S04/S05; S03/S05 should reuse the helper and fixture pattern produced here.

## Verification

- Centralized ownership checks should emit structured deny diagnostics with actor id, role, patient/resource id, and reason only. No PHI payloads, free-text responses, message content, patient names/phones, tokens, or secrets may be logged. Cache failures must remain non-critical but must never bypass ownership checks.

## Tasks

- [x] **T01: Add shared admin-or-assigned-doctor patient access helper** `est:1h`
  Expected executor skills (`skills_used`): `api-design`, `security-review`, `test`, `verify-before-complete`.
  - Files: `backend-hormonia/app/api/v2/patients_shared_helpers.py`, `backend-hormonia/app/utils/auth_helpers.py`, `backend-hormonia/app/models/patient.py`, `backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py`
  - Verify: cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py -q

- [ ] **T02: Scope message read/list/conversation routes by patient ownership** `est:2h`
  Expected executor skills (`skills_used`): `security-review`, `tdd`, `test`, `verify-before-complete`.
  - Files: `backend-hormonia/app/api/v2/routers/messages.py`, `backend-hormonia/app/api/v2/patients_shared_helpers.py`, `backend-hormonia/tests/api/v2/security_boundary_helpers.py`, `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py -q -k "message_read or conversation"

- [ ] **T03: Enforce message mutation and read-state ownership** `est:2h`
  Expected executor skills (`skills_used`): `security-review`, `tdd`, `test`, `verify-before-complete`.
  - Files: `backend-hormonia/app/api/v2/routers/messages.py`, `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`, `backend-hormonia/tests/api/v2/test_messages.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py -q -k "message_mutation or read_state or bulk or send_message"

- [ ] **T04: Protect flow responses and flow overrides with patient ownership** `est:2h`
  Expected executor skills (`skills_used`): `security-review`, `tdd`, `test`, `verify-before-complete`.
  - Files: `backend-hormonia/app/api/v2/routers/patients/flow_responses.py`, `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`, `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py -q

- [ ] **T05: Run S02 regression proof and close integration** `est:45m`
  Expected executor skills (`skills_used`): `test`, `security-review`, `verify-before-complete`.
  - Files: `backend-hormonia/app/api/v2/patients_shared_helpers.py`, `backend-hormonia/app/api/v2/routers/messages.py`, `backend-hormonia/app/api/v2/routers/patients/flow_responses.py`, `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`, `backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py`, `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`, `backend-hormonia/tests/api/v2/test_messages.py`, `backend-hormonia/tests/api/v2/test_patients_rbac_impl.py`, `backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py`
  - Verify: cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py -q

## Files Likely Touched

- backend-hormonia/app/api/v2/patients_shared_helpers.py
- backend-hormonia/app/utils/auth_helpers.py
- backend-hormonia/app/models/patient.py
- backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py
- backend-hormonia/app/api/v2/routers/messages.py
- backend-hormonia/tests/api/v2/security_boundary_helpers.py
- backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py
- backend-hormonia/tests/api/v2/test_messages.py
- backend-hormonia/app/api/v2/routers/patients/flow_responses.py
- backend-hormonia/app/api/v2/routers/patients/flow_overrides.py
- backend-hormonia/tests/api/v2/test_patients_rbac_impl.py
- backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py
