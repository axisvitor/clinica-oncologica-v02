# Clínica Oncológica — Refinamento para Produção

## What This Is

Sistema de acompanhamento oncológico via WhatsApp que envia questionários humanizados aos pacientes entre consultas, permitindo que médicos acompanhem seus pacientes de forma contínua — não apenas no dia da consulta. Usa LangGraph para orquestrar o fluxo de conversa e humanizar templates fixos, evitando tom robótico. Atualmente é um protótipo funcional que precisa ser refinado, otimizado e preparado para produção com pacientes reais.

## Core Value

Médicos acompanham pacientes oncológicos continuamente entre consultas via WhatsApp, com questionários humanizados que coletam dados clínicos sem sobrecarregar o paciente.

## Requirements

### Validated

<!-- Capacidades já implementadas no protótipo existente -->

- ✓ Backend FastAPI com DDD layers (API → Domain → Services → Infrastructure) — existing
- ✓ Celery + Dragonfly (Redis-compatible) como task queue e broker — existing
- ✓ 38 periodic tasks via Celery Beat — existing
- ✓ LangGraph orquestrando fluxo de conversação + humanização de templates — existing
- ✓ Templates fixos armazenados em banco de dados — existing
- ✓ Integração WhatsApp via Evolution API (UnifiedWhatsAppService) — existing
- ✓ Firebase Auth para autenticação de usuários — existing
- ✓ LGPD compliance (middleware, PII redaction, consent management, encryption) — existing
- ✓ Saga orchestrator para onboarding de pacientes com compensação — existing
- ✓ Quiz mensal interface (Next.js) com short links — existing
- ✓ Frontend admin SPA (React 19 + Vite + shadcn/ui) — existing
- ✓ WebSocket para dashboard real-time — existing
- ✓ Circuit breaker e resilience patterns — existing
- ✓ Structured logging + Sentry integration — existing
- ✓ DLQ para webhook/message failures — existing

### Active

<!-- Escopo deste trabalho: refinamento para produção -->

- [ ] Validar se LangGraph é a melhor escolha para orquestração + humanização
- [ ] Avaliar se templates no DB podem ser otimizados ou substituídos
- [ ] Resolver sync-in-async pattern (42+ métodos bloqueando event loop)
- [ ] Consolidar dual flow systems (production flat-file vs QW-021 step-based)
- [ ] Refatorar arquivos >500 linhas (60+ arquivos identificados)
- [ ] Corrigir bugs conhecidos (physician availability, asyncio.run() inconsistency)
- [ ] Resolver security issues (placeholder auth em monitoring, test token registry)
- [ ] Implementar funcionalidades faltantes críticas (batch re-encryption, AI audit types)
- [ ] Aumentar cobertura de testes em áreas frágeis (saga compensation, dual flow, auth)
- [ ] Remover código morto e shims desnecessários de forma segura
- [ ] Preparar stack para produção com pacientes reais

### Out of Scope

- Features novas além do que já existe — foco é refinamento
- Migração de infra (manter Railway + AWS RDS + Dragonfly)
- Redesign de UI do frontend admin ou quiz interface
- Implementação de real-time chat com pacientes
- OAuth/SSO (Firebase Auth já atende)

## Context

- Protótipo funcional, nunca usado com pacientes reais
- Codebase brownfield com padrões maduros (DDD, Saga, Circuit Breaker) mas dívida técnica acumulada
- Já mapeado em `.planning/codebase/` com 7 documentos detalhados
- Python 3.13 + FastAPI + SQLAlchemy sync (AsyncSession migration pendente)
- LangGraph 1.0.7 com Google Gemini para humanização de mensagens
- Dual flow systems coexistindo (production vs QW-021) — precisa consolidar
- 42+ sync-in-async methods anotados com `# TODO(async-migration)`
- 60+ arquivos com >500 linhas precisando split
- Tombstone pattern e shim pattern já estabelecidos no projeto

## Constraints

- **Stack**: Manter Python/FastAPI, não migrar para outro framework
- **AI Provider**: Google Gemini (já integrado via langchain-google-genai)
- **Compliance**: LGPD obrigatório (dados de pacientes oncológicos são sensíveis)
- **Deploy**: Railway (API + Workers) + Firebase Hosting (frontends)
- **Database**: PostgreSQL (AWS RDS) — manter, não migrar
- **WhatsApp**: Evolution API — manter integração existente

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LangGraph para orquestração + humanização | Precisa validação — pode ser overengineered | — Pending |
| Templates fixos no DB reformulados por IA | Precisa validação — pode ter alternativa melhor | — Pending |
| Manter dual flow vs consolidar em um | Dois sistemas paralelos geram overhead | — Pending |
| Sync-in-async: migrar tudo vs migrar hot paths | Migração completa é projeto grande | — Pending |

---
*Last updated: 2026-02-22 after initialization*
