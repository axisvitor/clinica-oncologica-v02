# Clinica Oncologica — Sistema de Acompanhamento

## What This Is

Sistema de acompanhamento oncologico via WhatsApp que envia questionarios humanizados aos pacientes entre consultas, permitindo que medicos acompanhem seus pacientes de forma continua. O sistema roda com 4 agentes Pydantic AI tipados (sentiment, humanize, variation, empathy), PII redaction obrigatoria, orquestracao de fluxo em funcoes async Python diretas e GeminiClient baseado em `google-genai` com circuit breaker, rate limiter e cache. Toda a camada API opera sobre AsyncSession (SQLAlchemy), enquanto Celery workers mantem sync Session por design. A integracao WhatsApp agora opera em hard cut com WuzAPI (whatsmeow), com Evolution API tombstonada.

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

### Active

- [ ] Executar verificacao operacional em ambiente real WuzAPI (send/media, webhook HMAC real, QR pairing, LID DLQ observability)
- [ ] Definir requirements e roadmap do proximo milestone (`/gsd-new-milestone`)
- [ ] Modelar disponibilidade medica por medico (substituir baseline hardcoded Mon-Fri 08:00-17:00)
- [ ] Continuar reducao de arquivos >500 linhas em modulos criticos
- [ ] Revisitar ADK/OTel stack quando conflitos de dependencia forem destravados

<details>
<summary>Archived v1.6 planning scope</summary>

**Goal:** Replace Evolution API with WuzAPI as the WhatsApp provider — hard cut, no dual-provider hacks.

**Target features:**
- WuzAPIClient replacing EvolutionAPIClient (aiohttp async, whatsmeow-backed)
- Webhook handlers rewritten for WuzAPI payload format (Message, ReadReceipt events)
- Phone format adaptation (final implementation sends raw digits in WuzAPI `Phone` field)
- Auth model update (apikey header -> Token/Authorization header)
- HMAC validation update (SHA-256 via x-hmac-signature)
- Session management (instance model -> session model)
- UnifiedWhatsAppService adapter wired to WuzAPI
- Environment variables migrated
- Evolution API code tombstoned (both legacy and canonical stacks)
- Tests updated for WuzAPI contracts

</details>

### Out of Scope

- Full Celery task async conversion — workers run in separate processes; sync Session is correct
- Redesign de UI do frontend admin ou quiz interface — foco backend
- Live chat medico-paciente via mesmo numero — requer shared inbox product
- OAuth/SSO — Firebase Auth ja atende
- Migraçao de infra (Railway/AWS RDS/Dragonfly) — manter stack atual
- 50+ files >500 lines needing split — tracked as tech debt
- Google ADK — deferred pending dependency conflict resolution
- Physician availability hours model — hardcoded Mon-Fri 08:00-17:00 functional baseline
- ORM query rewrite to raw SQL — keep SQLAlchemy ORM; just switch Session type
- Saga event-sourcing rewrite — existing saga pattern functional, audit confirmed
- Dual-provider mode (Evolution + WuzAPI) — intentionally rejected after hard cut

## Current State

- v1.6 WuzAPI Migration shipped (Phases 33-39, 21 plans, 42 tasks)
- Milestone stats: 132 files changed, +16,433 / -7,093 lines (net +9,340 LOC), 99 commits
- Audit findings M-1/M-2 closed in Phase 39; remaining debt is live-environment verification only
- Artifacts archived in `.planning/milestones/v1.6-ROADMAP.md` and `.planning/milestones/v1.6-REQUIREMENTS.md`

## Next Milestone Goals

- Formalizar novo milestone com requirements frescos (sem herdar backlog implícito)
- Fechar lacunas de validacao operacional WuzAPI em ambiente real
- Priorizar melhorias de confiabilidade clinica observadas em producao
- Continuar hardening de arquitetura (files >500 LOC, observability de saga/flow)

## Context

- v1.0 shipped: security, LGPD, stability, AI reliability, flow consolidation (net -9,314 LOC)
- v1.1 shipped: async hot paths, LGPD key rotation, AI rationalization, observability (net +4,664 LOC)
- v1.2 shipped: AI framework migration — LangGraph removed, Pydantic AI agents, google-genai SDK (net +7,680 LOC)
- v1.3 shipped: flow health fixes + dead code cleanup + 10 critical file splits (net +5,472 LOC)
- v1.4 shipped: full AsyncSession migration — all API routers async, dual-mode services, test stability (net +20,503 LOC)
- v1.5 shipped: saga orchestrator deep dive — audit, flow trace, compensation integrity, 40+ tests (net +7,166 LOC)
- v1.6 shipped: WuzAPI migration complete with Evolution tombstone and integration polish (net +9,340 LOC)
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

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Consolidar dual flow em production system | QW-021 tinha 7 callers vs 59 do production; low production use | ✓ Good (v1.0) |
| FlowDispatcher como facade permanente | Stable import target for enrollment routing | ✓ Good (v1.0) |
| Hot-path-first async migration | Full migration is too large; hot paths cover ~80% throughput | ✓ Good (v1.1) |
| Pydantic AI over LangGraph for agents | Type safety, structured output, zero graph overhead for 4 AI operations | ✓ Good (v1.2) |
| PIISafeAgent as mandatory wrapper | LGPD Art. 46 compliance; CI lint blocks direct .run() calls | ✓ Good (v1.2) |
| Direct async Python over ADK for flow orchestration | 10-15 lines each, identical semantics, zero new dependencies | ✓ Good (v1.2) |
| Hard-cut GeminiClient to google-genai SDK | Clean migration without feature toggle; preserves all resilience patterns | ✓ Good (v1.2) |
| Celery tasks remain on sync Session | Workers run in separate processes; sync is correct, avoids complexity | ✓ Good (v1.4) |
| Dual-mode DI pattern for shared services | Session\|AsyncSession via constructor, no branching in business code | ✓ Good (v1.4) |
| Source-level regression tests over live-DB tests | Module inspection avoids DB fixture coupling; catches import-level regressions | ✓ Good (v1.4) |
| Inline async SQL in routers (not pass AsyncSession to sync repos) | Prevents MissingGreenlet; repos stay sync for Celery compatibility | ✓ Good (v1.4) |
| begin_nested() direct impl on test adapters | __getattr__ passthrough returns non-awaitable; explicit wrappers safer | ✓ Good (v1.4) |
| Keep dual-session constructor contract (db: Any) | Fix runtime via adaptive helpers, not signature changes | ✓ Good (v1.5) |
| Cancel and saga compensation as independent lifecycles | Cancel = flow cleanup; compensation = saga failure; no coupling | ✓ Good (v1.5) |
| Compensation ownership on SagaCompensator | Orchestrator delegates; tests validate compensator API | ✓ Good (v1.5) |
| compensate_patient uses hard-delete (db.delete) | Matches production handler behavior; documented as contract | ✓ Good (v1.5) |
| Google ADK deferred | Irresolvable OTel cap + Pydantic 2.11+ + 300-400 MB footprint | ⚠ Revisit |
| Hardcoded physician hours (Mon-Fri 08-17) | No preferences model exists yet; functional baseline | ⚠ Revisit |
| WuzAPI over Evolution API | Evolution API instability and maintenance debt made hard-cut migration lower risk | ✓ Good (v1.6) |

---
*Last updated: 2026-03-03 after v1.6 milestone completion*
