---
estimated_steps: 13
estimated_files: 3
skills_used: []
---

# T03: Enforce message mutation and read-state ownership

Expected executor skills (`skills_used`): `security-review`, `tdd`, `test`, `verify-before-complete`.

Why: Message mutation/read-state endpoints can alter PHI state or initiate communication for arbitrary patient IDs. S02 must prove Doctor A cannot mutate Doctor B's messages or patient conversation state, while existing owned/admin flows continue to work.

Do:
1. Extend `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py` with `message_mutation`, `read_state`, and `bulk` tests. Cover: `POST /api/v2/messages` with foreign `patient_id`, `POST /api/v2/messages/bulk/send` with a foreign patient ID, `PATCH /api/v2/messages/{id}/read` for a foreign message, `DELETE /api/v2/messages/{id}` for a foreign pending/scheduled message, and `POST /api/v2/messages/conversations/{patient_id}/mark-read` for a foreign patient.
2. Tests must assert the HTTP denial is 403 for known foreign resources, the response body does not include message content or patient details, and the database row/status/read_at/override count is unchanged after denial.
3. Update `backend-hormonia/app/api/v2/routers/messages.py` mutation paths to call `load_patient_with_access` before creating outbound messages, before bulk-send accepts each patient ID, and before patient conversation mutations. For direct message mutations, load the `Message` with patient relationship and assert ownership before status validation or mutation.
4. Preserve 404/400 behavior for nonexistent or malformed IDs. If `/api/v2/messages/{id}/status` or retry routes are active in the mounted router, apply the same direct-message ownership pattern before returning status or retrying; if they remain unmounted/404, do not introduce new public behavior just for this slice.
5. Update existing regression tests in `backend-hormonia/tests/api/v2/test_messages.py` only where the old test used arbitrary nonexistent/foreign patient IDs as a stand-in for a legitimate send/bulk flow; use owned patients instead.
6. Invalidate user-scoped cache keys after successful mutations; denial paths must not invalidate or mutate foreign resources.

Failure Modes (Q5): DB row missing -> 404; existing foreign resource -> 403 before status validation/mutation; partial bulk list with any unauthorized/nonexistent patient -> fail the whole request before scheduling side effects; cache invalidation failure remains non-critical after successful owned mutation.

Load Profile (Q6): bulk ownership checks should query all requested patient IDs in one bounded query or otherwise avoid per-patient N+1 behavior for up to the endpoint limit.

Negative Tests (Q7): foreign send, mixed owned+foreign bulk, foreign direct read-state mutation, foreign delete/cancel, foreign mark-conversation-read, mutation unchanged after denial.

Done when: focused mutation tests pass, existing message tests pass with legitimate owned/admin fixtures, and no mutation endpoint can alter foreign patient/message state.

## Inputs

- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/app/api/v2/routers/messages.py`
- `backend-hormonia/app/models/message.py`
- `backend-hormonia/tests/api/v2/security_boundary_helpers.py`
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`
- `backend-hormonia/tests/api/v2/test_messages.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/messages.py`
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`
- `backend-hormonia/tests/api/v2/test_messages.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py -q -k "message_mutation or read_state or bulk or send_message"

## Observability Impact

Mutation denials reuse the shared deny signal; successful mutations continue existing cache debug logging without adding PHI to logs.
