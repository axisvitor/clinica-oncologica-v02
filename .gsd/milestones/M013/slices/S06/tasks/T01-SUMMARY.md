---
id: T01
parent: S06
milestone: M013
key_files:
  - backend-hormonia/app/tasks/helpers/reports_helpers.py
  - backend-hormonia/app/tasks/reports_taskiq.py
  - backend-hormonia/tests/tasks/test_reports_tasks.py
key_decisions:
  - Report task artifacts use report-id-only `{report_id}.pdf` filenames; generate_patient_report diagnostics omit free-form report_type values and retain task_name/report_id/status/reason/failure_type observability only.
duration: 
verification_result: passed
completed_at: 2026-05-13T03:05:46.246Z
blocker_discovered: false
---

# T01: Made generated report artifacts and report-task diagnostics opaque to free-form report_type input.

**Made generated report artifacts and report-task diagnostics opaque to free-form report_type input.**

## What Happened

Added failing-first coverage for report_type values containing traversal segments, patient-name-like text, phone/token-like fragments, and invalid-patient input. Updated report artifact path construction so generated PDFs are written as `{report_id}.pdf` under the private report artifact root while preserving the resolved-path traversal guard. Removed raw and sanitized report_type from generate_patient_report start, validation, success, and failure diagnostics; scheduled reports still pass the original report_type through the task API for dispatch compatibility, but filename and log surfaces no longer expose it.

## Verification

Ran the focused task suite with `cd backend-hormonia && pytest tests/tasks/test_reports_tasks.py -q`. The final run exited 0 and exercised helper path construction, successful report generation, invalid patient handling without artifact directory creation, PHI/sentinel report_type non-exposure in output paths and caplog/structured records, and scheduled report dispatch compatibility.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && pytest tests/tasks/test_reports_tasks.py -q` | 0 | ✅ pass | 27236ms |

## Deviations

None.

## Known Issues

The focused pytest run still emits an existing pytest-asyncio deprecation warning about `asyncio_default_fixture_loop_scope` being unset; it does not affect this task's pass/fail result.

## Files Created/Modified

- `backend-hormonia/app/tasks/helpers/reports_helpers.py`
- `backend-hormonia/app/tasks/reports_taskiq.py`
- `backend-hormonia/tests/tasks/test_reports_tasks.py`
