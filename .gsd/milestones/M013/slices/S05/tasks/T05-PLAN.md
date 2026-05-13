---
estimated_steps: 36
estimated_files: 4
skills_used: []
---

# T05: Authorize export status/download and prevent private URL leakage

---
estimated_steps: 8
estimated_files: 3
skills_used:
  - api-design
  - security-review
  - verify-before-complete
---

Why: Export status/download are direct export_id surfaces that currently return metadata or redirects without proving ownership, and redirects can reveal cached download URLs before authorization.

Files:
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/app/services/reporting/enhanced_reports_service.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`

Do:
1. Persist export metadata from `EnhancedReportsService.export_multi_format()` with raw `created_by`, `report_id`, formats, status, and timestamps so follow-up status/download can authorize by export owner and/or report owner.
2. In router `get_export_status()`, fetch raw export metadata from router cache or service, authorize before `_normalize_export_response()`, then return the response.
3. In router `download_export()`, authorize the raw export metadata before checking readiness or reading/redirecting `download_urls`; rename any local variable that shadows FastAPI's `status` module so redirect status constants are safe.
4. If no artifact URL exists, preserve the existing inline fallback for requested completed formats after authorization.
5. If a cached `download_url` is present, redirect only after authorization; never return `download_url`/Location to foreign users.
6. Do not create or advertise new `/uploads/...` URLs for private report artifacts. If legacy cached URLs point at public private-file paths, fail closed or require an already-gated API URL rather than reintroducing a public private-file URL.
7. Update existing enhanced report export tests/fixtures to include valid raw ownership metadata and to assert legitimate owner/admin behavior under the new guard.
8. Keep response bodies/logs generic for forbidden/missing export cases: export_id/report_id/user_id/reason/status only, no private paths, tokens, patient IDs, or report payload.

Failure Modes (Q5):
| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|-----------------------|
| Export cache/service lookup | missing export remains 404 | request timeout applies | missing/malformed created_by/report_id fails closed |
| Cached download_url | unauthorized users never see it | N/A | private/public `/uploads` private URLs are rejected or withheld |

Load Profile (Q6):
- Shared resources: Redis export cache and optional report ownership lookup.
- Per-operation cost: one export lookup plus optional report access lookup before redirect/inline bytes.
- 10x breakpoint: export status polling can stress cache; keep auth checks narrow and no file/redirect work before auth.

Negative Tests (Q7):
- Malformed inputs: export metadata without owner/report_id, invalid report_id, unknown format.
- Error paths: foreign user status/download, not-ready export, missing download_url, legacy public private URL.
- Boundary conditions: completed export owner inline fallback, owner redirect to gated URL, admin access, foreign denied before Location header.

Done when: Export portions of the S05 regression tests pass, existing enhanced export compatibility tests pass with raw metadata, and no unauthorized response exposes export download URLs or private paths.

## Inputs

- `backend-hormonia/app/services/reporting/report_access.py`
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/app/services/reporting/enhanced_reports_service.py`
- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`
- `backend-hormonia/tests/services/test_report_service_task_compat.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/app/services/reporting/enhanced_reports_service.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "export" -q && pytest tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py -q

## Observability Impact

Makes export denial/readiness failures distinguishable through export_id/report_id/user_id/reason fields while withholding download URLs and private paths until after authorization.
