---
id: T01
parent: S04
milestone: M014
key_files:
  - backend-hormonia/app/api/v2/routers/upload/active_content.py
  - backend-hormonia/app/api/v2/routers/upload/config.py
  - backend-hormonia/app/api/v2/routers/upload/validators.py
  - backend-hormonia/app/services/mime_validator.py
  - backend-hormonia/app/services/file_security.py
  - backend-hormonia/tests/security/test_m014_s04_active_content_validation.py
key_decisions:
  - Use a centralized first-64KiB active web-content guard with coarse reason codes for validators and scanners (captured as MEM088).
duration: 
verification_result: passed
completed_at: 2026-05-13T21:02:37.001Z
blocker_discovered: false
---

# T01: Added a shared bounded active web-content guard and wired upload type, MIME, and file security validation to deny stored-XSS upload shapes with safe reason codes.

**Added a shared bounded active web-content guard and wired upload type, MIME, and file security validation to deny stored-XSS upload shapes with safe reason codes.**

## What Happened

Implemented `active_content.py` as the shared primitive for active web-content detection. The guard rejects active web extensions, declared/actual active MIME types, and first-64KiB byte signatures for HTML/SVG/XML/script shapes, returning only coarse PHI/path-safe reason codes. Extended upload configuration and `validate_file_type` so `.html`, `.htm`, `.xhtml`, `.svg`, `.xml`, double-extension variants, and declared active MIME types are rejected before broader allowlist checks. Updated `MimeTypeValidator` so active signatures and declared active MIME deny even when `python-magic` is unavailable, and actual active MIME such as `text/html` cannot pass same-category variance. Updated `FileSecurityService` to perform a bounded active-signature scan for all upload shapes and to detect generic `<script>` tags in HTML/SVG/XML-like content. Added focused low-level pytest coverage using only tmp_path and inline byte fixtures for malicious active content, bounded reads, magic-unavailable behavior, same-category active MIME denial, and benign PNG/PDF/text controls.

## Verification

Fresh verification ran after the last code change. Static syntax/line-length sanity passed for the six edited files. The task verification command `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py` passed with 36 tests in 1.38s (pytest exit code 0).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py` | 0 | ✅ pass — 36 passed in 1.38s | 29626ms |
| 2 | `python static sanity check: compile edited files and report lines >120 chars` | 0 | ✅ pass — syntax ok and no long lines | 97ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/upload/active_content.py`
- `backend-hormonia/app/api/v2/routers/upload/config.py`
- `backend-hormonia/app/api/v2/routers/upload/validators.py`
- `backend-hormonia/app/services/mime_validator.py`
- `backend-hormonia/app/services/file_security.py`
- `backend-hormonia/tests/security/test_m014_s04_active_content_validation.py`
