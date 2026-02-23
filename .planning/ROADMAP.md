# Roadmap: Clinica Oncologica — Refinamento para Producao

## Milestones

- ✅ **v1.0 Foundations** — Phases 1-5 (shipped 2026-02-22)
- 📋 **v1.1 Architecture & Observability** — Phases 6-9 (planned)

## Phases

<details>
<summary>✅ v1.0 Foundations (Phases 1-5) — SHIPPED 2026-02-22</summary>

- [x] Phase 1: Security Hardening (3/3 plans) — completed 2026-02-22
- [x] Phase 2: LGPD Compliance (3/3 plans) — completed 2026-02-22
- [x] Phase 3: Operational Stability (3/3 plans) — completed 2026-02-22
- [x] Phase 4: AI Reliability (2/2 plans) — completed 2026-02-22
- [x] Phase 5: Flow Consolidation (2/2 plans) — completed 2026-02-22

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

### 📋 v1.1 Architecture & Observability (Phases 6-9)

- [x] **Phase 6: Async Hot Path Migration** - Migrar os tres hot paths de banco de dados para AsyncSession (completed 2026-02-23)
- [ ] **Phase 7: LGPD Key Rotation** - Implementar batch re-encryption para viabilizar rotaçao de chaves criptograficas
- [ ] **Phase 8: AI Rationalization** - Simplificar cinco grafos single-node e adicionar circuit breaker para Gemini
- [ ] **Phase 9: Observability** - Substituir metricas hardcoded por instrumentaçao real e corrigir WebSocket scaling

## Phase Details

### Phase 6: Async Hot Path Migration
**Goal**: Os tres hot paths de banco de dados de maior throughput usam AsyncSession — o webhook handler, quiz response processing e flow advancement nao bloqueiam o event loop
**Depends on**: Phase 5
**Requirements**: ASYNC-01, ASYNC-02, ASYNC-03, ASYNC-05
**Success Criteria** (what must be TRUE):
  1. `sequential_message_handler.py` usa AsyncSession em todas as 12 instancias anotadas com `TODO(async-migration)` — nenhum `Session` sincrono dentro de handlers async
  2. `flow_core.py` usa AsyncSession nas 7 instancias anotadas — avanço de flow nao bloqueia o event loop sob carga
  3. `enhanced_quiz_service.py` usa AsyncSession nas 8 instancias anotadas — processamento de respostas de quiz nao bloqueia o event loop
  4. O saga orchestrator (compensation + steps) usa AsyncSession — operaçoes de compensaçao de saga nao criam risco de corrupçao de dados por timeout
**Plans:** 4/4 plans complete

Plans:
- [ ] 06-01-PLAN.md -- Migrate sequential_message_handler.py to AsyncSession (12 instances, ASYNC-01)
- [ ] 06-02-PLAN.md -- Migrate flow_core.py to AsyncSession (7 instances, ASYNC-02)
- [ ] 06-03-PLAN.md -- Migrate enhanced_quiz_service.py to AsyncSession (8 instances, ASYNC-03)
- [ ] 06-04-PLAN.md -- Migrate saga orchestrator compensation + steps to AsyncSession (ASYNC-05)

### Phase 7: LGPD Key Rotation
**Goal**: E possivel realizar rotaçao de chaves criptograficas via Celery task sem perda de dados — batch re-encryption existe e e operacional
**Depends on**: Phase 5, Phase 6
**Requirements**: LGPD-04
**Success Criteria** (what must be TRUE):
  1. Uma Celery task de batch re-encryption existe e pode ser invocada com nova chave — ela processa registros em chunks sem timeout ou perda de dados
  2. A task pode ser interrompida e retomada sem corromper dados parcialmente re-encriptados — idempotencia verificada por teste
**Plans:** 1 plan

Plans:
- [ ] 07-01-PLAN.md -- Batch re-encryption Celery task with chunked processing, Redis idempotency, and tests (LGPD-04)

### Phase 8: AI Rationalization
**Goal**: Cinco grafos LangGraph single-node estao eliminados — o codigo AI e mais simples, e chamadas Gemini tem circuit breaker explicito
**Depends on**: Phase 4, Phase 5
**Requirements**: AI-03, AI-04
**Success Criteria** (what must be TRUE):
  1. Os grafos `humanization`, `sentiment`, `generation`, `question_variation` e `empathetic_follow_up` nao existem mais como StateGraph compilados — as chamadas Gemini correspondentes passam diretamente por `GeminiClient.generate_content()`
  2. Um circuit breaker envolve chamadas Gemini — quando Gemini retorna 5xx ou timeout repetidamente, o circuit breaker abre e `FeatureNotAvailableError` e levantado em vez de retry infinito
**Plans:** 2 plans

Plans:
- [ ] 08-01-PLAN.md -- Remove 5 single-node LangGraph graphs, migrate all callers to direct GeminiClient.generate_content() (AI-03)
- [ ] 08-02-PLAN.md -- Fix circuit breaker exception: raise FeatureNotAvailableError instead of GeminiAPIError on circuit open (AI-04)

### Phase 9: Observability
**Goal**: Metricas refletem o comportamento real do sistema, o endpoint de disponibilidade do medico retorna slots reais, e o WebSocket funciona em multiplas instancias
**Depends on**: Phase 5, Phase 6
**Requirements**: OBS-01, OBS-02, OBS-03
**Success Criteria** (what must be TRUE):
  1. `avg_task_duration_seconds` nao esta hardcoded como 2.5 — o valor reflete a media real das ultimas N execuçoes de tasks, calculada via rolling average no Redis
  2. `get_available_slots()` retorna slots reais baseados nos horarios configurados do medico — o endpoint nao retorna lista vazia silenciosamente
  3. O WebSocket dashboard funciona corretamente com duas instancias da aplicaçao rodando simultaneamente — eventos de uma instancia aparecem nos dashboards conectados a outra instancia via Redis pub/sub
**Plans**: TBD

Plans:
- [ ] 09-01: Instrumentar Celery task completion times com rolling average em Redis (OBS-01)
- [ ] 09-02: Implementar get_available_slots() com logica real de geraçao de slots (OBS-02)
- [ ] 09-03: Verificar e corrigir WebSocket scaling com Redis pub/sub para multi-instance (OBS-03)

## Progress

**Execution Order:**
Phases 6-9 continue from v1.0. Phase 8 can begin after Phase 5 (already done), independently of Phase 6-7.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Security Hardening | v1.0 | 3/3 | Complete | 2026-02-22 |
| 2. LGPD Compliance | v1.0 | 3/3 | Complete | 2026-02-22 |
| 3. Operational Stability | v1.0 | 3/3 | Complete | 2026-02-22 |
| 4. AI Reliability | v1.0 | 2/2 | Complete | 2026-02-22 |
| 5. Flow Consolidation | v1.0 | 2/2 | Complete | 2026-02-22 |
| 6. Async Hot Path Migration | 4/4 | Complete   | 2026-02-23 | - |
| 7. LGPD Key Rotation | v1.1 | 0/1 | Planned | - |
| 8. AI Rationalization | v1.1 | 0/2 | Not started | - |
| 9. Observability | v1.1 | 0/3 | Not started | - |

---
*Roadmap created: 2026-02-22*
*Last updated: 2026-02-22 after v1.0 milestone completion*
