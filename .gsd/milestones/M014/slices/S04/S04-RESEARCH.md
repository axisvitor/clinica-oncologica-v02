# S04 Research — Upload Stored-XSS e Private Artifact Serving

**Depth:** Targeted research. The storage/private-serving architecture is already present from M013, but the stored-XSS proof gap is still real and needs focused hardening/proof.

## Active requirements this slice owns/supports

- **R012** — S04 owns the upload/private-artifact hardening portion of the medium backlog.
- **R013** — S04 owns the deferred upload stored-XSS proof gap and contributes private artifact serving evidence to the final matrix.
- **R015** — all proof should remain controlled local pytest/unit fixtures; no production exploitation, no live providers, no real patient data.
- **R017** — S04 must keep denial diagnostics and proof artifacts PHI/secret/path-safe; scanner logs are a watch-out because several currently log raw `file_path`.
- **R018** — S04 should emit explicit command evidence for upload XSS/private serving rows so S05 does not silently drop them.

## Recommendation

Keep the existing M013 storage split: `/uploads` should mount only the intentionally public upload subdirectory, while private uploads and generated report artifacts stay under unmounted private roots and are streamed through authenticated owner/admin endpoints. Do not redesign storage.

For M014, add a narrow active-content hardening layer and proof:

1. **Reject active web-document upload shapes before persistence**: `.html`, `.htm`, `.xhtml`, `.svg`, `.xml`/script-like payloads should not pass just because the declared content type is `text/plain` or `image/png`. The current code can fail open when `python-magic` is absent and misses generic `<script>` tags in HTML/SVG.
2. **Serve legacy/private active-looking records as non-executable downloads**: owner/admin may retrieve existing private files, but responses must be `attachment` and preferably `application/octet-stream` for active or unknown MIME; anonymous/foreign access must deny without bytes/paths.
3. **Extend, do not replace, report/export proof**: base/enhanced report downloads already use attachment headers and raw owner checks; add assertions for `Content-Disposition`, `nosniff`, unsafe `/uploads` redirect denial, and HTML export fallback attachment behavior.
4. **Scrub upload scanner diagnostics**: remove raw filesystem paths from upload/MIME/file-security/virus logs or wrap them in coarse IDs/reason/status only.
5. **Decide avatar scope explicitly**: `/api/v2/auth/avatar` is a direct public upload path that bypasses the upload package. Either fold it into the same validator/scanner/public-root helpers in S04 or document it as an explicit non-goal/deferral; do not leave it unmentioned in S05.

## Implementation landscape

### Existing storage/private-serving architecture

- `backend-hormonia/app/core/application_factory.py:212-220` mounts `StaticFiles` at `/uploads` using `get_public_upload_root(create=True)`, not the common upload root. This matches D004/D010/D011 and MEM004/MEM034.
- `backend-hormonia/app/api/v2/routers/upload/config.py:97-176,249-273` defines public/private storage prefixes, `get_public_upload_root`, `get_private_upload_root`, `build_storage_path`, and safe storage-path resolution. Private roots default to a sibling `.uploads_private` root.
- `backend-hormonia/app/api/v2/routers/upload/storage.py` stores under `get_storage_root(public=...)` and persists visibility-prefixed storage paths.
- `backend-hormonia/app/api/v2/routers/upload/handlers.py:501-571` authorizes owner/admin before local file IO and returns `FileResponse(path=..., media_type=upload_record.file_type, filename=_generic_download_filename(...))`. Local Starlette inspection (`gsd_exec 44370791-991b-4f8a-a85e-7c5f6b1e8e07`) confirmed `FileResponse` defaults `content_disposition_type='attachment'` when a filename is supplied.
- `backend-hormonia/tests/api/v2/test_private_upload_serving.py` already covers private URL behavior, public static denial, owner/admin success, anonymous/foreign denial, missing/deleted/unsafe paths, and no private bytes/path leakage.

### Upload validation/scanning surfaces

- `backend-hormonia/app/api/v2/routers/upload/config.py:44-79` allowlists MIME types and blocks a small dangerous-extension set. `image/svg+xml` and `text/html` are not allowed MIME types, but `.html`/`.svg` extensions are not blocked.
- `backend-hormonia/app/api/v2/routers/upload/validators.py:25-45` validates only declared MIME and extension membership in `DANGEROUS_EXTENSIONS`.
- `backend-hormonia/app/services/mime_validator.py:114-137` fails open when `python-magic` is unavailable. Current environment probe (`gsd_exec 820fceae-862a-48c1-87a7-5c19929018c1`) showed `magic_available=False` and both SVG-as-`image/png` and HTML-as-`text/plain` validate as true. By code, when magic is available, `_is_similar_mime` can allow same top-level category variance (`text/html` vs `text/plain`, `image/svg+xml` vs `image/png`) unless stricter handling is added for active web-document types.
- `backend-hormonia/app/services/file_security.py:147-152,400-426` treats `.html/.htm/.svg/.xml` as suspicious and scans patterns, but the current pattern set misses generic `<script>alert(1)</script>` with no `eval`, `document.write`, iframe, redirect, or event handler. Probe `gsd_exec 0a305bae-96d4-4f6e-9df9-a6ef96a1700a`: `html_generic_script safe=True`, `svg_generic_script safe=True`, while `onload` and `iframe` were blocked.
- `backend-hormonia/app/api/v2/routers/upload/security.py`, `backend-hormonia/app/services/mime_validator.py`, `backend-hormonia/app/services/file_security.py`, and `backend-hormonia/app/services/virus_scanner.py` log raw `file_path` in several failure/success branches. This conflicts with R017/M013 matrix guidance forbidding private filesystem paths in diagnostics/proof artifacts.

### Generated report/export artifacts

- `backend-hormonia/app/tasks/helpers/reports_helpers.py` builds report-id-only private PDF paths under `get_private_upload_root()/reports`; M013 tests assert no patient/report-type fragments in filenames/logs.
- `backend-hormonia/app/tasks/reports_taskiq.py:101-107` writes PDFs under that private root, but still returns `output_path` in the Taskiq result. Existing tests accept it; memory/requirements warn that task results should avoid private paths. Planner should decide whether S04 changes this now or leaves it to S05 as a documented residual. If changed, update `tests/tasks/test_reports_tasks.py` expectations accordingly.
- `backend-hormonia/app/api/v2/routers/reports.py:599-687` returns base report downloads with `Content-Disposition: attachment` and no HTML format.
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py:445-530` withholds unsafe export URLs, including `/uploads`, `file:`, `data:`, `javascript:`, Windows/absolute paths, and common private roots.
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py:627-669` builder downloads are JSON/CSV attachments.
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py:929-1006` export download fallback can return `text/html` for HTML format, but with `Content-Disposition: attachment`; unsafe download URLs are denied with 404/no redirect.
- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py` already covers raw owner/patient evidence, owner/admin allow, foreign/missing deny, unsafe `/uploads/private/...` URL withholding, and no redirect on unsafe private URLs.

### Direct upload bypass watch-out

- `backend-hormonia/app/api/v2/routers/auth.py:1177-1253` implements `/api/v2/auth/avatar` separately. It accepts only declared JPEG/PNG/WebP/GIF, writes to `settings.BASE_DIR/uploads/avatars`, and returns `/uploads/avatars/{filename}`. It bypasses upload package storage roots, MIME validation, file security scanning, and the public-root helper. Because `/uploads` now mounts `uploads/public`, this may also produce stale/non-served URLs depending on settings. At minimum, S04/S05 should mention this path; ideally reuse upload helpers or add focused rejection proof for SVG/HTML spoofing.

## What exists vs. what is missing

### Already exists / likely reusable

- Private upload root split and public-only StaticFiles mount.
- Owner/admin gate for `/api/v2/upload/{upload_id}/download` before local file IO.
- Safe storage path resolution with traversal/prefix mismatch fail-closed.
- Existing private-upload and report-ownership tests with two-user/admin patterns and generic denial assertions.
- Report download/export endpoints mostly use attachment responses and raw access checks.

### Missing / high-risk proof gaps

- No dedicated upload stored-XSS tests for malicious HTML/SVG/script payloads (`rg` scan found generic XSS tests but no upload-specific stored-XSS proof; `test_private_upload_serving.py` monkeypatches `scan_file_security` to `_ok`).
- Generic `<script>` in `.html`/`.svg` currently passes `FileSecurityService` (`gsd_exec 0a305bae-96d4-4f6e-9df9-a6ef96a1700a`).
- MIME validation is not deterministic in controlled proof because `python-magic` can be missing and fail open (`gsd_exec 820fceae-862a-48c1-87a7-5c19929018c1`).
- Declared MIME + extension validation can admit active extensions under allowed MIME categories by code inspection (`.html` with `text/plain`, `.svg` with `image/png`).
- Upload scanner logs expose private filesystem paths (`file_path`) in multiple modules.
- Existing S04-adjacent baseline command `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/tasks/test_reports_tasks.py -q` (`gsd_exec 5077a9a9-49dd-463d-8fb6-1eaff556088c`) failed locally because API-v2 autouse fixture queried missing SQLite `flow_kinds`; the report task tests themselves passed. Planner should either stabilize that fixture/schema for root-level evidence or keep new first-proof tests independent of `tests/api/v2/conftest.py` until the route-level gate is fixed.

## Natural seams / suggested work units

1. **Stored-XSS input validation seam**
   - Files: `upload/config.py`, `upload/validators.py`, `app/services/file_security.py`, `app/services/mime_validator.py`.
   - Goal: reject active web-document extensions/MIME/payloads deterministically before persistence, independent of `python-magic` availability.
   - Suggested policy: add an explicit active-content denylist (`.html`, `.htm`, `.xhtml`, `.svg`, `.xml`, possibly `.mhtml`) and/or active MIME denylist (`text/html`, `image/svg+xml`, `application/xhtml+xml`, JavaScript MIME aliases). If product later needs SVG, require sanitizer + attachment-only serving, not public static.

2. **Private/legacy active-content serving seam**
   - Files: `upload/handlers.py`, `upload/config.py`, `tests/api/v2/test_private_upload_serving.py` or new `tests/security/test_m014_s04_private_upload_active_content.py`.
   - Goal: seed legacy private rows with active MIME/extension and malicious bytes; prove owner/admin get safe attachment/non-executable headers, while anonymous/foreign get no bytes/paths.
   - Implementation option: keep Starlette attachment default explicit by passing `content_disposition_type="attachment"`; override `media_type` to `application/octet-stream` for active or unknown persisted types.

3. **Report/export attachment and unsafe URL proof seam**
   - Files: `reports.py`, `enhanced_reports.py`, `tests/api/v2/test_report_ownership_closure.py`.
   - Goal: assert base/builder/export downloads include attachment and security headers; HTML fallback is not inline; unsafe `/uploads`/private paths still withhold and do not redirect.
   - Likely minimal code change unless tests reveal missing headers in test middleware.

4. **Direct avatar upload seam**
   - Files: `auth.py` and possibly upload helpers.
   - Goal: either route through shared upload validation/storage/public-root helpers or add a focused proof that SVG/HTML/script spoofing is rejected and URL points only to the intended public root.
   - This is independent from private artifact serving and can be deferred only if S05 explicitly records owner/rationale.

5. **PHI-safe diagnostics seam**
   - Files: `upload/security.py`, `mime_validator.py`, `file_security.py`, `virus_scanner.py`, maybe `tasks/reports_taskiq.py` if removing `output_path` from results.
   - Goal: log `upload_id`/reason/status/scan class, not raw private paths, payloads, archive member names, tokens, or patient labels. Add caplog tests around failed malicious upload.

## First proof to write

Start with a small, fast failing test file that does not need DB fixtures:

`backend-hormonia/tests/security/test_m014_s04_upload_stored_xss.py`

Recommended first assertions:

- `FileSecurityService.scan_file()` rejects `.html` and `.svg` containing generic `<script>alert(1)</script>`.
- `validate_file_type()` rejects active extensions even when declared MIME is otherwise allowed (`evil.html` + `text/plain`, `evil.svg` + `image/png`).
- MIME validator absence cannot be the only protection: active-content decisions must remain deterministic without `python-magic`.
- Scanner/validator denial logs and HTTP details do not contain temp paths, private roots, tokens, or payload bodies.

Why first: the probe already shows this is the current gap, and it can be red/greened without fighting the current API-v2 SQLite `flow_kinds` fixture issue.

Then add route-level proof:

- POST `/api/v2/upload/` with malicious HTML/SVG/script payloads returns 400/415 before DB row/bytes are persisted. Keep rate/quota/virus monkeypatched as needed, but do **not** monkeypatch the active-content validator/scanner under test.
- Seeded legacy private active-content row downloads as owner/admin only, with `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff` (test middleware), and either `application/octet-stream` or otherwise non-inline semantics; anonymous/foreign deny without malicious bytes/private paths.
- Public static `/uploads/{private_storage_path}` remains 403/404 and cannot reveal private bytes.

## Verification plan

Use root-relative commands; do not `cd`.

Focused unit/security proof:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml \
  backend-hormonia/tests/security/test_m014_s04_upload_stored_xss.py -q
```

Private upload route proof after fixture/schema stabilization:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml \
  backend-hormonia/tests/api/v2/test_private_upload_serving.py -q
```

Report/export private artifact proof:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml \
  backend-hormonia/tests/api/v2/test_report_ownership_closure.py \
  backend-hormonia/tests/tasks/test_reports_tasks.py \
  backend-hormonia/tests/services/test_report_service_task_compat.py -q
```

Suggested integrated S04 closeout command:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml \
  backend-hormonia/tests/security/test_m014_s04_upload_stored_xss.py \
  backend-hormonia/tests/api/v2/test_private_upload_serving.py \
  backend-hormonia/tests/api/v2/test_report_ownership_closure.py \
  backend-hormonia/tests/tasks/test_reports_tasks.py \
  backend-hormonia/tests/services/test_report_service_task_compat.py -q
```

If `test_private_upload_serving.py` still fails with missing `flow_kinds`, fix the test schema/import guard or split S04 route proof into a new focused test that imports only the needed fixtures. Do not mark S04 complete with the route proof skipped.

## Skill discovery

Installed/generic skills in the prompt that are relevant if executor chooses to invoke them: `api-design` (HTTP download/header contract), `security-review`/`best-practices` (stored-XSS and upload threat model), `observability` (PHI-safe diagnostics), `verify-before-complete` (fresh evidence before completion). No FastAPI/Starlette-specific installed skill was visible.

External skill search (`gsd_exec ae97c805-3cf4-4627-8683-754b691d9558`) found possible but not installed skills:

- `npx skills add aj-geddes/useful-ai-prompts@file-upload-handling` — 317 installs; generic file upload handling.
- `npx skills add davila7/claude-code-templates@file-uploads` — 242 installs; generic file uploads.
- `npx skills add secondsky/claude-skills@api-security-hardening` — 205 installs; API security hardening.

These are optional; existing codebase patterns are likely sufficient.

## Watch-outs for the planner/executors

- Do not rely on `python-magic` or ClamAV availability for the proof; controlled tests should pass deterministically without external scanners.
- Do not make `/uploads` serve private roots again for convenience. Static mount must remain public-root only.
- Do not log temp paths/private roots in failed upload proof. Current scanner modules need scrutiny before caplog evidence.
- Do not count M013 private-serving evidence as M014 stored-XSS closure; M014 needs new malicious HTML/SVG/script proof.
- Be careful with `text/html` export fallback: attachment is probably acceptable, but tests should assert no inline rendering path and no unsafe redirect.
- If changing Taskiq report result shape to remove `output_path`, update `tests/tasks/test_reports_tasks.py` and any compatibility callers; otherwise document residual private-path-in-task-result explicitly for S05.

## Sources / research evidence

- Memories: MEM004, MEM029, MEM034, MEM035, MEM036, MEM037, MEM038, MEM061.
- Code scans: `gsd_exec e05236d6-482b-4f35-a8f7-780c3b6e0cc4`, `7ff1cc5d-a80f-4f75-b415-08df1bf29e3a`, `3e123f13-e463-4fa6-be8e-5404dc10c0f1`, `41292c92-5e25-4a15-9b4b-d45b0c43d67e`.
- Active-content scanner probe: `gsd_exec 0a305bae-96d4-4f6e-9df9-a6ef96a1700a`.
- MIME fail-open probe: `gsd_exec 820fceae-862a-48c1-87a7-5c19929018c1`.
- FileResponse attachment default probe: `gsd_exec 44370791-991b-4f8a-a85e-7c5f6b1e8e07`.
- Baseline adjacent test run: `gsd_exec 5077a9a9-49dd-463d-8fb6-1eaff556088c` (task tests passed; private upload tests blocked by local SQLite `flow_kinds` schema issue).
