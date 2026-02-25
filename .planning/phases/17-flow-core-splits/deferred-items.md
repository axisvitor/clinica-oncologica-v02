# Deferred Items - Phase 17 Flow Core Splits

## Out-of-scope Test Failure

- Command: `python3 -m pytest tests/unit/services/flow/test_sequential_message_handler.py -k "direct_function or run_flow_message or run_flow_response" -x`
- Issue: `Settings` model in test runtime rejects monkeypatching `AI_FLOW_FRAMEWORK` (`ValueError: "Settings" object has no field "AI_FLOW_FRAMEWORK"`).
- Scope note: This test failure is not introduced by the `_flow_functions` split and is outside this plan's targeted contract checks.

- Command: `python3 -m pytest -x`
- Issue: `tests/api/critical/test_patient_security_fixes.py::TestPatientSecurityFixes::test_idempotency_rbac_denies_other_doctor` fails with `psycopg.errors.UndefinedColumn: column "messaging_stopped_at" of relation "patients" does not exist`.
- Scope note: This failure occurs in API security tests and database schema setup, unrelated to the flow-management service split changes in this plan.

## 2026-02-25 Schema Guard Recheck

- Command: `python3 -m pytest tests/api/critical/test_patient_security_fixes.py::TestPatientSecurityFixes::test_idempotency_rbac_denies_other_doctor -x`
- Result: schema guard executed (`[critical.conftest] Applying schema patch: add patients.messaging_stopped_at`); previous `UndefinedColumn` blocker no longer reproduces.

- Command: `python3 -m pytest -x`
- Date/Time (UTC): `2026-02-25T17:33:59Z`
- New first failure: `tests/api/critical/test_patient_security_fixes.py::TestPatientSecurityFixes::test_idempotency_rbac_denies_other_doctor`
- Error class: `AssertionError` (`422 != 403`)
- Context: request path now reaches authorization assertion flow; runtime logs show `AttributeError: 'AsyncSession' object has no attribute 'query'` inside patient validation path.
- Scope note: This is a different blocker than the original missing-column schema issue and is not introduced by Phase 17 split-module changes.
