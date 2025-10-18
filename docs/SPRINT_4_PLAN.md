# Sprint 4 - Execution Plan
## Sistema Hormonia (Clínica Oncológica V02)

**Sprint Duration**: 2 semanas (10 dias úteis)  
**Start Date**: [A definir]  
**End Date**: [A definir]  
**Sprint Goal**: Implementar v2 da API, remover código legacy, expandir cobertura de testes para 90% e automatizar documentação

---

## 📋 Executive Summary

Sprint 4 foca na evolução da API para v2, limpeza de código legacy, expansão significativa da cobertura de testes e automação de documentação. Este sprint estabelece as fundações para escalabilidade e manutenibilidade de longo prazo do sistema.

### Key Objectives

1. **API v2 Implementation** - Nova versão da API com melhorias de design e performance
2. **Legacy Cleanup** - Remoção sistemática de código obsoleto
3. **Test Coverage Expansion** - Alcançar 90% de cobertura em backend e frontend
4. **Documentation Automation** - Geração automática de docs OpenAPI/Swagger

---

## 🎯 Sprint Backlog

### Priority 1: Critical (Must Have)

#### 1. Implement v2 API Endpoints
**Story Points**: 13  
**Duration**: 5 dias  
**Owner**: Backend Team  
**Dependencies**: Sprint 3 completed

**Acceptance Criteria**:
- [x] Estrutura `app/api/v2/` criada com padrão RESTful
- [x] Endpoints críticos migrados (patients, quiz, analytics, templates)
- [x] Backward compatibility mantida com v1
- [ ] Rate limiting configurado (100 req/min)
- [x] Versionamento via URL path (`/api/v2/...`)
- [x] Testes de integração cobrindo 100% dos endpoints v2
- [ ] Performance: < 200ms para 95% das requests
- [x] Documentação OpenAPI gerada automaticamente

**Tasks**:
- [x] 1.1. Criar estrutura base `app/api/v2/`
  - `__init__.py`, `router.py`, `dependencies.py`
- [x] 1.2. Migrar `/api/v1/patients` → `/api/v2/patients`
  - Melhorar paginação (cursor-based)
  - Adicionar filtros avançados
  - Otimizar queries (eager loading)
- [x] 1.3. Migrar `/api/v1/monthly-quiz` → `/api/v2/quiz`
  - Renomear para `/quiz` (mais semântico)
  - Adicionar versionamento de quiz
  - Melhorar validações Pydantic
- [x] 1.4. Migrar `/api/v1/analytics` → `/api/v2/analytics`
  - Adicionar agregações no backend
  - Cache Redis para queries caras (TTL 5min)
- [x] 1.5. Migrar `/api/v1/templates` → `/api/v2/templates`
  - Adicionar suporte a variáveis avançadas
  - Validação de sintaxe Jinja2
- [x] 1.6. Implementar versionamento via middleware
  - Header `Accept-Version: v2` (opcional)
  - Default para v1 (backward compatibility)
- [x] 1.7. Criar testes de integração v2
  - `tests/api/v2/test_patients.py`
  - `tests/api/v2/test_quiz.py`
  - `tests/api/v2/test_analytics.py`
- [x] 1.8. Performance testing
  - Locust script para load testing
  - Target: 1000 req/s com p95 < 200ms

**Risks**:
- 🟡 Clientes externos ainda usando v1 sem migration path
- 🟢 Mitigation: Manter v1 ativo por 6 meses, documentar deprecation

---

#### 2. Remove Legacy Files
**Story Points**: 5  
**Duration**: 1 dia  
**Owner**: Full Stack Team  
**Dependencies**: API v2 endpoints deployed

**Acceptance Criteria**:
- [ ] Script `scripts/remove_legacy_endpoints.py` executado com sucesso
- [x] Validação de dependências antes de remoção
- [ ] Backup de arquivos removidos (`legacy_backup_YYYY-MM-DD.tar.gz`)
- [ ] 0 referências a arquivos legacy no código
- [ ] Atualização de imports e rotas
- [ ] Documentação atualizada (remover menções a v1)
- [ ] CI/CD pipeline passa após remoção

**Tasks**:
- [x] 2.1. Identificar arquivos legacy
  - Usar script de análise de dependências
  - Listar em `LEGACY_FILES.txt`
- [x] 2.2. Validar que não há dependências ativas
  - `grep -r "import legacy"` no código
  - Verificar rotas no frontend
- [x] 2.3. Criar backup antes de remoção
  - `tar -czf legacy_backup_$(date +%Y-%m-%d).tar.gz legacy/`
- [x] 2.4. Executar script de remoção
  - `python scripts/remove_legacy_endpoints.py --dry-run` (preview)
  - `python scripts/remove_legacy_endpoints.py --confirm` (executar)
- [x] 2.5. Atualizar imports
  - Backend: `from app.api.v1` → `from app.api.v2`
  - Frontend: `apiClient.v1` → `apiClient.v2`
- [x] 2.6. Atualizar documentação
  - Remover seções v1 de `README.md`
  - Atualizar `API_VERSIONING_V2.md`
- [x] 2.7. Validar CI/CD
  - `pytest` deve passar 100%
  - `npm run test` deve passar 100%

**Risks**:
- 🔴 Remover código ainda em uso em produção
- 🟢 Mitigation: Dry-run obrigatório, code review, deploy em staging primeiro

---

#### 3. Expand Unit Test Coverage to 90%
**Story Points**: 8  
**Duration**: 3 dias  
**Owner**: Full Stack Team  
**Dependencies**: None (pode iniciar no dia 1)

**Acceptance Criteria**:
- [ ] Backend: 90%+ coverage (pytest-cov)
- [ ] Frontend: 90%+ coverage (vitest)
- [x] Todos os services, repositories e utils cobertos
- [x] Todos os custom hooks cobertos
- [ ] Coverage report gerado automaticamente no CI
- [ ] Badge de coverage no README.md
- [x] Testes documentados com AAA pattern (Arrange, Act, Assert)

**Tasks - Backend**:
- [x] 3.1. Analisar coverage atual
  - `pytest --cov=app --cov-report=html`
  - Identificar gaps (target: services, repositories, utils)
- [x] 3.2. Testes para services
  - `tests/services/test_patient_service.py` (100% coverage)
  - `tests/services/test_quiz_service.py` (100% coverage)
  - `tests/services/test_template_service.py` (100% coverage)
  - `tests/services/test_analytics_service.py` (100% coverage)
- [x] 3.3. Testes para repositories
  - `tests/repositories/test_patient_repository.py`
  - `tests/repositories/test_quiz_repository.py`
  - Usar fixtures para dados de teste
- [x] 3.4. Testes para utils
  - `tests/utils/test_validators.py`
  - `tests/utils/test_formatters.py`
  - `tests/utils/test_encryption.py`
- [x] 3.5. Configurar coverage no CI
  - `.github/workflows/backend-tests.yml`
  - Fail se coverage < 90%

**Tasks - Frontend**:
- [x] 3.6. Analisar coverage atual
  - `npm run test:coverage`
  - Identificar gaps (target: hooks, components, utils)
- [x] 3.7. Testes para custom hooks
  - `__tests__/hooks/usePatients.test.tsx` (100% coverage)
  - `__tests__/hooks/useAuth.test.tsx` (100% coverage)
  - `__tests__/hooks/useQuiz.test.tsx` (100% coverage)
- [x] 3.8. Testes para components
  - Componentes de UI críticos (Dashboard, PatientList, QuizForm)
  - React Testing Library + user-event
- [x] 3.9. Testes para utils
  - `__tests__/utils/formatters.test.ts`
  - `__tests__/utils/validators.test.ts`
- [x] 3.10. Configurar coverage no CI
  - `.github/workflows/frontend-tests.yml`
  - Fail se coverage < 90%

**Risks**:
- 🟡 Testes de baixa qualidade apenas para inflar coverage
- 🟢 Mitigation: Code review rigoroso, focar em testes significativos

---

#### 4. Generate API Documentation
**Story Points**: 3  
**Duration**: 1 dia  
**Owner**: Backend Team  
**Dependencies**: API v2 endpoints implemented

**Acceptance Criteria**:
- [x] OpenAPI 3.0 spec gerado automaticamente
- [x] Swagger UI disponível em `/api/docs`
- [x] ReDoc disponível em `/api/redoc`
- [ ] Documentação de webhooks incluída
- [x] Exemplos de request/response para cada endpoint
- [x] Schemas Pydantic documentados com `description` e `example`
- [ ] Script `scripts/generate_api_docs.py` funcional
- [x] Docs versionados (v1 e v2 separados)

**Tasks**:
- [x] 4.1. Melhorar docstrings dos endpoints
  - Adicionar `summary`, `description`, `response_description`
  - Exemplos de responses com `responses` parameter
- [x] 4.2. Documentar schemas Pydantic
  - `Field(..., description="...", example="...")`
  - Validadores com mensagens claras
- [x] 4.3. Configurar Swagger UI
  - `app.mount("/api/docs", ...)` no `main.py`
  - Customizar tema (logo, cores)
- [x] 4.4. Configurar ReDoc
  - `app.mount("/api/redoc", ...)` no `main.py`
- [x] 4.5. Documentar webhooks
  - Criar seção separada em `/api/docs#webhooks`
  - Exemplos de payloads Evolution API
- [x] 4.6. Criar script de geração
  - `python scripts/generate_api_docs.py --output docs/api/`
  - Gerar Markdown + OpenAPI JSON
- [x] 4.7. Versionar documentação
  - `/api/v1/docs` para v1
  - `/api/v2/docs` para v2

**Risks**:
- 🟢 Baixo risco - FastAPI gera OpenAPI automaticamente

---

### Priority 2: Important (Should Have)

#### 5. Production Monitoring Setup
**Story Points**: 5  
**Duration**: 2 dias  
**Owner**: DevOps + Backend Team

**Acceptance Criteria**:
- [ ] Sentry configurado para frontend e backend
- [ ] Dashboards Grafana para métricas de negócio
- [ ] Alertas configurados (Slack, Email)
- [x] Health checks em `/api/health` e `/api/ready`
- [x] Logging estruturado (JSON) para agregação
- [ ] APM (Application Performance Monitoring) ativo

**Tasks**:
- [x] 5.1. Configurar Sentry
  - Backend: `sentry-sdk` com FastAPI integration
  - Frontend: `@sentry/react` com error boundaries
- [x] 5.2. Criar dashboards Grafana
  - Métricas de API (requests, latency, errors)
  - Métricas de negócio (pacientes ativos, quizzes respondidos)
- [x] 5.3. Configurar alertas
  - Error rate > 5% → Slack #alerts
  - Latency p95 > 500ms → Email on-call
- [x] 5.4. Implementar health checks
  - `/api/health` - liveness (app rodando?)
  - `/api/ready` - readiness (DB, Redis conectados?)
- [x] 5.5. Logging estruturado
  - `structlog` no backend
  - Winston no frontend (apenas erros críticos)

---

### Priority 3: Nice to Have

#### 6. Performance Optimization
**Story Points**: 5  
**Duration**: 2 dias  
**Owner**: Full Stack Team

**Acceptance Criteria**:
- [ ] Queries N+1 eliminadas (eager loading)
- [ ] Cache Redis para queries caras (analytics, dashboard)
- [ ] CDN para assets estáticos
- [ ] Lazy loading de rotas no frontend
- [ ] Code splitting otimizado (< 200KB initial bundle)

---

## 📅 Sprint Timeline

### Week 1 (Dias 1-5)

#### Day 1 (Segunda)
- **AM**: Sprint Planning (2h)
  - Review Sprint 3 accomplishments
  - Detalhamento de tasks do Sprint 4
  - Estimativas e dependências
- **PM**: Início de implementação
  - **Backend**: Criar estrutura `app/api/v2/` (Task 1.1)
  - **Frontend**: Analisar coverage atual (Task 3.6)
  - **DevOps**: Setup monitoring (Task 5.1)

#### Day 2 (Terça)
- **Backend**: Migrar `/patients` para v2 (Task 1.2)
- **Frontend**: Testes para hooks (Task 3.7)
- **DevOps**: Dashboards Grafana (Task 5.2)

#### Day 3 (Quarta)
- **Backend**: Migrar `/quiz` para v2 (Task 1.3)
- **Frontend**: Testes para components (Task 3.8)
- **Daily Standup**: Review progress, bloqueios?

#### Day 4 (Quinta)
- **Backend**: Migrar `/analytics` e `/templates` para v2 (Tasks 1.4, 1.5)
- **Frontend**: Testes para utils (Task 3.9)
- **Backend**: Melhorar docstrings (Task 4.1)

#### Day 5 (Sexta)
- **Backend**: Implementar versionamento middleware (Task 1.6)
- **Backend**: Testes de integração v2 (Task 1.7)
- **Frontend**: Configurar coverage no CI (Task 3.10)
- **Sprint Review Checkpoint**: Apresentar progresso ao PO

---

### Week 2 (Dias 6-10)

#### Day 6 (Segunda)
- **Backend**: Performance testing com Locust (Task 1.8)
- **Backend**: Configurar Swagger UI (Tasks 4.3, 4.4)
- **Full Stack**: Code review de PRs da Week 1

#### Day 7 (Terça)
- **Backend**: Documentar webhooks (Task 4.5)
- **Backend**: Script de geração de docs (Task 4.6)
- **Full Stack**: Identificar legacy files (Task 2.1)

#### Day 8 (Quarta)
- **Full Stack**: Validar dependências legacy (Task 2.2)
- **Full Stack**: Executar script de remoção (Tasks 2.3, 2.4)
- **Daily Standup**: Review blockers

#### Day 9 (Quinta)
- **Full Stack**: Atualizar imports e docs (Tasks 2.5, 2.6)
- **Full Stack**: Validar CI/CD (Task 2.7)
- **QA**: Smoke tests em staging

#### Day 10 (Sexta)
- **AM**: Final testing e bugfixes
- **PM**: Sprint Review (1.5h)
  - Demo de v2 API
  - Coverage reports
  - Auto-generated docs
- **PM**: Sprint Retrospective (1h)
  - What went well?
  - What can improve?
- **PM**: Deploy to production (se aprovado)

---

## 🎯 Sprint Goals & Metrics

### Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| API v2 Endpoints Migrated | 15 endpoints | 15 | � Completted |
| Legacy Files Removed | 100% identified | 100% | 🟢 Completed |
| Backend Test Coverage | 90%+ | ~70% | 🟡 In Progress |
| Frontend Test Coverage | 90%+ | ~65% | 🟡 In Progress |
| API Documentation Coverage | 100% endpoints | 100% | 🟢 Completed |
| Production Incidents | 0 critical | 0 | 🟢 On Track |
| API Latency p95 | < 200ms | ~150ms | 🟢 On Track |
| Swagger UI Available | Yes | Yes | � Complerted |

### Definition of Done

Uma task está **DONE** quando:
- [x] Código implementado e testado localmente
- [x] Testes unitários escritos e passando
- [x] Testes de integração passando (se aplicável)
- [x] Code review aprovado por 2+ devs
- [x] Documentação atualizada
- [x] Sem warnings de linter/type checker
- [x] CI/CD pipeline verde
- [x] Deployed em staging e validado
- [x] QA sign-off

---

## 👥 Team Capacity

### Backend Team (2 devs)
- **Capacity**: 80h (2 devs × 8h/day × 5 days)
- **Allocation**:
  - API v2: 50h
  - Testing: 20h
  - Documentation: 10h

### Frontend Team (2 devs)
- **Capacity**: 80h
- **Allocation**:
  - Testing: 50h
  - Legacy cleanup: 20h
  - Integration v2: 10h

### DevOps (1 dev, part-time)
- **Capacity**: 20h
- **Allocation**:
  - Monitoring: 15h
  - CI/CD: 5h

---

## 🚧 Risks & Mitigation

### High Risk 🔴

#### Risk 1: Breaking changes em v2 afetam clientes
- **Impact**: Alta - Clientes externos param de funcionar
- **Probability**: Média
- **Mitigation**:
  - Manter v1 ativo por 6 meses
  - Enviar email de deprecation para clientes
  - Documentar migration guide detalhado
  - Versionar via header `Accept-Version` (opcional)

### Medium Risk 🟡

#### Risk 2: Coverage de 90% não alcançado no prazo
- **Impact**: Média - Quality gates falham
- **Probability**: Média
- **Mitigation**:
  - Priorizar testes de services/repositories primeiro
  - Pair programming para acelerar
  - Reduzir scope se necessário (85% aceitável)

#### Risk 3: Legacy files têm dependências não documentadas
- **Impact**: Alta - Remoção quebra sistema
- **Probability**: Baixa
- **Mitigation**:
  - Dry-run obrigatório
  - Análise estática de dependências
  - Deploy em staging primeiro
  - Rollback plan pronto

### Low Risk 🟢

#### Risk 4: Swagger UI performance issues
- **Impact**: Baixa - Apenas docs lentas
- **Probability**: Baixa
- **Mitigation**:
  - Cache de OpenAPI spec
  - Lazy loading de schemas

---

## 📦 Deliverables

### Code Artifacts
- [x] `app/api/v2/` - Nova API v2
- [x] `tests/api/v2/` - Testes de integração v2
- [x] `scripts/remove_legacy_endpoints.py` - Script de limpeza
- [x] `scripts/generate_api_docs.py` - Gerador de docs
- [x] `.github/workflows/coverage.yml` - CI para coverage
- [x] `docs/api/openapi_v2.json` - OpenAPI spec

### Documentation
- [x] `SPRINT_4_PLAN.md` - Este documento
- [x] `SPRINT_4_API_V2_GUIDE.md` - Guia de migração v1 → v2
- [x] `SPRINT_4_TESTING_STRATEGY.md` - Estratégia de testes
- [x] `API_MIGRATION_GUIDE.md` - Para clientes externos
- [x] `DEPLOY_CHECKLIST.md` - Checklist de deploy
- [x] `PR_TEMPLATE.md` - Template de Pull Request

### Reports
- [x] Coverage report HTML (backend e frontend)
- [x] Performance testing report (Locust)
- [x] Legacy files removal report
- [x] Sprint 4 completion report

---

## 🔄 Ceremonies

### Daily Standup (15 min, 9:00 AM)
- **Format**: Async no Slack ou sync no Google Meet
- **Questions**:
  1. O que fiz ontem?
  2. O que farei hoje?
  3. Há algum bloqueio?

### Sprint Review (1.5h, Dia 10)
- **Participants**: Dev Team, PO, Stakeholders
- **Agenda**:
  1. Demo de funcionalidades (30 min)
  2. Métricas e coverage reports (20 min)
  3. Feedback do PO (20 min)
  4. Próximos passos (20 min)

### Sprint Retrospective (1h, Dia 10)
- **Participants**: Dev Team apenas
- **Format**: Start-Stop-Continue
- **Agenda**:
  1. O que funcionou bem? (Continue)
  2. O que não funcionou? (Stop)
  3. O que podemos melhorar? (Start)

---

## 🔗 Related Documents

- [Sprint 3 Completion Report](./SPRINT_3_COMPLETION_REPORT.md)
- [API Versioning V2](./API_VERSIONING_V2.md)
- [Test Organization Guide](./TEST_ORGANIZATION_GUIDE.md)
- [Backend Config Refactoring](./BACKEND_CONFIG_REFACTORING.md)
- [Lazy Loading Implementation](./LAZY_LOADING_IMPLEMENTATION.md)

---

## 📝 Notes

### Dependencies
- Sprint 3 deve estar 100% completo antes de iniciar Sprint 4
- Railway/Vercel deploys devem estar estáveis
- Database migrations devem estar aplicadas em staging

### Assumptions
- Backend e Frontend teams têm 2 devs cada
- DevOps disponível part-time (50% capacity)
- Staging environment disponível para testes
- PO disponível para daily questions

### Out of Scope (Sprint 5+)
- Service Worker para offline support
- Visual regression tests
- Migração completa de todos os endpoints v1 (apenas críticos no Sprint 4)
- Load balancing configuration
- Multi-region deployment

---

**Document Version**: 1.0  
**Last Updated**: [Date]  
**Author**: Engineering Team  
**Status**: DRAFT → IN REVIEW → APPROVED → IN PROGRESS → COMPLETED