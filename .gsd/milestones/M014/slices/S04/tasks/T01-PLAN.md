---
estimated_steps: 5
estimated_files: 6
skills_used:
  - tdd
  - security-review
  - verify-before-complete
---

# T01: Add shared active web-content guard and low-level proof

Why: The current upload validation allowlists declared MIME and a small dangerous-extension set, but research confirmed `.html`/`.svg`/`.xml` and spoofed generic `<script>` payloads can pass when declared as allowed `text/plain` or `image/png`, especially when `python-magic` is unavailable. This task creates the reusable fail-closed primitive before route wiring.

Executor skills_used frontmatter to record: `tdd`, `security-review`, `verify-before-complete`.

Threat Surface (Q3): malicious multipart filename/content-type/content bytes can become stored-XSS if later served by browser; sensitive exposure is uploaded PHI plus scanner diagnostics; trust boundary is client-supplied filename, declared MIME, extension, and first bytes.
Requirement Impact (Q4): touches R012, R013, R015, R017, R018 and follows D022 plus existing private-storage decisions. Re-verify upload validation, MIME validation, file security scan, and benign allowed fixture uploads.
Failure Modes (Q5): if `python-magic` is absent, active web-document signatures still deny; if file bytes are undecodable or malformed, detection uses byte/ASCII-lowercase signatures without raising; if a scanner throws, active-content checks must not be bypassed for known HTML/SVG/XML/script signatures.
Load Profile (Q6): bounded first-N-byte inspection only (target 64 KiB or similar), no full-file memory scan in the general upload path beyond existing small scanner behavior; 10x upload load should not create unbounded CPU/memory work.
Negative Tests (Q7): `.html`, `.htm`, `.xhtml`, `.svg`, `.xml`, declared active MIME, spoofed `text/plain`/`image/png` with `<script>`, `<svg>`, `<!doctype html>`, `<?xml`, `javascript:`, event-handler attributes, double extension, and benign PNG/PDF/plain-text controls.

Do:
1. Add a shared active web-content classifier/guard (for example `backend-hormonia/app/api/v2/routers/upload/active_content.py`) with constants for active extensions/MIME types and a bounded byte-sample detector for HTML/SVG/XML/script signatures.
2. Extend `backend-hormonia/app/api/v2/routers/upload/config.py` and `backend-hormonia/app/api/v2/routers/upload/validators.py` so active web-document extensions and declared active MIME types are rejected even if the top-level category would otherwise be allowed.
3. Update `backend-hormonia/app/services/mime_validator.py` so active actual MIME/content never passes same-category variance, and active-content signatures still deny when `python-magic` is unavailable or returns `unknown`.
4. Update `backend-hormonia/app/services/file_security.py` so generic `<script>...</script>` in HTML/SVG/XML-like content is detected, not only eval/document.write/iframe/event handlers.
5. Add focused low-level pytest proof in `backend-hormonia/tests/security/test_m014_s04_active_content_validation.py`; tests must use tmp_path/bytes fixtures only and must not inspect `.gsd/` or other gitignored planning artifacts.

Must-haves:
- Central guard returns a coarse reason/code suitable for safe logs and HTTP errors without echoing filename paths or uploaded bytes.
- Benign allowed fixtures still pass the relevant validator/scanner tests.
- Detection is deterministic without `python-magic` installed.

Done when: low-level tests prove active web-document shapes are denied and safe controls pass, with bounded reads and PHI/path-safe failure metadata.

## Inputs

- `backend-hormonia/app/api/v2/routers/upload/config.py`
- `backend-hormonia/app/api/v2/routers/upload/validators.py`
- `backend-hormonia/app/services/mime_validator.py`
- `backend-hormonia/app/services/file_security.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/upload/active_content.py`
- `backend-hormonia/app/api/v2/routers/upload/config.py`
- `backend-hormonia/app/api/v2/routers/upload/validators.py`
- `backend-hormonia/app/services/mime_validator.py`
- `backend-hormonia/app/services/file_security.py`
- `backend-hormonia/tests/security/test_m014_s04_active_content_validation.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py

## Observability Impact

Adds coarse active-content reason codes that later route/scanner logs can emit without raw filename paths, storage paths, uploaded bytes, PHI, tokens, or secrets.
