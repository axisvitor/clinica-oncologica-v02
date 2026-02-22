# Requirements: Clínica Oncológica — Refinamento para Produção

**Defined:** 2026-02-22
**Core Value:** Médicos acompanham pacientes oncológicos continuamente entre consultas via WhatsApp, com questionários humanizados que coletam dados clínicos sem sobrecarregar o paciente.

## v1 Requirements

Requirements para levar o protótipo a produção com pacientes reais.

### Security

- [x] **SEC-01**: Monitoring endpoints autenticados com `get_current_user` + role check (substituir placeholder auth em `enhanced_monitoring.py`)
- [x] **SEC-02**: TEST_TOKEN_REGISTRY removido do binário de produção (mover para conftest de testes)
- [x] **SEC-03**: Firebase service account key removido do working directory (usar GCP Secret Manager ou env var)
- [x] **SEC-04**: `APP_ENABLE_DEBUG=False` enforced em staging e produção via deployment config validation

### LGPD Compliance

- [ ] **LGPD-01**: Tabela `patient_deletion_audit` persistente com registro imutável de deleções (LGPD Art. 16/18)
- [ ] **LGPD-02**: Handler de opt-out WhatsApp (STOP/PARAR/CANCELAR) que interrompe messaging imediatamente e registra revogação de consentimento (LGPD Art. 18)
- [ ] **LGPD-03**: AI event types (`AI_QUERY`, `AI_HUMANIZATION`, `AI_SENTIMENT`, `AI_FOLLOW_UP`) adicionados ao `AuditEventType` enum + Alembic migration
- [ ] **LGPD-04**: Batch re-encryption implementado via Celery task com chunked processing para viabilizar key rotation (LGPD Art. 46)

### AI Reliability

- [ ] **AI-01**: LangGraph startup health check que verifica disponibilidade na inicialização da aplicação
- [ ] **AI-02**: Converter fallbacks `None` de LangGraph para `FeatureNotAvailableError` explícito (sem silent degradation)
- [ ] **AI-03**: Simplificar 5 grafos single-node (humanization, sentiment, generation, question_variation, empathetic_follow_up) para chamadas diretas `GeminiClient.generate_content()`
- [ ] **AI-04**: Adicionar circuit breaker ao redor de chamadas Gemini (gap identificado na pesquisa de arquitetura)

### Flow Consolidation

- [ ] **FLOW-01**: Consolidar dual flow systems — escolher sistema canônico (production `flow_core.py` ou QW-021 `services/flow/core/manager.py`) e decomissionar o outro via Strangler Fig pattern
- [ ] **FLOW-02**: Implementar `FlowDispatcher` facade com feature-flag routing para migração incremental
- [ ] **FLOW-03**: Testes de integração cobrindo flow system unificado + alert pipeline end-to-end

### Async Migration

- [ ] **ASYNC-01**: Migrar hot paths para `AsyncSession` — webhook handling (`sequential_message_handler.py`, 12 instances)
- [ ] **ASYNC-02**: Migrar hot paths para `AsyncSession` — flow advancement (`flow_core.py`, 7 instances)
- [ ] **ASYNC-03**: Migrar hot paths para `AsyncSession` — quiz response processing (`enhanced_quiz_service.py`, 8 instances)
- [ ] **ASYNC-04**: Padronizar todas Celery tasks para `async_to_sync` (eliminar `asyncio.run()` — memory leak fix)
- [ ] **ASYNC-05**: Migrar saga orchestrator para `AsyncSession` (compensation + steps — data integrity risk)

### Reliability

- [ ] **REL-01**: Rate limiter atômico via Lua script Redis (template já existe em comment, `rate_limit_core.py`)
- [ ] **REL-02**: Sweep e remoção de imports `from jose` remanescentes (CVE-2024-23342)
- [ ] **REL-03**: python-jose confirmado removido de todos os módulos — substituído por `pyjwt`

### Observability

- [ ] **OBS-01**: Remover métricas hardcoded (`avg_task_duration_seconds` = 2.5) e instrumentar Celery task completion times com rolling average em Redis
- [ ] **OBS-02**: Implementar `get_available_slots()` com lógica real de geração de slots baseada em horários do médico
- [ ] **OBS-03**: Verificar e corrigir WebSocket scaling com Redis pub/sub para multi-instance

## v2 Requirements

Deferred para após validação clínica com primeiro cohort de pacientes.

### Async Migration (Completa)

- **ASYNC-V2-01**: Migrar todos 42+ métodos restantes para AsyncSession (além dos hot paths)
- **ASYNC-V2-02**: Full AsyncSession driver migration (asyncpg como driver principal)

### Scalability

- **SCALE-01**: Celery Beat HA com redbeat (leader election via Redis)
- **SCALE-02**: Shim cleanup — remover 10+ compatibility shims após migração de imports completa
- **SCALE-03**: Split de 60+ arquivos >500 linhas (package-split pattern)

### Infrastructure

- **INFRA-01**: Documentar migration path para WhatsApp Cloud API (quando >500 pacientes ativos)
- **INFRA-02**: Adicionar integration test que verifica todos shim targets existem

## Out of Scope

| Feature | Reason |
|---------|--------|
| Recomendações clínicas autônomas por IA | AI overtrust risk (PMC12325106); sem clearance regulatória |
| Real-time chat com pacientes | Requer triage 24/7; fora do escopo do sistema de questionários |
| Integração EHR/HIS | Complexidade + dependência externa; não necessário para v1 |
| Multi-tenant / multi-clinic | Requer schema isolation, billing — produto separado |
| Wearable device integration | Zero código existente; caminho regulatório FDA/ANVISA |
| Redux/Zustand no frontend | React Query + Context é adequado; UI redesign fora de escopo |
| Full AsyncSession migration de uma vez | Risco alto; migrar hot paths primeiro |
| Live chat médico-paciente via mesmo número | Requer shared inbox product separado |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 1 | Complete (01-01) |
| SEC-02 | Phase 1 | Complete |
| SEC-03 | Phase 1 | Complete |
| SEC-04 | Phase 1 | Complete |
| LGPD-01 | Phase 2 | Pending |
| LGPD-02 | Phase 2 | Pending |
| LGPD-03 | Phase 2 | Pending |
| LGPD-04 | Phase 7 | Pending |
| AI-01 | Phase 4 | Pending |
| AI-02 | Phase 4 | Pending |
| AI-03 | Phase 8 | Pending |
| AI-04 | Phase 8 | Pending |
| FLOW-01 | Phase 5 | Pending |
| FLOW-02 | Phase 5 | Pending |
| FLOW-03 | Phase 5 | Pending |
| ASYNC-01 | Phase 6 | Pending |
| ASYNC-02 | Phase 6 | Pending |
| ASYNC-03 | Phase 6 | Pending |
| ASYNC-04 | Phase 3 | Pending |
| ASYNC-05 | Phase 6 | Pending |
| REL-01 | Phase 3 | Pending |
| REL-02 | Phase 3 | Pending |
| REL-03 | Phase 3 | Pending |
| OBS-01 | Phase 9 | Pending |
| OBS-02 | Phase 9 | Pending |
| OBS-03 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-22*
*Last updated: 2026-02-22 after roadmap creation (9-phase structure)*
