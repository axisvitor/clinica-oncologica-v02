# Clinica Oncologica — Sistema de Acompanhamento

## What This Is

Sistema de acompanhamento oncologico via WhatsApp que envia questionarios humanizados aos pacientes entre consultas, permitindo que medicos acompanhem seus pacientes de forma continua. Usa LangGraph para orquestrar o fluxo de conversa e humanizar templates fixos, evitando tom robotico. Apos v1.0, o sistema tem seguranca reforçada, compliance LGPD, estabilidade operacional, confiabilidade de IA e um unico sistema de flow canonico.

## Core Value

Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.

## Requirements

### Validated

- ✓ Backend FastAPI com DDD layers (API → Domain → Services → Infrastructure) — existing
- ✓ Celery + Dragonfly (Redis-compatible) como task queue e broker — existing
- ✓ 38 periodic tasks via Celery Beat — existing
- ✓ LangGraph orquestrando fluxo de conversaçao + humanizaçao de templates — existing
- ✓ Templates fixos armazenados em banco de dados — existing
- ✓ Integraçao WhatsApp via Evolution API (UnifiedWhatsAppService) — existing
- ✓ Firebase Auth para autenticaçao de usuarios — existing
- ✓ LGPD compliance (middleware, PII redaction, consent management, encryption) — existing
- ✓ Saga orchestrator para onboarding de pacientes com compensaçao — existing
- ✓ Quiz mensal interface (Next.js) com short links — existing
- ✓ Frontend admin SPA (React 19 + Vite + shadcn/ui) — existing
- ✓ WebSocket para dashboard real-time — existing
- ✓ Circuit breaker e resilience patterns — existing
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

## Current Milestone: v1.1 Architecture & Observability

**Goal:** Complete async migration of hot paths, enable LGPD key rotation, rationalize AI layer, and add real observability.

**Target features:**
- AsyncSession migration for webhook handler, flow advancement, quiz processing, saga orchestrator
- Batch re-encryption Celery task for LGPD key rotation
- Replace 5 single-node LangGraph graphs with direct GeminiClient calls
- Gemini circuit breaker
- Real Celery task metrics (replace hardcoded 2.5s)
- Physician availability slot generation
- WebSocket multi-instance scaling via Redis pub/sub

### Active

- [ ] Migrar hot paths para AsyncSession (webhook, flow, quiz, saga)
- [ ] Batch re-encryption para key rotation (LGPD Art. 46)
- [ ] Simplificar grafos LangGraph single-node para chamadas diretas GeminiClient
- [ ] Adicionar circuit breaker ao redor de chamadas Gemini
- [ ] Instrumentar metricas reais de Celery tasks (remover hardcoded 2.5s)
- [ ] Implementar get_available_slots() com logica real de slots
- [ ] WebSocket scaling com Redis pub/sub para multi-instance

### Out of Scope

- Features novas alem do que ja existe — foco e refinamento
- Migraçao de infra (manter Railway + AWS RDS + Dragonfly)
- Redesign de UI do frontend admin ou quiz interface
- Implementaçao de real-time chat com pacientes
- OAuth/SSO (Firebase Auth ja atende)
- Full AsyncSession migration de uma vez — migrar hot paths primeiro
- Live chat medico-paciente via mesmo numero

## Context

- v1.0 shipped: segurança, LGPD, estabilidade, AI reliability, flow consolidation
- Codebase brownfield com padroes maduros (DDD, Saga, Circuit Breaker)
- Python 3.13 + FastAPI + SQLAlchemy sync (AsyncSession migration pendente para hot paths)
- LangGraph 1.0.7 com Google Gemini para humanizaçao de mensagens
- Flow system unificado: FlowDispatcher facade routing to production flow_core.py
- 42+ sync-in-async methods anotados com `# TODO(async-migration)`
- 60+ arquivos com >500 linhas precisando split
- Net -9,314 LOC reduzidos no v1.0 (QW-021 deletion foi maior contributor)

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
| LangGraph para orquestraçao + humanizaçao | Retained — rationalize single-node graphs, keep multi-node | ✓ Good (v1.0) |
| Consolidar dual flow em production system | QW-021 tinha 7 callers vs 59 do production; low production use | ✓ Good (v1.0) |
| FlowDispatcher como facade permanente | Stable import target for enrollment routing | ✓ Good (v1.0) |
| Sync-in-async: migrar hot paths primeiro | Migraçao completa e projeto grande; hot paths cobrem 80% do throughput | — Pending (v1.1) |
| Full code deletion (not tombstone) for QW-021 | Zero callers outside package; clean break preferred | ✓ Good (v1.0) |
| Patient-type routing (not percentage) for flow flags | Deterministic: new patients always canonical, existing patients migrated | ✓ Good (v1.0) |
| PostgreSQL RULE (not trigger) for audit immutability | RULEs intercept at rewrite layer, cannot be bypassed by superusers | ✓ Good (v1.0) |
| async_to_sync as sole sync→async bridge | Eliminates asyncio.run() memory leaks; matches 15+ existing task files | ✓ Good (v1.0) |

---
*Last updated: 2026-02-22 after v1.1 milestone start*
