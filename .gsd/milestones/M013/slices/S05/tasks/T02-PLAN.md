---
estimated_steps: 32
estimated_files: 4
skills_used: []
---

# T02: Create shared raw report access guard

---
estimated_steps: 7
estimated_files: 1
skills_used:
  - api-design
  - security-review
---

Why: Base and enhanced report APIs need one consistent fail-closed authorization primitive instead of endpoint-local boolean checks that allow every authenticated user.

Files:
- `backend-hormonia/app/services/reporting/report_access.py`

Do:
1. Add `backend-hormonia/app/services/reporting/report_access.py` as the shared report authorization module; import it directly from routers/services rather than placing report auth in only one router.
2. Implement strict raw metadata parsing helpers for owner fields (`generated_by`, `created_by`, optionally `owner_id`) and patient fields (`patient_id`, `patient_ids`, nested filter/report metadata forms already present in payloads).
3. Implement async patient assignment checks against `Patient.doctor_id` for all parsed patient IDs, treating invalid UUIDs, empty owner evidence, missing DB rows, or partial assignment as denied.
4. Implement DB fallback metadata lookup for existing `Report` and `MedicalReport` rows by report ID where cached metadata is absent but the report exists, returning patient/generator evidence without loading PHI-heavy content.
5. Implement `assert_report_access(...)`/equivalent that allows admins for existing resources, allows owners by raw owner field, allows doctors assigned to every patient ID, and otherwise raises generic `HTTPException(status_code=403, detail="Access denied")`.
6. Add PHI-safe denial logging with report_id/export_id where available, actor user_id/role, status/reason, and no raw report data, patient names, private paths, tokens, or download_urls.
7. Keep normalization defaults out of the helper contract; callers must pass raw cached/service/DB metadata before response normalization.

Failure Modes (Q5):
| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|-----------------------|
| DB ownership query | fail closed with generic denial or existing 404 path as appropriate; log reason only | no explicit timeout here; caller/request timeout applies | invalid UUID/shape fails closed |
| Cached metadata | absent metadata is not treated as owner proof | N/A | malformed owner/patient fields fail closed |

Load Profile (Q6):
- Shared resources: DB session and Redis-derived metadata supplied by callers.
- Per-operation cost: O(number of patient IDs) parsing plus one DB count/select for patient assignment or report fallback.
- 10x breakpoint: DB pool/query pressure if report download/export is abused; keep queries narrow to IDs/doctor_id.

Negative Tests (Q7):
- Malformed inputs: non-UUID owner/patient fields, scalar/list mismatches, missing owner evidence.
- Error paths: DB returns no patients, partial patient assignment, unsupported non-admin role.
- Boundary conditions: admin, exact owner, all patients assigned, one foreign patient, no patient IDs.

Done when: The helper compiles, has no dependency on normalized response defaults, and exposes enough API surface for both report routers and the enhanced report service to enforce D012.

## Inputs

- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/app/models/report.py`
- `backend-hormonia/app/models/patient.py`
- `backend-hormonia/app/models/user.py`
- `backend-hormonia/app/utils/auth_helpers.py`

## Expected Output

- `backend-hormonia/app/services/reporting/report_access.py`

## Verification

cd backend-hormonia && python -m py_compile app/services/reporting/report_access.py

## Observability Impact

Centralizes report denial logs into a PHI-safe reason/status surface so future agents can localize whether denial came from missing owner metadata, owner mismatch, invalid patient IDs, DB miss, or foreign patient assignment.
