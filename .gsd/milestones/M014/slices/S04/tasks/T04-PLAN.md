---
estimated_steps: 5
estimated_files: 5
skills_used:
  - api-design
  - tdd
  - security-review
  - verify-before-complete
---

# T04: Extend report/export artifact attachment proof and closeout suite

Why: S04 also owns generated artifact serving. Existing report ownership tests prove raw owner checks and unsafe URL denial, but they do not assert attachment/nosniff/no-store behavior or HTML export fallback non-execution. This task closes that report/export portion and provides the final S04 command suite for S05.

Executor skills_used frontmatter to record: `api-design`, `tdd`, `security-review`, `verify-before-complete`.

Threat Surface (Q3): cached report/export metadata may expose unsafe `/uploads`, `file:`, `data:`, `javascript:`, absolute/private-root URLs or fallback HTML content; attacker may try to redirect/render active artifact content. Sensitive data includes patient report contents, report IDs/ownership metadata, and private artifact paths.
Requirement Impact (Q4): touches R012 private artifact/report serving, R013 proof gap, R015 controlled proof, R017 diagnostics, R018 evidence matrix. Re-verify existing report ownership closure tests and new artifact header tests.
Failure Modes (Q5): missing/ambiguous raw owner metadata fails closed before formatting; unsafe download URLs return generic 404 and no redirect; unsupported real artifact URL stays 501/controlled behavior; fallback HTML is attachment/non-executable; malformed download_urls are withheld.
Load Profile (Q6): report response generation remains existing in-memory fixture formatting; per-operation header helper is trivial; 10x load bottleneck remains existing report formatting/cache service, not new header logic.
Negative Tests (Q7): base JSON/CSV/PDF downloads, builder JSON/CSV downloads, HTML export fallback, unsafe `/uploads/private`, `file:`, `data:`, `javascript:`, absolute/private root URLs, malformed download_urls, foreign/missing owner metadata.

Do:
1. Update `backend-hormonia/app/api/v2/routers/reports.py` base download responses to use safe attachment headers (`Content-Disposition`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store` or stricter) without changing owner/admin access semantics.
2. Update `backend-hormonia/app/api/v2/routers/enhanced_reports.py` builder downloads and export fallback downloads to use the same safe attachment/header helper; ensure HTML fallback is non-executable (prefer `application/octet-stream` for HTML/active fallback, or at minimum attachment plus nosniff/no-store if compatibility requires keeping `text/html`).
3. Keep unsafe export URL filtering fail-closed: `/uploads`, `uploads/`, embedded `/uploads/`, `file:`, `data:`, `javascript:`, Windows/absolute/private roots, malformed `download_urls` produce no public status URL and no redirect/body path leak.
4. Add focused proof in `backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py` and strengthen `backend-hormonia/tests/api/v2/test_report_ownership_closure.py` only where needed for header assertions and no-redirect denial coverage.
5. Run the full S04 closeout suite and record the `gsd_exec` IDs in the eventual task/slice summary so S05 can map these evidence rows.

Must-haves:
- Existing owner/admin/foreign/missing report access behavior is preserved and not replaced by header-only checks.
- Downloadable report/export artifacts are attachments with nosniff/no-store; unsafe URLs never redirect to `/uploads` or private roots.
- Tests use fixture cache/service data only and do not read production files, `.gsd/`, `.planning/`, `.audits/`, secrets, or real patient data.

Done when: new report artifact tests plus existing report ownership closure tests pass, then the focused and supporting S04 command suites from the slice success criteria pass.

## Inputs

- `backend-hormonia/app/utils/download_responses.py`
- `backend-hormonia/app/api/v2/routers/reports.py`
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/reports.py`
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py`
- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py

## Observability Impact

Preserves report/export unsafe-artifact denial logs with report_id/export_id/reason/status only and adds testable response-header signals (`Content-Disposition`, `X-Content-Type-Options`, `Cache-Control`) that future agents can inspect without seeing PHI or private paths.
