# S04: Upload Stored-XSS e Private Artifact Serving

**Goal:** Close the M014 upload stored-XSS and private artifact serving proof gap by rejecting active HTML/SVG/XML/script upload shapes before durable persistence, hardening the direct avatar upload bypass, and proving private uploads plus report/export artifacts are owner/admin-gated, non-executable attachments with PHI/secret/path-safe diagnostics.
**Demo:** Reviewer runs upload/download tests with malicious HTML/SVG/script payloads and sees rejection or safe attachment serving under auth/ownership, with anonymous/foreign access denied.

## Must-Haves

- Slice verification is defined up front and must be fresh at closeout:
- Focused S04 proof command passes: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py`.
- Supporting regression command passes: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py`.
- Upload stored-XSS contract: `.html`, `.htm`, `.xhtml`, `.svg`, `.xml`, declared `text/html`/`image/svg+xml`, and spoofed `text/plain`/`image/png` payloads containing active web-document/script signatures are denied before an `Upload` DB row, durable stored file, derivative, public URL, or cache entry is created; benign allowed fixture uploads still pass.
- Avatar bypass contract: `/api/v2/auth/avatar` reuses the same active-content guard/public-root convention or equivalent shared validator; spoofed HTML/SVG/script avatar payloads are denied and no user avatar URL/file is persisted, while a controlled valid image still works if covered by existing behavior.
- Private upload/artifact serving contract: owner/admin access to legacy active-looking private records returns bytes only as `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store` (or stricter), and `application/octet-stream` for active/unknown MIME; anonymous/foreign access is denied without body bytes, filesystem paths, storage paths, tokens, or PHI.
- Report/export artifact contract: base reports, enhanced builder downloads, export fallback downloads, and unsafe export URL denials preserve owner checks, use attachment/nosniff/no-store for downloadable artifacts, deny `/uploads`, `file:`, `data:`, `javascript:`, absolute/private-root URLs without redirect, and keep HTML fallback non-executable.
- Diagnostics remain R017-safe: upload/MIME/file-security/virus/report denial logs expose coarse IDs, reason, status, scanner/result metadata, and timing only; tests must not read `.gsd/`, `.planning/`, `.audits/`, production paths, live providers, or real PHI.

## Proof Level

- This slice proves: Controlled contract/integration proof. Real production runtime required: no. Human/UAT required: no. Evidence is local pytest with fixture auth/users/storage/cache and mocked scanner/provider dependencies only, satisfying R015 while producing explicit R012/R013/R018 rows for S05.

## Integration Closure

Upstream surfaces consumed: S01 authenticated/session ingress assumptions and S03 no-store/browser persistence assumptions; existing private upload root split in `backend-hormonia/app/api/v2/routers/upload/config.py`; existing owner/admin gates in `backend-hormonia/app/api/v2/routers/upload/handlers.py`, `backend-hormonia/app/api/v2/routers/reports.py`, and `backend-hormonia/app/api/v2/routers/enhanced_reports.py`. New wiring introduced: shared active web-content validation at upload/avatar ingress and shared safe attachment/header behavior for private artifact responses. Remaining before milestone closure: S05 must map S04 command evidence plus any documented residuals into the final M014 evidence matrix.

## Verification

- Runtime signals should remain structured and PHI-safe: `upload_request_received`, `upload_active_content_denied`, `upload_download_denied`, scanner-denial events, and report/export unsafe-artifact denials should include upload_id/export_id/report_id where already present, reason, status/response_status, scanner/result class, and timing; they must not include raw filesystem paths, storage paths, patient identifiers, prompts, answers, tokens, cookies, or uploaded bytes. Future agents inspect failures by rerunning the focused pytest files and checking sanitized log extras asserted by the tests.

## Tasks

- [x] **T01: Add shared active web-content guard and low-level proof** `est:2h`
  Why: The current upload validation allowlists declared MIME and a small dangerous-extension set, but research confirmed `.html`/`.svg`/`.xml` and spoofed generic `<script>` payloads can pass when declared as allowed `text/plain` or `image/png`, especially when `python-magic` is unavailable. This task creates the reusable fail-closed primitive before route wiring.
  - Files: `backend-hormonia/app/api/v2/routers/upload/active_content.py`, `backend-hormonia/app/api/v2/routers/upload/config.py`, `backend-hormonia/app/api/v2/routers/upload/validators.py`, `backend-hormonia/app/services/mime_validator.py`, `backend-hormonia/app/services/file_security.py`, `backend-hormonia/tests/security/test_m014_s04_active_content_validation.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py

- [ ] **T02: Wire active-content denial into upload and avatar ingress** `est:2h`
  Why: Low-level validation is not sufficient unless the actual FastAPI entrypoints deny spoofed active content before durable persistence and the known `/api/v2/auth/avatar` bypass stops accepting declared image uploads that contain HTML/SVG/script bodies.
  - Files: `backend-hormonia/app/api/v2/routers/upload/handlers.py`, `backend-hormonia/app/api/v2/routers/upload/storage.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/api/v2/test_private_upload_serving.py

- [ ] **T03: Harden private upload downloads and scanner diagnostics** `est:1.5h`
  Why: Even after new uploads reject active content, legacy/private records can already contain `.html`, `.svg`, `.xml`, `text/html`, or unknown MIME metadata. Owner/admin retrieval must not execute in-browser, and scanner diagnostics must not leak local private paths.
  - Files: `backend-hormonia/app/utils/download_responses.py`, `backend-hormonia/app/api/v2/routers/upload/handlers.py`, `backend-hormonia/app/api/v2/routers/upload/security.py`, `backend-hormonia/app/services/mime_validator.py`, `backend-hormonia/app/services/file_security.py`, `backend-hormonia/app/services/virus_scanner.py`, `backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py`, `backend-hormonia/tests/api/v2/test_private_upload_serving.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/api/v2/test_private_upload_serving.py

- [ ] **T04: Extend report/export artifact attachment proof and closeout suite** `est:1.5h`
  Why: S04 also owns generated artifact serving. Existing report ownership tests prove raw owner checks and unsafe URL denial, but they do not assert attachment/nosniff/no-store behavior or HTML export fallback non-execution. This task closes that report/export portion and provides the final S04 command suite for S05.
  - Files: `backend-hormonia/app/utils/download_responses.py`, `backend-hormonia/app/api/v2/routers/reports.py`, `backend-hormonia/app/api/v2/routers/enhanced_reports.py`, `backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py`, `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py

## Files Likely Touched

- backend-hormonia/app/api/v2/routers/upload/active_content.py
- backend-hormonia/app/api/v2/routers/upload/config.py
- backend-hormonia/app/api/v2/routers/upload/validators.py
- backend-hormonia/app/services/mime_validator.py
- backend-hormonia/app/services/file_security.py
- backend-hormonia/tests/security/test_m014_s04_active_content_validation.py
- backend-hormonia/app/api/v2/routers/upload/handlers.py
- backend-hormonia/app/api/v2/routers/upload/storage.py
- backend-hormonia/app/api/v2/routers/auth.py
- backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py
- backend-hormonia/app/utils/download_responses.py
- backend-hormonia/app/api/v2/routers/upload/security.py
- backend-hormonia/app/services/virus_scanner.py
- backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py
- backend-hormonia/tests/api/v2/test_private_upload_serving.py
- backend-hormonia/app/api/v2/routers/reports.py
- backend-hormonia/app/api/v2/routers/enhanced_reports.py
- backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py
- backend-hormonia/tests/api/v2/test_report_ownership_closure.py
