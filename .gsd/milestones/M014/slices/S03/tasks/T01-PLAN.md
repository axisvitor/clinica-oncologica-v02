---
estimated_steps: 32
estimated_files: 3
skills_used: []
---

# T01: Classify browser-sensitive backend responses as no-store

---
estimated_steps: 8
estimated_files: 3
skills_used:
  - api-design
  - tdd
  - verify-before-complete
---

Why: S03 cannot prove browser PHI cache safety while `CacheMiddleware` treats only `Authorization: Bearer` as authenticated and emits `Cache-Control: public`/`ETag` for cookie-backed or tokenized GETs. This task creates the backend no-store contract while keeping intentional non-PHI caching testable.

Files: `backend-hormonia/app/middleware/cache_headers.py`, `backend-hormonia/app/middleware/cache_middleware.py`, `backend-hormonia/tests/security/test_m014_s03_cache_headers.py`.

Do:
1. Add a small reusable cache-header/classification seam, preferably `backend-hormonia/app/middleware/cache_headers.py`, with functions for sensitive request/path detection and no-store header application.
2. Classify as browser-sensitive when any auth/session/CSRF/quiz cookie is present (`session`, `session_id`, `quiz_session_id`, `quiz_session_state`, CSRF/session cookie names), any `Authorization` header is present, query params include `token`/`access_token`/session-like values, the response sets cookies, or the path is PHI/session-bearing (`/api/v2/patients`, `/api/v2/dashboard`, `/api/v2/reports`, `/api/v2/quiz-extensions/session/active`, `/api/v2/quiz-extensions/monthly/public/current`, public quiz access/submit/logout paths).
3. Wire `CacheMiddleware.dispatch` so sensitive requests are detected before exclude/cache-key logic for every method: call the endpoint, apply no-store headers, remove public cache-control and reusable validator headers, and never read/write `http_cache` for that response.
4. Preserve useful caching for clearly non-PHI GETs by leaving the existing miss/store/hit/ETag behavior intact when the classifier says non-sensitive.
5. Add focused tests with a tiny FastAPI app and in-memory/fake cache manager rather than relying on production middleware setup: cookie-only session GET, bearer auth, token query, PHI path prefix, response `Set-Cookie`, and public static GET miss/hit.
6. Assert sensitive paths do not call the fake cache manager, do not expose `public`, do include no-store/Pragma/Expires, and avoid reusable validators; assert the non-PHI route stores once and returns a HIT on the second request.

Failure Modes (Q5): Cache manager lookup/write exceptions on sensitive routes must be impossible because the cache is bypassed; cache exceptions on non-sensitive routes may serve fresh responses but must not make PHI paths cacheable; malformed cookies/query strings should classify conservatively rather than trying to parse secrets.

Load Profile (Q6): Header/path/cookie classification is O(number of headers/cookies/query params); sensitive bodies are no longer copied into cache storage; non-PHI cache keeps existing TTL/size behavior.

Negative Tests (Q7): Session cookie without bearer auth, arbitrary `Authorization` header, token query strings, PHI path prefixes, response `Set-Cookie`, conditional request headers on sensitive paths, and a non-PHI GET proving cache still works.

Done when: the focused backend security test passes and proves sensitive browser/session responses are no-store/non-replayable while a non-PHI GET still has deterministic MISS/HIT evidence.

## Inputs

- `backend-hormonia/app/middleware/cache_middleware.py` — existing HTTP cache implementation and cache-manager integration.
- `backend-hormonia/app/core/middleware_setup.py` — confirms real app middleware wiring and default behavior.
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py` — public quiz session/cookie paths that must classify as sensitive.
- `backend-hormonia/tests/conftest.py` — test conventions and client/cache fixture patterns.

## Expected Output

- `backend-hormonia/app/middleware/cache_headers.py` — new/central sensitive-response classification and no-store helpers.
- `backend-hormonia/app/middleware/cache_middleware.py` — cache middleware wired to bypass sensitive responses and preserve non-PHI caching.
- `backend-hormonia/tests/security/test_m014_s03_cache_headers.py` — focused deterministic proof for no-store and non-PHI cache behavior.

## Verification

- `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s03_cache_headers.py`

## Inputs

- `backend-hormonia/app/middleware/cache_middleware.py`
- `backend-hormonia/app/core/middleware_setup.py`
- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`
- `backend-hormonia/tests/conftest.py`

## Expected Output

- `backend-hormonia/app/middleware/cache_headers.py`
- `backend-hormonia/app/middleware/cache_middleware.py`
- `backend-hormonia/tests/security/test_m014_s03_cache_headers.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s03_cache_headers.py

## Observability Impact

Sensitive responses become inspectable via explicit no-store headers; non-sensitive cache diagnostics remain visible via `X-Cache`/`ETag`. Cache-bypass logs must include only route/method/classification reason and no cookies, tokens, or PHI.
