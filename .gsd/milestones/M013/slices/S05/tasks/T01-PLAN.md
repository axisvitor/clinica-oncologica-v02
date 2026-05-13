---
estimated_steps: 35
estimated_files: 3
skills_used: []
---

# T01: Add report ownership closure regression tests

---
estimated_steps: 8
estimated_files: 2
skills_used:
  - tdd
  - security-review
  - test
---

Why: S05 needs executable proof before implementation so direct report UUID abuse, export URL leakage, and normalization-derived ownership regressions are caught.

Files:
- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`

Do:
1. Create `backend-hormonia/tests/api/v2/test_report_ownership_closure.py` with reusable helpers for two doctors, two patients, auth override swapping, and an in-memory async Redis/cache seam compatible with report routers.
2. Cover base reports: foreign `patient_ids` on `POST /api/v2/reports/generate` returns 403; owner/admin generation succeeds; completed cached reports download for owner/admin; foreign or missing raw ownership/patient evidence returns 403 before data formatting.
3. Cover enhanced builder read/download: owner/admin succeed; foreign user is denied; cached records missing raw `created_by`/patient evidence are denied even though `_normalize_builder_response()` would otherwise default `created_by` to the requester.
4. Cover enhanced sharing/public link/share listing, report history/restore, export status, and export download with seeded raw metadata: owner/admin behavior remains valid and foreign users receive generic 403/404-style denials.
5. Include an export download case with a cached `download_urls` entry and assert a foreign user never receives the Location/download URL or any `/uploads`/private path text.
6. Include caplog or response-body assertions that denied responses/logs contain generic ID/status/reason diagnostics only, not patient IDs, private paths, tokens, or report data.
7. Update existing `test_enhanced_reports.py` cached fixtures for legitimate operations to include raw `created_by` and/or `report_id` ownership metadata so compatibility tests model valid resources instead of relying on the old permissive helper.
8. Keep tests inside `backend-hormonia/tests/...`; tests must not read `.gsd/`, `.planning/`, `.audits/`, or other gitignored planning artifacts.

Failure Modes (Q5):
| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|-----------------------|
| Redis/cache test seam | fail the test with fixture-level error | no network timeout; in-memory seam only | seed malformed owner/patient metadata and assert fail-closed 403 |
| Auth override | fail the test setup rather than anonymous fallback | N/A | invalid/missing user context should assert 401/403 |

Load Profile (Q6):
- Shared resources: transactional SQLite test DB and in-memory Redis seam.
- Per-operation cost: one route call plus one cache lookup and optional DB ownership query.
- 10x breakpoint: test runtime/fixture setup, not production resource pressure.

Negative Tests (Q7):
- Malformed inputs: invalid/missing owner metadata, unknown report/export IDs, invalid patient_ids query values.
- Error paths: foreign doctor, anonymous/missing user ID, deleted/missing cache metadata where applicable.
- Boundary conditions: owner vs admin vs foreign; completed export with and without download_urls.

Done when: The new test file collects cleanly and encodes every S05 boundary as executable assertions, with existing compatibility fixtures no longer depending on permissive access checks.

## Inputs

- `backend-hormonia/app/api/v2/routers/reports.py`
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/app/services/reporting/enhanced_reports_service.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`
- `backend-hormonia/tests/conftest.py`
- `backend-hormonia/tests/api/v2/conftest.py`
- `backend-hormonia/app/models/patient.py`
- `backend-hormonia/app/models/user.py`

## Expected Output

- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py --collect-only -q

## Observability Impact

Adds explicit PHI-safety assertions for report access denial responses/logs, including no private paths, tokens, download URLs, patient names, or report payload data.
