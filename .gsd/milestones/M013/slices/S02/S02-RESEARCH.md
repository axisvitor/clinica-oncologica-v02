# S02 Research — Patient Ownership Boundary

## Summary

Depth: targeted security research. This slice owns R003 (messages), R009 (flow responses/overrides), R010 (two-doctor/two-patient negative proof), and R011 (safe denial diagnostics). It also produces the patient ownership helper/test pattern consumed by S03 and S05.

Key finding: message routes already have partial doctor/admin filtering helpers, but at least one message status endpoint lacks ownership and appears to call a non-existent sender method. Patient flow response and flow override endpoints only check “doctor or admin” role, then query by arbitrary `patient_id`; they do not prove the current doctor owns the patient.

## Prior Decisions / Memory

- M013 architecture memory: use shared auth/ownership helpers, not one-off endpoint patches.
- PHI boundary memory: ambiguous ownership fails closed; no partial data response.
- Installed skills relevant to implementation planning: `api-design`, `security-review`, `test`, `verify-before-complete`.
- Optional skill discovery from S01 also found FastAPI/security skills; no install required for S02.

## Implementation Landscape

### Existing ownership helpers

- `backend-hormonia/app/utils/auth_helpers.py` extracts role/user IDs from both dict session payloads and `User` models (`extract_user_context`, `extract_user_role_and_uuid`). This is the safest base for S02’s “model and mapping-style user contexts” acceptance.
- `backend-hormonia/app/dependencies/business_dependencies.py:52` has async `validate_patient_access`, but it goes through `patient_service.get_patient(...)` and sync fallback; it is a FastAPI dependency, not a simple helper for arbitrary routers.
- `backend-hormonia/app/api/v2/routers/patients/base.py:101` has `ensure_patient_access(current_user, patient_doctor_id)` for model/mapping contexts, but it is local to patient routers and async.
- `backend-hormonia/app/api/v2/messages/helpers.py:55` `_get_patient_with_access(...)` and `:97` `_load_message_with_access(...)` are useful patterns, but message-local.

Recommendation: add a small shared helper in `app/api/v2/patients_shared_helpers.py` or a new `app/api/v2/patient_access.py` such as:

- `assert_admin_or_assigned_doctor(current_user, patient_doctor_id) -> None`
- `async load_patient_with_access(db: AsyncSession, patient_id: UUID, current_user) -> Patient`
- sync equivalent if needed by sync message routers: `load_patient_with_access_sync(db: Session, patient_id, current_user)`

Use `extract_user_role_and_uuid`/`extract_user_context` internally; admin passes; doctor must match `Patient.doctor_id`; all else 403.

### Messages

Mounted router: `backend-hormonia/app/api/v2/router.py` includes `messages_router` at `/api/v2/messages` from `app/api/v2/routers/messages.py` (monolithic file). There is also a modular package `app/api/v2/messages/`, but the currently mounted import path is the monolithic `routers/messages.py` because Python chooses `routers/messages.py` under `.routers`.

Relevant modular message files still matter if the package is imported elsewhere, but S02 should confirm which router is active in tests.

Observed message ownership state:

- `backend-hormonia/app/api/v2/messages/helpers.py:55-83` `_get_patient_with_access` checks patient doctor_id for patient-scoped message endpoints.
- `messages/helpers.py:97-123` `_load_message_with_access` loads a message and checks its patient doctor_id before mutation.
- `backend-hormonia/app/api/v2/messages/send.py:43-80` send checks target patient ownership.
- `send.py:119-151` scheduled list filters by patient doctor_id for non-admins.
- `send.py:168-204` cancel uses `_load_message_with_access`.
- **Gap:** `send.py:211-230` `GET /{message_id}/status` parses `message_id` and calls `IdempotentMessageSender.get_message_delivery_status(msg_uuid)` without first loading the `Message` and checking the related patient. Static search found no `get_message_delivery_status` implementation, so the route is both an authorization gap and likely a runtime bug.
- Monolithic `backend-hormonia/app/api/v2/routers/messages.py` has many inline RBAC joins/filters. Planner should decide whether the active router uses the monolith or modular package before editing.

### Flow responses

- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py:58` decorates with `@require_doctor_or_admin()` only.
- It loads the patient at `:92-97` just to prove existence and then queries `PatientFlowResponse.patient_id == patient_id` at `:100-112`.
- There is no `Patient.doctor_id == current_user.id` check before returning free-text responses.

### Flow overrides

- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py:175` and `:206` also use only `@require_doctor_or_admin()`.
- `_get_active_flow_state(patient_id, db)` at `:49-66` returns any active flow state for the supplied patient.
- `get_flow_overrides` at `:193` and `put_flow_overrides` at `:226` call `_get_active_flow_state` directly; no ownership check.
- `put_flow_overrides` uses `created_by=current_user.id` at `:258`, but `get_current_user_from_session` returns mapping-style session data in many tests. This may break legitimate dict-user paths and should use a helper (`get_user_uuid`) instead.

### Test infrastructure

- `backend-hormonia/tests/conftest.py:1459` `create_test_user(...)` and `:1558` `create_test_patient(...)` are the fixture factory pattern.
- `auth_headers` at `tests/conftest.py:1611` overrides `get_current_user_from_session` and `get_current_user_object_from_session` for the default `test_user`.
- For two-doctor negative tests, create doctor A/doctor B and then override `get_current_user_from_session` directly for doctor A, or build a local fixture modelled after `auth_headers`.
- Existing RBAC tests for patients are in `backend-hormonia/tests/api/v2/test_patients_rbac_impl.py`; use their doctor A/B style and add message/flow-specific fixtures.

## Recommendation

1. Create shared admin-or-assigned-doctor access helpers that handle both dict and model user contexts.
2. Wire flow response and flow override endpoints through `load_patient_with_access(...)` before any response/override query.
3. Fix message status route by loading the `Message` with `_load_message_with_access` (or shared helper), then return local status fields or call a delivery-status provider only after authorization succeeds.
4. Prefer 403 for known foreign resources in authenticated tests; 404 can be chosen later for anti-enumeration, but tests should assert fail-closed (`in {403, 404}`) only if product wants concealment.

## Natural Seams / Work Units

1. **Shared helper:** `app/api/v2/patients_shared_helpers.py` or new `app/api/v2/patient_access.py`; unit tests for dict/model/admin/doctor/foreign contexts.
2. **Messages:** active `/api/v2/messages` router status/read/mutate gaps; add one or two negative route tests for Doctor A vs Doctor B message IDs.
3. **Flow responses:** `patients/flow_responses.py`; deny foreign doctor before returning free text.
4. **Flow overrides:** `patients/flow_overrides.py`; deny GET/PUT foreign patient and fix `current_user.id` mapping incompatibility.
5. **Fixtures:** reusable two-doctor/two-patient setup for S03/S05.

## First Proof

Highest-value failing tests:

- `test_doctor_cannot_get_foreign_flow_responses`: Doctor A session, patient B belongs to Doctor B, response row exists; `GET /api/v2/patients/{patient_b.id}/flow-responses` must be 403/404 and return no response text.
- `test_doctor_cannot_get_or_put_foreign_flow_overrides`: same setup with active flow state; both GET and PUT fail before returning merged day list or mutating overrides.
- `test_doctor_cannot_get_foreign_message_status`: Doctor B patient/message exists; Doctor A requests `/api/v2/messages/{message_id}/status`; fail closed and do not call delivery provider.
- `test_admin_can_access_foreign_patient_boundaries`: admin session still succeeds for the same fixtures.
- Helper unit tests for `User` model and dict session payloads.

## Verification Commands

- `cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py -q` (new focused file)
- `cd backend-hormonia && pytest tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py -q` (regression suites)
- If touching active monolithic router: `cd backend-hormonia && pytest tests/api/v2/test_phase25_messages_quiz_async.py -q`

## Forward Intelligence / Watch-outs

- Confirm active router before editing: `app/api/v2/router.py` imports `.routers.messages`, not the modular `app/api/v2/messages` package. Some tests may still import modular helpers directly.
- The `require_doctor_or_admin()` decorator checks role only; do not mistake it for patient ownership.
- Keep free-text flow responses out of logs and error details. Log IDs/correlation only.
- For async routers using `SyncToAsyncSessionAdapter` in tests, write helpers using `await db.execute(select(...))` and avoid direct `.query` unless providing a sync version.
- S02’s helper should be reusable by S03 quiz and S05 report closures; avoid naming it message-specific.

## Sources

- `backend-hormonia/app/api/v2/messages/helpers.py`
- `backend-hormonia/app/api/v2/messages/send.py`
- `backend-hormonia/app/api/v2/routers/messages.py`
- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py`
- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`
- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/app/utils/auth_helpers.py`
- `backend-hormonia/tests/conftest.py`
- `backend-hormonia/tests/api/v2/test_patients_rbac_impl.py`
