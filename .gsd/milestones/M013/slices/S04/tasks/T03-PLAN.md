---
estimated_steps: 18
estimated_files: 3
skills_used: []
---

# T03: Move generated patient reports to private non-identifying artifacts

Expected executor task-plan metadata: estimated_steps=8; estimated_files=3; skills_used=[security-review, tdd, verify-before-complete].

Why: generated patient PDFs currently use deterministic patient UUID/report-type filenames under the public upload tree; S04 must make report artifacts private before S05 closes report-ID ownership surfaces.

Failure Modes (Q5): invalid patient UUID => existing failed result without writing a file; private report root unavailable => task logs ID-only failure and raises/retries; PDF generation failure => no partial public artifact; malformed report type => sanitized fallback; path traversal attempt through report type => output remains inside private report root.

Load Profile (Q6): shared resources are DB scoped session, ReportService, filesystem private report directory, and Taskiq retries. Per operation writes one PDF; at 10x load disk space and concurrent report generation are the first risks. Avoid public deterministic overwrites by using a report ID or random artifact ID.

Steps:
1. Reuse the S04 private storage helper from `backend-hormonia/app/api/v2/routers/upload/config.py` or add an equivalent runtime helper in the report helper module that resolves under `settings.UPLOAD_DIRECTORY/private/reports`.
2. Change `_build_safe_report_path` so output filenames no longer include `patient_uuid`; prefer a random UUID artifact id or generated report id plus a sanitized report type, with `.pdf` extension and a resolve/parents guard.
3. Update `generate_patient_report` to write PDFs to the private report-artifact root rather than `Path(settings.UPLOAD_DIRECTORY) / "reports"`.
4. Ensure report task logs do not emit full filesystem paths or patient-identifying filenames; log task name, report_id, and generic failure reason.
5. Extend `backend-hormonia/tests/tasks/test_reports_tasks.py` to assert the output file exists under the private report root, is not inside the public static root, and `UUID(patient_id)`/raw `patient_id` is absent from the output filename.
6. Add helper-level tests for report type sanitization/path traversal if not already covered by the task-level test.
7. Run the focused report task tests.
8. Run the upload private-serving tests again to ensure shared private-root helpers remain compatible.

Must-haves:
- Generated patient report PDFs are never written under the mounted public upload root.
- Output filenames do not contain patient UUIDs and cannot be influenced into leaving the private report root.
- Existing Taskiq report behavior still returns `status`, `report_id`, and `output_path` for successful generation.

Done when: report task tests prove private, non-identifying report artifact storage and the S04 upload tests still pass.

## Inputs

- `backend-hormonia/app/tasks/helpers/reports_helpers.py`
- `backend-hormonia/app/tasks/reports_taskiq.py`
- `backend-hormonia/tests/tasks/test_reports_tasks.py`
- `backend-hormonia/app/api/v2/routers/upload/config.py`
- `backend-hormonia/app/config/settings/features.py`
- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`
- `backend-hormonia/tests/services/test_report_service_task_compat.py`

## Expected Output

- `backend-hormonia/app/tasks/helpers/reports_helpers.py`
- `backend-hormonia/app/tasks/reports_taskiq.py`
- `backend-hormonia/tests/tasks/test_reports_tasks.py`

## Verification

cd backend-hormonia && pytest tests/tasks/test_reports_tasks.py -q && pytest tests/api/v2/test_private_upload_serving.py -q && pytest tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py -q

## Observability Impact

Report-generation diagnostics should remain useful but PHI-safe: logs identify task/report status and IDs without exposing patient-identifying filenames, public URLs, or private filesystem paths.
