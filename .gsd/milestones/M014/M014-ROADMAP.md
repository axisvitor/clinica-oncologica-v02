# M014: Hardening Médio e Proof Gaps

**Vision:** Transformar o backlog R012/R013 de hardening médio e proof gaps em controles fail-closed, provas reproduzíveis e uma matriz de evidência auditável, preservando os fluxos clínicos existentes e sem depender de produção, provedores vivos, segredos ou PHI real.

## Success Criteria

- Cada item relevante de R012/R013 aparece na matriz M014 como closed, not applicable com evidência, ou deferred com owner e racional explícito.
- Ingressos externos/session-protected negam CSRF ausente/inválido, replay/idempotency abuse, duplicate-oracle e rate-limit/X-Forwarded-For indevido antes de efeitos colaterais, mantendo caminhos legítimos sob fixtures.
- ADK, cache/browser/quiz, upload stored-XSS, JWT/config posture e regressões tocadas de M013 têm comandos de prova controlados e reproduzíveis.
- Logs, erros, artefatos e documentação de prova permanecem PHI-safe: sem nomes, telefones, prompts, respostas, tokens, cookies, segredos ou caminhos privados.
- M014 não reivindica harness runtime produção-like; WuzAPI/Gemini/DB+queue realistas e dados reais permanecem fora de escopo/R014-M015.

## Slices

- [x] **S01: S01** `risk:Externally reachable state changes may accept missing CSRF, replay/idempotency failures, duplicate-oracle probes or ambiguous X-Forwarded-For before side-effect sentries exist.` `depends:[]`
  > After this: Reviewer runs focused backend pytest for CSRF, password reset/webhook replay, duplicate-oracle and trusted-proxy rate limiting; denied paths return 403/409/422/429 before queue/provider/DB side effects while legitimate fixture paths still pass.

- [x] **S02: S02** `risk:ADK endpoints can be publicly callable or trust payload-supplied identity, allowing cross-user/session execution before provider calls.` `depends:[]`
  > After this: Reviewer runs ADK route/service tests where authenticated same-user sessions are allowed and missing, foreign, expired or payload-mismatched sessions are denied without invoking live Gemini.

- [ ] **S03: S03** `risk:Session-cookie GETs and quiz/dashboard persistence can store sensitive patient or answer data under public cache/localStorage/IndexedDB behavior.` `depends:[]`
  > After this: Reviewer runs backend cache-header tests plus targeted frontend/quiz tests showing PHI responses are no-store/non-persistent, non-PHI cache still works, and quiz frontend coverage now has deterministic pass/fail evidence.

- [ ] **S04: Upload Stored-XSS e Private Artifact Serving** `risk:Malicious HTML/SVG/script uploads or generated artifacts may execute in a browser or bypass authorization if served with unsafe content type/disposition or public paths.` `depends:[S01,S03]`
  > After this: Reviewer runs upload/download tests with malicious HTML/SVG/script payloads and sees rejection or safe attachment serving under auth/ownership, with anonymous/foreign access denied.

- [ ] **S05: JWT/Config Posture, Evidence Matrix e Regression Closure** `risk:The milestone can fix visible code paths while leaving JWT revocation semantics, deployment secret posture, DB TLS/RLS claims, R012/R013 mapping or M013 regressions unverifiable.` `depends:[S01,S02,S03,S04]`
  > After this: Reviewer runs the documented M014 evidence matrix command suite and sees every R012/R013 row mapped to command evidence, not-applicable rationale or explicit deferral owner, plus JWT/config posture and touched M013 regression status.

## Boundary Map

## Boundary map

- **Ingress/session/provider entrypoints:** FastAPI routers, CSRF/session middleware, WuzAPI webhook/reset flows, rate-limit identity helpers.
- **Identity/ownership:** shared auth/session dependencies, request-state identity, ADK session ownership, two-doctor/two-patient fixtures where patient-bound.
- **Browser persistence:** HTTP cache headers, React Query/IndexedDB persistence, quiz frontend state/localStorage behavior.
- **Files/artifacts:** upload validation, private serving, content-disposition/content-type/nosniff, sanitized file IDs.
- **Posture/evidence:** JWT revocation semantics, deployment secret checks, DB TLS/RLS classification, M013 touched regression commands, M014 evidence matrix.

## Horizontal checklist considered

- **Requirements:** R012/R013 mapped; R014 explicitly out of scope; R015/R017/R018 constraints represented.
- **Decisions:** controlled backend proof and ingress-first sequence honored; no production-like harness added.
- **Shutdown/background work:** denied paths must not enqueue provider/Taskiq/DB side effects; retries only for safe/idempotent paths.
- **Revenue/billing:** not applicable; no payment or monetization surfaces touched.
- **Auth/session:** central concern in S01/S02/S04 and cache classification in S03.
- **Shared resources:** DB, queue, Dragonfly/rate-limit store, upload storage and browser persistence are fixture-controlled.
- **Reconnection/provider behavior:** WuzAPI/Gemini are mocked; live provider lifecycle is deferred to R014/M015.
- **Secrets:** no new external API keys or credentials are required for M014 planning.
