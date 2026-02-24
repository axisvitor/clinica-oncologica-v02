# Clinica Oncologica — Sistema de Acompanhamento

## What This Is

Sistema de acompanhamento oncologico via WhatsApp que envia questionarios humanizados aos pacientes entre consultas, permitindo que medicos acompanhem seus pacientes de forma continua. Usa 4 agentes Pydantic AI tipados (sentiment, humanize, variation, empathy) com PII redaction obrigatoria para humanizar templates fixos. Orquestracao de fluxo via funcoes async Python diretas. GeminiClient usa google-genai SDK com circuit breaker, rate limiter, e cache. Hot paths de banco sao async, key rotation LGPD e operacional, e metricas/WebSocket refletem o comportamento real do sistema.

## Core Value

Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.

## Requirements

### Validated

- ✓ Backend FastAPI com DDD layers (API → Domain → Services → Infrastructure) — existing
- ✓ Celery + Dragonfly (Redis-compatible) como task queue e broker — existing
- ✓ 38 periodic tasks via Celery Beat — existing
- ✓ Templates fixos armazenados em banco de dados — existing
- ✓ Integraçao WhatsApp via Evolution API (UnifiedWhatsAppService) — existing
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
- ✓ TEST_TOKEN_REGISTRY removido de produçao; Firebase key guardrail — v1.0
- ✓ Debug flag validation bloqueando APP_ENABLE_DEBUG=True em prod/staging — v1.0
- ✓ Audit trail imutavel para deleçoes de pacientes (patient_deletion_audit) — v1.0
- ✓ WhatsApp opt-out handler (STOP/PARAR/CANCELAR) com send guard — v1.0
- ✓ AI audit event types no AuditEventType enum — v1.0
- ✓ Celery tasks usando async_to_sync (sem asyncio.run()) — v1.0
- ✓ Rate limiter atomico via Lua sliding window script — v1.0
- ✓ python-jose eliminado, substituido por PyJWT — v1.0
- ✓ Dual flow system eliminado: FlowDispatcher facade + QW-021 deletado — v1.0
- ✓ Integration tests para flow unificado (onboarding, advancement, alerts) — v1.0
- ✓ AsyncSession nos hot paths: webhook handler, flow engine, quiz, saga — v1.1
- ✓ Batch re-encryption Celery task com dual-key pattern e Redis idempotency — v1.1
- ✓ Metricas reais de Celery tasks via Redis rolling average — v1.1
- ✓ Physician availability retorna slots reais (Mon-Fri 08:00-17:00) — v1.1
- ✓ WebSocket cross-instance delivery via Redis pub/sub corrigido — v1.1
- ✓ 4 agentes Pydantic AI tipados (Sentiment, Humanize, Variation, Empathy) com PIISafeAgent — v1.2
- ✓ PII/PHI redaction obrigatoria antes de cada chamada Gemini (LGPD Art. 46) — v1.2
- ✓ Output guardrails reconectados via @result_validator (banned patterns, prompt leak, length) — v1.2
- ✓ GeminiDomainClient delegando para agentes Pydantic AI (zero breaking changes) — v1.2
- ✓ 50-scenario regression suite validando paridade estrutural agentes vs GeminiClient — v1.2
- ✓ LangGraph totalmente removido: 9 modulos tombstoned, pacotes desinstalados — v1.2
- ✓ Fluxos de orquestracao substituidos por funcoes async Python diretas — v1.2
- ✓ Redis checkpoint PHI keys purgados com audit LGPD — v1.2
- ✓ GeminiClient migrado de langchain-google-genai para google-genai SDK — v1.2
- ✓ langchain-google-genai removido (ultimo pacote LangChain) — v1.2
- ✓ Celery AI tasks usando run_sync() com bridge seguro (sem event loop closure) — v1.2
- ✓ CI gates permanentes: LangChain import blocker + Celery sync wiring validator — v1.2

### Active

(No active requirements — next milestone not yet defined)

### Out of Scope

- Full AsyncSession migration (42+ remaining methods in 65+ files) — hot paths cover ~80% throughput
- Redesign de UI do frontend admin ou quiz interface — foco backend
- Live chat medico-paciente via mesmo numero — requer shared inbox product
- OAuth/SSO — Firebase Auth ja atende
- Migraçao de infra (Railway/AWS RDS/Dragonfly) — manter stack atual
- 60+ files >500 lines needing split — tracked as tech debt
- Google ADK — deferred to v1.3 pending issue #3615 resolution (OTel cap + Pydantic 2.11+ conflicts)
- Physician availability hours model — hardcoded Mon-Fri 08:00-17:00 functional baseline

## Context

- v1.0 shipped: seguranca, LGPD, estabilidade, AI reliability, flow consolidation (net -9,314 LOC)
- v1.1 shipped: async hot paths, LGPD key rotation, AI rationalization, observability (net +4,664 LOC)
- v1.2 shipped: AI framework migration — LangGraph/LangChain fully removed, 4 Pydantic AI agents, google-genai SDK (net +7,680 LOC)
- Codebase brownfield com padroes maduros (DDD, Saga, Circuit Breaker)
- Python 3.13 + FastAPI + SQLAlchemy (AsyncSession on hot paths, sync elsewhere)
- AI stack: Pydantic AI agents + google-genai SDK + GeminiClient (cache, rate limit, circuit breaker, PII redaction)
- Flow system: FlowDispatcher facade routing to direct async Python functions
- 42+ sync-in-async methods remaining (outside hot paths) — tech debt
- 60+ arquivos com >500 linhas precisando split
- 9 tombstoned LangGraph modules remain as ImportError sentinels

## Constraints

- **Stack**: Manter Python/FastAPI, nao migrar para outro framework
- **AI Provider**: Google Gemini via google-genai SDK + Pydantic AI agents
- **Compliance**: LGPD obrigatorio (dados de pacientes oncologicos sao sensiveis)
- **Deploy**: Railway (API + Workers) + Firebase Hosting (frontends)
- **Database**: PostgreSQL (AWS RDS) — manter, nao migrar
- **WhatsApp**: Evolution API — manter integraçao existente

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Consolidar dual flow em production system | QW-021 tinha 7 callers vs 59 do production; low production use | ✓ Good (v1.0) |
| FlowDispatcher como facade permanente | Stable import target for enrollment routing | ✓ Good (v1.0) |
| Hot-path-first async migration | Full migration is too large; hot paths cover ~80% throughput | ✓ Good (v1.1) |
| Dual-session DI in flows router | async_db for FlowCore, sync db for FlowManagementService — avoids MissingGreenlet | ✓ Good (v1.1) |
| Secrets as env var names (not values) in Celery tasks | Prevents PHI/keys appearing in broker/backend logs | ✓ Good (v1.1) |
| Hardcoded physician hours (Mon-Fri 08-17) for v1.1 | No preferences model exists yet; functional baseline | ⚠️ Revisit |
| FeatureNotAvailableError for circuit-open | Single exception type for all AI unavailability; existing catch blocks work | ✓ Good (v1.1) |
| PostgreSQL RULE (not trigger) for audit immutability | RULEs intercept at rewrite layer, cannot be bypassed by superusers | ✓ Good (v1.0) |
| async_to_sync as sole sync→async bridge | Eliminates asyncio.run() memory leaks; matches 15+ existing task files | ✓ Good (v1.0) |
| Pydantic AI over LangGraph for agents | Type safety, structured output, zero graph overhead for 4 AI operations | ✓ Good (v1.2) |
| PIISafeAgent as mandatory wrapper | LGPD Art. 46 compliance; CI lint blocks direct .run() calls | ✓ Good (v1.2) |
| PromptedOutput for SentimentAgent | Gemini cannot use tool-calling + native structured output simultaneously | ✓ Good (v1.2) |
| Direct async Python over ADK for flow orchestration | 10-15 lines each, identical semantics, zero new dependencies | ✓ Good (v1.2) |
| Hard-cut GeminiClient to google-genai SDK | Clean migration without feature toggle; preserves all resilience patterns | ✓ Good (v1.2) |
| Google ADK deferred to v1.3 | Irresolvable OTel cap + Pydantic 2.11+ + 300-400 MB footprint | — Pending |
| PIISafeAgent run_sync for Celery | Repairs closed/missing event loops; avoids async_to_sync for AI calls | ✓ Good (v1.2) |
| LangGraph tombstone (not delete) | ImportError sentinels with migration messages for discoverability | ✓ Good (v1.2) |

---
*Last updated: 2026-02-24 after v1.2 milestone*
