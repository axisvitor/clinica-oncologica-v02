# S04: Upload Stored-XSS e Private Artifact Serving — UAT

**Milestone:** M014
**Written:** 2026-05-13T22:59:37.882Z

## UAT Type

Automated controlled security UAT. No production runtime, live providers, secrets, or real patient data are required.

## Preconditions

1. Run from the repository root.
2. Python test dependencies for backend-hormonia are installed.
3. Use only fixture users, fixture patients, in-memory cache/service seams, mocked scanner/provider behavior, and tmp_path files.
4. Do not use production uploads, .planning, .audits, secrets, live provider credentials, or real PHI.

## Steps

1. Run the focused S04 proof command:
   PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py

   Expected: all tests pass. Active .html, .htm, .xhtml, .svg, .xml, declared text/html or image/svg+xml, spoofed text/plain or image/png script payloads, and avatar bypass payloads are denied before durable persistence. Owner/admin private and report artifacts download only as attachments with nosniff and no-store. HTML fallback export content is not served as text/html. Unsafe raw and encoded export URLs are withheld and never redirected.

2. Run the supporting regression command:
   PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py

   Expected: all tests pass. Existing owner/admin access remains allowed, foreign/anonymous/missing-owner access remains denied, and report/private upload regression paths retain attachment, nosniff, no-store, no redirect, and generic denial behavior.

3. Optional reviewer cross-check: run the full combined S04 suite from the task plan.

   Expected: all six S04 proof and regression files pass together. In this closeout the combined run was gsd_exec d6c102d6-e4cb-494f-ab66-259ddd31b4e7 with 93 passing tests.

## Edge Cases Covered

- Active file extensions and active declared or detected MIME types.
- Spoofed benign MIME declarations containing active HTML, SVG, XML, or script signatures.
- Avatar uploads that previously bypassed the main upload route.
- Legacy private artifacts with active-looking filenames or unknown MIME metadata.
- Malicious filenames attempting header injection or inline rendering.
- Anonymous, foreign-owner, missing-owner, and admin/owner boundaries.
- Base report, enhanced builder, and export fallback downloads.
- Unsafe export URLs using /uploads, embedded /uploads, encoded /uploads, double-encoded /uploads, file, data, javascript, external http/https, protocol-relative, Windows-style, encoded backslash, private-root, and malformed download_urls shapes.

## Not Proven By This UAT

- Production CDN, proxy, or browser rendering behavior.
- Real malware scanner engines or live provider-generated report files.
- Object-storage signed URL policy and expiry behavior.
- Production telemetry quality under real traffic.
- Runtime security validation outside controlled local fixtures; those remain for S05 evidence mapping or later M015 runtime validation.
