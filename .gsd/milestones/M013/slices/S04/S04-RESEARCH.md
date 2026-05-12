# S04 Research — Private Upload/Report Serving

## Summary

Depth: targeted/deep security research. This slice owns R006 (private upload access control), R007 (generated patient PDF confidentiality), and R011 (safe failure diagnostics). It produces the private-file boundary consumed by S05.

Key finding: the app mounts the entire upload directory as unauthenticated `/uploads`, while upload responses return `/uploads/{storage_path}` even when `is_public=False`. The advertised gated `download_url` has no corresponding route. Taskiq patient reports write deterministic PDFs into the same public upload tree under `reports/{patient_uuid}_{report_type}.pdf`.

## Prior Decisions / Memory

- M013 private file memory: uploads/reports private by default; serve via authenticated/ownership-checked endpoint or short-lived signed access, not `StaticFiles`.
- PHI boundary memory: no public fallback if ownership cannot be proven.
- Installed skills relevant to this slice: `api-design`, `security-review`, `observability`, `test`, `verify-before-complete`.

## Implementation Landscape

### Static mount and upload storage

- `backend-hormonia/app/core/application_factory.py:214-219` creates `Path(settings.UPLOAD_DIRECTORY)` and mounts the whole directory at `/uploads` via `StaticFiles`. This bypasses all auth dependencies, route checks, audit logging, and `Upload.is_public` metadata.
- `backend-hormonia/app/config/settings/features.py:91` defines `UPLOAD_DIRECTORY` defaulting to `uploads`.
- `backend-hormonia/app/api/v2/routers/upload/config.py:96-97` defines `UPLOAD_DIR = Path(getattr(settings, "UPLOAD_DIR", "uploads"))`; `settings.UPLOAD_DIR` is not defined in the settings scan. In default dev/test this still resolves to `uploads`, but patches of `settings.UPLOAD_DIRECTORY` will not automatically affect upload module import-time `UPLOAD_DIR`.
- `backend-hormonia/app/api/v2/routers/upload/storage.py:89-103` saves files under `UPLOAD_DIR / category / user_id / safe_filename`.
- `backend-hormonia/app/api/v2/routers/upload/handlers.py:254-260` always builds `public_url = f"/uploads/{storage_path}"` and returns it as `url`, regardless of the `public` query flag.
- `_build_upload_response()` at `handlers.py:66-67` also returns `url=f"/uploads/{upload_record.storage_path}"` and `download_url=f"/api/v2/upload/{upload_record.id}/download"` regardless of `is_public`.
- `backend-hormonia/app/models/upload.py:62` has `is_public`, but this is only metadata because static serving ignores it.
- `backend-hormonia/app/middleware/csrf.py:191` skips `/uploads/`, which is reasonable for true public assets but confirms `/uploads` has no route-level security.

### Missing gated upload download

- `backend-hormonia/app/api/v2/routers/upload/__init__.py` exposes POST `/`, GET `/{upload_id}`, DELETE `/{upload_id}`. Static search found no `@router.get("/{upload_id}/download")` even though responses advertise that path.
- `get_upload_info()` at `upload/__init__.py:151-162` does not pass `db` to `get_upload_info_handler(...)`, whose database lookup is optional (`db=None`) at `handlers.py:339-403`; cache misses therefore return 404 even for persisted uploads.
- `delete_upload()` at `upload/__init__.py:181-190` likewise does not pass `db` to `delete_upload_handler(...)`, weakening delete/ownership behavior outside cache.
- `delete_upload_handler()` checks owner-only at `handlers.py:474-479`, but the “admin” comment is not implemented.

### Generated report PDFs

- `backend-hormonia/app/tasks/reports_taskiq.py:96-100` generates PDF bytes and writes them to `Path(settings.UPLOAD_DIRECTORY) / "reports"`.
- `backend-hormonia/app/tasks/helpers/reports_helpers.py:26-28` builds deterministic filenames: `{patient_uuid}_{sanitize(report_type)}.pdf`.
- Because `settings.UPLOAD_DIRECTORY` is statically mounted, those PDFs are reachable as `/uploads/reports/{patient_uuid}_{report_type}.pdf` in the current design.
- Base `/api/v2/reports/{report_id}/download` returns in-memory bytes from Redis via `Response` (`routers/reports.py:575-650`) and is not itself a public static-file path, but S05 must close its missing `generated_by` ownership check.
- Enhanced reports can redirect to stored `download_urls` (`routers/enhanced_reports.py:587-627`); if those URLs are `/uploads/...`, S04/S05 should prevent static private artifacts from being used as report delivery.

## Recommendation

1. Split storage by visibility:
   - private default: `uploads/private/...` or a new `settings.PRIVATE_UPLOAD_DIRECTORY`, never mounted.
   - public optional: `uploads/public/...` mounted at `/uploads` only if true public assets are still needed.
   - avoid module import-time paths for testability; expose `get_upload_root()`/`get_private_upload_root()` or read settings at call time.
2. For private uploads (`public=False`, default):
   - do not return unauthenticated `/uploads/...` in `url`.
   - return only `download_url` (or set `url` equal to the gated endpoint if the schema requires non-null).
   - add `GET /api/v2/upload/{upload_id}/download` with `get_current_user_object_from_session`, `get_async_db`, DB lookup, owner/admin check, path normalization, and `FileResponse`.
3. For public uploads (`public=True`): either save under the mounted public directory and return `/uploads/...`, or keep all uploads gated for M013 and document public serving as deferred. Do not leave private files in the mounted tree.
4. Move Taskiq report outputs out of `settings.UPLOAD_DIRECTORY/reports` and away from deterministic patient filenames. Prefer private report artifact storage keyed by `report.id` or random UUID. If an API must return the file, use a gated endpoint; S05 will add report ownership checks.
5. Avoid leaking filesystem paths/PHI in logs. Log upload/report IDs, not patient names, original full paths, or public URLs for private files.

## Natural Seams / Work Units

1. **Static mount boundary:** `app/core/application_factory.py`; mount only a public subdirectory or remove `/uploads` static mount. Tests must use a freshly created app or patch before app creation.
2. **Upload storage/response:** `upload/config.py`, `upload/storage.py`, `upload/handlers.py`; make public/private path decision and stop returning `/uploads` for private files.
3. **Gated download endpoint:** `upload/__init__.py` plus handler; pass `db` to info/delete handlers while here.
4. **Report artifact path:** `tasks/reports_taskiq.py` and `tasks/helpers/reports_helpers.py`; private non-deterministic file paths.
5. **Regression tests:** private static URL 404, authorized gated download 200, foreign user/admin behavior, report output not under public static tree.

## First Proof

Highest-value failing tests:

- `test_private_upload_response_does_not_return_public_upload_url`: upload with default `public=false`; response has `is_public=false` and no `/uploads/...` private `url`.
- `test_private_upload_static_url_not_served`: create private file under the private root and/or upload it; unauthenticated `GET /uploads/...` returns 404.
- `test_private_upload_download_requires_auth_and_owner`: unauthenticated gated download is 401/403; owner gets file bytes and content type; other doctor/user fails; admin policy if implemented succeeds.
- `test_generated_patient_report_not_written_under_public_uploads`: patch temp private/public dirs, run `generate_patient_report`, assert `output_path` is not inside mounted public upload dir and filename does not include the patient UUID.

## Verification Commands

- `cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q` (new focused file)
- `cd backend-hormonia && pytest tests/tasks/test_reports_tasks.py -q`
- `cd backend-hormonia && pytest tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py -q` (regression if report surfaces touched)

## Forward Intelligence / Watch-outs

- `app.main` creates the FastAPI app at import time, so static mounts are established before many tests run. Static-mount tests may need to instantiate `create_application()` with patched settings or ensure implementation no longer mounts private roots.
- Upload module paths are currently import-time constants. If tests patch directories after import, also patch `upload.config.UPLOAD_DIR`, `upload.storage.UPLOAD_DIR`, and `upload.handlers.UPLOAD_DIR` unless implementation changes to runtime settings lookup.
- Image processing currently emits `/uploads/thumbnails/...`, `/uploads/previews/...`, `/uploads/resized/...` in `upload/processing.py`; private derivatives must not be exposed publicly.
- Do not rely on obscurity of UUID-ish filenames. Generated report filenames currently contain patient UUID and report type; remove both from public paths.
- S04 should produce the gated storage boundary; S05 should close report ownership for direct report APIs.

## Sources

- `backend-hormonia/app/core/application_factory.py`
- `backend-hormonia/app/config/settings/features.py`
- `backend-hormonia/app/api/v2/routers/upload/__init__.py`
- `backend-hormonia/app/api/v2/routers/upload/config.py`
- `backend-hormonia/app/api/v2/routers/upload/storage.py`
- `backend-hormonia/app/api/v2/routers/upload/handlers.py`
- `backend-hormonia/app/api/v2/routers/upload/processing.py`
- `backend-hormonia/app/models/upload.py`
- `backend-hormonia/app/tasks/reports_taskiq.py`
- `backend-hormonia/app/tasks/helpers/reports_helpers.py`
- `backend-hormonia/app/api/v2/routers/reports.py`
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
