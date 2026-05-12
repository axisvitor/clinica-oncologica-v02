---
estimated_steps: 21
estimated_files: 7
skills_used: []
---

# T02: Implement public-only static mount and gated upload download

Expected executor task-plan metadata: estimated_steps=10; estimated_files=7; skills_used=[api-design, security-review, tdd, verify-before-complete].

Why: close the upload exposure itself by separating public/private local storage, removing public URLs for private files, and adding the advertised authenticated download route.

Failure Modes (Q5): missing DB record => 404; auth/session failure => 401/403 before file IO; foreign owner => 403 with generic detail; malformed/path-traversal storage path => 404/403 and no filesystem detail; missing local file for authorized upload => 404 and structured ID-only log; Redis/cache outage => fall back to DB; malformed cached metadata => ignore cache and fall back to DB.

Load Profile (Q6): shared resources are filesystem, DB session, optional Redis cache, and upload quota/rate-limit checks. Per operation should be one DB lookup plus streamed file response. At 10x load, DB pool/file descriptor pressure is the first risk; do not read whole download files into memory.

Steps:
1. In upload config, replace import-time `UPLOAD_DIR` usage with runtime helpers based on `settings.UPLOAD_DIRECTORY`: a common upload root, an unmounted private root, and a mounted public root (for example `uploads/private` and `uploads/public`). Ensure helpers create directories lazily and are test-patchable.
2. Update `_setup_static_files()` so `/uploads` mounts only the public root, never the common upload root or private root. Keep startup fail-soft behavior but log only the public mount target.
3. Update `save_upload_file` to accept the `public` flag, store files under the correct root, generate storage paths with a visibility prefix or equivalent unambiguous metadata, and keep filenames UUID/timestamp-safe.
4. Update upload response construction so private uploads set `url` to the gated endpoint (or another non-public gated URL) and `download_url` to `/api/v2/upload/{upload_id}/download`; only intentionally public uploads may return `/uploads/...`.
5. Update image processing so private thumbnails/previews/resized outputs are not exposed as `/uploads/...`; public derivatives may use public URLs under the mounted public root, while private derivative URLs should be omitted or gated.
6. Add `download_upload_handler` and `GET /api/v2/upload/{upload_id}/download` with `get_current_user_object_from_session` and `get_async_db`; stream with `FileResponse` after owner/admin authorization.
7. Centralize upload authorization and path resolution in handler/config helpers: owner or `UserRole.ADMIN` may access; deleted records, missing records, private-static attempts, and unsafe paths fail closed.
8. Pass `db` from `get_upload_info` and `delete_upload` routes to their handlers, and enforce the same owner/admin boundary for metadata and delete operations. Delete should resolve paths with the new safe resolver and should not derive private paths from public URLs.
9. Keep cache behavior non-authoritative: cache hits must still be safe for ownership or be bypassed/revalidated before returning private metadata/downloads.
10. Update logging/error details to avoid original path/filename/PHI leakage; use upload IDs and denial reasons only.

Must-haves:
- No private upload or private derivative is reachable through the public static mount.
- Download route serves bytes only after auth + owner/admin + safe-path checks.
- Existing public uploads still have a coherent `/uploads/...` path if public serving remains supported.
- T01 tests pass without relying on repository-level `uploads/` state.

Done when: the upload boundary tests pass and the application no longer mounts the private upload root.

## Inputs

- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`
- `backend-hormonia/app/config/settings/features.py`
- `backend-hormonia/app/core/application_factory.py`
- `backend-hormonia/app/api/v2/routers/upload/config.py`
- `backend-hormonia/app/api/v2/routers/upload/storage.py`
- `backend-hormonia/app/api/v2/routers/upload/processing.py`
- `backend-hormonia/app/api/v2/routers/upload/handlers.py`
- `backend-hormonia/app/api/v2/routers/upload/__init__.py`
- `backend-hormonia/app/models/upload.py`
- `backend-hormonia/app/models/user.py`
- `backend-hormonia/app/dependencies/auth_dependencies.py`

## Expected Output

- `backend-hormonia/app/config/settings/features.py`
- `backend-hormonia/app/core/application_factory.py`
- `backend-hormonia/app/api/v2/routers/upload/config.py`
- `backend-hormonia/app/api/v2/routers/upload/storage.py`
- `backend-hormonia/app/api/v2/routers/upload/processing.py`
- `backend-hormonia/app/api/v2/routers/upload/handlers.py`
- `backend-hormonia/app/api/v2/routers/upload/__init__.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q

## Observability Impact

Changes runtime diagnostics for upload serving: ID-only structured logs for upload denied/missing/unsafe-path cases, generic HTTP details for clients, and pytest-visible status-code evidence for future agents.
