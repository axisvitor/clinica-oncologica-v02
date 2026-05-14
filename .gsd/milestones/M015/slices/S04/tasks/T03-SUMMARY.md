---
id: T03
parent: S04
milestone: M015
key_files:
  - scripts/security/m015-runtime/artifact_seam.py
  - backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py
key_decisions:
  - Seed report and enhanced report/export metadata directly into Dragonfly using the same router cache key shapes the runtime app consumes, so the future Docker seam can exercise real FastAPI routes without dependency overrides.
  - Assert no unsafe/private redirects rather than a blanket no-redirect rule, preserving the existing safe redirect nuance for enhanced exports.
  - Keep report/export evidence to route labels, status classes, safe-header booleans, unsafe-url-withheld booleans, redirect booleans, hashes, and raw-value persistence flags.
duration: 
verification_result: passed
completed_at: 2026-05-14T16:48:39.382Z
blocker_discovered: false
---

# T03: Extended the S04 artifact probe to cover base report, enhanced builder, and enhanced export app-route proof with sanitized Redis-backed runtime fixtures and unsafe URL checks.

**Extended the S04 artifact probe to cover base report, enhanced builder, and enhanced export app-route proof with sanitized Redis-backed runtime fixtures and unsafe URL checks.**

## What Happened

Extended `artifact_seam.py` beyond upload proof to cover base report, enhanced builder, and enhanced export app-route behavior. The probe now has Redis cache helpers for the base report and enhanced reports route key formats, seeds synthetic owner/admin/foreign report metadata, calls `/api/v2/reports/{id}/download`, `/api/v2/enhanced-reports/builder/{id}/download`, `/api/v2/enhanced-reports/export/{id}`, and `/api/v2/enhanced-reports/export/{id}/download` over the same HTTP/cookie mechanism as uploads. It checks owner/admin report and builder downloads for safe attachment headers, anonymous/foreign report/builder denial without payload/ID leakage, unsafe `/uploads/private/...` export URL withholding in status, unsafe export download 404/no-location behavior, and fallback PDF/HTML downloads as safe attachments. The evidence model now includes an `artifact_probe.report` section and summary lines for base report and enhanced export outcomes while avoiding raw report bodies, raw download URLs, private paths, session IDs, or PHI-shaped values. Added static/unit contracts for report cache key shapes, export status sanitization, safe attachment requirements, and report/export evidence shape.

## Verification

Fresh T03 verification passed after the last edit: `cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/api/v2/test_report_ownership_closure.py tests/security/test_m014_s04_report_artifact_serving.py -q`. Pytest reported `......................................... [100%]` for 41 tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/api/v2/test_report_ownership_closure.py tests/security/test_m014_s04_report_artifact_serving.py -q` | 0 | ✅ pass — 41 report/export artifact runtime-contract and ownership regression tests reached 100% | 23300ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `scripts/security/m015-runtime/artifact_seam.py`
- `backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py`
