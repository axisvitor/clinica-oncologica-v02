# S05: Report Ownership Closure

**Goal:** Close the report-ID ownership boundary for base and enhanced report APIs. Direct report generation/download, builder read/download, sharing/public-link/share listing, history/restore, and export status/download must authorize against raw owner metadata or patient assignment before returning report data or redirects, while legitimate owners and admins continue to work and denials remain PHI-safe.
**Demo:** Direct report download/export/share/history reject cross-user or cross-doctor report IDs and preserve legitimate owner/admin behavior.

## Must-Haves

- Threat Surface (Q3):
- Abuse: report_id/export_id UUID enumeration, replaying direct download links, laundering missing created_by through response normalization, generating reports for foreign patient_ids, and obtaining export download_urls before authorization.
- Data exposure: report bytes, export artifacts, share/public-link metadata, history/version metadata, patient_ids, private artifact paths, and private download URLs.
- Input trust: URL UUIDs, query patient_ids, format parameters, Redis/cache report/export metadata, and cached download_urls are untrusted and must be validated before use.
- Requirement Impact (Q4):
- Requirements touched: R008 primary; R010/R011 supporting; R007 preserved by avoiding new public private-report URLs; R006/S04 private serving re-verified for regression safety.
- Re-verify: base report generation/download, enhanced builder/share/history/export flows, enhanced report compatibility tests, S04 private upload/report serving tests.
- Decisions followed/revisited: D002 shared authorization helpers, D004 application-owned private reports, D011 public-only /uploads mount, D012 raw report metadata/fail-closed report authorization.
- Verification defined before implementation:
- `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -q`
- `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py tests/api/v2/test_private_upload_serving.py tests/tasks/test_reports_tasks.py -q`
- Done when:
- A reusable two-doctor/two-patient report ownership regression test file proves owner/admin success and foreign/anonymous/missing-evidence denial for report surfaces in scope.
- Base reports persist raw `generated_by` plus parsed `patient_ids`, reject foreign patient_ids during generation, and reject direct downloads unless owner/admin/patient-assigned access is proven.
- Enhanced builder/share/public-link/share-list/history/restore/export status/export download paths check raw cached/service metadata before normalization or redirect.
- Export download never reveals `download_url`, private filesystem paths, patient IDs, or public private-file URLs to unauthorized users.
- Denial responses and logs carry only IDs/status/reason-style diagnostics and no PHI/private paths/tokens.

## Proof Level

- This slice proves: Integration/contract proof with FastAPI route tests, transactional test DB fixtures, mocked Redis/cache metadata, and two-doctor/two-patient negative authorization cases. Real runtime server and human UAT are not required for this slice; S06 will assemble the milestone-wide evidence matrix.

## Integration Closure

Consumes S04 private upload/report storage and S02 patient ownership patterns. Introduces one shared report access helper used by `backend-hormonia/app/api/v2/routers/reports.py`, `backend-hormonia/app/api/v2/routers/enhanced_reports.py`, and `backend-hormonia/app/services/reporting/enhanced_reports_service.py`. After S05, only S06 remains to consolidate F-01..F-11 proof and deferred medium/proof-gap follow-ups.

## Verification

- Standardizes PHI-safe report access denial diagnostics: structured log fields should include report_id/export_id when relevant, user_id/role, status/reason, and no patient names, patient IDs in messages, raw report data, private filesystem paths, tokens, or public private-file URLs. Future agents inspect behavior through focused pytest failures, HTTP status codes, caplog assertions in `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`, and generic route-level denial details.

## Tasks

- [x] **T01: Add report ownership closure regression tests** `est:1.5h`
  ---
  estimated_steps: 8
  estimated_files: 2
  skills_used:
    - tdd
    - security-review
    - test
  ---
  - Files: `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`, `backend-hormonia/tests/api/v2/test_enhanced_reports.py`, `backend-hormonia/tests/conftest.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py --collect-only -q

- [ ] **T02: Create shared raw report access guard** `est:1h`
  ---
  estimated_steps: 7
  estimated_files: 1
  skills_used:
    - api-design
    - security-review
  ---
  - Files: `backend-hormonia/app/services/reporting/report_access.py`, `backend-hormonia/app/api/v2/patients_shared_helpers.py`, `backend-hormonia/app/models/report.py`, `backend-hormonia/app/models/patient.py`
  - Verify: cd backend-hormonia && python -m py_compile app/services/reporting/report_access.py

- [ ] **T03: Enforce base report patient and download ownership** `est:1h`
  ---
  estimated_steps: 7
  estimated_files: 1
  skills_used:
    - api-design
    - security-review
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/api/v2/routers/reports.py`, `backend-hormonia/app/services/reporting/report_access.py`, `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "base_report or generate" -q

- [ ] **T04: Guard enhanced builder, sharing, and history routes before normalization** `est:2h`
  ---
  estimated_steps: 9
  estimated_files: 2
  skills_used:
    - api-design
    - security-review
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/api/v2/routers/enhanced_reports.py`, `backend-hormonia/app/services/reporting/enhanced_reports_service.py`, `backend-hormonia/app/services/reporting/report_access.py`, `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "builder or sharing or public_link or history or restore" -q

- [ ] **T05: Authorize export status/download and prevent private URL leakage** `est:1.5h`
  ---
  estimated_steps: 8
  estimated_files: 3
  skills_used:
    - api-design
    - security-review
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/api/v2/routers/enhanced_reports.py`, `backend-hormonia/app/services/reporting/enhanced_reports_service.py`, `backend-hormonia/tests/api/v2/test_enhanced_reports.py`, `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "export" -q && pytest tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py -q

- [ ] **T06: Run integrated report ownership proof suite** `est:45m`
  ---
  estimated_steps: 5
  estimated_files: 0
  skills_used:
    - verify-before-complete
    - test
    - security-review
  ---
  - Files: `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`, `backend-hormonia/tests/api/v2/test_enhanced_reports.py`, `backend-hormonia/tests/services/test_report_service_task_compat.py`, `backend-hormonia/tests/api/v2/test_private_upload_serving.py`, `backend-hormonia/tests/tasks/test_reports_tasks.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py tests/api/v2/test_private_upload_serving.py tests/tasks/test_reports_tasks.py -q

## Files Likely Touched

- backend-hormonia/tests/api/v2/test_report_ownership_closure.py
- backend-hormonia/tests/api/v2/test_enhanced_reports.py
- backend-hormonia/tests/conftest.py
- backend-hormonia/app/services/reporting/report_access.py
- backend-hormonia/app/api/v2/patients_shared_helpers.py
- backend-hormonia/app/models/report.py
- backend-hormonia/app/models/patient.py
- backend-hormonia/app/api/v2/routers/reports.py
- backend-hormonia/app/api/v2/routers/enhanced_reports.py
- backend-hormonia/app/services/reporting/enhanced_reports_service.py
- backend-hormonia/tests/services/test_report_service_task_compat.py
- backend-hormonia/tests/api/v2/test_private_upload_serving.py
- backend-hormonia/tests/tasks/test_reports_tasks.py
