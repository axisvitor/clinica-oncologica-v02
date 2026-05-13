---
id: S04
parent: M013
milestone: M013
provides:
  - Private-by-default local upload storage and gated private download route
  - Public-only /uploads static mount boundary
  - Private non-identifying Taskiq patient report artifact storage
  - PHI-safe upload/download/report failure diagnostics
requires:
  []
affects:
  - backend upload API responses and download/delete/info authorization
  - FastAPI static upload mount wiring
  - Taskiq patient report artifact generation
  - Report/upload regression test suites
key_files:
  - backend-hormonia/tests/api/v2/test_private_upload_serving.py
  - backend-hormonia/app/api/v2/routers/upload/config.py
  - backend-hormonia/app/api/v2/routers/upload/storage.py
  - backend-hormonia/app/api/v2/routers/upload/processing.py
  - backend-hormonia/app/api/v2/routers/upload/handlers.py
  - backend-hormonia/app/api/v2/routers/upload/__init__.py
  - backend-hormonia/app/core/application_factory.py
  - backend-hormonia/app/models/upload.py
  - backend-hormonia/alembic/versions/m013_s04_upload_deleted_at.py
  - backend-hormonia/app/tasks/helpers/reports_helpers.py
  - backend-hormonia/app/tasks/reports_taskiq.py
  - backend-hormonia/tests/tasks/test_reports_tasks.py
key_decisions:
  - D011: Mount only the public upload root at /uploads; store private files under an unmounted private root with private/... logical paths and serve them through the gated download route.
  - Generated patient report PDFs use private upload-root-backed report artifact storage and report_id-based sanitized filenames instead of patient UUID/report-type paths under the public upload tree.
  - Report-generation logs omit full filesystem paths, patient IDs, and patient-identifying filenames while retaining task/report IDs, status, report type, and generic reasons for diagnostics.
patterns_established:
  - Resolve upload storage through shared public/private root helpers and serve private files through application authorization, never the static mount.
  - Build patient report artifact names from report_id plus sanitized report_type and guard resolved output paths with relative_to(private_root).
  - Keep PHI-sensitive failure visibility ID-based and generic: upload_id/report_id/user_id/reason/status without private filesystem paths or patient identifiers.
observability_surfaces:
  - Focused pytest suites: tests/api/v2/test_private_upload_serving.py and tests/tasks/test_reports_tasks.py
  - Upload/download/report structured log fields: upload_id, report_id, user_id, task_name, reason, status, sanitized report_type
  - Generic route-level HTTP status codes for unauthorized, forbidden, missing, and unsafe private file records
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-05-13T01:10:50.287Z
blocker_discovered: false
---

# S04: Private Upload/Report Serving

**Made local uploads and Taskiq patient report PDFs private by default, with public-only /uploads, authenticated gated private downloads, and report-id-based private PDF artifacts.**

## What Happened

S04 closed the local PHI exposure boundary across upload serving and generated report artifacts. T01 added FastAPI regression coverage for private upload defaults, public static denial, owner/admin gated downloads, DB metadata fallback, missing IDs, unsafe storage paths, and generic errors. T02 split local upload storage into a mounted public root and an unmounted private root, changed private upload responses to use /api/v2/upload/{upload_id}/download, enforced owner/admin authorization from DB-backed metadata, denied anonymous/foreign/deleted/missing/path-traversal-backed records with generic responses, removed public URLs for private derivatives, and added the Upload.deleted_at mapping plus migration needed by the route contract. T03 moved Taskiq-generated patient PDFs into the private report artifact root, built report filenames from generated report IDs plus sanitized report types, guarded output paths against traversal, preserved the status/report_id/output_path success contract, and kept report diagnostics PHI-safe by avoiding patient IDs, full filesystem paths, patient-identifying filenames, and public private-file URLs in logs.

## Verification

Automated slice verification passed. Commands run from backend-hormonia: (1) pytest tests/api/v2/test_private_upload_serving.py -q — 7 tests passed during T01/T02 verification; (2) pytest tests/tasks/test_reports_tasks.py -q && pytest tests/api/v2/test_private_upload_serving.py -q && pytest tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py -q — 10 report task tests, 7 private upload serving tests, and 38 enhanced report/report-service compatibility tests passed on the final T03 verification run. The final combined command exited 0 in 79229ms.

## Requirements Advanced

- R006 — Private upload access control enforced through DB-backed owner/admin authorization and gated download route.
- R007 — Generated patient PDFs now land in private report artifact storage with non-identifying report_id filenames.
- R011 — Diagnostics remain useful through IDs/status/reason while avoiding PHI, private paths, tokens, and public private-file URLs.

## Requirements Validated

- R006 — tests/api/v2/test_private_upload_serving.py passed, covering default-private responses, public static denial, owner/admin access, and anonymous/foreign/deleted/missing/unsafe path denials.
- R007 — tests/tasks/test_reports_tasks.py passed, covering private report root placement, non-patient filenames, sanitized report types, and traversal-resistant paths.
- R011 — Focused tests assert generic HTTP errors and absence of patient IDs/output paths in report task logs.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

Failure visibility improved without PHI leakage. Upload/download/report diagnostics use upload_id, report_id, user_id, reason, status, task name, and sanitized report_type where applicable. HTTP errors remain generic 401/403/404-style responses, and logs avoid original full filesystem paths, patient names, patient-identifying filenames, tokens, and public URLs for private files. Future agents can inspect behavior through backend-hormonia/tests/api/v2/test_private_upload_serving.py, backend-hormonia/tests/tasks/test_reports_tasks.py, route-level status codes, and PHI-safe structured log fields.

## Deviations

T02 added Upload.deleted_at, an Alembic migration, and a test schema guard beyond the original implementation file list because the DB-backed owner/admin and deleted-record route contract depends on that soft-delete column.

## Known Limitations

The existing pytest-asyncio deprecation warning about asyncio_default_fixture_loop_scope still appears in focused test output and is unrelated to this slice.

## Follow-ups

S05 should close the remaining report-ID ownership surfaces for report download/export/share/history paths and any enhanced-report redirect authorization.

## Files Created/Modified

- `backend-hormonia/tests/api/v2/test_private_upload_serving.py` — Regression coverage for private upload/default/static/download/error behavior.
- `backend-hormonia/app/api/v2/routers/upload/config.py` — Public/private upload root helpers.
- `backend-hormonia/app/api/v2/routers/upload/storage.py` — Visibility-aware local storage paths and URL behavior.
- `backend-hormonia/app/api/v2/routers/upload/processing.py` — Private derivative handling without public URLs.
- `backend-hormonia/app/api/v2/routers/upload/handlers.py` — DB-backed owner/admin download, info, and delete authorization with generic errors.
- `backend-hormonia/app/api/v2/routers/upload/__init__.py` — Advertised private download route wiring.
- `backend-hormonia/app/core/application_factory.py` — Static mount now points only at the public upload root.
- `backend-hormonia/app/models/upload.py` — Mapped deleted_at for deleted-record access checks.
- `backend-hormonia/alembic/versions/m013_s04_upload_deleted_at.py` — Migration for Upload.deleted_at.
- `backend-hormonia/app/tasks/helpers/reports_helpers.py` — Private report artifact root, sanitized report types, and traversal-resistant report paths.
- `backend-hormonia/app/tasks/reports_taskiq.py` — Taskiq report generation writes private non-identifying artifacts and logs PHI-safe contexts.
- `backend-hormonia/tests/tasks/test_reports_tasks.py` — Report task tests for private artifact placement, non-identifying filenames, sanitization, and PHI-safe logs.
