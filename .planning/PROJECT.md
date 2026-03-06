# Clinica Oncologica — Sistema de Acompanhamento

## What This Is

Sistema de acompanhamento oncologico via WhatsApp que envia questionarios humanizados aos pacientes entre consultas, permitindo que medicos acompanhem seus pacientes de forma continua. O sistema roda com 4 agentes Pydantic AI tipados (sentiment, humanize, variation, empathy), PII redaction obrigatoria, orquestracao de fluxo em funcoes async Python diretas e GeminiClient baseado em `google-genai` com circuit breaker, rate limiter e cache. O Google ADK esta integrado com runtime controls (timeout, budget, cancel), tool safety guardrails deterministicos, e observabilidade Prometheus no endpoint `/api/v2/adk/run`. Toda a camada API opera sobre AsyncSession (SQLAlchemy), enquanto Celery workers mantem sync Session por design. A integracao WhatsApp agora opera em hard cut com WuzAPI (whatsmeow), com Evolution API tombstonada.

## Core Value

Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.

## Requirements

### Validated

- ✓ Backend FastAPI com DDD layers (API -> Domain -> Services -> Infrastructure) — existing
- ✓ Celery + Dragonfly (Redis-compatible) como task queue e broker — existing
- ✓ 38 periodic tasks via Celery Beat — existing
- ✓ Templates fixos armazenados em banco de dados — existing
- ✓ Firebase Auth para autenticaçao de usuarios — existing
- ✓ LGPD compliance (middleware, PII redaction, consent management, encryption) — existing
- ✓ Saga orchestrator para onboarding de pacientes com compensaçao — existing
- ✓ Quiz mensal interface (Next.js) com short links — existing
- ✓ Frontend admin SPA (React 19 + Vite + shadcn/ui) — existing
- ✓ WebSocket para dashboard real-time (multi-instance via Redis pub/sub) — v1.1
- ✓ Circuit breaker e resilience patterns (FeatureNotAvailableError on Gemini circuit-open) — v1.1
- ✓ Structured logging + Sentry integration — existing
- ✓ DLQ para webhook/message failures — existing
- ✓ Monitoring endpoints com auth canonica (session-based, role check) — v1.0
- ✓ Audit trail imutavel para deleçoes de pacientes (patient_deletion_audit) — v1.0
- ✓ WhatsApp opt-out handler (STOP/PARAR/CANCELAR) com send guard — v1.0
- ✓ Celery tasks usando async_to_sync (sem asyncio.run()) — v1.0
- ✓ Rate limiter atomico via Lua sliding window script — v1.0
- ✓ 4 agentes Pydantic AI tipados com PIISafeAgent e CI enforcement — v1.2
- ✓ LangGraph totalmente removido: 9 modulos tombstoned — v1.2
- ✓ GeminiClient migrado para google-genai SDK — v1.2
- ✓ Fluxos de orquestracao substituidos por funcoes async Python diretas — v1.2
- ✓ Flow control stabilized: pause/resume/cancel semantics — v1.3
- ✓ 10 critical file splits with compatibility shims — v1.3
- ✓ Full AsyncSession migration: all API routers use get_async_db — v1.4
- ✓ Dual-mode Session/AsyncSession DI for shared API/Celery services — v1.4
- ✓ Alerts schema fix (alerts.type column mapping) — v1.4
- ✓ Test adapter AsyncSession contract support (begin_nested, delete, add, scalars, get) — v1.4
- ✓ Source-level regression tests locking async migration correctness — v1.4
- ✓ Saga modules async-safe with dual-session DB adapters and SagaDBAdapterMixin — v1.5
- ✓ Two onboarding paths (saga + dispatcher) independently traced end-to-end — v1.5
- ✓ Compensation integrity: step mapping, reverse-order rollback, transaction boundaries, idempotency — v1.5
- ✓ 40+ saga/flow tests: happy path, compensation, edge cases, shim contracts, lifecycle — v1.5
- ✓ WuzAPI provider migration complete (client, webhook, outbound, cleanup, CI guards) — v1.6
- ✓ Evolution API runtime removed and tombstoned across Stack A/Stack B — v1.6
- ✓ WuzAPI integration polish from audit findings (settings secret consistency + contacts sync 501) — v1.6
- ✓ OpenTelemetry instrumentation removido e Google ADK integrado com PIISafeADKWrapper + FunctionTool/Runner path — v1.7
- ✓ Frontend quality hardening concluida em admin SPA e quiz interface (format/lint/type/test gates) — v1.7
- ✓ ADK runtime controls: timeout, LLM budget, cancellation, bounded session state com Redis metadata store — v1.8
- ✓ ADK tool safety: before_tool_callback bloqueia calls inseguros antes de side effects; operator policy imutavel — v1.8
- ✓ ADK deterministic errors: timeout/policy_block/tool_error/upstream_error sem fallback ambiguo — v1.8
- ✓ ADK observability: Prometheus latency/throughput/in-flight metrics + structured invocation logs — v1.8
- ✓ ADK CI smoke gate: oncology tool trajectories bloqueiam deploy em regressao — v1.8

### Active

- [ ] Definir replacement de observabilidade pos-OTel com padrao unico de instrumentacao (OBS-01)
- [ ] Propagar correlation IDs obrigatorios em toda cadeia API -> Celery -> ADK (OBS-03)
- [ ] Mapear taxonomia de erro ADK para envelope HTTP padronizado (ADK-14)
- [ ] Definir politica retryable/non-retryable com idempotencia para chamadas ADK (ADK-15)
- [ ] Fechar criterios de estabilidade operacional ADK com runbook e alertas minimos

### Out of Scope

- Full Celery task async conversion — workers run in separate processes; sync Session is correct
- Redesign de UI do frontend admin ou quiz interface — foco backend
- Live chat medico-paciente via mesmo numero — requer shared inbox product
- OAuth/SSO — Firebase Auth ja atende
- Migraçao de infra (Railway/AWS RDS/Dragonfly) — manter stack atual
- 50+ files >500 lines needing split — tracked as tech debt
- Physician availability hours model — hardcoded Mon-Fri 08:00-17:00 functional baseline
- ORM query rewrite to raw SQL — keep SQLAlchemy ORM; just switch Session type
- Saga event-sourcing rewrite — existing saga pattern functional, audit confirmed
- Dual-provider mode (Evolution + WuzAPI) — intentionally rejected after hard cut
- Verificacao operacional WuzAPI em ambiente real — adiada para milestone posterior apos estabilizacao ADK

## Current State

- **Latest shipped milestone:** v1.8 ADK Stability & Error Hardening (2026-03-06)
- **Production posture:** ADK runtime controls, tool safety guardrails, deterministic error classification, and Prometheus observability are live on `/api/v2/adk/run`; CI smoke gate blocks deploy on oncology trajectory regressions
- **Frontend posture:** Admin SPA e quiz alinhados em baseline de qualidade (Prettier, ESLint 9, type gates e testes unitarios verdes)
- **ADK module:** ~2,319 LOC across session_store, runtime, wrapper, tools, metrics in `app/ai/adk/`
- **Codebase snapshot:** ~434k LOC Python + ~163k LOC TypeScript/TSX em arquitetura brownfield madura (DDD + Saga + circuit breaker)

<details>
<summary>Archived Milestone Brief: v1.8 ADK Stability & Error Hardening</summary>

**Goal:** Consolidar o ADK como caminho operacional estavel no sistema, eliminando erros criticos e fechando lacunas de observabilidade.

**Target features:**
- Alinhamento completo ADK no backend (wrapper -> runtime -> endpoint -> tool dispatch)
- Correcao de erros ADK priorizados com validacao por testes e smoke checks
- Observabilidade ADK pos-OTel com metricas de latencia/throughput/erro
- Runbook operacional e alertas minimos para incidentes ADK

</details>

<details>
<summary>Archived Milestone Brief: v1.7 Frontend Quality & ADK Integration</summary>

**Goal:** Revisar e corrigir ambos os frontends (admin SPA + quiz mensal) em qualidade geral, e desbloquear/integrar Google ADK removendo OTel.

**Target features:**

- Dead code removal nos dois frontends
- Organizacao e alinhamento das chamadas de API com o backend
- Consistencia visual e de layout entre paginas
- Qualidade de codigo: lint, tipos, padroes
- Remocao do OpenTelemetry (desbloqueio de dependencias)
- Integracao do Google ADK no sistema

</details>

## Context

- v1.0 shipped: security, LGPD, stability, AI reliability, flow consolidation (net -9,314 LOC)
- v1.1 shipped: async hot paths, LGPD key rotation, AI rationalization, observability (net +4,664 LOC)
- v1.2 shipped: AI framework migration — LangGraph removed, Pydantic AI agents, google-genai SDK (net +7,680 LOC)
- v1.3 shipped: flow health fixes + dead code cleanup + 10 critical file splits (net +5,472 LOC)
- v1.4 shipped: full AsyncSession migration — all API routers async, dual-mode services, test stability (net +20,503 LOC)
- v1.5 shipped: saga orchestrator deep dive — audit, flow trace, compensation integrity, 40+ tests (net +7,166 LOC)
- v1.6 shipped: WuzAPI migration complete with Evolution tombstone and integration polish (net +9,340 LOC)
- v1.7 shipped: frontend quality hardening + ADK integration unlocked post-OTel removal (net +4,873 LOC)
- v1.8 shipped: ADK runtime controls, tool safety, deterministic errors, observability, CI smoke gate (net +8,028 LOC)
- Codebase: ~434k LOC Python (brownfield, mature patterns: DDD, Saga, Circuit Breaker)
- Python 3.13 + FastAPI + SQLAlchemy (AsyncSession on all API paths, sync on Celery workers)
- AI stack: Pydantic AI agents + google-genai SDK + GeminiClient (cache, rate limit, circuit breaker, PII redaction)
- Flow system: FlowDispatcher facade routing to direct async Python functions
- Saga: async-safe dual-session orchestrator with verified compensation and 40+ test suite

## Constraints

- **Stack**: Manter Python/FastAPI, nao migrar para outro framework
- **AI Provider**: Google Gemini via google-genai SDK + Pydantic AI agents
- **Compliance**: LGPD obrigatorio (dados de pacientes oncologicos sao sensiveis)
- **Deploy**: Railway (API + Workers) + Firebase Hosting (frontends)
- **Database**: PostgreSQL (AWS RDS) — manter, nao migrar
- **WhatsApp**: WuzAPI (Go + whatsmeow) como provider unico
- **Session Model**: API routes use AsyncSession; Celery tasks use sync Session

## Key Decisions

| Decision                                                          | Rationale                                                                         | Outcome       |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------- | ------------- |
| Consolidar dual flow em production system                         | QW-021 tinha 7 callers vs 59 do production; low production use                    | ✓ Good (v1.0) |
| FlowDispatcher como facade permanente                             | Stable import target for enrollment routing                                       | ✓ Good (v1.0) |
| Hot-path-first async migration                                    | Full migration is too large; hot paths cover ~80% throughput                      | ✓ Good (v1.1) |
| Pydantic AI over LangGraph for agents                             | Type safety, structured output, zero graph overhead for 4 AI operations           | ✓ Good (v1.2) |
| PIISafeAgent as mandatory wrapper                                 | LGPD Art. 46 compliance; CI lint blocks direct .run() calls                       | ✓ Good (v1.2) |
| Direct async Python over ADK for flow orchestration               | 10-15 lines each, identical semantics, zero new dependencies                      | ✓ Good (v1.2) |
| Hard-cut GeminiClient to google-genai SDK                         | Clean migration without feature toggle; preserves all resilience patterns         | ✓ Good (v1.2) |
| Celery tasks remain on sync Session                               | Workers run in separate processes; sync is correct, avoids complexity             | ✓ Good (v1.4) |
| Dual-mode DI pattern for shared services                          | Session\|AsyncSession via constructor, no branching in business code              | ✓ Good (v1.4) |
| Source-level regression tests over live-DB tests                  | Module inspection avoids DB fixture coupling; catches import-level regressions    | ✓ Good (v1.4) |
| Inline async SQL in routers (not pass AsyncSession to sync repos) | Prevents MissingGreenlet; repos stay sync for Celery compatibility                | ✓ Good (v1.4) |
| begin_nested() direct impl on test adapters                       | **getattr** passthrough returns non-awaitable; explicit wrappers safer            | ✓ Good (v1.4) |
| Keep dual-session constructor contract (db: Any)                  | Fix runtime via adaptive helpers, not signature changes                           | ✓ Good (v1.5) |
| Cancel and saga compensation as independent lifecycles            | Cancel = flow cleanup; compensation = saga failure; no coupling                   | ✓ Good (v1.5) |
| Compensation ownership on SagaCompensator                         | Orchestrator delegates; tests validate compensator API                            | ✓ Good (v1.5) |
| compensate_patient uses hard-delete (db.delete)                   | Matches production handler behavior; documented as contract                       | ✓ Good (v1.5) |
| OTel removed to unblock ADK                                       | OTel instrumentation conflicts with ADK deps; user chose to remove OTel           | ✓ Good (v1.7) |
| ADK runtime controls at execution boundary                         | Timeout, budget, cancel share semantics across runner and direct-handler paths     | ✓ Good (v1.8) |
| Operator policy metadata immutable in tool dispatch                | Prevents model-generated context from overwriting safety decisions                 | ✓ Good (v1.8) |
| Default Prometheus registry for ADK metrics                        | Existing /metrics exporter surfaces new series without extra wiring                | ✓ Good (v1.8) |
| Conditional real-runner tests via skipif(not HAS_ADK)              | Local environments stay green; CI smoke-adk job provides real coverage             | ✓ Good (v1.8) |
| Hardcoded physician hours (Mon-Fri 08-17)                         | No preferences model exists yet; functional baseline                              | ⚠ Revisit     |
| WuzAPI over Evolution API                                         | Evolution API instability and maintenance debt made hard-cut migration lower risk | ✓ Good (v1.6) |

---

_Last updated: 2026-03-06 after v1.8 milestone completion_
