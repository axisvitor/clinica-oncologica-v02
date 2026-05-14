---
estimated_steps: 9
estimated_files: 2
skills_used: []
---

# T03: Build report and export app-route runtime probe

Why: S04 also needs report and enhanced export app-route proof, including ownership checks and unsafe URL withholding, without overclaiming that all redirects are forbidden.

Do:
1. Extend the artifact probe to seed runtime DB/Dragonfly fixtures for base report, enhanced builder, and enhanced export route cases using synthetic-only owner/admin/foreign users.
2. Prove `/api/v2/reports/{report_id}/download` owner/admin success with safe attachment headers and anonymous/foreign denial before payload exposure.
3. Prove `/api/v2/enhanced-reports/builder/{builder_id}/download` owner/admin success and foreign denial with the same safe header evidence.
4. Prove `/api/v2/enhanced-reports/export/{export_id}` status sanitizes unsafe/private/static/external download URLs and the download route returns 404/no location for unsafe private/static targets.
5. Prove supported fallback downloads are returned as non-executable attachments, while safe non-private redirects remain explicitly outside the denial claim.
6. Ensure no raw `download_urls`, private paths, report payload bytes, patient fields, or raw IDs are stored in durable probe results.

Done when: report/export probe contracts pass and the runtime evidence can distinguish base report, builder, export status, unsafe download denial, and fallback attachment outcomes.

## Inputs

- ``scripts/security/m015-runtime/artifact_seam.py``
- ``backend-hormonia/app/api/v2/routers/reports.py``
- ``backend-hormonia/app/api/v2/routers/enhanced_reports.py``
- ``backend-hormonia/app/services/reporting/report_access.py``
- ``backend-hormonia/app/utils/download_responses.py``
- ``backend-hormonia/tests/api/v2/test_report_ownership_closure.py``
- ``backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py``

## Expected Output

- ``scripts/security/m015-runtime/artifact_seam.py` — report/export runtime probe cases and sanitized results.`
- ``backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py` — report/export runtime contract coverage.`

## Verification

cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/api/v2/test_report_ownership_closure.py tests/security/test_m014_s04_report_artifact_serving.py -q

## Observability Impact

Adds report/export route labels, ownership outcome classes, unsafe-url-withheld booleans, no-unsafe-redirect booleans, attachment header booleans, and redaction-safe hashes for fixture correlation.
