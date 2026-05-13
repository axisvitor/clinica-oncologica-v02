---
id: S03
parent: M014
milestone: M014
provides:
  - S04 can assume browser-sensitive routes and quiz session paths are no-store and not relying on local answer persistence.
  - S05 receives reproducible backend, frontend, and quiz command evidence for the PHI client-cache and quiz frontend rows in the M014 evidence matrix.
  - Downstream reviewers receive explicit operational readiness signals/failure signals for cache and browser-persistence regressions.
requires:
  - slice: S01
    provides: Consumes the signed public quiz session-state/session-cookie hardening assumptions without weakening CSRF/session behavior.
affects:
  - S04
  - S05
key_files:
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
  - quiz-mensal-interface/components/quiz-interface.tsx
  - quiz-mensal-interface/tests/security/quiz-progress-storage.test.tsx
  - quiz-mensal-interface/tests/security/no-phi-local-storage.test.tsx
key_decisions:
  - Browser-sensitive backend requests are classified before cache lookup/write and Set-Cookie responses are classified after endpoint execution; sensitive responses bypass `http_cache`, force no-store, and strip reusable validators/diagnostics.
  - Dashboard React Query persistence is deny-by-default and allows only explicit static/non-PHI dictionary/template query roots; persisted mutations and denied legacy restored queries are filtered out.
  - Public quiz resume/progress state is backend/cookie-only; browser web storage is cleanup-only for legacy `quiz-progress*` entries and must not persist answers, free text, labels, tokens, session identifiers, or signed cookie state.
patterns_established:
  - Fail-closed browser persistence classification for PHI-bearing or token/session-bearing surfaces.
  - Apply persistence filters at both write and restore boundaries, with App-level dehydration as defense in depth.
  - Preserve useful observability/cache diagnostics only on explicitly non-sensitive paths.
observability_surfaces:
  - Backend cache headers (`Cache-Control`, `Pragma`, `Expires`) and absence/presence of `ETag`/`X-Cache` as sensitive vs non-PHI health signals.
  - React Query persistence policy tests over sanitized query-key/persisted-client metadata.
  - Quiz web-storage tests that inspect key/value persistence without logging PHI, tokens, cookies, prompts, or answers.
drill_down_paths:
  - .gsd/milestones/M014/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M014/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M014/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-05-13T20:15:36.765Z
blocker_discovered: false
---

# S03: Browser PHI Cache e Quiz Frontend Proof

**Closed the browser PHI cache and quiz frontend proof gap by forcing sensitive backend GETs no-store, making dashboard React Query persistence deny-by-default, and removing quiz answer/PHI web-storage persistence while preserving controlled non-PHI cache behavior.**

## What Happened

S03 delivered the browser/cache hardening lane for M014 across three coordinated surfaces. T01 added a backend cache-header classification seam and wired it into CacheMiddleware before cache-key lookup/write so session-cookie, authorization-header, token-query, PHI path, public quiz session, malformed cookie/query, and Set-Cookie responses bypass `http_cache`, return `Cache-Control: no-store, no-cache, max-age=0, must-revalidate`, `Pragma: no-cache`, and `Expires: 0`, and strip reusable validators/diagnostics such as ETag and X-Cache. It also preserved deterministic public caching for safe non-PHI GETs with public Cache-Control, ETag, and X-Cache MISS/HIT behavior in a controlled test app.

T02 hardened dashboard IndexedDB persistence by introducing a deny-by-default React Query persistence policy. The policy recursively rejects patient/dashboard/report/message/AI/alert/physician/clinical/auth/user/session/monthly-quiz/session-like query keys, removes persisted mutations, filters before IndexedDB writes and after legacy restores, and keeps only explicit non-PHI/static dictionary/template allowlist roots. The App-level PersistQueryClientProvider also applies `shouldDehydrateQuery` as defense in depth.

T03 removed public quiz PHI web-storage persistence. `quiz-progress-storage` is now cleanup-only/no-op: save/load/has/get/clear/cleanup remove legacy `quiz-progress*` entries, preserve unrelated entries, and swallow localStorage/private-mode failures without logging sensitive data. Quiz resume state now comes from backend session/cookie state only; answer/free-text autosave and local resume paths were removed, and tests prove answers, free text, session identifiers, patient/template labels, token-like values, signed cookie state, and PHI-like payloads are not written to localStorage/sessionStorage.

Closeout reviewer and security subagents both returned PASS with no blockers. Operational readiness: the health signal is the focused backend/frontend/quiz command suite plus observable cache headers and non-sensitive X-Cache diagnostics; the failure signal is any non-zero verification, sensitive response containing public cache headers/ETag/X-Cache, IndexedDB persisted denied query data/mutations, or quiz web storage containing progress/PHI/token/session fields; recovery is to keep sensitive routes on direct no-store response paths, clear browser persisted-client/legacy quiz storage, and re-run the focused suite before re-enabling non-PHI cache behavior. Monitoring gaps remain intentionally out of scope for S03: production CDN/proxy/browser telemetry and live provider/runtime harness validation are deferred to later M014/M015 evidence work.

## Verification

Fresh closeout verification was run through `gsd_exec` from the project root and all required slice-level commands passed:

1. `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s03_cache_headers.py` — exit 0, 7 pytest tests passed (`gsd_exec` a7192f1b-7943-4c8a-be7a-121e377a621f). This proves sensitive backend responses are no-store/no-cache, lack reusable cache validators/diagnostics, bypass cache-manager lookup/write, and safe public GETs retain deterministic MISS/HIT caching.
2. `npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts` — exit 0, 1 Vitest file / 5 tests passed (`gsd_exec` 09a0a6b5-5a04-498d-a850-d6b6d5be1f31). This proves dashboard persisted-client filtering keeps explicit static/template allowlist data and drops PHI/auth/session/dashboard/report/message/quiz payloads and mutations, including object/array key variants and malformed legacy states.
3. `npm --prefix quiz-mensal-interface test -- tests/security/quiz-progress-storage.test.tsx tests/security/no-phi-local-storage.test.tsx` — exit 0, 2 Jest suites / 8 tests passed (`gsd_exec` 0bece41c-9df5-473b-8c3e-50082f6bd878). This proves legacy quiz progress cleanup, no-op save/load behavior, malformed/unavailable storage handling, unrelated-key preservation, and no answer/free-text/token/session/patient-label/cookie-state web-storage persistence. The run emitted non-fatal baseline-browser-mapping, punycode, and Jest worker teardown warnings but exited 0 with all tests passing.

Fresh-context closeout review was also performed: `reviewer` returned PASS and `security` returned PASS with no blockers.

## Requirements Advanced

- R012 — Advanced the PHI client cache hardening item with controlled no-store/cache-bypass backend proof and dashboard IndexedDB persistence filtering proof.
- R013 — Advanced the deferred quiz frontend lane by adding deterministic Jest proof that public quiz answers/free text/session/token/label data are not persisted to browser storage.
- R015 — Maintained the no-production/no-real-patient-data constraint by using only controlled local pytest/Vitest/Jest fixtures.
- R017 — Maintained PHI-safe diagnostics by limiting evidence to headers, cache diagnostics, sanitized query metadata, and storage assertions rather than raw patient data, tokens, cookies, prompts, answers, or private paths.
- R018 — Produced command evidence for the R012/R013-relevant browser cache and quiz frontend proof gap so S05 can map it instead of silently dropping it.

## Requirements Validated

None.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

T03 touched `quiz-mensal-interface/components/quiz-interface.tsx` in addition to the initially expected files to remove a duplicate reset effect that was clearing controlled "Other" free-text interaction; this preserved the real quiz answer flow without reintroducing local persistence. `ResumeQuizDialog.tsx` was left unused rather than deleted. Focused Jest verification still emits non-fatal dependency/environment warnings (`baseline-browser-mapping`, Node `punycode`, and worker teardown notice) while passing.

## Known Limitations

S03 proves controlled local contract/integration behavior only. It does not prove production CDN/proxy/browser cache behavior, live provider/runtime harnesses, real shared-device profiles, upload artifact serving, or final JWT/config/evidence-matrix posture.

## Follow-ups

S04 should consume S03's no-store/private browser persistence assumptions when validating upload stored-XSS and private artifact serving. S05 should map S03 command evidence into the M014 evidence matrix and keep production/runtime cache telemetry gaps explicit if still out of scope.

## Files Created/Modified

- `backend-hormonia/app/middleware/cache_headers.py` — Added cache sensitivity classification and no-store/cache-stripping helpers.
- `backend-hormonia/app/middleware/cache_middleware.py` — Bypassed cache-manager lookup/write for sensitive requests and stripped validators/diagnostics from sensitive responses.
- `backend-hormonia/tests/security/test_m014_s03_cache_headers.py` — Added focused backend cache-header/cache-bypass proof.
- `frontend-hormonia/src/lib/react-query/persistencePolicy.ts` — Added deny-by-default React Query persisted-client filtering with explicit non-PHI allowlist.
- `frontend-hormonia/src/lib/react-query/persistentCache.ts` — Applied filtering before IndexedDB writes and after restores.
- `frontend-hormonia/src/lib/react-query/queryClient.ts` — Wired the filtered dashboard persister.
- `frontend-hormonia/src/App.tsx` — Applied shouldDehydrateQuery defense-in-depth at PersistQueryClientProvider.
- `frontend-hormonia/tests/unit/react-query/persistencePolicy.test.ts` — Added persistence-policy tests for allowed static data and denied PHI/auth/session/mutation data.
- `quiz-mensal-interface/lib/quiz-progress-storage.ts` — Converted quiz progress web storage to cleanup-only/no-op behavior.
- `quiz-mensal-interface/hooks/quiz/useQuizState.ts` — Removed answer/free-text restore/autosave persistence paths.
- `quiz-mensal-interface/app/page.tsx` — Removed local resume-dialog storage wiring; resume comes from backend session/cookie state.
- `quiz-mensal-interface/components/quiz-interface.tsx` — Removed duplicate reset effect so controlled Other/free-text answer flow remains stable without persistence.
- `quiz-mensal-interface/tests/security/quiz-progress-storage.test.tsx` — Added storage utility cleanup/no-op tests.
- `quiz-mensal-interface/tests/security/no-phi-local-storage.test.tsx` — Added component/security proof that quiz interactions do not persist PHI/session/token/cookie data.
