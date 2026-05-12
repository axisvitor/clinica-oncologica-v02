---
estimated_steps: 12
estimated_files: 4
skills_used: []
---

# T01: Add shared admin-or-assigned-doctor patient access helper

Expected executor skills (`skills_used`): `api-design`, `security-review`, `test`, `verify-before-complete`.

Why: S02 needs one reusable authorization seam for messages, flow responses, flow overrides, and later S03/S05 work. The helper must handle both mapping-style session users and `User` model instances so endpoint code does not keep reimplementing brittle ownership checks.

Do:
1. Extend `backend-hormonia/app/api/v2/patients_shared_helpers.py` with shared helpers such as `assert_admin_or_assigned_doctor(current_user, patient_doctor_id, patient_id=None)`, `async load_patient_with_access(db, patient_id, current_user)`, and a small role/user extraction helper if needed.
2. Internally use `app.utils.auth_helpers.extract_user_role_and_uuid`/`get_user_uuid` instead of ad hoc `current_user.id`; admin passes, doctor passes only when `Patient.doctor_id == current_user_uuid`, all ambiguous/missing/malformed contexts fail closed with 403.
3. Return 404 only for nonexistent patients; return generic 403 for known foreign/unassigned patients per D008. Do not include PHI in error details.
4. Add structured deny logging in the helper using IDs/reason only; do not log patient name, phone, diagnosis, message content, response text, tokens, or secrets.
5. Add unit tests in `backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py` covering dict user, `User` model user, admin pass, assigned doctor pass, foreign doctor 403, missing/invalid user id 403, unassigned patient 403 for doctors, and not-found 404.

Failure Modes (Q5): DB lookup returns no patient -> 404; malformed user context -> 403; missing patient doctor for doctor user -> 403; logging failure must not change authorization outcome.

Load Profile (Q6): one indexed `Patient.id` lookup per patient-scoped endpoint and constant-time role comparison; no per-message Python filtering or N+1 behavior should be introduced.

Negative Tests (Q7): foreign doctor, malformed session dict, model-vs-dict role variants, admin override, nonexistent patient, unassigned patient.

Done when: helper unit tests pass and the helper is importable by routers without circular imports.

## Inputs

- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/app/utils/auth_helpers.py`
- `backend-hormonia/app/models/patient.py`
- `backend-hormonia/app/models/user.py`
- `backend-hormonia/tests/conftest.py`

## Expected Output

- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py`

## Verification

cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py -q

## Observability Impact

Adds the single deny-log location for patient ownership failures. Future agents can inspect unit tests and logs for denial reason fields while PHI remains redacted.
