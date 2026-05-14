---
id: T03
parent: S04
milestone: M014
key_files:
  - backend-hormonia/app/utils/download_responses.py
  - backend-hormonia/app/api/v2/routers/upload/handlers.py
  - backend-hormonia/app/api/v2/routers/upload/security.py
  - backend-hormonia/app/services/mime_validator.py
  - backend-hormonia/app/services/file_security.py
  - backend-hormonia/app/services/virus_scanner.py
  - backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py
  - backend-hormonia/tests/api/v2/test_private_upload_serving.py
key_decisions:
  - Use a shared `app.utils.download_responses.build_attachment_file_response` helper for gated private downloads so legacy active/unknown artifacts are served as attachments with nosniff/no-store and octet-stream where required.
  - Scrub upload scanner diagnostics to coarse extension/reason/status/scanner/result/timing metadata rather than raw filesystem paths or tracebacks.
duration: 
verification_result: passed
completed_at: 2026-05-13T21:52:32.906Z
blocker_discovered: false
---

# T03: Hardened gated private upload downloads to serve legacy active/unknown artifacts only as non-executable attachments and scrubbed scanner diagnostics of raw paths.

**Hardened gated private upload downloads to serve legacy active/unknown artifacts only as non-executable attachments and scrubbed scanner diagnostics of raw paths.**

## What Happened

Added a shared safe download response helper for application-served private artifacts. The helper sanitizes attachment filenames, forces `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, and `Cache-Control: no-store`, and downgrades active or unknown MIME/extension metadata to `application/octet-stream`. Wired `download_upload_handler` to use this helper after existing owner/admin authorization and safe local path resolution, with helper failures converted to generic 404 denial rather than inline serving.

Scrubbed upload scanner diagnostics in the route security wrapper plus MIME, file-security, and virus scanner services. Logs now preserve useful fields such as extension, reason, status/result class, scanner, and scan_time_ms while avoiding raw `file_path`, storage paths, exception tracebacks, and uploaded bytes. Archive/double-extension/file-scan threat strings were adjusted to avoid embedding attacker-controlled filenames.

Added `test_m014_s04_private_artifact_serving.py` covering owner/admin access to legacy HTML/SVG/unknown private records as non-executable attachments, malicious filename header safety, anonymous/foreign denial leak checks, pre-file-IO foreign denial, and scanner log path-safety. Strengthened the existing private upload serving regression suite to assert attachment/nosniff/no-store headers for owner/admin gated downloads.

## Verification

Fresh task-level verification ran after the final MIME hardening change: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/api/v2/test_private_upload_serving.py` passed with 17 tests. A static diagnostic over the touched scanner modules also passed, confirming no raw `file_path` log extras or `exc_info=True` remain in the T03 scanner modules.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/api/v2/test_private_upload_serving.py` | 0 | ✅ pass — 17 passed in 2.38s | 34797ms |
| 2 | `python static diagnostic: check T03 scanner modules for raw file_path log extras or exc_info=True` | 0 | ✅ pass — no raw file_path log extras or exc_info=True in T03 scanner modules | 55ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/utils/download_responses.py`
- `backend-hormonia/app/api/v2/routers/upload/handlers.py`
- `backend-hormonia/app/api/v2/routers/upload/security.py`
- `backend-hormonia/app/services/mime_validator.py`
- `backend-hormonia/app/services/file_security.py`
- `backend-hormonia/app/services/virus_scanner.py`
- `backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py`
- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`
