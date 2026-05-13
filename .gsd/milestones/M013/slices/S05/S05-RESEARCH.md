# S05 Research — Report Ownership Closure

## Summary

Depth: targeted/deep security research. S05 owns R008 and supports R007/R010/R011. The codebase already has strong S02/S04 ownership patterns, but report APIs remain mostly cache-backed and permissive.

Key finding: direct base report download trusts any authenticated user who knows a UUID, and enhanced report download/export/share/history use `_check_report_access()` helpers that currently allow any authenticated non-admin. Several direct read/download endpoints do not call even that permissive helper. S05 should add one shared report-access proof step that checks admin, raw report owner metadata (`generated_by`/`created_by`), and patient assignment where patient IDs are present, before data formatting, redirect, sharing, export creation, history, or restore.

Also note the current verification failure is path-related, not a missing S04 file: tests live under `backend-hormonia/tests/...`; from the repository root, use prefixed pytest paths or run inside `backend-hormonia`.

## Active Requirements / Scope

- **R008 (primary):** Downloads, exports, sharing and history for report IDs must validate ownership or patient assignment before returning data.
- **R010 (support):** Add reusable two-doctor/two-patient negative authorization proof for report surfaces.
- **R011 (support):** Denials must fail closed with ID/status/reason diagnostics only; no PHI, private paths, tokens, or public private-file URLs.
- **R007 (support/watch-out):** Report artifacts are private after S04; S05 must not reintroduce public `/uploads` private report URLs via export redirects or download URLs.

## Prior Decisions / Memory

- MEM002/M013 decision: use shared auth/role/patient-ownership helpers instead of endpoint-only patches.
- MEM004/MEM029: private uploads/reports are application resources, not public static assets; report access must go through authz-aware endpoints.
- MEM020: patient-bound routes should call `load_patient_with_access` before DB/cache/service reads.
- MEM035/MEM036/MEM037/MEM038: report artifact names/logs should be opaque/allowlisted and PHI-safe; sanitized free-form strings are not redaction.
- MEM039 captured during this research: do not authorize against normalized enhanced-report metadata that defaults missing `created_by` to the current requester.

## Skill Discovery

Installed/relevant skills from the prompt: `api-design`, `observability`, `security-review`, `test`, `verify-before-complete`. No external library docs are needed; this is local FastAPI/SQLAlchemy/Redis-cache wiring.

Promising optional skills found via `npx skills find` (do not install automatically):

- FastAPI: `npx skills add wshobson/agents@fastapi-templates` (16.8K installs), `npx skills add mindrally/skills@fastapi-python` (8.5K installs), `npx skills add jeffallan/claude-skills@fastapi-expert` (2.9K installs).
- SQLAlchemy: `npx skills add bobmatnyc/claude-mpm-skills@sqlalchemy-orm` (871 installs), `npx skills add wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` (791 installs).
- Redis: `npx skills add redis/agent-skills@redis-development` (2.7K installs), `npx skills add mindrally/skills@redis-best-practices` (1.5K installs).

## Implementation Landscape

### Base reports router

- `backend-hormonia/app/api/v2/routers/reports.py` is Redis/cache-oriented and mounted at `/api/v2/reports`.
- `_check_patient_access()` at `reports.py:168-184` already counts `Patient.id` where `Patient.doctor_id == user_id`, but it is not used for current generation/download paths.
- `generate_report()` parses `patient_ids` at `reports.py:514-522`, but the comment says access checks are intentionally skipped. That means a doctor can create metadata for foreign patient IDs unless S05 closes it.
- `generate_report()` stores `generated_by` at `reports.py:529-541`, but does not store parsed `patient_ids` in the cached report record. `_generate_report_async()` also writes pending/completed records with `generated_by` but no patient IDs at `reports.py:232-285`.
- `download_report()` at `reports.py:565-650` checks auth and report status, then formats and returns the report data. It never checks `report.generated_by`, patient IDs, or admin before returning JSON/CSV/Excel/PDF bytes.
- `list_reports()` filters cached reports to `generated_by == user_id` at `reports.py:411-416` for everyone, including admins. This is less critical than direct download, but the helper should keep list/download semantics consistent if touched.

### Enhanced reports router

- `backend-hormonia/app/api/v2/routers/enhanced_reports.py` is mounted at `/api/v2/enhanced-reports` and fronts builder, visualization, delivery, sharing, export, history/restore, and dashboards.
- Router `_check_report_access()` at `enhanced_reports.py:133-139` allows admins and then returns `user_id is not None` for everyone else. It does not inspect report ownership or patient assignment.
- `get_builder_report()` and `download_builder_report()` at `enhanced_reports.py:309-367` do not perform ownership checks before returning cached or service-loaded report data.
- `_normalize_builder_response()` at `enhanced_reports.py:147-166` fills `created_by` from the current requester when cached data lacks owner metadata. Authorization must inspect raw cached/DB metadata before normalization, or a foreign user can become the apparent owner.
- `create_visualization()`, `create_delivery_schedule()`, `share_report()`, `create_public_link()`, `list_report_shares()`, `export_multi_format()`, `get_report_history()`, and `restore_report_version()` call `_check_report_access()`, but the helper is permissive.
- `get_export_status()` at `enhanced_reports.py:576-586` and `download_export()` at `enhanced_reports.py:589-640` do not check ownership before returning export metadata, inline bytes, or redirecting to `download_url`.
- `download_export()` can redirect to any cached `download_urls[format]`. S04 prevents private static serving, but S05 should still authorize before redirect and avoid creating a new public private-file URL path.
- `revoke_share()` at `enhanced_reports.py:544-550` is currently a no-op by `share_id` and returns no data. If share persistence is added, it must resolve `share_id -> report_id` and reuse the report guard.

### Enhanced reports service

- `backend-hormonia/app/services/reporting/enhanced_reports_service.py` has a second `_check_report_access()` at lines `60-66`; it currently returns `True` for every non-admin.
- `build_custom_report()` at `enhanced_reports_service.py:109-148` returns `created_by`, but does not persist the builder record to the cache key that later direct GET/download paths expect. This makes legitimate follow-up owner operations hard to prove without test monkeypatches.
- `share_report()`, `create_public_link()`, `export_multi_format()`, `get_report_history()`, and `restore_report_version()` repeat the permissive service check at `enhanced_reports_service.py:266-383`.
- `export_multi_format()` returns `export_id`, `report_id`, and status but does not persist `created_by`/owner metadata. Direct export status/download therefore needs either persisted export metadata or a lookup back to the report metadata.

### Models/repositories and existing ownership helpers

- `backend-hormonia/app/models/report.py` defines `MedicalReport(patient_id, generated_by)` and generic `Report(patient_id, ...)`. Generic `Report` has no `generated_by`, so patient assignment is the safe fallback there.
- `backend-hormonia/app/repositories/report.py` can query `MedicalReport` by `patient_id` or `generated_by`, but no direct API currently uses it for report-ID authorization.
- `backend-hormonia/app/api/v2/patients_shared_helpers.py:139-224` provides the preferred S02 helper: `assert_admin_or_assigned_doctor()` and `load_patient_with_access()`. Use the same fail-closed pattern and generic 403/404 details.
- `backend-hormonia/tests/api/v2/security_boundary_helpers.py` already creates doctor A, doctor B, admin, patient A/B, and auth override helpers. It is a good base for R010 report proof.
- `backend-hormonia/app/api/v2/routers/upload/handlers.py:74-103` is a compact owner/admin authorization pattern with ID/reason-only structured logging; report denials can mirror this shape (`report_id`, `user_id`, `reason`, `status`).

## Recommendation

1. **Create one report-access helper** (e.g. `app/api/v2/report_access.py` or a router-local helper if the team wants minimal surface) that operates on raw report/export metadata before normalization/formatting:
   - Extract strict `(role, user_uuid)`; do not default malformed roles to doctor for the authorization decision.
   - Admin passes.
   - Extract owner IDs from `generated_by`, `created_by`, `user_id`, `owner_id` as UUIDs.
   - Extract patient IDs from `patient_id`, `patient_ids`, and known filter locations such as `filters.patient_id` / `filters.patient_ids` where applicable.
   - If patient IDs are present, require all of them to be assigned to the doctor (or admin). This closes the current `generate_report()` foreign-patient gap and prevents historical/corrupt cache metadata with `generated_by=current_user` from authorizing foreign patient PHI.
   - If no patient IDs are present, allow current owner (`generated_by`/`created_by`) as the proof for non-patient/general reports.
   - If no proof can be established, fail closed with generic 403/404 and log only IDs/reason/status.
2. **Base reports:**
   - In `generate_report()`, validate parsed `patient_ids` through `_check_patient_access()` or the new shared helper before caching/scheduling.
   - Persist `patient_ids` into pending/completed cached records and pass them into `_generate_report_async()`.
   - In `download_report()`, call the report-access helper after loading raw cached report metadata and before status/data/format handling.
3. **Enhanced reports:**
   - Replace both permissive `_check_report_access()` functions with an async check that loads raw report metadata from cache and/or service before allowing report-bound operations.
   - Persist builder report metadata (`created_by`, `filters`, any extracted `patient_ids`) when `build_custom_report()` returns, using the same key(s) the router/service will later read. At minimum, make tests seed the raw cache shape that the guard expects.
   - Guard `get_builder_report()`, `download_builder_report()`, `share_report()`, `create_public_link()`, `list_report_shares()`, `export_multi_format()`, `get_export_status()`, `download_export()`, `get_report_history()`, and `restore_report_version()` before returning data or redirects.
   - For export status/download, authorize against the export record's `report_id` plus `created_by`, or load the underlying report metadata by `report_id` before returning metadata/bytes/redirects.
4. **Testing:** add a focused `backend-hormonia/tests/api/v2/test_report_ownership_closure.py` instead of trying to stretch existing happy-path `test_enhanced_reports.py`. Keep existing tests passing by adding explicit `created_by`/`generated_by` to their cached mocks or by adjusting them to the new secure contract.
5. **Diagnostics:** add `report_access_denied`/`report_lookup_not_found` logs with `report_id`, `export_id` where relevant, `user_id`, `role`, `reason`, and `status`. Do not log report titles, report data, patient names, full private paths, tokens, or download URLs.

## Natural Seams / Work Units

1. **Shared report access helper and unit tests**
   - Files: new `backend-hormonia/app/api/v2/report_access.py` (or equivalent), tests under `backend-hormonia/tests/unit/api/v2/`.
   - Purpose: parse raw metadata, strict user context, owner IDs, patient IDs, all-patients-assigned DB check, generic denial/logging.
   - Independent enough to build/test first.
2. **Base `/api/v2/reports` closure**
   - Files: `backend-hormonia/app/api/v2/routers/reports.py` plus focused route tests.
   - Purpose: validate generation `patient_ids`, persist patient metadata, guard direct download before formatting.
3. **Enhanced report operation guard**
   - Files: `backend-hormonia/app/api/v2/routers/enhanced_reports.py`, `backend-hormonia/app/services/reporting/enhanced_reports_service.py`.
   - Purpose: replace permissive checks, guard direct builder/download/share/export/history/restore operations, persist/lookup owner metadata.
4. **Focused cross-doctor proof**
   - Files: new `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`, possibly reuse `tests/api/v2/security_boundary_helpers.py`.
   - Purpose: doctor A cannot use doctor B report IDs; owner and admin still work; response bodies do not include secret report data or patient B PHI.
5. **Regression compatibility cleanup**
   - Files: `backend-hormonia/tests/api/v2/test_enhanced_reports.py`, `backend-hormonia/tests/services/test_report_service_task_compat.py` if needed.
   - Purpose: remove tests' reliance on permissive access patching/default owner normalization; keep existing positive paths explicit.

## First Proof

Write the failing tests first. The highest-value failures are:

- Base direct download: cached completed report with `generated_by=doctor_b.id` and data containing a sentinel secret. Doctor A GET `/api/v2/reports/{report_id}/download` must return 403/404 and not include the sentinel; doctor B and admin get 200.
- Base patient assignment: cached completed report with `patient_ids=[patient_b.id]` and no usable current-owner metadata. Doctor A denied, doctor B/admin allowed.
- Enhanced builder download: raw cached builder report with `created_by=doctor_b.id` and `data=[{"secret": ...}]`. Doctor A GET `/api/v2/enhanced-reports/builder/{builder_id}/download?format=csv` must be denied before CSV rendering; doctor B/admin allowed.
- Enhanced sharing/export/history: doctor A cannot `POST /sharing`, `POST /sharing/public-link`, `POST /export`, `GET /reports/{report_id}/history`, or `GET /export/{export_id}/download` for a report/export owned by doctor B or bound to patient B. Owner/admin remain successful.
- PHI-safe denial: foreign responses must not contain patient B name, report data sentinel, private paths, tokens, or public private-file URLs.

## Verification Commands

From repository root (current no-`cd` policy), use prefixed paths:

- `pytest backend-hormonia/tests/api/v2/test_report_ownership_closure.py -q`
- `pytest backend-hormonia/tests/api/v2/test_enhanced_reports.py backend-hormonia/tests/services/test_report_service_task_compat.py -q`
- `pytest backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/tasks/test_reports_tasks.py -q`

If running from inside `backend-hormonia`, the equivalent paths are `tests/...`. The automated failure that triggered this research used `pytest tests/...` from the repository root, so pytest could not find the backend test files.

Expected existing warning: pytest-asyncio emits the `asyncio_default_fixture_loop_scope` deprecation warning; prior slices considered it unrelated.

## Forward Intelligence / Watch-outs

- **Fail closed before normalization.** Enhanced normalizers can synthesize `created_by` from the current user; never authorize on normalized data.
- **Cache key drift exists.** Router `_build_cache_key("builder", id)` differs from service `RedisJsonCacheMixin._get_cache_key(...)`. Decide one lookup contract or check both in the access helper, otherwise legitimate owner tests will need heavy monkeypatching.
- **Generation must be fixed with download.** If `generate_report()` still accepts foreign `patient_ids`, a simple `generated_by == current_user` check can authorize malicious cached foreign-patient reports later.
- **Patient-scoped reports should prefer assignment proof.** Owner-only is acceptable for non-patient/general reports; when patient IDs are present, prove assignment/admin to avoid PHI leakage from bad historical metadata.
- **Do not broaden public artifacts.** `download_export()` redirects should be authorized first and should not expose private report artifacts via public `/uploads` URLs.
- **Existing tests patch `_check_report_access`.** New tests should exercise real guards. Old tests may need explicit owner metadata instead of patching the guard to `True` for every report.
- **Status code choice:** S04 uses 403 for authenticated foreign owner and 404 for missing/deleted. Mirroring that is consistent; tests can allow 403/404 only where anti-enumeration is intentionally chosen.

## Sources

- `.gsd/REQUIREMENTS.md`
- `backend-hormonia/app/api/v2/routers/reports.py`
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/app/services/reporting/enhanced_reports_service.py`
- `backend-hormonia/app/models/report.py`
- `backend-hormonia/app/repositories/report.py`
- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/app/api/v2/routers/upload/handlers.py`
- `backend-hormonia/app/schemas/v2/enhanced_reports.py`
- `backend-hormonia/app/schemas/v2/reports.py`
- `backend-hormonia/tests/api/v2/security_boundary_helpers.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`
- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`
- `frontend-hormonia/src/lib/api-client/reports.ts`
