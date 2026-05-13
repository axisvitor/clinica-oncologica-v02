# S03: Browser PHI Cache e Quiz Frontend Proof

**Goal:** Close the browser PHI cache and quiz frontend proof gap by making session/auth/token-bearing backend responses no-store and non-replayable from the HTTP cache, allowing only explicitly non-PHI dashboard React Query data into IndexedDB persistence, and removing quiz answer/free-text/patient-label localStorage persistence while preserving controlled non-PHI cache behavior.
**Demo:** Reviewer runs backend cache-header tests plus targeted frontend/quiz tests showing PHI responses are no-store/non-persistent, non-PHI cache still works, and quiz frontend coverage now has deterministic pass/fail evidence.

## Must-Haves

- ## Must-Haves
- Backend sensitive browser responses are denied HTTP cache storage/replay and return `Cache-Control: no-store, no-cache, max-age=0, must-revalidate`, `Pragma: no-cache`, and `Expires: 0` for session-cookie, auth-header, token-query, patient/dashboard/report, and public quiz session paths.
- Backend non-PHI/public GET responses still prove useful HTTP caching with `Cache-Control: public, max-age=...`, `ETag`, and deterministic `X-Cache` miss/hit behavior in a controlled test app.
- Dashboard React Query persistence defaults to deny, drops patient/dashboard/report/message/AI/alert/physician/clinical/auth/monthly-quiz-status query data, and keeps only explicit non-PHI/static allowlist keys.
- Public quiz frontend no longer stores answers, free-text `otherTexts`, patient/template labels, session identifiers, token values, or signed cookie state in `localStorage`/`sessionStorage`; legacy `quiz-progress-*` entries are cleared deterministically.
- Verification is deterministic and local only: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s03_cache_headers.py`, `npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts`, and `npm --prefix quiz-mensal-interface test -- tests/security/quiz-progress-storage.test.tsx tests/security/no-phi-local-storage.test.tsx` pass.
- ## Threat Surface (Q3)
- **Abuse**: Browser/proxy replay of session-cookie GETs, tokenized quiz links cached under public headers, IndexedDB/localStorage recovery of another user's PHI after logout/shared device, and stale quiz answer replay.
- **Data exposure**: Patient IDs/names, dashboard/clinical/report/message payloads, quiz answers/free text, template labels, session IDs, CSRF/token-like query data, and signed quiz cookie state.
- **Input trust**: Cookies, authorization headers, query tokens, React Query keys/payloads, and legacy localStorage records are untrusted and must be classified/filter-cleared before persistence.
- ## Requirement Impact (Q4)
- **Requirements touched**: R012, R013, R015, R017, R018.
- **Re-verify**: HTTP cache headers/cache replay, dashboard IndexedDB persistence, quiz frontend storage behavior, and existing legitimate non-PHI cache behavior.
- **Decisions revisited**: D021 applies; S01 CSRF/session-cookie assumptions are consumed without weakening the signed public quiz session-state contract.
- ## Failure Modes (Q5)
- Cache backend unavailable or corrupt must not make sensitive responses cacheable; it may fail open only by serving the fresh response with no-store headers.
- IndexedDB unavailable, oversized, or malformed persisted-client state must degrade to in-memory React Query behavior without persisting PHI.
- localStorage unavailable, malformed legacy records, or private-mode exceptions must not block quiz usage and must not leak answers/labels/tokens.
- ## Load Profile (Q6)
- Backend classification is O(path/header/cookie/query count) per request and avoids storing sensitive bodies in `http_cache`; non-PHI cache remains bounded by existing TTLs.
- Dashboard persisted-client filtering is O(number of dehydrated queries) and must reduce, not increase, IndexedDB size under 10x patient/dashboard query volume.
- Quiz legacy cleanup is O(localStorage key count) and should only run at page/session boundaries, not per keystroke.
- ## Negative Tests (Q7)
- Session cookie without bearer auth, bearer auth, token query strings, PHI path prefixes, malformed legacy quiz progress JSON, PHI query keys with object/array variants, and allowlisted static keys adjacent to denied PHI keys.
- Assert denied/sensitive paths have no `public` cache-control, no reusable validators, no cache-manager writes, and no local/IndexedDB persisted payloads containing PHI fixtures.

## Proof Level

- This slice proves: Contract/integration proof with controlled local pytest, Vitest, and Jest fixtures. No production runtime, live providers, real patient data, or secret-bearing files are required or allowed.

## Integration Closure

Consumes S01's session-cookie/CSRF hardening and public quiz signed-state model. Wires the cache classification into `CacheMiddleware`, React Query persistence into the existing `PersistQueryClientProvider` path, and quiz state into backend-session recovery. Leaves upload stored-XSS/private artifact serving to S04 and final M014 evidence matrix/JWT/config closure to S05.

## Verification

- Adds deterministic, PHI-safe inspection through cache headers (`Cache-Control`, `Pragma`, `Expires`, `X-Cache` only for non-sensitive cache diagnostics) and sanitized query-cache metadata/counts. Logs/tests must never emit raw cookies, tokens, patient names, answers, prompt text, report contents, or private filesystem paths.

## Tasks

- [x] **T01: Classify browser-sensitive backend responses as no-store** `est:2h`
  ---
  estimated_steps: 8
  estimated_files: 3
  skills_used:
    - api-design
    - tdd
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/middleware/cache_headers.py`, `backend-hormonia/app/middleware/cache_middleware.py`, `backend-hormonia/tests/security/test_m014_s03_cache_headers.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s03_cache_headers.py

- [x] **T02: Add deny-by-default dashboard React Query persistence allowlist** `est:2h`
  ---
  estimated_steps: 8
  estimated_files: 5
  skills_used:
    - react-best-practices
    - tdd
    - verify-before-complete
  ---
  - Files: `frontend-hormonia/src/lib/react-query/persistencePolicy.ts`, `frontend-hormonia/src/lib/react-query/persistentCache.ts`, `frontend-hormonia/src/lib/react-query/queryClient.ts`, `frontend-hormonia/src/App.tsx`, `frontend-hormonia/tests/unit/react-query/persistencePolicy.test.ts`
  - Verify: npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts

- [x] **T03: Remove quiz answer and PHI localStorage persistence** `est:2h`
  ---
  estimated_steps: 8
  estimated_files: 5
  skills_used:
    - react-best-practices
    - tdd
    - verify-before-complete
  ---
  - Files: `quiz-mensal-interface/lib/quiz-progress-storage.ts`, `quiz-mensal-interface/hooks/quiz/useQuizState.ts`, `quiz-mensal-interface/app/page.tsx`, `quiz-mensal-interface/tests/security/quiz-progress-storage.test.tsx`, `quiz-mensal-interface/tests/security/no-phi-local-storage.test.tsx`
  - Verify: npm --prefix quiz-mensal-interface test -- tests/security/quiz-progress-storage.test.tsx tests/security/no-phi-local-storage.test.tsx

## Files Likely Touched

- backend-hormonia/app/middleware/cache_headers.py
- backend-hormonia/app/middleware/cache_middleware.py
- backend-hormonia/tests/security/test_m014_s03_cache_headers.py
- frontend-hormonia/src/lib/react-query/persistencePolicy.ts
- frontend-hormonia/src/lib/react-query/persistentCache.ts
- frontend-hormonia/src/lib/react-query/queryClient.ts
- frontend-hormonia/src/App.tsx
- frontend-hormonia/tests/unit/react-query/persistencePolicy.test.ts
- quiz-mensal-interface/lib/quiz-progress-storage.ts
- quiz-mensal-interface/hooks/quiz/useQuizState.ts
- quiz-mensal-interface/app/page.tsx
- quiz-mensal-interface/tests/security/quiz-progress-storage.test.tsx
- quiz-mensal-interface/tests/security/no-phi-local-storage.test.tsx
