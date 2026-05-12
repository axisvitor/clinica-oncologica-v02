---
estimated_steps: 45
estimated_files: 4
skills_used: []
---

# T01: Gate authenticated quiz link/status/history lists by patient ownership

---
estimated_steps: 8
estimated_files: 4
skills_used:
  - tdd
  - api-design
  - security-review
  - verify-before-complete
---

## Why
Authenticated quiz link/status surfaces currently authenticate the caller but do not scope `patient_id` or active-link lists by the assigned doctor. This closes R004 before public-token work builds on those sessions.

## Files
- Modify `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py`.
- Create/extend `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`.
- Reuse `backend-hormonia/tests/api/v2/security_boundary_helpers.py` and `backend-hormonia/app/api/v2/patients_shared_helpers.py`.

## Do
1. Import and use `load_patient_with_access(db, patient_id, current_user)` before `create_quiz_link` verifies/creates sessions or generates tokens.
2. Use the same helper at the start of `get_patient_quiz_status`; keep `get_patient_quiz_history` delegated to the secured status function.
3. Rewrite `get_active_links` so doctors only see sessions joined through `Patient.doctor_id == current_user.id`; admins may see all. Do not load all patients and filter after PHI has been assembled.
4. Treat active quiz sessions as DB status `started` plus non-expired/link-active metadata; do not rely on invalid `QuizSession.status == 'active'`.
5. If `get_dashboard_stats` is touched while sharing query helpers, scope doctor aggregate counts to assigned patients and leave admin-all behavior intact.
6. Add focused tests using the S02 boundary fixture pattern: Doctor A cannot create a link for Patient B and no Patient B session is created; Doctor A cannot read Patient B status/history; Doctor A active links excludes Patient B ID/name/session; Doctor B or admin positive paths still work.
7. Keep denial responses/logs generic; assertions must verify Patient B name and any forbidden quiz/session values are absent.
8. Ensure the new tests do not reference `.gsd/`, `.planning/`, or `.audits/`.

## Must-Haves
- [ ] Foreign authenticated doctors receive 403/404-safe failures before quiz session/token side effects.
- [ ] Assigned doctors and admins retain legitimate link/status/list behavior.
- [ ] Active-link list does not leak `patient_name` for foreign patients.

## Failure Modes (Q5)
| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|-----------------------|
| DB patient/session/template query | Fail closed with existing HTTPException or 500 for true DB failure; no token/session side effects before patient ownership succeeds | TestClient/DB has no network timeout; production DB timeout should surface as 500 without PHI | Invalid/missing patient UUID returns the shared helper's generic 400/404/403 |
| Auth dependency | Existing `_get_current_user_simple` returns 401 | N/A | Malformed actor fails through shared helper with generic denial |

## Load Profile (Q6)
- Shared resources: database session and patient/session indexes.
- Per-operation cost: create/status each adds one patient lookup; active links should remain one scoped joined query plus bounded template/patient hydration.
- 10x breakpoint: unscoped Python-side PHI hydration would break first, so keep doctor scoping in SQL before serialization.

## Negative Tests (Q7)
- Malformed inputs: invalid patient_id for status/history.
- Error paths: foreign doctor create/status/history/active list, nonexistent patient/template.
- Boundary conditions: admin sees all active links; assigned doctor sees only own patient when both doctors have active sessions.

## Verify
- `cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py -q -k "authenticated or active_links or patient_status or patient_history"`

## Done when
The focused authenticated-boundary tests pass and a foreign doctor cannot create/read/list quiz links or status for another doctor's patient.

## Inputs

- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py`
- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/tests/api/v2/security_boundary_helpers.py`
- `backend-hormonia/app/models/quiz.py`
- `backend-hormonia/app/models/patient.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py`
- `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_quiz_link_session_boundary.py -q -k "authenticated or active_links or patient_status or patient_history"

## Observability Impact

Reuses S02's PHI-free patient ownership denial diagnostics for quiz link/status paths and prevents active-link PHI serialization before ownership scoping.
