# S03 Research — Browser PHI Cache e Quiz Frontend Proof

## Summary

Depth: deep targeted research because this slice crosses backend HTTP caching, dashboard React Query persistence, and the separate Next.js quiz app. There are two concrete proof gaps/defects:

1. `CacheMiddleware` can cache GET responses with `Cache-Control: public, max-age=...`; it treats only `Authorization: Bearer` as authenticated, so session-cookie GETs such as quiz recovery can be cached as public responses. There are no backend tests covering `Cache-Control`, `X-Cache`, `ETag`, or no-store behavior.
2. Quiz frontend progress persistence writes answers, free-text `otherTexts`, patient/template labels, and session IDs to `localStorage` for 7 days. Existing quiz security tests only check for exact key names before answers are saved, so they do not prove answer/PHI non-persistence.

Primary active requirements: R012/R013 for browser/cache/quiz proof, R015 for controlled local tests only, R017 for PHI/secret-safe evidence, and R018 so the M014 matrix has explicit cache/quiz rows.

## Recommendation

Close S03 with explicit classification instead of blanket cache removal:

1. **Backend browser cache hardening**
   - Add a small classification seam, e.g. `app/middleware/cache_headers.py` or methods inside `CacheMiddleware`, that decides whether a request/response is browser-sensitive.
   - Sensitive if any session/auth cookie is present (`session`, `session_id`, `quiz_session_id`, `quiz_session_state`, CSRF/session cookie names), if `Authorization` is present, if query params contain access tokens, or if the path is known PHI/session-bearing (`/api/v2/patients`, `/api/v2/dashboard`, `/api/v2/reports`, `/api/v2/quiz-extensions/session/active`, `/api/v2/quiz-extensions/monthly/public/current`, etc.).
   - For sensitive responses: bypass HTTP response cache storage/replay and set `Cache-Control: no-store, no-cache, max-age=0, must-revalidate`, `Pragma: no-cache`, and `Expires: 0`; avoid `public` and preferably avoid validator headers that enable reuse.
   - Keep clearly non-PHI/public endpoints cacheable (e.g. system config/static public data) so S03 can prove useful cache still works.

2. **Dashboard React Query persistence allowlist**
   - Current Vite dashboard persists the whole React Query state to IndexedDB for 7 days. Switch to an explicit allowlist/metadata predicate for persistence; default should be non-persistent.
   - Exclude PHI/user/session keys such as `patients`, `patient`, `dashboard`, `messages`, `reports`, `ai-*`, `alerts`, `physician`, `clinical`, `auth`, `monthly-quiz-status`, and similar patient-bound data.
   - Keep non-PHI/static query keys persistable when needed: templates/treatment distributions/system config/static dictionaries. Implement as `shouldPersistQuery`/`isPersistableQuery` and wire it through `PersistQueryClientProvider` `persistOptions` dehydrate filtering or a sanitizing persister wrapper.

3. **Quiz localStorage hardening**
   - Remove persistent answer storage. The safest M014 implementation is to stop saving quiz progress to localStorage entirely, clear legacy `quiz-progress-*` entries on load, and rely on HttpOnly cookies + backend `current_question`/session state for refresh recovery.
   - If product insists on client-side resume, persist only non-PHI minimal metadata (for example current question index and last-saved timestamp under a non-capability key). Do not store answers, free text, patient IDs/names, phone numbers, token values, raw session cookies, signed session state, or template/patient labels.
   - Update or remove `ResumeQuizDialog` flow accordingly; its current `QuizProgress` type encourages PHI/answer persistence.

## Implementation Landscape

### Backend HTTP cache

- `backend-hormonia/app/middleware/cache_middleware.py` caches successful GETs. It stores response bodies and headers in `http_cache` and returns `Cache-Control: public, max-age={ttl}` with `ETag` and `X-Cache` on fresh responses.
- `CacheMiddleware._is_authenticated()` only checks `Authorization: Bearer`. It does not treat session cookies or quiz cookies as authenticated/sensitive.
- `CacheMiddleware._generate_cache_key()` includes user identity only for bearer-authenticated requests. Cookie-backed session requests therefore look public to the HTTP cache.
- Default `exclude_patterns` skip auth/admin/alerts/ws/health only. PHI-heavy `/api/v2/patients`, `/api/v2/dashboard`, `/api/v2/reports`, and quiz session recovery are not excluded; some are given explicit positive TTLs.
- `backend-hormonia/app/core/middleware_setup.py` does not load `CacheMiddleware` in test mode, so focused cache-header tests should instantiate a tiny FastAPI app with the middleware or unit-test middleware helpers directly.
- No backend test files currently assert `Cache-Control`, `ETag`, `X-Cache`, `no-store`, or `CacheMiddleware` behavior (`gsd_exec 49137e79-4c32-4c03-9872-f88318fdf34d` found no matches).

### Public quiz backend

- `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py` has cookie/token-sensitive paths:
  - `GET /api/v2/quiz-extensions/auth/csrf-token` returns CSRF token and sets cookie.
  - `GET /api/v2/quiz-extensions/monthly/public/current?token=...` validates a link token and returns session/template/question data.
  - `POST /api/v2/quiz-extensions/access` sets `quiz_session_id` and signed `quiz_session_state` HttpOnly cookies; POST is not cached by `CacheMiddleware` but response headers can still be hardened.
  - `GET /api/v2/quiz-extensions/session/active` recovers via signed cookies and returns `quiz_session_id`, `patient_id`, questions, status, and `current_question_index`; this is the highest-risk GET.
  - `POST /submit` and `/logout` are not HTTP-cache candidates but should remain no-store if headers are added globally/locally.
- Public quiz security from earlier work uses signed `quiz_session_state` as the authorization proof; raw `quiz_session_id` is compatibility only (MEM021/MEM025). S03 should not weaken that.

### Dashboard React Query / IndexedDB

- `frontend-hormonia/src/App.tsx` wraps the whole app in `PersistQueryClientProvider client={queryClient} persistOptions={{ persister }}`.
- `frontend-hormonia/src/lib/react-query/queryClient.ts` configures a singleton `queryClient` and `persister` using `createIndexedDBPersister({ dbName: 'hormonia-query-cache', ttl: 7 days, maxSize: 50MB })`.
- `frontend-hormonia/src/lib/react-query/persistentCache.ts` stores the entire `PersistedClient` under IndexedDB object store `queryCache`, key `state`; no query filtering/sanitization is present.
- Many query keys are patient/dashboard/clinical/message/report related (`usePatients`, `useAI`, `useFlowEngine`, dashboard pages, reports/messages features). Persisting all state risks PHI staying in IndexedDB beyond logout/tab close.

### Quiz frontend / localStorage

- `quiz-mensal-interface/lib/quiz-progress-storage.ts` defines `QuizProgress` with `answers`, `otherTexts`, `patientName`, `templateName`, `sessionId`, and `totalQuestions`, and saves it to `localStorage` under `quiz-progress-v1-${sessionId}` for 7 days.
- `quiz-mensal-interface/hooks/quiz/useQuizState.ts` autosaves progress after answers are set and clears only on completion. It also reloads saved answers when `resumeFromSaved` is true.
- `quiz-mensal-interface/app/page.tsx` calls `cleanupOldProgress()`, loads progress for `session.quiz_session_id`, and shows `ResumeQuizDialog` if saved progress exists.
- `quiz-mensal-interface/tests/security/session-security.test.tsx` has storage tests, but they only inspect exact key names after initial render. They do not submit an answer or inspect stored values, so current tests would miss the real persistence issue.
- `quiz-mensal-interface/lib/api-client.ts` keeps CSRF token in RAM and uses `credentials: 'include'`; this part aligns with the desired model.

## Natural Seams / Task Candidates

1. **Backend no-store/cache classifier**
   - Files: `backend-hormonia/app/middleware/cache_middleware.py`, optional new `backend-hormonia/app/middleware/cache_headers.py`, `backend-hormonia/app/core/middleware_setup.py` if defaults need new exclude patterns.
   - Work: classify sensitive requests, bypass cache manager storage/replay, set no-store headers, keep public/non-PHI cache behavior.

2. **Backend cache proof tests**
   - Files: new `backend-hormonia/tests/security/test_m014_s03_cache_headers.py`.
   - Work: use a tiny app with fake cache manager to prove session-cookie GETs and PHI paths are no-store/no-cache-manager-set, while a non-PHI GET still gets public max-age and cache HIT on second request.

3. **React Query persistence filter**
   - Files: `frontend-hormonia/src/lib/react-query/queryClient.ts`, possibly `frontend-hormonia/src/lib/react-query/persistentCache.ts`, `frontend-hormonia/src/App.tsx`.
   - Work: introduce `shouldPersistQuery` allowlist; wire through persistence dehydrate options or sanitize `PersistedClient` before IndexedDB write.

4. **React Query persistence tests**
   - Files: new `frontend-hormonia/src/lib/react-query/queryClient.persistence.test.ts` or similar.
   - Work: prove PHI-like query keys/data are not persisted and safe static/template keys still are.

5. **Quiz localStorage removal/sanitization**
   - Files: `quiz-mensal-interface/lib/quiz-progress-storage.ts`, `quiz-mensal-interface/hooks/quiz/useQuizState.ts`, `quiz-mensal-interface/app/page.tsx`, `quiz-mensal-interface/components/quiz/ResumeQuizDialog.tsx` if the resume dialog becomes obsolete or metadata-only.
   - Work: prevent answer/patient/template/session sensitive values from entering localStorage; clear legacy entries.

6. **Quiz proof tests**
   - Files: new `quiz-mensal-interface/tests/unit/quiz-progress-storage.test.ts` and update `quiz-mensal-interface/tests/security/session-security.test.tsx`.
   - Work: direct storage utility test with synthetic PHI/answer values; component submit/autosave test that waits for debounce and asserts localStorage has no answer/free-text/patient/template data.

## First Proof

Start with the direct quiz storage unit test because it is deterministic and exposes the current gap without backend setup:

```ts
saveQuizProgress({
  sessionId: 'session-a',
  currentQuestionIndex: 1,
  answers: { q1: 'synthetic answer text' },
  otherTexts: { q2: 'synthetic free text' },
  patientName: 'Synthetic Patient',
  templateName: 'Synthetic Template',
  totalQuestions: 3,
  lastSaved: Date.now(),
})
expect(JSON.stringify(localStorage)).not.toContain('synthetic answer text')
expect(JSON.stringify(localStorage)).not.toContain('Synthetic Patient')
```

It should fail today. Then add backend cache-header proof for `Cookie: quiz_session_state=...` GET and dashboard/patient PHI paths.

## Verification Plan

Focused backend cache proof:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml \
  backend-hormonia/tests/security/test_m014_s03_cache_headers.py
```

Supporting backend quiz/session boundary proof (existing relevant suite):

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml \
  backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py \
  backend-hormonia/tests/unit/api/v2/test_quiz_sessions_orphan_security.py
```

Dashboard React Query persistence proof:

```bash
npm --prefix frontend-hormonia test -- src/lib/react-query/queryClient.persistence.test.ts
```

Quiz frontend proof:

```bash
npm --prefix quiz-mensal-interface test -- \
  tests/unit/quiz-progress-storage.test.ts \
  tests/security/session-security.test.tsx \
  tests/unit/use-quiz-session.test.tsx
```

Expected evidence: PHI/session/token-bearing GETs return no-store and are not stored/replayed by HTTP cache; non-PHI GET still uses deterministic public cache; React Query IndexedDB persistence excludes PHI query keys/data; quiz localStorage no longer contains answers/free text/patient labels/session capability data after interaction; existing quiz behavior still renders/submits under mocked APIs.

## Watch-outs / Constraints

- Do not claim all server-side Redis application caches are eliminated; S03 is about browser/client-visible HTTP cache and browser persistence. If internal Redis caches contain PHI, classify separately in S05 or a follow-up unless they affect browser cache proof.
- Avoid a blanket `no-store` on every endpoint if it breaks documented non-PHI performance. The acceptance criteria explicitly wants non-PHI cache to keep working.
- `CacheMiddleware` currently stores original response headers in cache. Sensitive responses must bypass storage entirely; setting no-store after storing the body is not enough.
- Tokenized public quiz GETs with token query parameters must be no-store even if they do not use cookies, because browser/proxy caches can persist token-bound responses.
- The quiz backend currently returns `patient_id` and `quiz_session_id` to the frontend. Do not add these to localStorage; ideally avoid rendering them into DOM as existing tests expect.
- Existing quiz progress resume UX depends on localStorage. If disabling localStorage, use backend `current_question`/`current_question_index` or accept a simpler resume contract for M014 proof.
- Existing security tests use synthetic strings; keep all new fixtures synthetic and assert evidence output does not contain names, phone numbers, answers, tokens, cookies, or private filesystem paths.

## Skill Discovery

Installed skills relevant from the prompt: `react-best-practices` for React/Next code changes, `api-design` for cache/header contract, `observability` for PHI-safe diagnostics, and `verify-before-complete` for evidence discipline. External skill search (`gsd_exec cc27828c-dbaf-44f1-917c-7b8315af2f6b`) found optional but not installed skills:

- FastAPI: `npx skills add wshobson/agents@fastapi-templates` (16.8K installs), `npx skills add mindrally/skills@fastapi-python` (8.6K), `npx skills add fastapi/fastapi@fastapi` (2.4K).
- TanStack Query: `npx skills add deckardger/tanstack-agent-skills@tanstack-query-best-practices` (5.4K installs), `npx skills add jezweb/claude-skills@tanstack-query` (2.5K), `npx skills add tanstack-skills/tanstack-skills@tanstack-query` (1.9K).
- Next.js: available Vercel skills are mostly docs/runtime-update oriented; installed `react-best-practices` is enough for this slice.

No skill installation is required before planning S03.

## Research Sources

- Memory: MEM003 PHI-safe fail-closed boundaries; MEM020 patient-bound route guard pattern; MEM021/MEM025 public quiz signed-state cookie model; MEM061 M014 slice order; MEM067 CSRF/session-backed mutation guidance.
- Code scans: `gsd_exec 2ee33584-ddb5-4354-865d-921d3ea137ba` (cache/storage/quiz candidates), `gsd_exec d7e93091-5322-48ae-91b8-b82ef8852b25` (React Query persistence setup/query keys; timed out after useful output due generated folders), `gsd_exec 76c9f818-0c5b-4aee-9462-710eec2b5fae` (quiz tests/storage), `gsd_exec 49137e79-4c32-4c03-9872-f88318fdf34d` (no backend cache-header tests found), `gsd_exec 01486ce5-88ef-421a-96a0-00219840d006` (explicit cache-control usage scan).
- Key files read: `backend-hormonia/app/middleware/cache_middleware.py`, `backend-hormonia/app/core/middleware_setup.py`, `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`, `frontend-hormonia/src/App.tsx`, `frontend-hormonia/src/lib/react-query/queryClient.ts`, `frontend-hormonia/src/lib/react-query/persistentCache.ts`, `quiz-mensal-interface/lib/quiz-progress-storage.ts`, `quiz-mensal-interface/hooks/quiz/useQuizState.ts`, `quiz-mensal-interface/app/page.tsx`, `quiz-mensal-interface/lib/api-client.ts`, `quiz-mensal-interface/tests/security/session-security.test.tsx`.
