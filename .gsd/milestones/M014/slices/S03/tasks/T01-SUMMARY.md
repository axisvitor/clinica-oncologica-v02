---
id: T01
parent: S03
milestone: M014
key_files:
  - backend-hormonia/app/middleware/cache_headers.py
  - backend-hormonia/app/middleware/cache_middleware.py
  - backend-hormonia/tests/security/test_m014_s03_cache_headers.py
key_decisions:
  - Sensitive backend responses bypass `http_cache` before cache-key generation/read/write whenever request headers/cookies/query/path classify as browser-sensitive.
  - Set-Cookie responses are marked no-store and not written to `http_cache`; non-PHI GETs keep existing ETag/X-Cache MISS/HIT diagnostics.
duration: 
verification_result: passed
completed_at: 2026-05-13T19:10:01.159Z
blocker_discovered: false
---

# T01: Classified browser-sensitive backend responses as no-store and bypassed the HTTP cache for auth/session/token/PHI routes while preserving MISS/HIT caching for non-PHI GETs.

**Classified browser-sensitive backend responses as no-store and bypassed the HTTP cache for auth/session/token/PHI routes while preserving MISS/HIT caching for non-PHI GETs.**

## What Happened

Added `backend-hormonia/app/middleware/cache_headers.py` as a reusable cache-sensitivity seam with sanitized request classification, response Set-Cookie detection, no-store header application, and legacy sensitive cached-entry detection. Wired `CacheMiddleware.dispatch` to classify requests before method/exclude/cache-key logic, bypass `http_cache` entirely for sensitive requests, strip reusable validators (`ETag`, `Last-Modified`, `Age`, `X-Cache`) on sensitive responses, and preserve existing ETag/X-Cache MISS/HIT behavior for non-sensitive GET responses. Added focused FastAPI tests using a fake in-memory cache manager to prove cookie-only sessions, arbitrary Authorization headers, token query params, PHI path prefixes, public quiz session paths, and Set-Cookie responses become no-store/non-replayable, while a static non-PHI GET still stores once and returns a deterministic HIT on the second request.

## Verification

Ran the focused backend security test command from the task plan. It passed with 7 tests verifying sensitive responses include no-store/Pragma/Expires, omit public cache directives and reusable validators, avoid fake cache-manager calls for request-classified sensitive traffic, avoid cache writes for Set-Cookie responses, and preserve public static MISS/HIT cache behavior.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s03_cache_headers.py` | 0 | ✅ pass | 23038ms |

## Deviations

Implemented a slightly broader sensitive path prefix set than the minimum examples by including auth, alerts, messages, AI, clinical, and physician API prefixes as browser-sensitive no-store surfaces; this is conservative for PHI/LGPD hardening.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/middleware/cache_headers.py`
- `backend-hormonia/app/middleware/cache_middleware.py`
- `backend-hormonia/tests/security/test_m014_s03_cache_headers.py`
