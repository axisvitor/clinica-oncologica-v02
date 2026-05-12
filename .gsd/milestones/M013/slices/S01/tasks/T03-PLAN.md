---
estimated_steps: 39
estimated_files: 2
skills_used: []
---

# T03: Wire SSRF guard into media fetch and redirect handling

Executor metadata:
- estimated_steps: 10
- estimated_files: 2
- skills_used: security-review, tdd, verify-before-complete

Why: closes the executable WuzAPI seam in R002 by ensuring `fetch_and_encode_media` validates the initial URL and every redirect before `aiohttp` can fetch attacker-controlled internal destinations, while preserving existing media behavior.

Files:
- `backend-hormonia/app/integrations/wuzapi/media.py`
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py`

Do:
1. Update `fetch_and_encode_media` to call the T02 guard before the first request. For blocked URLs, raise the generic unsafe-media error before constructing or invoking `ClientSession.get`.
2. Call `session.get(..., timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=False)` so aiohttp never follows redirects automatically.
3. Implement a small manual redirect loop (for example max 3 redirects). For each 3xx response with `Location`, resolve relative redirects with `urllib.parse.urljoin`, validate the candidate URL with the guard, and only then perform the next request. Missing/invalid/excessive redirects fail closed with the generic unsafe-media error.
4. Preserve current successful behavior: content type parsing, default `application/octet-stream`, 64 KiB chunk iteration, 16 MB maximum, and base64 data URI output.
5. Change `MediaTooLargeError` construction so it does not include the full media URL; keep useful non-sensitive detail such as size limit and bytes read.
6. Update the existing mock session in `test_wuzapi_media.py` to accept/record `allow_redirects` and multiple queued responses.
7. Update existing successful media tests to monkeypatch the SSRF resolver seam to return a public IP for `example.com`, avoiding real DNS.
8. Add `test_fetch_and_encode_media_blocks_private_resolution_before_get`: monkeypatch resolver for `attacker.test` to loopback/private, use a recording session, assert `UnsafeMediaUrlError` and zero `get` calls.
9. Add `test_fetch_and_encode_media_blocks_redirect_to_metadata`: first public host returns 302 to `http://169.254.169.254/latest/meta-data`; assert only the first request is made, the second destination is never fetched, and exception text does not contain the URL.
10. Add/keep assertions that every actual session call uses `allow_redirects=False`, and run both WuzAPI test files plus the WhatsApp auth test for final slice proof.

Failure Modes (Q5):

| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|------------------------|
| SSRF guard | Raise generic unsafe-media error before HTTP for blocked/ambiguous URLs | Raise generic unsafe-media error if validation cannot complete safely | Reject malformed URL/redirect before HTTP |
| Outbound HTTP response | Preserve `raise_for_status` behavior for allowed URLs | Preserve bounded `aiohttp.ClientTimeout(total=timeout)` | Missing/invalid redirect `Location` fails closed; missing content type defaults to octet-stream |

Load Profile (Q6):

- **Shared resources**: outbound HTTP connection/session and DNS resolver seam.
- **Per-operation cost**: at most one initial request plus a bounded redirect count; chunk memory remains capped at 16 MB.
- **10x breakpoint**: outbound socket/DNS latency and 16 MB in-memory media cap; no unbounded redirect following or response buffering beyond the existing cap.

Negative Tests (Q7):

- **Malformed inputs**: unsupported/private URLs and malformed redirect locations.
- **Error paths**: DNS/private resolution blocked before `get`; redirect to metadata blocked before second `get`; oversized media fails without URL leakage.
- **Boundary conditions**: exactly allowed public URL still encodes; response without content type still defaults; redirect count limit prevents loops.

Must-haves:
- [ ] Initial URL and every redirect are validated before outbound fetch.
- [ ] `allow_redirects=False` is passed on every `session.get` call.
- [ ] Blocked private/metadata destinations are never fetched.
- [ ] Existing MIME/default/oversize behavior remains covered by tests.
- [ ] Error messages do not expose full attacker-controlled media URLs.

Done when: WuzAPI media/guard tests and the WhatsApp auth test all pass together.

## Inputs

- `backend-hormonia/app/integrations/wuzapi/media.py`
- `backend-hormonia/app/integrations/wuzapi/ssrf_guard.py`
- `backend-hormonia/app/integrations/wuzapi/errors.py`
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py`
- `backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py`
- `backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py`

## Expected Output

- `backend-hormonia/app/integrations/wuzapi/media.py`
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py -q

## Observability Impact

The runtime media seam gains deterministic blocked-URL failures that are safe to persist through existing message failure handling because exception text is generic and does not contain full PHI-bearing URLs.
