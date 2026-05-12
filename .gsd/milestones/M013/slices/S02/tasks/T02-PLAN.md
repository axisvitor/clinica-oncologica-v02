---
estimated_steps: 13
estimated_files: 4
skills_used: []
---

# T02: Scope message read/list/conversation routes by patient ownership

Expected executor skills (`skills_used`): `security-review`, `tdd`, `test`, `verify-before-complete`.

Why: The active `/api/v2/messages` router is `backend-hormonia/app/api/v2/routers/messages.py`; its read/list/conversation paths currently query by direct message or patient IDs and can serve cached data before proving ownership. This task closes PHI read exposure before mutation endpoints are handled in T03.

Do:
1. Create reusable focused-test helpers in `backend-hormonia/tests/api/v2/security_boundary_helpers.py` (or equivalent non-collected module) for Doctor A/Doctor B, Patient A/Patient B setup and dependency override to a selected user. Build from `create_test_user`, `create_test_patient`, and `get_current_user_from_session` patterns in `tests/conftest.py`.
2. Add focused tests in `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py` named around `message_read`/`conversation` that prove Doctor A cannot retrieve Doctor B's message by `GET /api/v2/messages/{id}`, cannot list it via `GET /api/v2/messages?patient_id=...`, cannot see it in `GET /api/v2/messages/conversations`, cannot read `GET /api/v2/messages/conversations/{patient_id}`, and cannot read foreign unread counts. Assert no foreign patient name or message content appears in JSON.
3. Add positive tests that the assigned doctor can read their own message/conversation and admin can read both.
4. Update `backend-hormonia/app/api/v2/routers/messages.py` read paths to use the shared helper before returning data. For global list/conversation endpoints, scope SQL with a `Patient.doctor_id == current_user_uuid` join/exists condition for doctors and admin-all behavior for admins; do not load all messages then filter in Python.
5. Fix patient-bound cache safety: do not read direct-message cache before DB ownership succeeds, and include actor role/id (or equivalent ownership scope) in list/conversation cache keys so one user's cached response cannot be replayed to another user.
6. Apply the same ownership check to patient-specific statistics if it accepts a `patient_id` and returns patient-bound message data.

Failure Modes (Q5): Redis/cache get/set/delete errors remain non-critical but must not bypass DB authorization; missing message -> 404; existing foreign message/patient -> 403; malformed UUID -> existing 400 behavior.

Load Profile (Q6): list and conversation routes should add one indexed patient ownership predicate or join; avoid N+1 checks per message and preserve pagination semantics.

Negative Tests (Q7): direct message IDOR, `patient_id` filter IDOR, global conversation leakage, conversation history IDOR, unread-count side channel, cached foreign direct/list response replay.

Done when: focused read/conversation tests pass and legitimate assigned-doctor/admin reads still pass.

## Inputs

- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/app/api/v2/routers/messages.py`
- `backend-hormonia/app/models/message.py`
- `backend-hormonia/tests/conftest.py`
- `backend-hormonia/tests/api/v2/test_messages.py`
- `backend-hormonia/tests/api/v2/test_patients_rbac_impl.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/messages.py`
- `backend-hormonia/tests/api/v2/security_boundary_helpers.py`
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py -q -k "message_read or conversation"

## Observability Impact

Ensures message read denials flow through the shared structured deny signal and cache diagnostics remain non-PHI/non-authorizing.
