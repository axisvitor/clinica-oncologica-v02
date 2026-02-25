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

## 2026-02-25 Full-Suite Closure (422-vs-403 fix)

- Command: `python3 -m pytest tests/api/critical/test_patient_security_fixes.py::TestPatientSecurityFixes::test_idempotency_rbac_denies_other_doctor -x -v`
- Date/Time (UTC): `2026-02-25T18:42:23Z`
- Result: PASSED (`1 passed`) — idempotency RBAC now returns expected `403 Forbidden`
- Root cause closed: (1) critical fixture lacked `get_async_db` override so endpoint `AsyncSession` could not see test transaction data; (2) validation services used legacy `.query()` incompatible with async/session-adapter path
- Fix applied: `SyncToAsyncSessionAdapter` + `get_async_db` override in critical `client` fixture, plus `select()` migrations in `validation_service.py` and `sync_service.py`
- Phase 17 gap status: `422-vs-403` blocker CLOSED

- Command: `python3 -m pytest -x`
- Date/Time (UTC): `2026-02-25T18:47:18Z`
- New first failure: `tests/api/critical/test_patients_list.py::TestPatientList::test_list_patients_empty_or_existing`
- Error class: `ResponseValidationError` (HTTP 500 from `string_pattern_mismatch` on `treatment_phase='onboarding'`)
- Scope note: This new failure is outside Phase 17 split/async-session idempotency changes; it appears in patient list response validation semantics and should be tracked separately from the closed 422-vs-403 issue.

## 2026-02-25 Plan 17-06 Full-Suite Run

- Command: `python3 -m pytest -x --tb=short`
- Date/Time (UTC): `2026-02-25T16:35:52Z`
- New first failure: `tests/api/test_api_contract_fixes.py::TestNotificationsStructureFix::test_notifications_structure`
- Error class: `sqlalchemy.exc.ProgrammingError` (`psycopg.errors.UndefinedColumn: notifications.notification_type does not exist`)
- Scope note: This failure occurs in notifications schema/query contract and is unrelated to the Phase 17-06 `treatment_phase` response validation fix for `/api/v2/patients/`.
