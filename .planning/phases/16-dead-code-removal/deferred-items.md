## Deferred Items

- Full `pytest` currently fails outside Phase 16 scope at `tests/api/critical/test_patient_security_fixes.py::TestPatientSecurityFixes::test_idempotency_rbac_denies_other_doctor` due to missing `patients.messaging_stopped_at` column in test DB schema.
