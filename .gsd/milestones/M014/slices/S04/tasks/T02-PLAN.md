---
estimated_steps: 5
estimated_files: 4
skills_used:
  - api-design
  - tdd
  - security-review
  - verify-before-complete
---

# T02: Wire active-content denial into upload and avatar ingress

Why: Low-level validation is not sufficient unless the actual FastAPI entrypoints deny spoofed active content before durable persistence and the known `/api/v2/auth/avatar` bypass stops accepting declared image uploads that contain HTML/SVG/script bodies.

Executor skills_used frontmatter to record: `api-design`, `tdd`, `security-review`, `verify-before-complete`.

Threat Surface (Q3): attacker uploads active content through `/api/v2/upload/` or `/api/v2/auth/avatar`, then obtains a `/uploads` or gated URL that can execute in a browser. Sensitive data includes private upload bytes and avatar/user metadata; trust boundary is multipart parsing plus session-authenticated user context.
Requirement Impact (Q4): touches R012/R013 proof rows for stored-XSS, R015 controlled fixtures, R017 safe diagnostics, R018 evidence. Re-verify private upload create path, avatar path, and existing private upload serving tests.
Failure Modes (Q5): malformed/missing multipart file returns existing validation errors; stream seek/read failures deny without persisting; quota/rate-limit failures still happen before file writes; scanner/validator failures clean up any temporary file and leave no DB/cache/avatar URL side effect.
Load Profile (Q6): upload path samples only bounded bytes before `save_upload_file`; avatar path already enforces 5 MiB max and should reuse the same bounded guard before writing. 10x load should hit existing quota/rate-limit before expensive processing.
Negative Tests (Q7): spoofed SVG-as-PNG, HTML-as-text, script in `.txt`, `.svg` extension, `.html` extension, avatar SVG-as-PNG, missing file, and a safe valid PNG control.

Do:
1. In `backend-hormonia/app/api/v2/routers/upload/handlers.py`, call the shared active-content guard after size/quota checks and before `save_upload_file`; reset the file stream after sampling; map denial to 400/415 with generic detail such as `File type is not allowed for security reasons`.
2. Ensure denied uploads do not create an `Upload` row, storage file, derivative, Redis metadata cache entry, or public/gated URL payload.
3. In `backend-hormonia/app/api/v2/routers/auth.py`, replace the avatar-only declared MIME check with shared active-content validation plus existing allowlist; store successful avatars under `get_public_upload_root(create=True) / "avatars"` so `/uploads/avatars/...` matches the public-only static mount, and deny spoofed active content before writing/updating the user.
4. Add route/integration proof in `backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py` using existing client/auth/db fixtures and tmp_path storage monkeypatches; include side-effect sentries for DB row count, stored-file absence, user avatar URL unchanged, and no private bytes/path leaks in denial bodies.
5. Keep denial logs structured with upload_id/user_id/reason/status only; do not log raw uploaded content, raw path, token, cookie, or patient data.

Must-haves:
- Both upload and avatar paths consume the same guard from T01 or a clearly shared equivalent.
- Active-content denials happen before durable persistence, not merely before response serialization.
- Existing legitimate fixture paths remain compatible.

Done when: endpoint tests prove active payloads are denied without durable side effects and a controlled safe image/text fixture still follows the intended route behavior.

## Inputs

- `backend-hormonia/app/api/v2/routers/upload/active_content.py`
- `backend-hormonia/app/api/v2/routers/upload/handlers.py`
- `backend-hormonia/app/api/v2/routers/upload/storage.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/upload/handlers.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/api/v2/test_private_upload_serving.py

## Observability Impact

Adds/uses sanitized ingress-denial events such as `upload_active_content_denied` with upload_id/user_id/reason/status and avatar-denial reason/status, explicitly excluding raw bytes, filenames beyond coarse extension, filesystem paths, tokens, cookies, and PHI.
