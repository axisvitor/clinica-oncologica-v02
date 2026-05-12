---
estimated_steps: 16
estimated_files: 1
skills_used: []
---

# T01: Add private upload serving regression tests

Expected executor task-plan metadata: estimated_steps=7; estimated_files=1; skills_used=[tdd, security-review, api-design, verify-before-complete].

Why: lock the S04 security contract before changing storage/runtime wiring so implementation cannot accidentally keep public private-file URLs.

Threat/negative coverage (Q3/Q7): anonymous `/uploads` guessing, anonymous gated download, foreign-user upload ID access, owner/admin allowed paths, deleted/missing upload IDs, path traversal in persisted storage paths, and private image derivatives not returning public URLs.

Steps:
1. Create `backend-hormonia/tests/api/v2/test_private_upload_serving.py` using existing API v2 fixtures (`client`/`test_client`, `db_session`, `auth_headers_doctor`, `auth_headers_admin`, `test_doctor_user`, `test_admin_user`) and temporary upload roots via `tmp_path`/`monkeypatch`.
2. Add a default-private upload test that POSTs `public=false` or omits `public`, disables expensive virus scan if supported by the route, and asserts `is_public is False`, `download_url == /api/v2/upload/{id}/download`, `url` does not start with `/uploads/`, and any processing URLs for private files are absent or gated.
3. Add a static serving test that uploads or seeds a private file and asserts unauthenticated `GET /uploads/{private_storage_path}` returns 404/403 rather than file bytes.
4. Add a gated download test proving anonymous access fails, the owner receives original bytes and content type, a different doctor/user receives 403, and an admin receives bytes if admin access is the selected policy.
5. Add DB-backed metadata/delete regression assertions where practical so cache misses still find persisted uploads but respect owner/admin authorization.
6. Add path-normalization coverage by seeding an `Upload.storage_path` containing `..` or an absolute path and asserting the gated route fails closed without returning file contents or filesystem details.
7. Keep tests self-contained; do not read `.gsd/`, `.planning/`, `.audits/`, or any gitignored evidence directories.

Must-haves:
- Tests assert route behavior through the FastAPI app, not only helper functions.
- Tests use temporary filesystem roots and leave no real files under repository `uploads/`.
- Failure assertions check generic status/details and no private bytes.

Done when: the new test file exists, documents the expected private-file boundary, and fails against the current public-static implementation for the right reasons.

## Inputs

- `backend-hormonia/app/api/v2/routers/upload/__init__.py`
- `backend-hormonia/app/api/v2/routers/upload/handlers.py`
- `backend-hormonia/app/api/v2/routers/upload/storage.py`
- `backend-hormonia/app/api/v2/routers/upload/processing.py`
- `backend-hormonia/app/core/application_factory.py`
- `backend-hormonia/tests/api/v2/conftest.py`
- `backend-hormonia/tests/conftest.py`

## Expected Output

- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q

## Observability Impact

Adds executable failure-path signals for anonymous/static/foreign/path-traversal cases; future agents can inspect failures with `pytest tests/api/v2/test_private_upload_serving.py -q`.
