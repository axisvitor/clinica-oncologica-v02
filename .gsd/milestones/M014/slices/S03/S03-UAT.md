# S03: Browser PHI Cache e Quiz Frontend Proof — UAT

**Milestone:** M014
**Written:** 2026-05-13T20:15:36.767Z

# UAT — M014/S03 Browser PHI Cache e Quiz Frontend Proof

## UAT Type

Security regression / controlled local proof. This UAT is deterministic and uses local fixtures only; it does not require production services, live providers, real patient data, or secrets.

## Preconditions

- Work from the repository root.
- Existing development dependencies are installed for `backend-hormonia`, `frontend-hormonia`, and `quiz-mensal-interface`.
- Do not use real patient data, production cookies/tokens, or live WuzAPI/Gemini/DB+queue providers.

## Steps and Expected Outcomes

1. **Verify backend sensitive browser-cache controls.**
   - Run: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s03_cache_headers.py`
   - Expected: command exits 0 with 7 tests passing.
   - Expected security outcome: session-cookie, Authorization, token-query, PHI path, public quiz session, malformed cookie/query, and Set-Cookie responses return no-store/no-cache headers, do not expose `ETag` or `X-Cache`, and do not touch the fake cache manager.
   - Expected non-PHI outcome: the controlled `/public-static` fixture still returns public cache headers, ETag, and deterministic `X-Cache` MISS then HIT behavior.

2. **Verify dashboard IndexedDB React Query persistence filtering.**
   - Run: `npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts`
   - Expected: command exits 0 with 1 Vitest file / 5 tests passing.
   - Expected security outcome: patient/dashboard/report/message/AI/alert/physician/clinical/auth/session/monthly-quiz query payloads and persisted mutations are removed, including object/array key variants and malformed legacy states.
   - Expected allowed behavior: explicit non-PHI static/template allowlist query data remains persistable.

3. **Verify quiz frontend web-storage behavior.**
   - Run: `npm --prefix quiz-mensal-interface test -- tests/security/quiz-progress-storage.test.tsx tests/security/no-phi-local-storage.test.tsx`
   - Expected: command exits 0 with 2 Jest suites / 8 tests passing.
   - Expected security outcome: answers, free-text `otherTexts`, patient/template labels, session identifiers, token-like values, signed cookie state, and PHI-like payloads are not written to `localStorage` or `sessionStorage`.
   - Expected cleanup outcome: legacy `quiz-progress*` entries are cleared deterministically, malformed/large legacy records do not break quiz usage, storage/private-mode failures are swallowed, and unrelated storage entries are preserved.

## Edge Cases Covered

- Session-cookie GET without bearer auth.
- Arbitrary Authorization header.
- Token/session/CSRF-like query strings.
- PHI path prefixes and public quiz session paths.
- Endpoint responses that set cookies after handler execution.
- Non-PHI public cache MISS/HIT preservation.
- Dashboard denied query keys using string, object, and array variants adjacent to allowlisted static keys.
- Malformed legacy persisted React Query and quiz progress records.
- Unavailable browser storage/private-mode exceptions.
- Quiz submit failure paths that must not persist answer/free-text data.

## Operational Readiness (Q8)

- **Health signal:** all three focused commands pass; sensitive responses show no-store/no-cache headers; only safe non-PHI cache paths expose `X-Cache`; dashboard/quiz tests find no durable PHI in browser persistence.
- **Failure signal:** any non-zero command exit, sensitive response with `public`, `ETag`, or `X-Cache`, cache-manager access for sensitive paths, IndexedDB payload containing denied PHI/auth/session keys or mutations, or web storage containing quiz answers/free text/tokens/session/patient labels.
- **Recovery procedure:** keep sensitive requests on direct no-store response paths, clear/expire browser persisted-client and legacy `quiz-progress*` storage, disable or narrow non-PHI allowlists if classification is uncertain, rerun the focused suite, then restore only explicitly safe cache behavior.
- **Monitoring gaps:** this UAT does not prove CDN/proxy production caching, real shared-device browser profiles, live provider behavior, or production runtime telemetry; those remain outside S03 and feed final evidence/posture work.

## Not Proven By This UAT

- Production CDN, reverse proxy, or browser-specific cache behavior outside the controlled test app.
- Live WuzAPI/Gemini provider behavior, DB+queue runtime behavior, or production-like harnesses.
- Real patient data handling; only PHI-safe fixtures are used.
- Upload stored-XSS/private artifact serving, JWT/config posture, and final M014 evidence-matrix closure, which are owned by downstream slices.
