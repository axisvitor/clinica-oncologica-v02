# Requirements: Clinica Oncologica v1.7

**Defined:** 2026-03-03
**Core Value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.

## v1.7 Requirements

### ADK Integration

- [x] **ADK-01**: OTel instrumentation packages removidos de requirements.txt sem quebrar Sentry
- [x] **ADK-02**: `app/core/tracing.py` tombstoned com ImportError (fallback mock ja existe)
- [x] **ADK-03**: google-adk instalado e resolvido com pydantic-ai-slim[google] no Python 3.13
- [x] **ADK-04**: PIISafeADKWrapper criado em `app/ai/adk/` com sanitizacao PII antes de qualquer chamada Gemini via ADK
- [x] **ADK-05**: CI guard (`check_agent_run_calls.py`) estendido para cobrir patterns de chamada ADK
- [x] **ADK-06**: 4 agentes Pydantic AI existentes (sentiment, humanize, variation, empathy) wrapped como ADK FunctionTools
- [ ] **ADK-07**: ADK Runner configurado com pelo menos um endpoint FastAPI funcional
- [ ] **ADK-08**: HiveMind LangGraph dead code removido (`IntegrationMode.LANGGRAPH_ONLY`, `_process_with_langgraph()`)

### Admin SPA

- [ ] **ADMIN-01**: Dead code Evolution API removido do frontend (WhatsAppDashboard.tsx, AdminSettingsTab.tsx, env-validator.ts, runtime-config.ts)
- [ ] **ADMIN-02**: Modulo hive-mind.ts auditado — endpoints inexistentes removidos ou alinhados com backend
- [ ] **ADMIN-03**: API client consolidado — chamadas duplicadas eliminadas, tipos alinhados com contratos backend v2
- [ ] **ADMIN-04**: Componentes de polling (AgentSwarm.tsx, SystemHealth.tsx) migrados para TanStack Query
- [ ] **ADMIN-05**: Prettier configurado e aplicado em todo o admin SPA
- [ ] **ADMIN-06**: Warnings de ESLint zerados no admin SPA
- [ ] **ADMIN-07**: Pacotes npm nao utilizados removidos (audit via knip ou similar)
- [ ] **ADMIN-08**: Layout e espacamento consistentes entre paginas do admin

### Quiz Interface

- [ ] **QUIZ-01**: Prettier configurado e aplicado na quiz interface
- [ ] **QUIZ-02**: Next.js atualizado para v15 (desbloqueia ESLint 9 nativo)
- [ ] **QUIZ-03**: ESLint migrado para flat config (ESLint 9), alinhado com admin SPA
- [ ] **QUIZ-04**: Dependencia `identity-obj-proxy` adicionada ao devDependencies
- [ ] **QUIZ-05**: `msw` atualizado de v1.x (end-of-life) para v2.x
- [ ] **QUIZ-06**: Type coverage melhorada — tipos explicitados em hooks e API calls
- [ ] **QUIZ-07**: Layout e espacamento consistentes entre paginas do quiz

## v2 Requirements

### Observability

- **OBS-01**: Substituicao do OTel por alternativa de tracing (Sentry Performance, Datadog, ou custom)
- **OBS-02**: Metricas de latencia e throughput dos agentes ADK em producao

### ADK Advanced

- **ADK-ADV-01**: ADK session service com persistencia para fluxos multi-step
- **ADK-ADV-02**: ADK evaluation harness para validacao de qualidade de respostas

## Out of Scope

| Feature | Reason |
|---------|--------|
| Reescrita completa do frontend | Foco em qualidade e cleanup, nao redesign |
| Mobile app | Web-first, mobile adiado |
| ADK substituir Pydantic AI agents | ADK complementa, nao substitui — agents tipados sao estaveis |
| Novo design system | shadcn/ui ja esta em uso; foco em consistencia, nao troca |
| Testes E2E frontend | Foco em qualidade de codigo; testes E2E sao milestone separado |
| OTel replacement nesse milestone | OTel removido; replacement adiado para v2 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ADK-01 | Phase 40 | Complete |
| ADK-02 | Phase 40 | Complete |
| ADK-03 | Phase 40 | Complete |
| ADK-04 | Phase 40 | Complete |
| ADK-05 | Phase 40 | Complete |
| ADK-06 | Phase 41 | Complete |
| ADK-07 | Phase 41 | Pending |
| ADK-08 | Phase 41 | Pending |
| ADMIN-01 | Phase 42 | Pending |
| ADMIN-02 | Phase 42 | Pending |
| ADMIN-03 | Phase 42 | Pending |
| ADMIN-04 | Phase 42 | Pending |
| ADMIN-05 | Phase 42 | Pending |
| ADMIN-06 | Phase 42 | Pending |
| ADMIN-07 | Phase 42 | Pending |
| ADMIN-08 | Phase 42 | Pending |
| QUIZ-01 | Phase 43 | Pending |
| QUIZ-02 | Phase 43 | Pending |
| QUIZ-03 | Phase 43 | Pending |
| QUIZ-04 | Phase 43 | Pending |
| QUIZ-05 | Phase 43 | Pending |
| QUIZ-06 | Phase 43 | Pending |
| QUIZ-07 | Phase 43 | Pending |

**Coverage:**
- v1.7 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-03 — traceability mapped to Phases 40-43*
