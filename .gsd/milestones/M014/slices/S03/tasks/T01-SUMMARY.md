---
id: T01
parent: S03
milestone: M014
key_files:
  - backend-hormonia/app/middleware/cache_headers.py
  - backend-hormonia/app/middleware/cache_middleware.py
  - backend-hormonia/tests/security/test_m014_s03_cache_headers.py
key_decisions:
  - Browser-sensitive backend responses are classified before cache-key lookup and bypass `http_cache` entirely; response-level Set-Cookie detection also forces no-store after the endpoint runs.
  - Cache diagnostics (`X-Cache`, reusable validators) remain available only for non-sensitive cacheable GETs and are stripped from sensitive responses.
duration: 
verification_result: passed
completed_at: 2026-05-13T19:51:59.131Z
blocker_discovered: false
---

# T01: Classified browser-sensitive backend responses as no-store and bypassed HTTP cache replay for auth, cookie, token, PHI, quiz, and Set-Cookie routes while preserving MISS/HIT caching for safe public GETs.

**Classified browser-sensitive backend responses as no-store and bypassed HTTP cache replay for auth, cookie, token, PHI, quiz, and Set-Cookie routes while preserving MISS/HIT caching for safe public GETs.**

## What Happened

Added a reusable cache-header classification seam in `backend-hormonia/app/middleware/cache_headers.py` with sanitized sensitivity reasons for sensitive path prefixes, any Authorization header, session/CSRF/quiz/token cookie names, token/session/CSRF query parameters, malformed cookie/query fallbacks, and cookie-setting responses. Wired `CacheMiddleware.dispatch` to classify requests before exclude/cache-key/cache-manager logic, call the endpoint directly for sensitive requests, apply no-store headers, strip reusable validators/diagnostics, and avoid all `http_cache` lookup/write paths. Preserved existing non-PHI GET cache behavior for safe public/static routes, including ETag generation, public Cache-Control, X-Cache MISS/HIT diagnostics, and cache-manager storage. Added focused FastAPI/TestClient coverage using an in-memory fake cache manager for cookie-only session GETs, arbitrary Authorization headers, token queries, PHI path prefixes, public quiz session paths, Set-Cookie responses, and a non-PHI static GET proving one store and deterministic MISS then HIT.

## Verification

Ran the focused backend security verification command: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s03_cache_headers.py`. It passed 7 tests, proving sensitive responses return no-store/Pragma/Expires without public cache headers, ETag, X-Cache, or fake cache-manager access, while `/public-static` still stores once and returns MISS then HIT.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s03_cache_headers.py` | 0 | ✅ pass — 7 pytest tests passed | 22535ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/middleware/cache_headers.py`
- `backend-hormonia/app/middleware/cache_middleware.py`
- `backend-hormonia/tests/security/test_m014_s03_cache_headers.py`
