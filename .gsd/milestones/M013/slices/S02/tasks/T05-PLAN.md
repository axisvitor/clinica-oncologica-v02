---
estimated_steps: 12
estimated_files: 9
skills_used: []
---

# T05: Run S02 regression proof and close integration

Expected executor skills (`skills_used`): `test`, `security-review`, `verify-before-complete`.

Why: S02 changes shared authorization and active API routers. The slice is only done when focused negative proof and relevant regression suites pass together, preserving legitimate assigned-doctor/admin behavior.

Do:
1. Run the helper unit tests and full focused ownership boundary tests.
2. Run the message and patient RBAC regression suites, then the message/quiz async regression named in research because the active monolithic message router was touched.
3. If a regression reveals the new ownership checks broke a legitimate assigned-doctor or admin path, adjust only the helper/router/test fixture needed to preserve that legitimate path; do not weaken foreign-doctor denial.
4. Check the focused tests do not read `.gsd/`, `.planning/`, `.audits/`, or other gitignored planning artifacts.
5. Confirm denial details/log assertions remain generic and do not include PHI fields such as message content, flow response text, patient name/phone, quiz tokens, or secrets.

Failure Modes (Q5): failing regression -> fix before completion; flaky cache/test isolation -> clear dependency overrides in tests and keep cache failures non-authorizing; database fixture failures -> repair fixture setup, not production ownership semantics.

Load Profile (Q6): regression should not introduce unbounded message/patient scans; query scoping remains SQL-side.

Negative Tests (Q7): all foreign doctor denials from T02-T04 plus existing RBAC tests must pass in one run.

Done when: every verification command exits 0 and S02 has executable evidence for R003/R009 and reusable fixture evidence for R010/R011.

## Inputs

- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/app/api/v2/routers/messages.py`
- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py`
- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`
- `backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py`
- `backend-hormonia/tests/api/v2/security_boundary_helpers.py`
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`
- `backend-hormonia/tests/api/v2/test_messages.py`
- `backend-hormonia/tests/api/v2/test_patients_rbac_impl.py`
- `backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py`

## Expected Output

- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/app/api/v2/routers/messages.py`
- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py`
- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`
- `backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py`
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`
- `backend-hormonia/tests/api/v2/test_messages.py`
- `backend-hormonia/tests/api/v2/test_patients_rbac_impl.py`
- `backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py`

## Verification

cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py -q

## Observability Impact

Produces no new runtime code; confirms the observability/redaction contract added by prior tasks is tested and regression-safe.
