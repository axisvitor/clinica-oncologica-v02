---
id: T05
parent: S01
milestone: M014
key_files:
  - backend-hormonia/app/services/patient/validation_service.py
  - backend-hormonia/app/services/patient/integrity_service.py
  - backend-hormonia/app/services/patient/sync_service.py
  - backend-hormonia/app/domain/patient/onboarding/validation_service.py
  - backend-hormonia/app/api/v2/routers/patients/crud.py
  - backend-hormonia/app/core/exceptions.py
  - backend-hormonia/app/utils/db_retry.py
  - backend-hormonia/tests/api/v2/test_patients_create.py
  - backend-hormonia/tests/integration/test_duplicate_prevention.py
  - backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py
key_decisions:
  - Duplicate patient probes return generic 409 `Duplicate patient` with `details: {code: duplicate_patient}` only, while diagnostics carry PHI-safe event type/reason/route/request metadata without raw probed identifiers.
  - Expected domain/API validation denials are intentional input rejections and should not increment the database circuit breaker; only actual database/transient failures should affect the circuit state.
  - Captured MEM071 documenting the duplicate-denial and DB circuit-breaker pattern.
duration: 
verification_result: passed
completed_at: 2026-05-13T14:11:45.906Z
blocker_discovered: false
---

# T05: Closed patient duplicate probing with generic `duplicate_patient` conflicts before saga/provider side effects and proved the full S01 ingress suite passes.

**Closed patient duplicate probing with generic `duplicate_patient` conflicts before saga/provider side effects and proved the full S01 ingress suite passes.**

## What Happened

Resumed from the interrupted T05 run, verified the already-edited duplicate hardening files and new security test, then completed the remaining fixes exposed by the S01 proof suite. Patient validation now collapses duplicate CPF/email/phone candidates into a PHI-safe `Duplicate patient` denial with `details: {code: duplicate_patient}` and structured duplicate diagnostics that avoid raw patient identifiers. Patient creation maps duplicate domain validation failures to a generic 409 before saga orchestration, and existing duplicate tests were updated to assert the absence of probed CPF/email/phone/name values. Added the focused M014/S01 duplicate-oracle security proof covering CPF/email/phone/name-like probes, no saga side effect on duplicates, cross-doctor scope allowance, malformed validation behavior, and log redaction. During verification I also fixed two support issues: `ConflictError` now preserves domain-specific conflict detail codes while keeping the top-level HTTP error class as `CONFLICT`, and expected domain/API validation denials no longer poison the global DB circuit breaker. The real-DB duplicate phone-variant integration test now uses the existing `real_doctor_id` fixture instead of a fixed UUID that may violate the users FK.

## Verification

Ran the targeted duplicate regression tests after fixes and then the exact full S01 proof command from the task plan. The final suite passed 52 tests, covering rate-limit fail-closed, CSRF fail-closed, password-reset replay, webhook replay/idempotency, duplicate-oracle closure, patient create duplicate behavior, and duplicate phone normalization. A final source scan confirmed the known duplicate-oracle strings (`Patient with email/phone/CPF already exists`, `Patient already exists with ID`, and existing patient name/ID references) are absent from the touched patient duplicate paths.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py backend-hormonia/tests/api/v2/test_patients_create.py::TestPatientsCreateAPI::test_create_patient_duplicate_cpf_returns_error backend-hormonia/tests/integration/test_duplicate_prevention.py::test_duplicate_prevention_blocks_phone_variants` | 0 | ✅ pass (8 passed) | 25334ms |
| 2 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py backend-hormonia/tests/api/v2/test_patients_create.py backend-hormonia/tests/integration/test_duplicate_prevention.py` | 0 | ✅ pass (52 passed) | 26231ms |
| 3 | `T05 PHI/oracle duplicate message scan across touched patient duplicate paths` | 0 | ✅ pass (risky_duplicate_oracle_occurrences=0) | 56ms |

## Deviations

Added two small infrastructure-support fixes required by verification: preserving domain-specific codes in `app.core.exceptions.ConflictError`, and excluding intentional domain/API exceptions from DB circuit-breaker failure counts. Updated the real-DB duplicate integration test to use `real_doctor_id` rather than a hard-coded doctor UUID.

## Known Issues

The final pytest run emits an existing pytest-asyncio deprecation warning about `asyncio_default_fixture_loop_scope` being unset; all tests still pass.

## Files Created/Modified

- `backend-hormonia/app/services/patient/validation_service.py`
- `backend-hormonia/app/services/patient/integrity_service.py`
- `backend-hormonia/app/services/patient/sync_service.py`
- `backend-hormonia/app/domain/patient/onboarding/validation_service.py`
- `backend-hormonia/app/api/v2/routers/patients/crud.py`
- `backend-hormonia/app/core/exceptions.py`
- `backend-hormonia/app/utils/db_retry.py`
- `backend-hormonia/tests/api/v2/test_patients_create.py`
- `backend-hormonia/tests/integration/test_duplicate_prevention.py`
- `backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py`
