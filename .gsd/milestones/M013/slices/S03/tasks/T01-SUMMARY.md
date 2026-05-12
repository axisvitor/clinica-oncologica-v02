---
id: T01
parent: S03
milestone: M013
key_files:
  - backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py
  - backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py
key_decisions:
  - Use load_patient_with_access as the authenticated quiz patient boundary before any session/token side effects.
  - Scope active-link list queries through Patient.doctor_id in SQL before patient/template serialization; admins retain all-link visibility.
  - Require DB status 'started' plus non-expired/link_status='active' metadata for active quiz links rather than relying on invalid status='active'.
duration: 
verification_result: passed
completed_at: 2026-05-12T20:33:06.015Z
blocker_discovered: false
---

# T01: Gated authenticated quiz link creation/status/history by patient ownership and scoped active-link lists before PHI serialization.

**Gated authenticated quiz link creation/status/history by patient ownership and scoped active-link lists before PHI serialization.**

## What Happened

Updated the monthly quiz CRUD router so create_quiz_link calls load_patient_with_access before template lookup, session creation, token generation, or metadata writes; this makes foreign-doctor link attempts fail closed with the shared generic patient-access denial and no session/token side effects. get_patient_quiz_status now uses the same helper up front, while history continues delegating to status. Reworked get_active_links to resolve the authenticated medical actor safely for model or dict-shaped auth contexts, query QuizSession joined to Patient with doctor scoping in SQL for doctors and admin-all behavior for admins, and treat active links as status='started', non-expired sessions with link_status='active' metadata. Also fixed quiz link metadata persistence by assigning a fresh session_metadata dict before commit, ensuring token_hash/link_status/expires_at are observable to later queries. Added focused boundary tests covering foreign doctor create/status/history denial without PHI/session leakage, no session side effect on denied create, assigned doctor positive status, doctor-scoped active links, and admin visibility of both active links.

## Verification

Ran the task's focused pytest command successfully: cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py -q -k "authenticated or active_links or patient_status or patient_history". Also ran a diagnostic check confirming the new test file does not reference .gsd/, .planning/, or .audits/.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py -q -k "authenticated or active_links or patient_status or patient_history"` | 0 | ✅ pass (3 tests passed) | 28551ms |
| 2 | `python check for forbidden local planning artifact references in backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py` | 0 | ✅ pass (.gsd/.planning/.audits absent) | 57ms |

## Deviations

Added a test-local Postgres quiz-table schema guard in the new focused test file because the local verification database had legacy minimal quiz_tables that lacked ORM columns; the guard is scoped to this suite and does not affect production code.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py`
- `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`
