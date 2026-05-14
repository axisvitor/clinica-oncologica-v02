---
id: T04
parent: S04
milestone: M014
key_files:
  - backend-hormonia/app/utils/download_responses.py
  - backend-hormonia/app/api/v2/routers/reports.py
  - backend-hormonia/app/api/v2/routers/enhanced_reports.py
  - backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py
  - backend-hormonia/tests/api/v2/test_report_ownership_closure.py
key_decisions:
  - Use the shared attachment response helper for generated report/export artifact downloads so safe headers and active-content media-type downgrades are consistent across base reports, enhanced builder downloads, export fallback downloads, and private upload serving.
  - Preserve ownership/admin gates separately from response-header hardening; unsafe export URLs are withheld or denied fail-closed rather than redirected.
duration: 
verification_result: passed
completed_at: 2026-05-13T22:34:46.415Z
blocker_discovered: false
---

# T04: Extended generated report and export downloads to use shared non-executable attachment responses, with focused proof for safe report/export artifact serving.

**Extended generated report and export downloads to use shared non-executable attachment responses, with focused proof for safe report/export artifact serving.**

## What Happened

Verified that the existing T04 implementation routes base report downloads, enhanced builder downloads, and export fallback downloads through the shared attachment response helper. The helper adds Content-Disposition attachment, X-Content-Type-Options: nosniff, Cache-Control: no-store, safe filenames, and octet-stream normalization for active HTML-style fallback content. Unsafe export URL handling remains fail-closed for /uploads paths, embedded uploads paths, file/data/javascript URLs, absolute/private roots, Windows-style paths, and malformed download_urls, without redirects or body path leakage. Added durable project memory MEM092 for the generated report/export attachment-serving pattern.

## Verification

Ran the authoritative S04 closeout suite with gsd_exec id 9c067d76-0df5-4d2c-bf1e-8b6681d72126: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py. Result: 84 passed in 4.19s.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py` | 0 | ✅ pass — 84 passed | 24987ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/utils/download_responses.py`
- `backend-hormonia/app/api/v2/routers/reports.py`
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py`
- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
