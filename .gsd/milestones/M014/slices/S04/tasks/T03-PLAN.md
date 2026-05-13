---
estimated_steps: 5
estimated_files: 8
skills_used:
  - api-design
  - security-review
  - tdd
  - verify-before-complete
---

# T03: Harden private upload downloads and scanner diagnostics

Why: Even after new uploads reject active content, legacy/private records can already contain `.html`, `.svg`, `.xml`, `text/html`, or unknown MIME metadata. Owner/admin retrieval must not execute in-browser, and scanner diagnostics must not leak local private paths.

Executor skills_used frontmatter to record: `api-design`, `security-review`, `tdd`, `verify-before-complete`.

Threat Surface (Q3): persisted upload metadata (`storage_path`, `file_type`, `file_name`) may point to active-looking private artifacts or unsafe paths; anonymous/foreign users may probe for private bytes; logs may expose private roots. Sensitive data includes upload bytes, private filesystem layout, user IDs, and any PHI in filenames/paths.
Requirement Impact (Q4): touches R012 private artifact serving, R013 proof gap, R017 diagnostic safety, R018 matrix evidence, and D022. Re-verify private upload serving regressions.
Failure Modes (Q5): missing files and unsafe paths return generic 404 without bytes/path; foreign owner returns 403 before local file IO; active/unknown MIME falls back to `application/octet-stream`; response-header helper failures should fail closed rather than inline-render.
Load Profile (Q6): streaming remains `FileResponse`-based and does not buffer full files; per-download work is metadata inspection plus path resolution; 10x load is bounded by existing file IO and auth/db lookup.
Negative Tests (Q7): owner/admin legacy `.html`/`.svg` private record, unknown content type, malicious filename, anonymous/foreign access, missing file, path traversal/absolute path, and scanner log caplog with tmp private path.

Do:
1. Add or reuse a safe attachment/header helper (for example `backend-hormonia/app/utils/download_responses.py`) that builds `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, and `Cache-Control: no-store` headers and selects `application/octet-stream` for active or unknown MIME/extension.
2. Update `backend-hormonia/app/api/v2/routers/upload/handlers.py` so `download_upload_handler` uses the helper for all private/gated downloads while preserving owner/admin authorization and generic 404/403 behavior.
3. Scrub raw path logging in `backend-hormonia/app/api/v2/routers/upload/security.py`, `backend-hormonia/app/services/mime_validator.py`, `backend-hormonia/app/services/file_security.py`, and `backend-hormonia/app/services/virus_scanner.py`; replace `file_path` extras with coarse fields such as extension, scanner, status, reason, and scan_time_ms.
4. Add focused proof in `backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py`: owner/admin receive legacy active bytes only as attachment/octet-stream/nosniff/no-store; anonymous/foreign denial bodies lack private bytes/path/storage terms; scanner denial logs do not include tmp paths.
5. Keep `backend-hormonia/tests/api/v2/test_private_upload_serving.py` passing; update assertions only to strengthen header expectations without weakening existing owner/admin/foreign/static denial coverage.

Must-haves:
- Active-looking legacy private artifacts are still retrievable by owner/admin for continuity, but only as non-executable downloads.
- Denied users never receive bytes, private storage paths, raw filesystem paths, traceback, or active payload fragments.
- Scanner diagnostics remain useful through reason/status/timing/scanner metadata without path leakage.

Done when: private artifact tests and the existing private upload serving regression suite pass together.

## Inputs

- `backend-hormonia/app/api/v2/routers/upload/active_content.py`
- `backend-hormonia/app/api/v2/routers/upload/handlers.py`
- `backend-hormonia/app/api/v2/routers/upload/security.py`
- `backend-hormonia/app/services/mime_validator.py`
- `backend-hormonia/app/services/file_security.py`
- `backend-hormonia/app/services/virus_scanner.py`
- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`

## Expected Output

- `backend-hormonia/app/utils/download_responses.py`
- `backend-hormonia/app/api/v2/routers/upload/handlers.py`
- `backend-hormonia/app/api/v2/routers/upload/security.py`
- `backend-hormonia/app/services/mime_validator.py`
- `backend-hormonia/app/services/file_security.py`
- `backend-hormonia/app/services/virus_scanner.py`
- `backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py`
- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/api/v2/test_private_upload_serving.py

## Observability Impact

Changes scanner and download diagnostics to explicit, path-safe fields: reason/status/scanner/scan_time_ms/extension/upload_id where available, with tests guarding against raw tmp/private filesystem path leakage.
