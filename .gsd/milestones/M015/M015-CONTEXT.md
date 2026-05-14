# M015: Runtime Security Validation

**Gathered:** 2026-05-14
**Status:** Ready for planning

## Project Description

Sistema de acompanhamento oncológico via WhatsApp para acompanhamento contínuo entre consultas. O backend roda em FastAPI + Taskiq + PostgreSQL + Dragonfly, com WuzAPI como provedor de WhatsApp e frontends web para operação clínica. Depois de M013/M014 fecharem achados críticos/altos e hardening médio com provas controladas, M015 deve validar em runtime os gaps explicitamente deferidos: sessão/JWT em múltiplos processos, DB TLS/RLS, wiring real de DB+fila+workers, comportamento de artefatos privados por rotas da aplicação e fronteiras WuzAPI/Gemini sem tocar provedores reais.

M015 não é uma rodada de exploração em produção. É um harness **synthetic-only**, production-like e backend-runtime para transformar as deferrals M014/R014 em evidência reproduzível e PHI-safe.

## Why This Milestone

M014 validou R012/R013 dentro de uma fronteira controlada de pytest/frontend/unit proofs e deixou claro que não estava reivindicando garantias production-like. Essa honestidade é importante, mas ainda deixa uma lacuna de confiança operacional: alguns controles só são convincentes quando o app, banco, cache, filas e workers estão rodando como subsistemas separados.

Este marco existe para provar o que M014 não podia provar sem aumentar escopo indevidamente:

- revogação de sessão/JWT e fallback DB atravessando processos/cache, não só uma função isolada;
- negociação/postura TLS e execução de RLS em um PostgreSQL real de teste;
- integração FastAPI + Dragonfly + Taskiq workers + provider stubs;
- serving de uploads/reports privados por rotas autenticadas com headers/ownership corretos;
- diagnósticos/evidência que continuam sem PHI, tokens, cookies, secrets, provider payloads ou paths privados.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Run a single M015 validation runner, for example `./scripts/security/verify-m015-runtime-security.sh`, that starts a synthetic production-like backend stack, waits for readiness, runs runtime security validation, captures PHI-safe evidence, and tears down cleanly.
- Hand reviewers an M015 evidence matrix showing every M014-deferred runtime seam as closed by evidence, explicitly out of scope, or fixed before close.

### Entry point / environment

- Entry point: single committed runner script for M015 runtime security validation, backed by focused tests and an evidence-matrix validator.
- Environment: local dev / CI-ready Docker profile; backend-runtime only.
- Live dependencies involved: local TLS-enabled PostgreSQL, Dragonfly, FastAPI, Taskiq worker processes, and local HTTP stub services for WuzAPI/Gemini.
- Live dependencies not involved: production systems, real patient data, live WuzAPI/Gemini credentials, browser/frontend validation, object-storage/CDN services.

## Completion Class

- Contract complete means: focused tests and matrix validator prove the selected seams, redaction rules, fail-closed behavior, and evidence rows.
- Integration complete means: FastAPI, PostgreSQL, Dragonfly, Taskiq workers, session/cache behavior, private artifact routes, and WuzAPI/Gemini stubs run together through the harness.
- Operational complete means: startup, readiness, migrations, fixture seeding, validation execution, evidence capture, failure diagnostics, and teardown are repeatable without secrets or PHI.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- A synthetic production-like harness starts FastAPI, Dragonfly, Taskiq workers, a dedicated TLS-enabled PostgreSQL service, and controlled WuzAPI/Gemini HTTP stubs with security fixtures.
- The M014-deferred runtime seams are exercised end to end: multi-worker session revocation/cache-fallback behavior, DB TLS/RLS proof, app-route private artifact behavior, and DB+queue/provider-stub runtime wiring.
- A selected deferred seam that produces a red runtime security signal is fixed before milestone close; M015 must not close green with a core selected seam still red.
- What cannot be simulated if M015 is to be considered truly done: production exploitation, real PHI, live provider side effects, real CDN/object-storage policy, and browser/frontend UX flows are intentionally not simulated and must not be claimed.

## Architectural Decisions

### Synthetic Production-Like Backend Harness

**Decision:** M015 will build a local/CI-ready production-like backend runtime harness, not a live-provider, production exploitation, DAST-first, or frontend UI milestone.

**Rationale:** This closes the R014/M014 proof boundary while honoring LGPD/PHI safety and keeping evidence reproducible. The risk being addressed is runtime integration between real subsystems, not broad fuzzing or production observation.

**Alternatives Considered:**
- Sandbox/live providers — more realistic externally, but introduces secrets, quotas, cleanup risk, flakiness, and side effects.
- Black-box DAST-first validation — useful for unexpected route/header/auth regressions, but weaker for queue/worker/database lifecycle proof.
- Full UI flow — broader user confidence, but expands beyond the selected deferred runtime seams and increases flake/setup cost.

### TLS-Enabled Local PostgreSQL for DB Proof

**Decision:** The DB lane will use an M015-specific PostgreSQL service with test TLS material and RLS fixtures so the harness can prove both TLS negotiation/posture and RLS policy behavior locally.

**Rationale:** M014 only validated synthetic production config posture for `sslmode=require`/`sslminversion` and explicitly did not claim a live TLS handshake or RLS policy execution. A dedicated local test DB can close that gap without managed test DB secrets or production data.

**Alternatives Considered:**
- RLS local only — easier, but leaves TLS negotiation deferred.
- Managed test DB — more realistic, but requires secret handling, cleanup, cost, and acceptance of higher flakiness.

### Network-Real Provider Stubs

**Decision:** WuzAPI and Gemini will be represented by local HTTP stub services, not in-process fakes or live providers.

**Rationale:** The app should make real network calls to controlled endpoints so env wiring, provider boundary behavior, timeouts, 4xx/5xx paths, replay/duplicate handling, and synthetic payload assertions are exercised without live side effects.

**Alternatives Considered:**
- In-process fakes — faster and simpler, but weaker evidence for deployed env/network wiring.
- Existing WuzAPI container — closer to installed provider shape, but less controlled and may require tokens/state cleanup.

### App-Route Private Artifact Runtime Proof

**Decision:** Private artifact validation will prove deployed-style app-route behavior: auth/ownership, attachment download behavior, `nosniff`, `no-store`, safe content type, and no redirects to unsafe/private paths.

**Rationale:** The current security architecture treats private uploads/reports as application resources served through authenticated/ownership-checked routes. M015 should validate that current architecture under runtime without adding object-storage or CDN infrastructure that the app does not yet rely on.

**Alternatives Considered:**
- Local object-storage emulator — useful if reports/uploads move to object storage, but not needed to prove the current implementation.
- Reverse proxy/CDN simulation — can catch some cache/header regressions, but still would not be a true CDN guarantee.

### Strict Red-Signal Closure

**Decision:** If the harness finds a red runtime security signal in a selected deferred seam, M015 must fix product/harness behavior before completion.

**Rationale:** A milestone named Runtime Security Validation should not close green while a selected runtime security seam remains red. Report-only closure is acceptable for explicit non-goals, not for core selected seams.

**Alternatives Considered:**
- Report blocker only — faster visibility, but too weak for milestone completion.
- Fix core only with infra flakes deferred — pragmatic, but the selected expectation is stricter for selected runtime seams.

## Error Handling Strategy

The harness should fail closed and fail loudly without leaking sensitive material. Startup should stop on missing services, failed readiness, failed migrations, unsafe env posture, TLS/RLS proof failure, worker/queue readiness failure, provider-stub mismatch, red security assertions, or evidence redaction violations.

Runtime validation should distinguish product/security failures from harness setup failures, but both should prevent a green result. Provider stubs should support safe success, denial, timeout, replay/duplicate, and service-error scenarios. All diagnostics, matrix rows, logs, and captured artifacts must avoid PHI, tokens, cookies, signed state values, provider payloads, private filesystem paths, sensitive URLs, and secrets. User-facing failure messages should identify the failed seam and remediation class, not sensitive values.

## Risks and Unknowns

- Existing `backend-hormonia/docker-compose.yml` has Dragonfly/API/worker/scheduler/WuzAPI but no PostgreSQL service; M015 likely needs a dedicated compose profile/override rather than mutating the default dev stack.
- Local TLS-enabled PostgreSQL setup with generated test certificates is the highest brittleness risk.
- Multi-worker session revocation proof must genuinely cross process/cache boundaries; an in-process pytest shortcut would not close the deferral.
- Provider stubs must be realistic enough to prove env/network wiring while remaining simpler than real provider emulators.
- Strict red-signal closure can expand implementation work if runtime validation reveals a real product security defect.
- The final file placement for compose overrides, stubs, runner, evidence output, and tests should be decided during planning.

## Existing Codebase / Prior Art

- `.gsd/milestones/M014/M014-SUMMARY.md` — states that live JWT/session revocation, DB TLS/RLS, CDN/object-storage behavior, live providers, and production-like DB+queue+WuzAPI/Gemini harness proof are deferred to M015/R014.
- `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md` — establishes the reviewer-facing matrix pattern and exact deferred runtime register.
- `backend-hormonia/docker-compose.yml` — current Docker stack for Dragonfly, API, worker, scheduler, and WuzAPI; useful starting point, but missing PostgreSQL and too live-provider-oriented for M015's chosen boundary.
- `backend-hormonia/alembic/versions/6f8c2d4a9b10_enable_rls_sensitive_tables.py` — RLS migration candidate for runtime DB inspection/execution proof.
- `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py` — prior runtime proof pattern that can inform harness-driven assertions.
- `backend-hormonia/tests/integration/*` and `backend-hormonia/tests/integrations/wuzapi/*` — existing integration and WuzAPI test patterns for synthetic runtime checks.
- `backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py` and `backend-hormonia/tests/config/test_production_config.py` — M014 posture tests that M015 should not duplicate blindly but may use as contract baselines.

## Relevant Requirements

- R014 — M015 directly advances the deferred requirement to build a full runtime harness with DB, queue, WuzAPI/Gemini-style boundaries, and production-like synthetic fixtures if broad dynamic validation is required.
- R012 — M014 validated controlled hardening; M015 should close the remaining runtime-only DB TLS/RLS portion without reopening already proven controlled items unnecessarily.
- R013 — M014 validated proof-gap accounting; M015 should close the live-ish multi-worker JWT/session runtime proof that remained deferred.
- R015 — M015 must honor the anti-feature of no production exploitation and no real PHI.
- R017 — M015 must preserve PHI-safe evidence and diagnostics across logs, matrix rows, runner output, stubs, and captured artifacts.
- R018 — M015 should continue the no-silent-drop pattern by mapping every deferred runtime item to evidence, non-goal, or fixed outcome.

## Scope

### In Scope

- A single M015 runtime security validation runner.
- M015-specific Docker compose profile/override or equivalent harness assets.
- Local TLS-enabled PostgreSQL with generated test TLS material and RLS fixtures.
- FastAPI + Dragonfly + Taskiq worker process orchestration.
- WuzAPI/Gemini HTTP stub services that validate synthetic/redacted request behavior and simulate success/failure/replay/timeout cases.
- Synthetic security fixtures: two physicians, two patients, one admin, current/revoked/expired sessions, private upload/report artifacts, and minimal synthetic provider events.
- Runtime checks for multi-worker session revocation and DB fallback behavior.
- Runtime checks for DB TLS negotiation/posture and RLS policy execution.
- Runtime checks for private artifact app-route ownership, headers, content disposition, content type, and absence of unsafe redirects.
- Reviewer-facing M015 evidence matrix plus validator tests that reject missing rows, placeholders, and unsafe sentinel strings.
- PHI-safe structured diagnostics for harness failures.

### Out of Scope / Non-Goals

- Real PHI, production exploitation, or patient/provider side effects.
- Live WuzAPI/Gemini credentials by default.
- Browser/frontend validation.
- Object-storage, CDN, or reverse-proxy guarantees beyond app-route behavior.
- Mandatory CI workflow/gate; the runner should be CI-ready but not necessarily wired into CI in this milestone.
- Broad DAST/fuzzing as the primary validation strategy.
- Report-only completion while selected runtime seams remain red.

## Technical Constraints

- Operate within the existing FastAPI + Taskiq + PostgreSQL + Dragonfly architecture.
- Keep all data synthetic and all evidence PHI-safe.
- Do not commit secrets, provider credentials, private keys intended for real environments, cookies, tokens, signed state values, or provider payloads.
- Use generated test TLS material only for the local harness.
- Prefer shared auth/authorization/session helpers over endpoint-local security patches.
- Do not overclaim production, CDN, object-storage, or live-provider guarantees.
- Preserve M014's evidence discipline: rows should map findings/requirements/controls/commands/results/deferrals and be mechanically validated.

## Integration Points

- FastAPI backend — mounted routes, auth/session dependencies, private upload/report endpoints, health/config surfaces, and provider integration configuration.
- PostgreSQL — Alembic migrations, TLS connection settings, RLS enablement/force status, policy behavior, and synthetic fixture persistence.
- Dragonfly/Redis — session/cache behavior, rate-limit/cache semantics, and Taskiq broker wiring.
- Taskiq workers — separate-process execution and side-effect boundaries under queue-driven scenarios.
- WuzAPI stub — synthetic WhatsApp/provider boundary for outbound/inbound-style behavior and failure simulation.
- Gemini stub — synthetic AI/provider boundary for network/env wiring and failure simulation.
- Evidence artifacts — M015 matrix, runner output, redaction checks, and validator tests.

## Testing Requirements

M015 should include layered verification:

- Unit/contract tests for harness helper logic, redaction, unsafe sentinel detection, fixture generation, and stub request validation.
- Integration/runtime tests that run against the harness services rather than in-process dependency overrides where the deferral requires process/network boundaries.
- DB tests that prove TLS negotiation/posture and RLS policy execution with synthetic data.
- Session tests that prove revoked/expired/current sessions behave correctly across API process/cache/DB fallback and worker/runtime boundaries.
- Provider-stub tests that prove synthetic payloads, expected failure modes, replay/duplicate behavior, and no PHI/token/provider-payload leakage.
- Private artifact route tests that prove ownership, headers, download behavior, and fail-closed handling under the running app.
- Evidence-matrix validator tests that fail on missing deferred rows, placeholders, stale command references, or unsafe sensitive strings.

## Acceptance Criteria

- The M015 runner starts the runtime harness, validates readiness, runs migrations/fixtures, executes checks, captures evidence, and tears down cleanly.
- A dedicated TLS-enabled PostgreSQL test service is used; evidence proves TLS negotiation/posture and RLS policy behavior without exposing DSNs or credentials.
- Multi-worker/session validation proves revoked sessions are rejected across process/cache boundaries and that DB fallback does not accept revoked/expired sessions.
- Taskiq/Dragonfly validation proves queue/worker wiring participates in selected security scenarios rather than only mocked in-process calls.
- WuzAPI/Gemini stub validation proves the app uses configured stub endpoints, sends only synthetic/redacted payloads, and fails closed on timeout/error/replay-style scenarios.
- Private upload/report artifact validation proves authenticated owner/admin access, cross-owner denial, safe headers, attachment/download behavior, and no unsafe redirects through app routes.
- The M015 evidence matrix maps all M014-deferred runtime items to fresh evidence, explicit non-goals, or fixed outcomes, and a validator test enforces row presence and PHI-safe content.
- Any selected runtime security red signal discovered during M015 is fixed before the milestone is marked complete.

## Open Questions

- Exact file placement and naming for the compose override/profile, provider stub implementation, runner script, evidence output directory, and tests.
- Whether non-core harness/tooling flake failures can ever be documented as follow-ups; selected runtime security seams cannot remain red at completion.
- Whether future milestones should promote the CI-ready runner into a mandatory CI/release gate after M015 proves it is stable.
