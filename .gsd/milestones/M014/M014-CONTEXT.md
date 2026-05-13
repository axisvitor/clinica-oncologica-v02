# M014: Hardening Médio e Proof Gaps

**Gathered:** 2026-05-13
**Status:** Ready for planning

## Project Description

Sistema de acompanhamento oncológico via WhatsApp para acompanhamento contínuo entre consultas, com FastAPI + Taskiq + PostgreSQL + Dragonfly, WuzAPI como provedor de WhatsApp, dashboard médico e quiz mensal público. M014 é o follow-on de segurança depois de M013: fechar hardening médio e proof gaps deferred sem reabrir o escopo crítico/alto já concluído.

## Why This Milestone

M013 fechou F-01..F-11 críticos/altos, mas carregou R012/R013 como deferred: ADK auth/session ownership, CSRF, reset/webhook replay, X-Forwarded-For/rate-limit, PHI client cache, deployment secrets, duplicate-oracle, upload stored-XSS, JWT revocation multi-worker e quiz frontend lane incompleta. O risco agora é esses itens desaparecerem por não bloquearem M013; M014 existe para transformar o backlog cinza em controles e provas reproduzíveis.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Um reviewer/operador técnico roda a matriz de evidência M014 em local dev/CI e vê os médios/proof gaps mapeados para comandos pass/fail sem depender de produção ou PHI real.
- Médico, admin e paciente continuam usando login, dashboard, quiz, uploads e fluxos WhatsApp sem regressão funcional, enquanto entradas/replays/cache/ADK falham fechado em cenários indevidos.

### Entry point / environment

- Entry point: backend FastAPI/API tests, frontend/quiz test lanes where needed, and reviewer-facing security evidence artifact.
- Environment: local dev/CI controlled proof; no production data.
- Live dependencies involved: database/queue/provider behavior mocked or fixture-controlled for M014; broad production-like DB+queue+WuzAPI/Gemini harness remains M015/R014 unless explicitly pulled later.

## Completion Class

- Contract complete means: focused pytest/unit/integration evidence proves each selected R012/R013 item has an expected allow/deny contract and PHI-safe diagnostics.
- Integration complete means: auth/session/middleware/routes/cache/frontend quiz/upload/ADK boundaries work together in controlled backend proof without regressing M013 F-01..F-11 controls.
- Operational complete means: proof commands are reproducible from repo root/backend root, documented in a matrix, and avoid live providers, secrets, production exploitation, or PHI.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- Ingress/replay-first controls reject missing/invalid CSRF or replay/idempotency/rate-limit abuse before side effects, while legitimate session/provider paths still work under fixtures.
- Deferred proof gaps have concrete evidence: ADK access is auth/ownership-gated, upload stored-XSS is blocked or safely served, JWT revocation/X-Forwarded-For/rate-limit semantics are proven under the controlled harness, and quiz frontend lane coverage is no longer incomplete.
- What cannot be simulated for M014 completion is production-like exploitation against live WuzAPI/Gemini/real patient data; that remains out of scope and belongs to M015/R014 if required.

## Architectural Decisions

### M014 Scope Boundary

**Decision:** M014 should cover hardening médio plus proof gaps together: R012 and R013 are in scope; the broad R014 production-like runtime harness remains out of scope for M014.

**Rationale:** The user selected “Hardening + proof” because M013 intentionally deferred both implementation hardening and proof-only uncertainties. Closing them together prevents a second deferral loop while keeping runtime harness complexity contained.

**Alternatives Considered:**
- Hardening only — rejected because proof gaps such as stored-XSS/JWT revocation/XFF/rate-limit/quiz frontend could remain reviewer-visible unknowns.
- Proof gaps first — rejected because known medium controls would remain unresolved even after evidence gathering.
- Production-like runtime scope — rejected for M014 because it belongs to M015/R014 and would require broader lifecycle/secrets/provider setup.

### Proof Boundary

**Decision:** M014 completion should use controlled backend proof: pytest/integration tests with fixtures, dependency overrides, mocked WuzAPI/queue/provider behavior, and no live providers.

**Rationale:** The user selected “Controlled backend proof” to keep evidence reproducible, safe for PHI/LGPD, and aligned with M013’s negative-proof patterns.

**Alternatives Considered:**
- Local stack proof — not chosen as the default because Postgres/Dragonfly/workers add lifecycle complexity and can drift toward M015.
- Production-like proof — not chosen because it introduces secrets, live dependencies, and unstable evidence beyond M014.

### Sequencing Priority

**Decision:** Sequence M014 with ingress/replay first.

**Rationale:** The user selected “Ingress/replay first” because CSRF, webhook/reset replay, X-Forwarded-For/rate-limit, and duplicate-oracle behavior protect external entry points and can create reusable denial/logging proof early.

**Alternatives Considered:**
- Isolation/config first — valuable, but may touch deeper architecture/config before entry-point proof exists.
- Browser PHI first — valuable, but should follow once ingress/replay controls and proof conventions are established.

## Error Handling Strategy

Fail closed for auth, CSRF, replay/idempotency, rate-limit identity, ADK ownership, upload rendering, cache/private data, and quiz/frontend state. Denials should happen before side effects and return generic 401/403/409/422/429 style responses where appropriate. Logs and evidence must remain PHI-safe: no patient names, phones, message bodies, quiz answers, raw tokens, cookies, signed states, secrets, or private filesystem paths. Retries are allowed only for safe/idempotent provider or queue operations and must not turn replay protection into duplicate side effects.

## Risks and Unknowns

- Exact R012/R013 item list may need pruning if some medium findings are already closed or not real in current code — M014 should begin by validating actual current behavior.
- ADK auth/session ownership may require architectural decisions if ADK endpoints are currently test/demo oriented rather than production-facing.
- RLS and DB TLS may be posture/config decisions rather than code fixes under controlled proof; the milestone must avoid claiming runtime guarantees it did not exercise.
- PHI client cache hardening may conflict with existing frontend performance/IndexedDB cache behavior and needs targeted allow/deny criteria.
- X-Forwarded-For/rate-limit proof depends on trusted proxy assumptions; ambiguous proxy trust must be documented rather than guessed.

## Existing Codebase / Prior Art

- `.gsd/milestones/M013/M013-SUMMARY.md` — records M013 closure and explicitly carries R012/R013/R014 forward.
- `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md` — reviewer-facing matrix pattern to reuse for M014.
- `.gsd/REQUIREMENTS.md` — R012/R013 are deferred for M014; R014 is deferred for M015.
- `backend-hormonia/tests/api/v2/security_boundary_helpers.py` — two-doctor/two-patient negative fixture pattern from M013.
- `backend-hormonia/app/api/v2/routers/adk.py` and `backend-hormonia/app/ai/adk/*` — likely ADK auth/session ownership surface.
- `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/core/middleware_setup.py`, `backend-hormonia/app/integrations/wuzapi/webhook.py` — likely CSRF, reset, webhook, replay and rate-limit surfaces.
- `backend-hormonia/app/middleware/cache_middleware.py`, `frontend-hormonia/src/lib/react-query/persistentCache.ts`, `quiz-mensal-interface/app/page.tsx` — likely PHI cache and quiz frontend proof surfaces.

## Relevant Requirements

- R012 — M014 should correct and prove remaining medium hardening items.
- R013 — M014 should close deferred proof gaps and leave reviewer-facing evidence.
- R014 — Explicitly out of M014 unless later re-scoped; broad production-like runtime harness remains provisional M015.
- R015/R017 — M014 proof must avoid production exploitation, real PHI, and accidental secret disclosure.
- R018 — M014 exists because M013 intentionally did not fix all independent medium findings.

## Scope

### In Scope

- R012 + R013 hardening/proof backlog, starting with ingress/replay controls.
- Reusable negative tests with side-effect sentries and PHI-safe diagnostic assertions.
- Evidence matrix mapping each medium/proof-gap item to command evidence, status, and any explicit non-goal.
- Regression proof that M013 critical/high controls remain intact where touched.

### Out of Scope / Non-Goals

- Full production-like runtime harness with live DB+queue+WuzAPI/Gemini and realistic fixtures, unless M014 is explicitly re-scoped.
- Production exploitation, real patient data, real PHI, or live provider attack attempts.
- Broad frontend/dashboard rewrite beyond targeted PHI cache or quiz proof changes.
- Reopening M013 critical/high work except to prevent regressions in touched paths.

## Technical Constraints

- Work relative to the existing FastAPI/session-first architecture and shared auth/ownership helpers.
- Prefer controlled pytest/fixture proof over live services.
- Keep logs, task diagnostics, artifacts, and evidence PHI-safe.
- Do not claim RLS/DB TLS/runtime behavior beyond what the controlled proof actually exercises.
- Preserve existing clinical workflows and M013 security boundaries.

## Integration Points

- FastAPI auth/session/CSRF middleware — ingress denial and authenticated allow paths.
- WuzAPI webhook/inbound processing — replay/idempotency and side-effect sentries.
- Password reset/auth endpoints — reset replay and duplicate-oracle behavior.
- Rate-limit/client identity middleware or route helpers — X-Forwarded-For/trusted proxy semantics.
- ADK runtime/session store/routes — auth and session ownership boundaries.
- Upload/private serving and frontend rendering — stored-XSS proof.
- Frontend React Query/IndexedDB/cache and quiz interface — PHI cache and quiz lane proof.

## Testing Requirements

Use focused unit/integration tests plus a final integrated security proof command. Tests should include negative and positive cases, side-effect sentries for denied entry points, two-doctor/two-patient ownership fixtures where patient-bound, mocked providers/queue, no production services, and assertions that denial diagnostics omit PHI/tokens/secrets/private paths. A reviewer-facing M014 evidence matrix should map R012/R013 items to exact commands and outcomes.

## Acceptance Criteria

- Ingress/replay-first slice proves CSRF, reset/webhook replay, duplicate-oracle and X-Forwarded-For/rate-limit behavior with fail-closed denials before side effects.
- ADK slice proves authenticated/session-owned access only, with foreign/missing/expired session denial and PHI-safe logs.
- Browser/PHI slice proves private data is not stored or cached unsafely in HTTP/browser persistence and that quiz frontend lane coverage is complete enough for the chosen contract.
- Upload stored-XSS proof demonstrates malicious HTML/SVG/script payloads are rejected, downloaded safely, or served with non-executable content disposition/type under authorization.
- Evidence matrix explicitly marks every R012/R013 item as closed, non-applicable with rationale, or deferred with owner; M014 must not silently drop any item.
- Regression proof for touched M013 controls passes.

## Open Questions

- Which R012/R013 items are real current defects versus already-covered posture gaps after M013? — current thinking: validate first, then close or document as not-applicable with evidence.
- Should RLS/DB TLS be implemented in M014 or documented as deployment posture with validation checks only? — current thinking: do not over-claim under controlled proof.
- What is the trusted proxy model for X-Forwarded-For? — current thinking: define explicit trusted-proxy behavior before rate-limit tests.
- How aggressive should PHI cache hardening be against existing IndexedDB/performance caching? — current thinking: classify PHI endpoints/data and apply no-store/non-persistence there, not blanket-disable all useful cache.
