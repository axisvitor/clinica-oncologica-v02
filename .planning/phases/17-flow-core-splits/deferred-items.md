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

## 2026-02-25 Plan 17-07 Fail-Fast Rerun

- Command: `python3 -m pytest -x --tb=short`
- Date/Time (UTC): `2026-02-25T21:22:07Z`
- Result: `FAILED` (first blocker moved past notifications into audit log schema)
- First failing node: `tests/api/test_api_contracts.py::TestUserActivityAPIContract::test_user_activity_returns_activity_logs`
- Error class: `sqlalchemy.exc.ProgrammingError` (`psycopg.errors.UndefinedColumn: audit_logs.firebase_uid does not exist`)
- Notification blocker status: `CLOSED` (`tests/api/test_api_contract_fixes.py::TestNotificationsStructureFix::test_notifications_structure` now passes after fixture schema guard patch)

- Follow-up command: `python3 -m pytest tests/api/test_api_contracts.py::TestUserActivityAPIContract::test_user_activity_returns_activity_logs -x --tb=short`
- Follow-up result: `FAILED`
- New error class: `sqlalchemy.exc.IntegrityError` (`psycopg.errors.CheckViolation: valid_event_category` for `event_category='user_action'`)
- Scope note: Fail-fast is still not fully green because audit log legacy constraints now gate progress after the notifications schema issue was removed.

## 2026-02-25 Plan 17-08 Fail-Fast Rerun

- Command: `python3 -m pytest -x --tb=short`
- Date/Time (UTC): `2026-02-25T22:19:34Z`
- Result: `FAILED`
- First failing node: `tests/api/test_patients_endpoints.py::TestPatientCRUDEndpoints::test_create_patient_success`
- Error class: `AssertionError` (`422 != 201`)
- `valid_event_category` blocker status: `CLOSED` (no `CheckViolation` on `audit_logs.valid_event_category`; `tests/api/test_api_contracts.py::TestUserActivityAPIContract::test_user_activity_returns_activity_logs` now passes)
- Full fail-fast gate status: `NOT GREEN` (new first failure is patient create endpoint validation path, distinct from audit_logs constraint compatibility)

## 2026-02-25 Plan 17-09 Fail-Fast Rerun (post get_async_db override)

- Command: `python3 -m pytest -x --tb=short`
- Date/Time (UTC): `2026-02-25T23:27:07Z`
- Result: `FAILED`
- First failing node: `tests/api/test_patients_endpoints.py::TestPatientCRUDEndpoints::test_create_patient_success`
- Error class: `AssertionError` (`422 != 201`)
- Additional failure context: onboarding saga step 1 now fails with `TypeError: 'allergies' is an invalid keyword argument for Patient`, with downstream compensation `IntegrityError` (`psycopg.errors.UniqueViolation` on `patient_onboarding_saga_pkey`).
- `get_async_db` blocker status: `CLOSED` (patient-create path no longer fails on `'coroutine' object has no attribute 'scalars'`; execution now advances into saga create step).
- Full fail-fast gate status: `NOT GREEN` (new distinct blocker remains in patient onboarding saga payload/model compatibility, separate from the async-session dependency-override issue).

## 2026-02-26 Plan 17-10 Fail-Fast Rerun (post saga payload filter)

- Command: `python3 -m pytest -x --tb=short`
- Date/Time (UTC): `2026-02-26T00:39:59Z`
- Result: `FAILED`
- First failing node: `tests/api/test_patients_endpoints.py::TestPatientCRUDEndpoints::test_list_patients_pagination`
- Error class: `AssertionError` (`assert 4 >= 5`)
- Saga payload/model mismatch blocker status: `CLOSED` (`tests/api/test_patients_endpoints.py::TestPatientCRUDEndpoints::test_create_patient_success` now passes and no `TypeError: 'allergies' is an invalid keyword argument for Patient` appears)
- Full fail-fast gate status: `NOT GREEN` (new distinct blocker remains in patients list pagination expectations, separate from the closed saga payload issue)

## 2026-02-26 Plan 17-11 Fail-Fast Rerun (post pagination fix)

- Command: `python3 -m pytest tests/unit/services/flow/test_flow_functions_split_contract.py tests/unit/services/test_flow_core_split_contract.py tests/unit/services/test_flow_management_split_contract.py -x --tb=short`
- Date/Time (UTC): `2026-02-26T02:31:19Z`
- Result: `PASSED` (`9 passed`)

- Command: `python3 -m pytest tests/api/test_patients_endpoints.py -x --tb=short`
- Date/Time (UTC): `2026-02-26T02:31:19Z`
- Result: `PASSED` (`13 passed`)

- Command: `python3 -m pytest -x --tb=short`
- Date/Time (UTC): `2026-02-26T02:31:19Z`
- Result: `FAILED`
- First failing node: `tests/api/v2/test_admin.py::TestAuditLogs::test_get_audit_logs`
- Error class: `sqlalchemy.exc.IntegrityError` (`psycopg.errors.CheckViolation: valid_event_category`)
- Patient list pagination blocker status: `CLOSED`
- Full fail-fast gate status: `NOT GREEN` (new blocker: audit_logs valid_event_category check violation in admin audit log fixture path)

## 2026-02-26 Plan 17-12 Fail-Fast Rerun (post audit_logs fixture fix)

- Command: `python3 -m pytest tests/unit/services/flow/test_flow_functions_split_contract.py tests/unit/services/test_flow_core_split_contract.py tests/unit/services/test_flow_management_split_contract.py -x --tb=short`
- Date/Time (UTC): `2026-02-26T03:48:51Z`
- Result: `PASSED` (`9 passed`)

- Command: `python3 -m pytest tests/api/v2/test_admin.py::TestAuditLogs::test_get_audit_logs -x --tb=short`
- Date/Time (UTC): `2026-02-26T03:48:51Z`
- Result: `PASSED` (`1 passed`)

- Command: `python3 -m pytest -x --tb=short`
- Date/Time (UTC): `2026-02-26T03:48:51Z`
- Result: `FAILED`
- First failing node: `tests/api/v2/test_admin_extensions.py::TestListDLQItems::test_list_dlq_items_basic`
- Error class: `sqlalchemy.exc.IntegrityError` (caused by `psycopg.errors.ForeignKeyViolation` on `whatsapp_delivery_failures_patient_id_fkey`)
- Audit logs valid_event_category blocker status: `CLOSED`
- Full fail-fast gate status: `NOT GREEN` (new blocker: DLQ fixture inserts reference missing `patients` row in `whatsapp_delivery_failures` FK path)
