# S02: Patient Ownership Boundary — UAT

**Milestone:** M013
**Written:** 2026-05-12T19:54:03.639Z

# S02 UAT — Patient Ownership Boundary

## UAT Type
Automated API integration/security regression using pytest and FastAPI test clients. Runtime server/manual browser validation is not required for this slice.

## Preconditions
1. Work from the repository root and run backend tests from `backend-hormonia`.
2. Test fixtures can create two doctors, two patients assigned one-to-one, an admin user, messages, flow responses, flow state/template rows, and flow override rows.
3. Authentication/session overrides are available for Doctor A, Doctor B, and Admin.

## Steps and Expected Outcomes
1. Run helper proof: `cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py -q`.
   - Expected: admins and assigned doctors are allowed; foreign doctors, malformed users, unassigned patients, and missing patients fail closed with generic 403/404 details and ID/reason-only diagnostics.
2. Run ownership boundary proof: `cd backend-hormonia && pytest tests/api/v2/test_patient_ownership_boundary.py -q`.
   - Expected: Doctor A cannot access Doctor B's message, patient conversation, flow response, or flow override data; assigned doctor and admin positives pass.
3. Run message/RBAC/quiz-adjacent regressions: `cd backend-hormonia && pytest tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py -q`.
   - Expected: legitimate owned/admin message and patient flows still pass; quiz-adjacent message tests remain unaffected; the known rate-limit-disabled test may be skipped.
4. Run the full S02 proof command: `cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py -q`.
   - Expected: exit code 0 with only the known rate-limit skip and existing pytest-asyncio deprecation warning.

## Edge Cases Covered
- Dict-backed and `User` model session users.
- Admin override, assigned doctor allow, foreign doctor deny, malformed/missing actor UUID deny, and unassigned-patient deny.
- Direct message IDOR, patient_id list filter IDOR, conversation history/summary leakage, unread-count side channel, cached foreign response replay, read-state mutation, pending-message delete/cancel, single send, and mixed owned+foreign bulk-send requests.
- Flow response free-text non-disclosure, flow override GET denial, flow override PUT denial without row mutation, assigned-doctor override creation, and admin read access.
- Cache failures remain non-critical but never authorize or bypass the ownership check.

## Not Proven By This UAT
- Live deployed runtime behavior, production database migrations, external WhatsApp/WuzAPI traffic, and Taskiq/Celery worker execution.
- Quiz link/session hardening, which is S03.
- Private upload/report serving and report ownership, which are S04/S05.
- Final finding-level evidence matrix across F-01..F-11, which is S06.
