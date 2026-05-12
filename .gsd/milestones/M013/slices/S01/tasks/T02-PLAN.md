---
estimated_steps: 39
estimated_files: 4
skills_used: []
---

# T02: Add reusable SSRF validation for WuzAPI media URLs

Executor metadata:
- estimated_steps: 9
- estimated_files: 4
- skills_used: security-review, tdd, verify-before-complete

Why: closes the reusable guard portion of R002 by classifying media URLs and resolved addresses before any outbound HTTP request is possible.

Files:
- `backend-hormonia/app/integrations/wuzapi/ssrf_guard.py`
- `backend-hormonia/app/integrations/wuzapi/errors.py`
- `backend-hormonia/app/integrations/wuzapi/__init__.py`
- `backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py`

Do:
1. Add a generic `UnsafeMediaUrlError` (or similarly named subclass of `WuzAPIError`) to `errors.py`; its message must be generic such as `Blocked media URL` and must not include the full URL.
2. Create `ssrf_guard.py` with a narrow public API such as `async validate_media_url(url: str) -> str` plus injectable helpers for DNS resolution and address classification.
3. Parse with `urllib.parse.urlsplit`; allow only `http` and `https`; require a hostname; reject username/password/userinfo; reject invalid ports; normalize only enough for safe validation without rewriting attacker-controlled query strings into logs.
4. Treat IP literals directly with `ipaddress.ip_address`; otherwise resolve hostnames through an async `resolve_host(host, port)` seam that tests can monkeypatch. If resolution fails, returns no addresses, or returns mixed public+blocked answers, fail closed.
5. Reject loopback, private, link-local, multicast, unspecified, reserved, carrier-grade NAT (`100.64.0.0/10`), IPv6 ULA/link-local/reserved equivalents, and metadata destinations including `169.254.169.254` via IP classification. Also reject obvious localhost hostnames before DNS.
6. Keep any logging optional and sanitized; never log full URL, query string, bearer token, cookie or media path.
7. Export the new error/guard only if needed by tests or media code; avoid broad public API expansion.
8. Add deterministic unit tests in `test_ssrf_guard.py` for allowed public host resolution and for all blocked classes without real DNS/network access.
9. Include negative tests for malformed URL strings, unsupported schemes (`file:`, `ftp:`), userinfo (`https://user:pass@example.com/file`), missing host, invalid port, DNS failure, private/loopback/link-local/metadata IP literals, mixed DNS answers, and localhost-like names.

Failure Modes (Q5):

| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|------------------------|
| DNS resolver seam | Raise generic `UnsafeMediaUrlError` before HTTP | Raise generic `UnsafeMediaUrlError` before HTTP | Empty/non-IP/mixed responses fail closed with generic `UnsafeMediaUrlError` |
| URL parser | Raise generic `UnsafeMediaUrlError` | N/A | Unsupported scheme, missing host, userinfo or invalid port fail closed |

Load Profile (Q6):

- **Shared resources**: OS DNS resolver only; no database/cache/WuzAPI client.
- **Per-operation cost**: one hostname parse plus one DNS resolution for hostnames; IP literals skip DNS.
- **10x breakpoint**: DNS latency/concurrency; guard should be lightweight, async-compatible and bounded by caller timeout policy.

Negative Tests (Q7):

- **Malformed inputs**: empty string, relative path, missing host, invalid port, unsupported schemes, userinfo.
- **Error paths**: DNS failure, no answers, non-IP answer parsing failure.
- **Boundary conditions**: any blocked address among multiple DNS answers rejects the whole URL; public IPv4/IPv6 answers pass.

Must-haves:
- [ ] Guard has an injectable resolver seam and does not perform real network calls in tests.
- [ ] Block decisions are based on `ipaddress`, not regex-only matching.
- [ ] Any ambiguity fails closed with a generic, non-URL-leaking exception.
- [ ] Tests cover both allowed public hosts and blocked SSRF classes.

Done when: the new SSRF guard test module passes independently.

## Inputs

- `backend-hormonia/app/integrations/wuzapi/errors.py`
- `backend-hormonia/app/integrations/wuzapi/__init__.py`
- `backend-hormonia/app/integrations/wuzapi/media.py`
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py`

## Expected Output

- `backend-hormonia/app/integrations/wuzapi/ssrf_guard.py`
- `backend-hormonia/app/integrations/wuzapi/errors.py`
- `backend-hormonia/app/integrations/wuzapi/__init__.py`
- `backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py -q

## Observability Impact

Adds a single generic blocked-media-url failure class. Any diagnostic logging should be sanitized to host classification or hash only; tests should assert exception text does not include the attacker URL where practical.
