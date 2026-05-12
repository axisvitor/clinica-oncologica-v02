---
id: T03
parent: S01
milestone: M013
key_files:
  - backend-hormonia/app/integrations/wuzapi/media.py
  - backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py
key_decisions:
  - Reused the T02 `validate_media_url` guard instead of duplicating SSRF URL/IP checks in the media downloader.
  - Disabled aiohttp automatic redirects and implemented a small bounded manual redirect loop so every redirect target is validated before fetch.
  - Changed the oversize media exception to include only non-sensitive limit/read detail, not the attacker-controlled URL.
duration: 
verification_result: passed
completed_at: 2026-05-12T17:53:55.841Z
blocker_discovered: false
---

# T03: Wired the WuzAPI media SSRF guard into initial media fetches and bounded manual redirect handling.

**Wired the WuzAPI media SSRF guard into initial media fetches and bounded manual redirect handling.**

## What Happened

Updated `fetch_and_encode_media` so it validates the initial URL with the T02 `validate_media_url` guard before opening a client session or issuing any GET. Replaced aiohttp automatic redirects with `allow_redirects=False` and a bounded manual redirect loop that resolves relative `Location` headers with `urljoin`, validates every redirect candidate before the next request, and fails closed with `UnsafeMediaUrlError` for missing, unsafe, or excessive redirects. Preserved existing media behavior for MIME parsing, octet-stream defaulting, 64 KiB chunk iteration, the 16 MB cap, and base64 data URI output. Sanitized the oversize error so it reports the size boundary and bytes read without embedding attacker-controlled media URLs. Expanded the media test harness to record `allow_redirects`, queue multiple responses, monkeypatch the resolver seam to public/private answers without real DNS, prove private initial resolution is blocked before GET, prove metadata redirects are blocked before the second GET, and confirm safe relative redirects still work after validation.

## Verification

Ran the focused WuzAPI media tests and the required slice-level verification command. The final command covered `test_ssrf_guard.py`, `test_wuzapi_media.py`, and `test_whatsapp_management_auth.py`; all tests passed. The media tests assert all session GET calls use `allow_redirects=False`, blocked private/metadata destinations are never fetched, URL/token details are absent from unsafe and oversize exception text, and existing MIME/default/oversize behavior remains covered.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py -q` | 0 | ✅ pass | 32321ms |
| 2 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py -q` | 0 | ✅ pass | 25962ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/integrations/wuzapi/media.py`
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py`
