---
id: T02
parent: S04
milestone: M014
key_files:
  - backend-hormonia/app/api/v2/routers/upload/handlers.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py
  - backend-hormonia/tests/conftest.py
key_decisions:
  - Use the T01 shared bounded active-content guard at upload and avatar route ingress before durable persistence.
  - Store successful avatars under the configured public upload root `/avatars` subtree so `/uploads/avatars/...` aligns with the public-only static mount (captured as MEM089).
duration: 
verification_result: passed
completed_at: 2026-05-13T21:26:16.914Z
blocker_discovered: false
---

# T02: Wired shared active-content denial into upload and avatar ingress before persistence with route-level stored-XSS side-effect tests.

**Wired shared active-content denial into upload and avatar ingress before persistence with route-level stored-XSS side-effect tests.**

## What Happened

Updated the upload route handler to invoke the shared active-content guard after size/quota checks and before `save_upload_file`, resetting the stream after the bounded sample and returning a generic security denial without creating rows, files, cache entries, or response URLs. Added structured `upload_active_content_denied` logging with upload_id/user_id/reason/status/duration only.

Updated `/api/v2/auth/avatar` to read its already-capped content before any durable write, reuse the same active-content detector, preserve the existing image allowlist for benign files, and persist successful avatars under `get_public_upload_root(create=True) / "avatars"` so `/uploads/avatars/...` matches the public-only static mount. Avatar filenames no longer embed the user id, and user avatar metadata is updated only after the file write succeeds.

Added `backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py` with route-level proofs for spoofed SVG-as-PNG, HTML/script text, active extensions, missing file, safe PNG upload, avatar active-content denial, safe avatar persistence, DB/file/cache/user side-effect sentries, denial body leak checks, and sanitized denial log extras. Also fixed the test SQLite compatibility shim to strip PostgreSQL `::jsonb`/`::json` server defaults so the focused route suites can create local schemas when not using Postgres.

## Verification

Ran the task verification command after implementation and cleanup: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/api/v2/test_private_upload_serving.py`. Final run passed all 51 focused tests, proving low-level active-content validation, upload/avatar route denial before persistence, and existing private upload serving behavior.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/api/v2/test_private_upload_serving.py` | 0 | ✅ pass — 51 passed | 22589ms |

## Deviations

Added a small test-infrastructure compatibility fix in `backend-hormonia/tests/conftest.py` to strip PostgreSQL `::jsonb`/`::json` server defaults for SQLite fallback schemas. This was outside the expected output list but required for the focused route verification command to run locally without schema creation errors.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/upload/handlers.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py`
- `backend-hormonia/tests/conftest.py`
