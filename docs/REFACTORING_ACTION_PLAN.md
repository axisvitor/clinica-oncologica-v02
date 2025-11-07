# PLANO DE AÇÃO - REFATORAÇÃO BACKEND
## Priorização por Impacto vs. Esforço

**Data:** 2025-11-07
**Status:** 🚀 PRONTO PARA EXECUÇÃO

---

## 🎯 MATRIZ DE PRIORIZAÇÃO

### QUADRANTE 1: ALTO IMPACTO + BAIXO ESFORÇO ⚡ (FAZER PRIMEIRO)

| # | Tarefa | Impacto | Esforço | Prazo |
|---|--------|---------|---------|-------|
| 1 | Remover código morto (analytics placeholder) | 🔥🔥 | 5 min | Hoje |
| 2 | Criar @handle_api_errors decorator | 🔥🔥🔥 | 4h | 1 dia |
| 3 | Add Gemini interpretation cache | 🔥🔥🔥 | 4h | 1 dia |
| 4 | Extrair PhoneNormalizerService | 🔥🔥 | 2h | 1 dia |
| 5 | Criar PaginationService | 🔥🔥 | 3h | 1 dia |
| 6 | Criar ValidationService | 🔥🔥🔥 | 6h | 2 dias |

**Total Semana 1:** 6 tasks, ~1,000 linhas organizadas + performance boost

---

### QUADRANTE 2: ALTO IMPACTO + ALTO ESFORÇO 🏗️ (PLANEJAR BEM)

| # | Tarefa | Impacto | Esforço | Prazo |
|---|--------|---------|---------|-------|
| 7 | Fix saga double-commit problem | 🔥🔥🔥🔥 | 1-2 dias | Semana 2 |
| 8 | Add follow_up_system DB persistence | 🔥🔥🔥🔥 | 8h | Semana 2 |
| 9 | Split quiz_extensions.py (2,431→600/file) | 🔥🔥🔥 | 4 dias | Semana 3-4 |
| 10 | Refactor webhook_processor (9→3 concerns) | 🔥🔥🔥🔥 | 6 dias | Semana 4-5 |
| 11 | Split templates.py (1,902→950/file) | 🔥🔥 | 3 dias | Semana 5 |
| 12 | Refactor patients.py + extract services | 🔥🔥🔥 | 3 dias | Semana 6 |

**Total Mês 1-2:** 6 tasks críticas, ~6,000 linhas reorganizadas

---

### QUADRANTE 3: BAIXO IMPACTO + BAIXO ESFORÇO 🔧 (FAZER QUANDO TIVER TEMPO)

| # | Tarefa | Impacto | Esforço | Prazo |
|---|--------|---------|---------|-------|
| 13 | Fix redis_manager thread pool deadlock | 🔥 | 2h | Semana 3 |
| 14 | Split enhanced_monitoring (3 arquivos) | 🔥 | 3 dias | Mês 2 |
| 15 | Refactor ab_testing analytics | 🔥 | 2 dias | Mês 2 |
| 16 | Add caching to flow_integration | 🔥🔥 | 4h | Mês 2 |

---

### QUADRANTE 4: BAIXO IMPACTO + ALTO ESFORÇO ⏸️ (ADIAR)

| # | Tarefa | Impacto | Esforço | Prazo |
|---|--------|---------|---------|-------|
| 17 | Deprecar V1 APIs completamente | 🔥 | 3-18 meses | Roadmap longo |
| 18 | Reestruturar todos os tests | 🔥 | 4 semanas | Q2 2025 |

---

## 📅 CRONOGRAMA SEMANAL DETALHADO

### SEMANA 1: Quick Wins ⚡
**Meta:** Resolver 80% dos problemas com 20% do esforço

#### Segunda-feira
- [ ] Task #1: Remover analytics placeholder (5 min)
- [ ] Task #2: Criar @handle_api_errors decorator (4h)
- [ ] **Code review:** Decorator
- [ ] **Deploy:** Staging

#### Terça-feira
- [ ] Task #3: Add Gemini cache (4h)
- [ ] Task #4: Extrair PhoneNormalizerService (2h)
- [ ] **Testes unitários:** PhoneNormalizer
- [ ] **Code review**

#### Quarta-feira
- [ ] Task #5: Criar PaginationService (3h)
- [ ] **Aplicar** PaginationService em 3 APIs
- [ ] **Testes de integração**

#### Quinta-feira
- [ ] Task #6: Criar ValidationService (6h)
- [ ] **Testes unitários**
- [ ] **Code review**

#### Sexta-feira
- [ ] **Integração final** de todos os serviços
- [ ] **Deploy staging**
- [ ] **Smoke tests**
- [ ] **Retrospective**

**Entregáveis Semana 1:**
- ✅ 6 tasks completadas
- ✅ ~1,000 linhas organizadas
- ✅ 3 novos serviços reutilizáveis
- ✅ Performance boost (Gemini cache)

---

### SEMANA 2: Bugs Críticos 🔴

#### Segunda-feira
- [ ] Task #7: Fix saga double-commit (dia inteiro)
- [ ] **Análise:** Identificar todos os pontos de commit
- [ ] **Implementação:** Context managers
- [ ] **Testes:** Transaction rollback scenarios

#### Terça-feira
- [ ] Task #7 (continuação): Testes de saga
- [ ] **Code review detalhado**
- [ ] **QA:** Test em staging

#### Quarta-feira
- [ ] Task #8: Follow-up DB persistence (8h)
- [ ] **Criar migrations:** follow_up_actions, escalation_alerts, conversation_contexts
- [ ] **Criar repositories**

#### Quinta-feira
- [ ] Task #8 (continuação)
- [ ] **Implementar Redis cache** com TTL
- [ ] **Migração de dados** em memória → DB
- [ ] **Testes**

#### Sexta-feira
- [ ] **Deploy staging:** Saga fix + Follow-up persistence
- [ ] **Monitoring:** Verificar commits + DB persistence
- [ ] **Rollback plan** documentado
- [ ] **Go/No-go decision**

**Entregáveis Semana 2:**
- ✅ Saga atomicity garantida
- ✅ Follow-up system production-ready
- ✅ 0 data corruption risks

---

### SEMANA 3-4: Split quiz_extensions.py 📦

#### Planejamento
**Arquivo atual:** quiz_extensions.py (2,431 linhas, 27 endpoints)

**Estratégia:** Dividir por feature domain (4 sub-routers)

```
app/api/v2/quiz_extensions/
├── __init__.py (router aggregation)
├── responses.py (600 linhas, 8 endpoints)
│   ├── GET /quiz-responses/
│   ├── GET /quiz-responses/{id}
│   └── GET /quiz-responses/analytics
├── alerts.py (600 linhas, 7 endpoints)
│   ├── GET /quiz-alerts/
│   ├── GET /quiz-alerts/{id}
│   ├── POST /quiz-alerts/{id}/acknowledge
│   ├── GET /quiz-alerts/statistics
│   └── POST /alert-rules/
├── monthly_quiz.py (700 linhas, 9 endpoints)
│   ├── GET /monthly-quizzes/
│   ├── POST /monthly-quizzes/
│   ├── GET /monthly-quizzes/{id}
│   ├── PUT /monthly-quizzes/{id}
│   ├── DELETE /monthly-quizzes/{id}
│   ├── POST /monthly-quizzes/{id}/publish
│   ├── POST /monthly-quizzes/{id}/unpublish
│   ├── GET /monthly-quizzes/{id}/responses
│   └── GET /monthly-quizzes/{id}/statistics
└── public_quiz.py (500 linhas, 3 endpoints)
    ├── GET /public-quiz/current
    ├── POST /public-quiz/submit
    └── GET /public-quiz/results
```

#### Semana 3
- [ ] Criar estrutura de diretórios
- [ ] Mover responses.py (8 endpoints)
- [ ] Mover alerts.py (7 endpoints)
- [ ] Atualizar imports
- [ ] Testes de regressão

#### Semana 4
- [ ] Mover monthly_quiz.py (9 endpoints)
- [ ] Mover public_quiz.py (3 endpoints)
- [ ] Cleanup dependencies
- [ ] Integration tests
- [ ] Deploy staging

**Entregáveis Semana 3-4:**
- ✅ 2,431 linhas → 4 arquivos modulares
- ✅ Manutenibilidade 75% melhorada
- ✅ 0 breaking changes

---

### SEMANA 4-5: Refactor webhook_processor.py 🔧

#### Análise Atual
**Arquivo:** webhook_processor.py (1,233 linhas)
**Problemas:** 9 responsabilidades em uma classe

#### Estratégia de Extração

```
app/services/webhooks/
├── core/
│   ├── webhook_validator.py (150 linhas)
│   │   └── WebhookValidator (signature, payload validation)
│   ├── webhook_persistence.py (200 linhas)
│   │   └── WebhookPersistence (DB storage, audit trail)
│   └── idempotency_checker.py (100 linhas)
│       └── IdempotencyChecker (Redis + DB fallback)
├── services/
│   ├── phone_normalizer_service.py (80 linhas) ← JÁ FEITO
│   ├── patient_lookup_service.py (150 linhas)
│   │   └── PatientLookupService (6 lookup strategies)
│   └── security_monitor_service.py (120 linhas)
│       └── SecurityMonitorService (unauthorized access tracking)
└── webhook_processor.py (400 linhas)
    └── WebhookProcessor (orchestration only)
```

#### Semana 4
- [ ] Extrair WebhookValidator
- [ ] Extrair WebhookPersistence
- [ ] Extrair IdempotencyChecker
- [ ] Testes unitários (cada serviço)

#### Semana 5
- [ ] Extrair PatientLookupService
- [ ] Extrair SecurityMonitorService
- [ ] Refatorar WebhookProcessor (use extracted services)
- [ ] Integration tests
- [ ] Deploy staging

**Entregáveis Semana 4-5:**
- ✅ 1,233 → 400 linhas (67% redução)
- ✅ 6 serviços testáveis independentemente
- ✅ Código 100% mockable

---

### SEMANA 6: Refactor patients.py 👥

#### Análise Atual
**Arquivo:** patients.py (1,674 linhas)
**Problemas:** Validação + normalização inline

#### Estratégia
```
app/api/v2/patients/
├── routes.py (800 linhas) ← API endpoints only
├── schemas.py (200 linhas) ← Pydantic models
└── dependencies.py (100 linhas) ← Auth checks

app/services/patients/
├── patient_service.py (300 linhas) ← Business logic
├── patient_validator.py (150 linhas) ← CPF, email, phone validation
└── patient_normalizer.py (100 linhas) ← CPF/phone normalization
```

#### Cronograma
- [ ] **Dia 1-2:** Extrair PatientValidator
- [ ] **Dia 3:** Extrair PatientNormalizer
- [ ] **Dia 4:** Extrair PatientService
- [ ] **Dia 5:** Refatorar routes.py
- [ ] **Dia 6:** Integration tests + deploy

**Entregáveis:**
- ✅ 1,674 → 800 linhas (52% redução)
- ✅ Validação reutilizável
- ✅ Service layer completo

---

## 📊 DASHBOARD DE PROGRESSO

### Métricas de Acompanhamento

| Métrica | Baseline | Target Mês 1 | Target Mês 2 | Target Final |
|---------|----------|--------------|--------------|--------------|
| Arquivos >1000 linhas | 39 | 35 (-10%) | 25 (-36%) | 15 (-62%) |
| Total linhas backend | 55,000 | 53,500 | 50,000 | 45,000 |
| Duplicação código | 15% | 12% | 8% | <5% |
| Métodos >50 linhas | 18 | 14 | 8 | 5 |
| Cobertura testes (services) | 0% | 30% | 50% | 70% |
| Bugs críticos | 3 | 0 | 0 | 0 |

### Velocity Tracking

**Semana 1:** 6 tasks × 2h avg = 12h
**Semana 2:** 2 tasks × 8h avg = 16h
**Semana 3-4:** 1 task × 16h = 16h
**Semana 5-6:** 1 task × 16h = 16h

**Total Mês 1-2:** 60 horas de refatoração

### ROI por Fase

| Fase | Investimento | Linhas Refatoradas | ROI |
|------|--------------|-------------------|-----|
| Semana 1 | 12h | 1,000 | 83 linhas/hora |
| Semana 2 | 16h | 0 (bug fixes) | Qualidade |
| Semana 3-4 | 16h | 2,431 | 152 linhas/hora |
| Semana 5-6 | 16h | 1,233 | 77 linhas/hora |
| Semana 7 | 8h | 1,674 | 209 linhas/hora |

**Total:** 68h = **6,338 linhas** organizadas = **93 linhas/hora**

---

## ✅ DEFINITION OF DONE

### Para cada Task
- [ ] Código implementado e testado
- [ ] Testes unitários (>80% coverage)
- [ ] Testes de integração (casos críticos)
- [ ] Code review aprovado (2 approvals)
- [ ] Documentação atualizada
- [ ] Deploy em staging realizado
- [ ] Smoke tests passando
- [ ] Performance não degradada
- [ ] Zero breaking changes
- [ ] Rollback plan documentado

### Para cada Semana
- [ ] Todas as tasks completadas
- [ ] Retrospective realizada
- [ ] Métricas atualizadas
- [ ] Próxima semana planejada
- [ ] Stakeholders notificados

### Para cada Fase
- [ ] Objetivos de fase atingidos
- [ ] Deploy em produção realizado
- [ ] Monitoring em produção OK
- [ ] Team feedback coletado
- [ ] Lessons learned documentadas

---

## 🚨 RISK MITIGATION

### Riscos Identificados

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Breaking changes em APIs | MÉDIA | ALTO | Feature flags + versioning |
| Performance degradation | BAIXA | ALTO | Benchmarks antes/depois |
| Bugs em produção | MÉDIA | ALTO | Staged rollout + monitoring |
| Team bandwidth | ALTA | MÉDIO | Priorização rigorosa |
| Scope creep | ALTA | MÉDIO | Weekly checkpoints |

### Contingency Plans

**Se Task demora 2x o estimado:**
- Reduzir scope para MVP
- Pedir help de outro dev
- Postergar para próxima semana

**Se aparecem bugs em produção:**
- Rollback imediato
- Root cause analysis
- Fix + tests + redeploy

**Se performance degrada:**
- Profiling detalhado
- Identificar bottleneck
- Otimizar ou rollback

---

## 📞 COMUNICAÇÃO

### Daily Standup (10min)
- O que fiz ontem?
- O que farei hoje?
- Algum blocker?

### Weekly Review (30min)
- Tasks completadas
- Métricas atualizadas
- Próxima semana planejada

### Stakeholder Update (Sexta-feira)
- Progresso da semana
- Riscos identificados
- Próximos passos

---

## 🎯 SUCESSO =

### Após 1 Semana
✅ 6 quick wins implementados
✅ 1,000 linhas organizadas
✅ 3 serviços reutilizáveis criados

### Após 1 Mês
✅ 3 bugs críticos corrigidos
✅ 4,000 linhas reorganizadas
✅ 6 arquivos modulares criados

### Após 2 Meses
✅ 10 arquivos grandes refatorados
✅ 6,000 linhas reorganizadas
✅ Service layer completo
✅ 50% cobertura de testes

---

**Última atualização:** 2025-11-07
**Owner:** Tech Lead
**Status:** ✅ APROVADO E PRONTO PARA EXECUÇÃO
