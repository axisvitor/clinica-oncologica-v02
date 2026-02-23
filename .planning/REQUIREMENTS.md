# Requirements: v1.1 Architecture & Observability

**Defined:** 2026-02-22
**Core Value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.

## v1.1 Requirements

Requirements para completar migracao async dos hot paths, viabilizar key rotation LGPD, racionalizar camada AI e adicionar observabilidade real.

### Async Migration

- [x] **ASYNC-01**: Migrar hot paths para `AsyncSession` — webhook handling (`sequential_message_handler.py`, 12 instancias anotadas com `TODO(async-migration)`)
- [x] **ASYNC-02**: Migrar hot paths para `AsyncSession` — flow advancement (`flow_core.py`, 7 instancias anotadas)
- [x] **ASYNC-03**: Migrar hot paths para `AsyncSession` — quiz response processing (`enhanced_quiz_service.py`, 8 instancias anotadas)
- [x] **ASYNC-05**: Migrar saga orchestrator para `AsyncSession` (compensation + steps — data integrity risk por timeout)

### LGPD Compliance

- [x] **LGPD-04**: Batch re-encryption implementado via Celery task com chunked processing e idempotencia para viabilizar key rotation (LGPD Art. 46)

### AI Reliability

- [x] **AI-03**: Simplificar 5 grafos single-node (humanization, sentiment, generation, question_variation, empathetic_follow_up) para chamadas diretas `GeminiClient.generate_content()`
- [x] **AI-04**: Adicionar circuit breaker ao redor de chamadas Gemini (FeatureNotAvailableError quando circuit abre)

### Observability

- [ ] **OBS-01**: Remover metricas hardcoded (`avg_task_duration_seconds` = 2.5) e instrumentar Celery task completion times com rolling average em Redis
- [ ] **OBS-02**: Implementar `get_available_slots()` com logica real de geracao de slots baseada em horarios do medico
- [ ] **OBS-03**: Verificar e corrigir WebSocket scaling com Redis pub/sub para multi-instance

## Traceability

| Requirement | Phase | Plan(s) | Status |
|-------------|-------|---------|--------|
| ASYNC-01 | Phase 6 | 06-01 | Complete |
| ASYNC-02 | Phase 6 | 06-02 | Complete |
| ASYNC-03 | Phase 6 | 06-03 | Complete |
| ASYNC-05 | Phase 6 | 06-04 | Complete |
| LGPD-04 | Phase 7 | 07-01 | Complete |
| AI-03 | Phase 8 | 08-01 | Pending |
| AI-04 | Phase 8 | 08-02 | Pending |
| OBS-01 | Phase 9 | 09-01 | Pending |
| OBS-02 | Phase 9 | 09-02 | Pending |
| OBS-03 | Phase 9 | 09-03 | Pending |

**Coverage:**
- v1.1 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full AsyncSession migration (42+ metodos restantes) | v2 — migrar hot paths primeiro cobre 80% do throughput |
| Redesign de UI do frontend admin ou quiz interface | Foco e refinamento de backend |
| Live chat medico-paciente via mesmo numero | Requer shared inbox product separado |
| OAuth/SSO | Firebase Auth ja atende |
| Migracao de infra (Railway/AWS RDS/Dragonfly) | Manter stack atual |

---
*Requirements defined: 2026-02-22*
*Carried from v1.0 known gaps (see `.planning/milestones/v1.0-REQUIREMENTS.md`)*
