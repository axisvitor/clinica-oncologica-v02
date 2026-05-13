# S04: Private Upload/Report Serving

**Goal:** Make local uploads and generated patient report PDFs private by default: `/uploads` must serve only intentionally public assets, private upload responses must use an authenticated gated download URL, and Taskiq-generated patient PDFs must be written to non-public, non-patient-identifying artifact paths.
**Demo:** Private uploads and generated patient PDFs are not reachable through public `/uploads`; authorized gated download works in tests.

## Must-Haves

- Owned requirements: R006 private upload access control, R007 generated patient PDF confidentiality, R011 safe failure diagnostics. Supporting decisions: D003 fail-closed PHI boundaries, D004 private files are application resources, D010 S04 local storage layout.
- Done when:
- Default/private uploads return `is_public=false` and do not return an unauthenticated `/uploads/...` URL in `url`, processing URLs, or `download_url`.
- `GET /uploads/...` cannot retrieve a private upload or private derivative; the FastAPI static mount points only at a public upload subdirectory.
- `GET /api/v2/upload/{upload_id}/download` exists, requires session auth, returns bytes/content type for the owner and admin, and rejects anonymous, foreign-user, deleted, missing, or path-traversal-backed records with generic fail-closed errors.
- Upload info/delete paths receive the DB session and enforce the same owner/admin boundary rather than trusting cache-only metadata.
- Taskiq `generate_patient_report` writes PDFs under a private report-artifact root, not under the mounted public upload root, and the output filename does not include the patient UUID or other patient-identifying filename components.
- Verification passes: `cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q`; `cd backend-hormonia && pytest tests/tasks/test_reports_tasks.py -q`; `cd backend-hormonia && pytest tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py -q`.

## Proof Level

- This slice proves: Contract + integration proof. Real runtime required: yes, via FastAPI/TestClient upload/download/static-file requests and Taskiq report unit tests with temporary storage roots. Human/UAT required: no. Negative proof must exercise anonymous access, foreign-user access, deleted/missing records, path normalization, and public-static denial for private artifacts.

## Integration Closure

Threat Surface (Q3): unauthenticated path guessing under `/uploads`, patient UUID/report-type filename enumeration, cross-user upload ID access, stale cache metadata bypass, and storage-path traversal from persisted records. Sensitive data includes PHI in uploads and generated PDFs; untrusted inputs include filenames, content types, `public` flags, upload IDs, report types, and persisted `storage_path`.

Requirement Impact (Q4): touches R006, R007, R011; re-verify upload API contract, app startup/static mount, image derivative URLs, Taskiq report generation, and enhanced/report service compatibility. Decisions revisited/locked: D003, D004, D010.

Integration closure: S04 consumes existing `app.dependencies.auth_dependencies.get_current_user_object_from_session`, `get_async_db`, `Upload` metadata, local filesystem storage, and Taskiq report generation. It introduces the `/api/v2/upload/{upload_id}/download` route and public/private upload-root wiring. Remaining for S05: report download/export/share/history ownership checks for report IDs and any enhanced-report redirect authorization.

## Verification

- Failure visibility must improve without leaking PHI: upload/download/report logs should use upload_id/report_id/user_id/reason/status and avoid original full filesystem paths, patient names, patient-identifying filenames, tokens, or public URLs for private files. HTTP errors should be generic 401/403/404 messages. Future agents can inspect failing behavior through the focused pytest files and route-level status codes rather than filesystem path dumps.

## Tasks

- [x] **T01: Add private upload serving regression tests** `est:1.5h`
  Expected executor task-plan metadata: estimated_steps=7; estimated_files=1; skills_used=[tdd, security-review, api-design, verify-before-complete].
  - Files: `backend-hormonia/tests/api/v2/test_private_upload_serving.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q

- [x] **T02: Implement public-only static mount and gated upload download** `est:3h`
  Expected executor task-plan metadata: estimated_steps=10; estimated_files=7; skills_used=[api-design, security-review, tdd, verify-before-complete].
  - Files: `backend-hormonia/app/config/settings/features.py`, `backend-hormonia/app/core/application_factory.py`, `backend-hormonia/app/api/v2/routers/upload/config.py`, `backend-hormonia/app/api/v2/routers/upload/storage.py`, `backend-hormonia/app/api/v2/routers/upload/processing.py`, `backend-hormonia/app/api/v2/routers/upload/handlers.py`, `backend-hormonia/app/api/v2/routers/upload/__init__.py`
  - Verify: cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q

- [x] **T03: Move generated patient reports to private non-identifying artifacts** `est:2h`
  Expected executor task-plan metadata: estimated_steps=8; estimated_files=3; skills_used=[security-review, tdd, verify-before-complete].
  - Files: `backend-hormonia/app/tasks/helpers/reports_helpers.py`, `backend-hormonia/app/tasks/reports_taskiq.py`, `backend-hormonia/tests/tasks/test_reports_tasks.py`
  - Verify: cd backend-hormonia && pytest tests/tasks/test_reports_tasks.py -q && pytest tests/api/v2/test_private_upload_serving.py -q && pytest tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py -q

## Files Likely Touched

- backend-hormonia/tests/api/v2/test_private_upload_serving.py
- backend-hormonia/app/config/settings/features.py
- backend-hormonia/app/core/application_factory.py
- backend-hormonia/app/api/v2/routers/upload/config.py
- backend-hormonia/app/api/v2/routers/upload/storage.py
- backend-hormonia/app/api/v2/routers/upload/processing.py
- backend-hormonia/app/api/v2/routers/upload/handlers.py
- backend-hormonia/app/api/v2/routers/upload/__init__.py
- backend-hormonia/app/tasks/helpers/reports_helpers.py
- backend-hormonia/app/tasks/reports_taskiq.py
- backend-hormonia/tests/tasks/test_reports_tasks.py
