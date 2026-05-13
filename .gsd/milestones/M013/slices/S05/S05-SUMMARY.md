---
id: S05
parent: M013
milestone: M013
provides:
  - Validated R008 ownership closure for downloads, exports, sharing, public-link/share listing, builder read/download, history, restore, and direct report generation/download surfaces.
  - Reusable two-doctor/two-patient negative authorization tests for S06 evidence matrix assembly.
  - Shared raw report access guard and closed-denial metadata parsing pattern for future report routes.
  - Regression proof that S04 private upload/report serving remains intact after S05 changes.
requires:
  - slice: S02
    provides: Patient ownership/assigned-doctor authorization pattern and negative two-doctor fixture approach.
  - slice: S04
    provides: Private upload/report storage boundary and private serving regression tests consumed by the integrated proof suite.
affects:
  - S06: Integrated Security Proof
key_files:
  - backend-hormonia/app/services/reporting/report_access.py
  - backend-hormonia/app/api/v2/routers/reports.py
  - backend-hormonia/app/api/v2/routers/enhanced_reports.py
  - backend-hormonia/app/services/reporting/enhanced_reports_service.py
  - backend-hormonia/tests/api/v2/test_report_ownership_closure.py
  - backend-hormonia/tests/api/v2/test_enhanced_reports.py
key_decisions:
  - Centralize report access checks in a raw-metadata helper that denies before normalization, formatting, service work, redirects, or export URL disclosure.
  - Persist builder/export ownership evidence under both legacy and service cache keys so compatibility paths can still authorize from raw metadata.
  - Withhold unsafe private artifact URLs from export status responses and reject unsafe/private redirect destinations before download responses are returned.
  - Use API route tests with in-memory Redis/fake service seams to prove ownership behavior without production stubs.
patterns_established:
  - Use `report_access.assert_report_access` for any report_id/export_id route before data shaping, service calls, or redirects.
  - Treat cached report/export metadata as untrusted input and parse owner/patient evidence strictly before relying on it.
  - Deny report access with PHI-safe diagnostics only: IDs/status/reason-style fields are acceptable; patient names, report data, private paths, tokens, and private URLs are not.
  - Run backend verification commands with `cd backend-hormonia && ...` because test paths are backend-root relative.
observability_surfaces:
  - PHI-safe report access denial logging in the shared report access guard.
  - Focused caplog/route assertions in `tests/api/v2/test_report_ownership_closure.py` that verify denial hygiene and URL leakage prevention.
drill_down_paths:
  - .gsd/milestones/M013/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M013/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M013/slices/S05/tasks/T03-SUMMARY.md
  - .gsd/milestones/M013/slices/S05/tasks/T04-SUMMARY.md
  - .gsd/milestones/M013/slices/S05/tasks/T05-SUMMARY.md
  - .gsd/milestones/M013/slices/S05/tasks/T06-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-05-13T02:40:39.586Z
blocker_discovered: false
---

# S05: Report Ownership Closure

**Closed report-ID ownership gaps across base and enhanced report generation, download, builder, share, history, restore, export status/download, and private-artifact redirect surfaces.**

## What Happened

S05 added a reusable report ownership closure proof and routed report-ID authorization through a shared raw-metadata guard. T01 introduced route-level regression coverage with two-doctor/two-patient negative cases, owner/admin success paths, anonymous/foreign/missing-evidence denial cases, and redirect-history assertions that prevent private URL/token leakage. T02 created `app/services/reporting/report_access.py`, which parses untrusted raw `generated_by`, `created_by`, owner and patient metadata, falls back to DB evidence where appropriate, validates patient assignment, and logs only PHI-safe denial diagnostics. T03 applied the guard to base report generation/download/status paths so foreign `patient_ids` are rejected before report creation/cache disclosure and raw cached ownership evidence is required before returning report bytes or formatted data. T04 applied the same guard to enhanced builder, sharing/public-link/share listing, history/restore, delivery/visualization, and report-ID routes before normalization, service work, or redirects; builder ownership evidence is persisted under legacy and service cache keys so later checks can resolve raw evidence. T05 closed export status/download by persisting export ownership evidence, authorizing export IDs before response shaping, withholding unsafe legacy private artifact URLs from status responses, and denying redirects to `/uploads`, file, data, or javascript-style private/unsafe URLs. T06 and closeout reran the integrated proof suite from `backend-hormonia`, confirming S05 report ownership tests, enhanced report compatibility, report service task compatibility, S04 private upload serving regressions, and report task regressions pass together. R008 was updated to validated; R010/R011 were advanced for S06 evidence consolidation.

## Verification

Fresh closeout verification used the required backend working directory and passed. Evidence: (1) `gsd_exec` 8b04624b-47bc-4ac0-b1de-ab67f2dc407a ran `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -q` with exit code 0; stdout showed 11 focused report ownership tests reaching 100%. (2) `gsd_exec` 5bae543c-9ec1-453d-b9a1-e0816528d2d3 ran `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py tests/api/v2/test_private_upload_serving.py tests/tasks/test_reports_tasks.py -q` with exit code 0; stdout showed 66 integrated tests reaching 100%. Existing stderr on both commands is the known `pytest-asyncio` deprecation warning for unset `asyncio_default_fixture_loop_scope`; it does not affect the pass result.

## Requirements Advanced

- R007 — Re-ran S04 private upload/report serving regressions in the integrated S05 command to preserve private serving boundaries; final R007 validation remains reserved for its separate naming follow-up.
- R010 — Added reusable two-doctor/two-patient negative report ownership proof cases for S06's milestone-wide isolation matrix.
- R011 — Standardized PHI-safe report access denial diagnostics and verified that unauthorized export/download/share responses do not leak private paths, URLs, tokens, or report data.

## Requirements Validated

- R008 — Focused and integrated pytest gates passed from `backend-hormonia`, proving report download/export/share/history/builder/restore surfaces validate owner or patient assignment before returning data, redirects, or URLs.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

Closeout reran the suite from `backend-hormonia` because backend test paths are backend-root relative. No source or test edits were made during closeout.

## Known Limitations

The pytest suite still emits the existing `pytest-asyncio` deprecation warning about unset `asyncio_default_fixture_loop_scope`. Runtime server/manual UAT and final F-01..F-11 evidence matrix are reserved for S06. R007 remains active because its separate opaque/allowlisted generated filename follow-up is not closed by S05.

## Follow-ups

S06 should assemble the consolidated critical/high finding evidence matrix, include the S05 command evidence and MEM047/MEM048 context, and explicitly list medium/proof-gap/observability follow-ups. A later cleanup can set `asyncio_default_fixture_loop_scope` in pytest configuration to remove the warning.

## Files Created/Modified

- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py` — New/expanded focused regression proof for base/enhanced report ownership, PHI-safe denials, export leakage, and private redirect hygiene.
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py` — Updated enhanced report fixtures and compatibility expectations for raw owner/export metadata and safe export status responses.
- `backend-hormonia/app/services/reporting/report_access.py` — Shared raw report access guard with strict owner/patient evidence parsing, DB fallback, assignment authorization, closed-denial behavior, and PHI-safe logging.
- `backend-hormonia/app/api/v2/routers/reports.py` — Base report generation/download/status paths now validate patient assignment and raw report ownership before report creation, cache disclosure, or payload formatting.
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py` — Enhanced builder, share/public-link/share listing, history, restore, delivery/visualization, export status, and export download routes now authorize before normalization, service work, or redirects.
- `backend-hormonia/app/services/reporting/enhanced_reports_service.py` — Enhanced builder/export service metadata now persists raw ownership evidence across service and legacy cache keys and avoids unsafe private artifact URL disclosure.
