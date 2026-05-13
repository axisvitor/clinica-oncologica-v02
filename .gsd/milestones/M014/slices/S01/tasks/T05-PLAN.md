---
estimated_steps: 22
estimated_files: 7
skills_used: []
---

# T05: Close patient duplicate oracle and run S01 ingress proof

---
estimated_steps: 8
estimated_files: 7
skills_used:
  - api-design
  - tdd
  - verify-before-complete
---

Why: Patient creation duplicate checks currently risk revealing which identifier matched and, in some paths, an existing patient name/ID or raw phone values. S01 must turn duplicate probing into a generic conflict before saga/provider side effects and finish the slice with one reviewer-facing command suite.

Files: patient validation/integrity services, patient create router, duplicate tests, and a focused S01 duplicate-oracle proof.

Do:
1. Replace duplicate-specific messages such as `Patient with email/phone/CPF already exists: {existing.name}` and `Patient already exists with ID: ...` with a generic conflict message/code that does not reveal field, name, phone, CPF, email, patient ID or ownership details.
2. Keep legitimate validation errors for malformed input useful but avoid echoing sensitive values. For duplicate responses, return 409 with generic details like `{code: duplicate_patient}` only.
3. Remove or redact raw phone/email/CPF/name values from duplicate-check logs, patient create normalization logs and exception logs. If diagnostics need correlation, use request_id/correlation_id, field category, or one-way hash/length only.
4. Confirm duplicate detection still happens before `SagaOrchestrator.execute_patient_onboarding_saga`, WhatsApp registration, queues or provider calls.
5. Update existing duplicate tests to assert generic conflict and absence of probed values.
6. Add `backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py` covering duplicate by CPF/email/phone/name-like payloads, no field oracle, no PHI in response, and no saga side effect on duplicate.
7. Run the full S01 proof command suite from the slice success criteria and fix any regressions introduced by T01-T04.

Failure Modes (Q5): Duplicate candidate denies 409 before saga/provider effects; validation backend error denies safely or falls through only to DB uniqueness constraints with generic conflict; unexpected exceptions use existing service-unavailable/business-error path without PHI echo.

Load Profile (Q6): Duplicate checks remain indexed hash lookups by doctor scope; 10x duplicate probes should spend DB read budget only and never enqueue saga/provider work.

Negative Tests (Q7): duplicate CPF, duplicate email, duplicate phone, same values under another doctor as allowed/owned case where existing policy permits, malformed email/phone still returns validation not duplicate oracle, and log capture excludes raw PHI.

Done when: duplicate responses are generic, no duplicate path invokes saga/provider side effects, all S01 focused tests pass, and the final verification command suite in the slice success criteria passes.

## Inputs

- ``backend-hormonia/app/services/patient/validation_service.py``
- ``backend-hormonia/app/services/patient/integrity_service.py``
- ``backend-hormonia/app/domain/patient/onboarding/validation_service.py``
- ``backend-hormonia/app/api/v2/routers/patients/crud.py``
- ``backend-hormonia/tests/api/v2/test_patients_create.py``
- ``backend-hormonia/tests/integration/test_duplicate_prevention.py``
- ``backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py``
- ``backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py``
- ``backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py``
- ``backend-hormonia/tests/security/test_m014_s01_webhook_replay.py``

## Expected Output

- ``backend-hormonia/app/services/patient/validation_service.py``
- ``backend-hormonia/app/services/patient/integrity_service.py``
- ``backend-hormonia/app/domain/patient/onboarding/validation_service.py``
- ``backend-hormonia/app/api/v2/routers/patients/crud.py``
- ``backend-hormonia/tests/api/v2/test_patients_create.py``
- ``backend-hormonia/tests/integration/test_duplicate_prevention.py``
- ``backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py``

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py backend-hormonia/tests/api/v2/test_patients_create.py backend-hormonia/tests/integration/test_duplicate_prevention.py

## Observability Impact

Duplicate-path logs should state generic duplicate detection, field category if needed, doctor/user scope and request_id only. Do not log patient name, email, phone, CPF, existing patient ID, raw idempotency key, request body or private path.
