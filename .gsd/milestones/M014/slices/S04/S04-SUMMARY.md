---
id: S04
parent: M014
milestone: M014
provides:
  - S05 can map controlled S04 evidence for upload stored-XSS denial, avatar bypass hardening, private upload serving, and generated report/export artifact serving.
  - Reviewer can rerun focused pytest commands to prove malicious active upload shapes are denied before persistence and legacy/private artifacts download only as non-executable attachments.
  - Report/export unsafe URL denials now include raw and percent-encoded private path cases plus external and protocol-relative redirect bypasses.
requires:
  - slice: S01
    provides: Consumes authenticated/session ingress assumptions without weakening owner/admin access semantics.
  - slice: S03
    provides: Consumes no-store browser persistence assumptions for browser-sensitive artifact responses.
affects:
  - S05
key_files:
  - backend-hormonia/app/api/v2/routers/upload/active_content.py
  - backend-hormonia/app/api/v2/routers/upload/handlers.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/utils/download_responses.py
  - backend-hormonia/app/api/v2/routers/reports.py
  - backend-hormonia/app/api/v2/routers/enhanced_reports.py
  - backend-hormonia/app/services/mime_validator.py
  - backend-hormonia/app/services/file_security.py
  - backend-hormonia/app/services/virus_scanner.py
  - backend-hormonia/tests/security/test_m014_s04_active_content_validation.py
  - backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py
  - backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py
  - backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py
  - backend-hormonia/tests/api/v2/test_private_upload_serving.py
  - backend-hormonia/tests/api/v2/test_report_ownership_closure.py
key_decisions:
  - Centralize active web-content detection in the upload active-content guard and reuse its coarse reason codes across validators, route ingress, and scanners.
  - Serve private uploads and generated report/export artifacts through shared attachment response helpers after owner/admin checks, with nosniff no-store headers and octet-stream downgrades for active or unknown artifact shapes.
  - Classify enhanced export download URLs only after bounded percent-decoding and URL parsing so encoded uploads paths, backslashes, schemes, netlocs, and protocol-relative redirects are denied before exposure or redirect.
patterns_established:
  - Pre-persistence active-content guard before durable upload rows, files, derivatives, public URLs, cache entries, or avatar metadata updates.
  - Owner/admin authorization remains separate from response hardening, and denied artifact paths return generic bodies without PHI, tokens, storage paths, or uploaded bytes.
  - Unsafe generated artifact URLs are withheld from status responses and return no-redirect 404 downloads unless they are local non-private URLs.
observability_surfaces:
  - upload_active_content_denied logs with upload_id, reason, status, and duration only.
  - upload_download_denied and scanner-denial diagnostics with coarse extension, reason, scanner, result, status, and timing only.
  - Report/export unsafe-artifact denial logs with export_id, report_id where present, reason, status, response_status, role, and user_id only.
  - Response headers Content-Disposition attachment, X-Content-Type-Options nosniff, and Cache-Control no-store on owner/admin artifact downloads.
drill_down_paths:
  - .gsd/milestones/M014/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M014/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M014/slices/S04/tasks/T03-SUMMARY.md
  - .gsd/milestones/M014/slices/S04/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-05-13T22:59:37.874Z
blocker_discovered: false
---

# S04: Upload Stored-XSS e Private Artifact Serving

**Closed the upload stored-XSS and private artifact serving proof gap with pre-persistence active-content denial, owner/admin-gated non-executable downloads, and encoded/external export URL denial.**

## What Happened

S04 delivered the upload stored-XSS and private artifact serving lane for M014. T01 added a shared bounded active web-content guard that rejects active web extensions, declared or detected active MIME types, and first-64KiB HTML, SVG, XML, and script signatures with coarse reason codes. The guard is wired through upload type validation, MIME validation, and file-security scanning so low-level validation denies active web-document shapes even when python-magic is unavailable while benign PNG, PDF, and text fixtures still pass.

T02 wired that guard into upload and avatar ingress before durable persistence. Malicious upload or avatar content is sampled within existing caps and denied before Upload rows, stored files, derivatives, cache entries, public URLs, or user avatar metadata are created. Successful avatars persist under the configured public upload root avatars subtree so public URLs align with the intentional public-only static mount.

T03 hardened legacy private upload downloads and scanner diagnostics. Owner/admin access still goes through existing authorization and safe local path resolution, but file-backed private artifacts return with Content-Disposition attachment, X-Content-Type-Options nosniff, Cache-Control no-store, sanitized filenames, and application/octet-stream for active or unknown MIME/extension metadata. Anonymous and foreign requests are denied without bytes or path leaks. Scanner and MIME/file-security logs were scrubbed to coarse extension, reason, status, scanner, result, and timing metadata rather than raw file paths, storage paths, tracebacks, filenames, or uploaded bytes.

T04 extended the same non-executable attachment pattern to generated reports and enhanced report exports. Base report downloads, enhanced builder downloads, and export fallback payloads use the shared in-memory attachment helper; HTML fallback content is downgraded away from text/html. Unsafe export download_urls are withheld from status responses and denied on download without redirects. The closeout security review found a remaining raw-string sanitizer bypass for external, protocol-relative, and percent-encoded private upload URLs; this execution fixed it by bounded percent-decoding before urlsplit classification and by denying schemes, netlocs, protocol-relative URLs, encoded backslashes, encoded and double-encoded /uploads paths, Windows-style paths, private roots, and malformed download_urls. MEM093 captures this gotcha for S05 and future report/export work.

The slice uses only controlled pytest fixtures, in-memory cache/service seams, local tmp paths, mocked scanner/provider boundaries, and synthetic users/patients. It does not read production files, .planning, .audits, secrets, live providers, or real patient data.

## Verification

Fresh closeout verification after the export URL sanitizer fix passed through gsd_exec from the project root.

1. Focused S04 proof command: gsd_exec 55eacbb1-957e-4ddb-93b3-dcf1cadf6eff ran PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py and passed with 75 tests.
2. Supporting regression command: gsd_exec cba439b4-eb1a-4141-883f-7426323e29fb ran PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py and passed with 18 tests.
3. Full combined S04 closeout suite: gsd_exec d6c102d6-e4cb-494f-ab66-259ddd31b4e7 ran all six S04 proof and regression files together and passed with 93 tests.
4. Focused report/export sanitizer regression: gsd_exec a59f3ea2-74e1-46bb-a4f6-23c22a6fa564 ran the report artifact and ownership suites and passed with 32 tests, including external URL, protocol-relative URL, encoded /uploads, double-encoded /uploads, and encoded Windows-backslash denial cases.

## Requirements Advanced

- R012 — Advanced medium hardening proof for PHI client/report artifact serving by ensuring private uploads and generated reports are owner/admin-gated, no-store, nosniff, and attachment-only.
- R013 — Closed the upload stored-XSS proof gap with deterministic tests for active extension, active MIME, spoofed payload, avatar bypass, legacy private artifact, and report/export artifact denial cases.
- R015 — Kept evidence controlled and local with pytest fixtures, in-memory cache/service seams, mocked scanners/providers, and synthetic data only.
- R017 — Maintained PHI and path-safe diagnostics by asserting denial bodies and logs do not expose storage paths, filesystem paths, tokens, uploaded bytes, or patient identifiers.
- R018 — Produced S04 command evidence and residual-scope notes for S05 to map rather than silently dropping upload/report artifact proof rows.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

Health signal: the focused proof command, supporting regression command, and full combined S04 suite pass; owner/admin artifact downloads expose attachment, nosniff, and no-store headers; unsafe export URLs produce empty public download_urls and no Location redirects.

Failure signal: any non-zero S04 pytest result, any active upload creating a DB row/file/cache/avatar URL, any private/report artifact served inline or without nosniff/no-store, any anonymous/foreign response containing artifact bytes or PHI/path/token values, or any unsafe export URL appearing in status/download responses.

Recovery procedure: fail closed by keeping active-content denial before persistence, disable unsafe export redirects by withholding download_urls, route private artifacts through the shared attachment helpers, scrub diagnostics to IDs and coarse reason/status fields, clear any generated unsafe cache fixtures, and rerun the focused and supporting S04 commands before reopening S05 evidence mapping.

Monitoring gaps: S04 proves controlled local contract/integration behavior only. It does not prove production CDN/browser rendering, real malware scanner engines, live provider-generated reports, object-storage signed URL policy, or production telemetry; those remain evidence-matrix or later-runtime concerns.

## Deviations

T02 added a SQLite test-schema compatibility fix in backend-hormonia/tests/conftest.py so focused route suites can create local schemas. T04 was reopened by closeout security review and extended to canonicalize export download URL classification for external, protocol-relative, and encoded private-path bypasses.

## Known Limitations

S04 does not execute live production uploads, real scanner engines, object storage, CDN/browser rendering, live report providers, or real patient data. It proves local controlled behavior only.

## Follow-ups

S05 should map gsd_exec evidence 55eacbb1-957e-4ddb-93b3-dcf1cadf6eff, cba439b4-eb1a-4141-883f-7426323e29fb, d6c102d6-e4cb-494f-ab66-259ddd31b4e7, and a59f3ea2-74e1-46bb-a4f6-23c22a6fa564 into the M014 evidence matrix. S05 should keep production object-storage/CDN/live-scanner/runtime proof explicitly deferred if still out of scope.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/upload/active_content.py` — Shared bounded active web-content guard with coarse reason codes.
- `backend-hormonia/app/api/v2/routers/upload/handlers.py` — Upload ingress denies active content before persistence and private downloads use safe file attachment responses.
- `backend-hormonia/app/api/v2/routers/auth.py` — Avatar upload path reuses active-content guard before durable avatar writes.
- `backend-hormonia/app/utils/download_responses.py` — Shared attachment response helpers for file-backed and in-memory private artifacts.
- `backend-hormonia/app/api/v2/routers/reports.py` — Base generated reports use safe attachment responses after owner/admin access checks.
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py` — Enhanced builder/export downloads use safe attachment responses and canonicalized unsafe URL denial.
- `backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py` — Report/export attachment and unsafe URL denial proof including encoded/external bypass regressions.
