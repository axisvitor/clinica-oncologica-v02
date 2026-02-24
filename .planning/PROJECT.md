# Clinica Oncologica — Sistema de Acompanhamento

## What This Is

Sistema de acompanhamento oncologico via WhatsApp que envia questionarios humanizados aos pacientes entre consultas, permitindo que medicos acompanhem seus pacientes de forma continua. Usa LangGraph para orquestrar o fluxo de conversa e chamadas diretas GeminiClient para humanizar templates fixos. Apos v1.1, hot paths de banco sao async, key rotation LGPD e operacional, a camada AI e simplificada (sem grafos single-node), e metricas/WebSocket refletem o comportamento real do sistema.

## Core Value

Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.

## Requirements

### Validated

- ✓ Backend FastAPI com DDD layers (API → Domain → Services → Infrastructure) — existing
- ✓ Celery + Dragonfly (Redis-compatible) como task queue e broker — existing
- ✓ 38 periodic tasks via Celery Beat — existing
- ✓ LangGraph orquestrando fluxo de conversaçao (multi-node graphs only) — v1.1
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
- ✓ LangGraph startup health check + FeatureNotAvailableError — v1.0
- ✓ Centralized invoke_langgraph_graph() wrapper (sem silent None fallback) — v1.0
- ✓ Dual flow system eliminado: FlowDispatcher facade + QW-021 deletado — v1.0
- ✓ Integration tests para flow unificado (onboarding, advancement, alerts) — v1.0
- ✓ AsyncSession nos hot paths: webhook handler, flow engine, quiz, saga — v1.1
- ✓ Batch re-encryption Celery task com dual-key pattern e Redis idempotency — v1.1
- ✓ 5 single-node LangGraph graphs eliminados, chamadas diretas GeminiClient — v1.1
- ✓ Metricas reais de Celery tasks via Redis rolling average — v1.1
- ✓ Physician availability retorna slots reais (Mon-Fri 08:00-17:00) — v1.1
- ✓ WebSocket cross-instance delivery via Redis pub/sub corrigido — v1.1

### Active

## Current Milestone: v1.2 AI Framework Migration

**Goal:** Substituir LangGraph por Pydantic AI + Google ADK, eliminando overhead de orquestracao mantendo as mesmas operacoes AI com melhor type safety e estrutura de agentes.

**Target features:**
- Remover LangGraph e toda infraestrutura associada (grafos, runtime, checkpointing, state)
- Remover sistema de consensus (codigo morto, nao utilizado em producao)
- Implementar agentes Pydantic AI com structured output tipado para as 4 operacoes AI
- Implementar orquestracao Google ADK (SequentialAgent/ParallelAgent) para fluxos
- Reavaliar e migrar protecoes do GeminiClient (cache, rate limit, circuit breaker, PII redaction)

### Out of Scope

- Full AsyncSession migration (42+ remaining methods in 65+ files) — hot paths cover ~80% throughput
- Redesign de UI do frontend admin ou quiz interface — foco backend
- Live chat medico-paciente via mesmo numero — requer shared inbox product
- OAuth/SSO — Firebase Auth ja atende
- Migraçao de infra (Railway/AWS RDS/Dragonfly) — manter stack atual
- 60+ files >500 lines needing split — tracked as tech debt

## Context

- v1.0 shipped: segurança, LGPD, estabilidade, AI reliability, flow consolidation (net -9,314 LOC)
- v1.1 shipped: async hot paths, LGPD key rotation, AI rationalization, observability (net +4,664 LOC)
- Codebase brownfield com padroes maduros (DDD, Saga, Circuit Breaker)
- Python 3.13 + FastAPI + SQLAlchemy (AsyncSession on hot paths, sync elsewhere)
- LangGraph 1.0.7 com Google Gemini — only multi-node graphs remain (flow_message, flow_response)
- Flow system unificado: FlowDispatcher facade routing to production flow_core.py
- 42+ sync-in-async methods remaining (outside hot paths) — tech debt for future milestone
- 60+ arquivos com >500 linhas precisando split

## Constraints

- **Stack**: Manter Python/FastAPI, nao migrar para outro framework
- **AI Provider**: Google Gemini (ja integrado via langchain-google-genai)
- **Compliance**: LGPD obrigatorio (dados de pacientes oncologicos sao sensiveis)
- **Deploy**: Railway (API + Workers) + Firebase Hosting (frontends)
- **Database**: PostgreSQL (AWS RDS) — manter, nao migrar
- **WhatsApp**: Evolution API — manter integraçao existente

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LangGraph para orquestraçao (multi-node only) | Retained multi-node graphs, eliminated 5 single-node wrappers | ✓ Good (v1.1) |
| Consolidar dual flow em production system | QW-021 tinha 7 callers vs 59 do production; low production use | ✓ Good (v1.0) |
| FlowDispatcher como facade permanente | Stable import target for enrollment routing | ✓ Good (v1.0) |
| Hot-path-first async migration | Full migration is too large; hot paths cover ~80% throughput | ✓ Good (v1.1) |
| Dual-session DI in flows router | async_db for FlowCore, sync db for FlowManagementService — avoids MissingGreenlet | ✓ Good (v1.1) |
| Secrets as env var names (not values) in Celery tasks | Prevents PHI/keys appearing in broker/backend logs | ✓ Good (v1.1) |
| Hardcoded physician hours (Mon-Fri 08-17) for v1.1 | No preferences model exists yet; functional baseline | ⚠️ Revisit |
| FeatureNotAvailableError for circuit-open | Single exception type for all AI unavailability; existing catch blocks work | ✓ Good (v1.1) |
| Full code deletion (not tombstone) for QW-021 | Zero callers outside package; clean break preferred | ✓ Good (v1.0) |
| PostgreSQL RULE (not trigger) for audit immutability | RULEs intercept at rewrite layer, cannot be bypassed by superusers | ✓ Good (v1.0) |
| async_to_sync as sole sync→async bridge | Eliminates asyncio.run() memory leaks; matches 15+ existing task files | ✓ Good (v1.0) |

---
*Last updated: 2026-02-23 after v1.2 milestone start*
