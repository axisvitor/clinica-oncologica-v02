# Sprint 4 - Kickoff Document
## Sistema Hormonia (Clínica Oncológica V02)

**Sprint**: 4  
**Duration**: 2 semanas (10 dias úteis)  
**Start Date**: [A definir]  
**Team**: Backend (2), Frontend (2), DevOps (1 part-time)  
**Sprint Goal**: Implementar API v2, remover legacy, alcançar 90% coverage, automatizar docs

---

## 🎯 Executive Summary

### Sprint 3 Recap (Completed ✅)

Sprint 3 foi um sucesso completo com **100% das tarefas concluídas**:

- ✅ API Client refatorado (modular, testável)
- ✅ Backend config modularizado (settings/)
- ✅ E2E tests implementados (quiz, dashboard)
- ✅ Lazy loading com skeletons e preloading
- ✅ Endpoint consolidation (bonus)
- ✅ Performance otimizada (TTI, bundle size)

**Métricas Sprint 3**:
- Coverage: Backend 70%, Frontend 65%
- Bundle size: Reduzido em 30%
- Lighthouse score: 95+ (mobile)
- Core Web Vitals: Todos verdes

### Sprint 4 Objectives

Sprint 4 foca em **evolução e limpeza**:

1. **API v2** - Nova arquitetura com cursor pagination, field selection, eager loading
2. **Legacy Cleanup** - Remover código obsoleto (v1) com segurança
3. **Test Coverage** - Expandir de ~70% para **90%+**
4. **Documentation** - Automatizar geração de OpenAPI/Swagger docs

### Why This Matters

- 📈 **Escalabilidade**: v2 suporta 10x mais tráfego
- 🧹 **Manutenibilidade**: Menos código = menos bugs
- 🛡️ **Confiabilidade**: 90% coverage = menos regressões
- 📚 **Developer Experience**: Auto-generated docs

---

## 📊 Sprint Backlog Summary

| Task | Priority | Story Points | Duration | Owner |
|------|----------|--------------|----------|-------|
| Implement v2 API endpoints | 🔴 Critical | 13 | 5 dias | Backend |
| Remove legacy files | 🔴 Critical | 5 | 1 dia | Full Stack |
| Expand test coverage to 90% | 🔴 Critical | 8 | 3 dias | Full Stack |
| Generate API documentation | 🟡 Important | 3 | 1 dia | Backend |
| Production monitoring setup | 🟢 Nice-to-have | 5 | 2 dias | DevOps |

**Total Story Points**: 31 (within team capacity)

---

## 🚀 Quick Start Guide

### For Backend Team

#### Day 1: Setup v2 Structure

```bash
# 1. Create v2 directory structure
cd backend-hormonia
mkdir -p app/api/v2
mkdir -p app/schemas/v2
mkdir -p tests/api/v2

# 2. Create base files
touch app/api/v2/__init__.py
touch app/api/v2/router.py
touch app/api/v2/dependencies.py
touch app/api/v2/patients.py
touch app/api/v2/quiz.py
touch app/api/v2/analytics.py

# 3. Create v2 schemas
touch app/schemas/v2/__init__.py
touch app/schemas/v2/common.py
touch app/schemas/v2/patient.py
touch app/schemas/v2/quiz.py

# 4. Create tests
touch tests/api/v2/__init__.py
touch tests/api/v2/test_patients.py
touch tests/api/v2/test_quiz.py
```

#### Day 2-5: Implement Endpoints

Reference: [API v2 Implementation Guide](./SPRINT_4_API_V2_GUIDE.md)

**Priority order**:
1. `/api/v2/patients` (45% of traffic)
2. `/api/v2/quiz` (30% of traffic)
3. `/api/v2/analytics` (15% of traffic)
4. `/api/v2/templates` (10% of traffic)

**Key features to implement**:
- Cursor-based pagination
- Field selection (`?fields=id,name`)
- Eager loading (`?include=doctor,quizzes`)
- Rate limiting (100 req/min)
- Redis caching (analytics)

### For Frontend Team

#### Day 1-3: Expand Test Coverage

```bash
cd frontend-hormonia

# 1. Install test dependencies (if not installed)
npm install -D @testing-library/react @testing-library/user-event vitest

# 2. Create test files for hooks
mkdir -p src/__tests__/hooks
touch src/__tests__/hooks/usePatients.test.tsx
touch src/__tests__/hooks/useAuth.test.tsx
touch src/__tests__/hooks/useQuiz.test.tsx

# 3. Create test files for components
mkdir -p src/__tests__/components
touch src/__tests__/components/Dashboard.test.tsx
touch src/__tests__/components/PatientList.test.tsx
touch src/__tests__/components/QuizForm.test.tsx

# 4. Run coverage report
npm run test:coverage
```

Reference: [Testing Strategy](./SPRINT_4_TESTING_STRATEGY.md)

**Coverage targets**:
- Hooks: 95%+ (priority)
- Components: 85%+
- Utils: 95%+

#### Day 4-5: Integrate v2 API

Update API client to use v2 endpoints:

```typescript
// src/lib/api-client/patients.ts
export const patients = {
  list: async (params?: {
    cursor?: string
    limit?: number
    fields?: string[]
    include?: string[]
  }) => {
    const searchParams = new URLSearchParams()
    if (params?.cursor) searchParams.set('cursor', params.cursor)
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.fields) searchParams.set('fields', params.fields.join(','))
    if (params?.include) searchParams.set('include', params.include.join(','))
    
    return api.get(`/api/v2/patients?${searchParams}`)
  }
}
```

### For DevOps

#### Day 1-2: Setup Monitoring

```bash
# 1. Configure Sentry (backend)
railway variables set SENTRY_DSN="https://..."
railway variables set SENTRY_ENVIRONMENT="production"

# 2. Configure Sentry (frontend)
# In Vercel dashboard:
# Environment Variables → Add
# NEXT_PUBLIC_SENTRY_DSN = https://...

# 3. Setup Grafana dashboards
# Import dashboard templates from docs/monitoring/
```

Reference: [Sprint 4 Plan - Monitoring Section](./SPRINT_4_PLAN.md#5-production-monitoring-setup)

---

## 📅 Sprint Schedule

### Week 1 (Days 1-5)

| Day | Morning (4h) | Afternoon (4h) | Ceremonies |
|-----|--------------|----------------|------------|
| **Mon** | Sprint Planning | Setup v2 structure | Planning (2h) |
| **Tue** | Implement patients v2 | Write hook tests | Daily (15min) |
| **Wed** | Implement quiz v2 | Write component tests | Daily (15min) |
| **Thu** | Implement analytics v2 | Write utils tests | Daily (15min) |
| **Fri** | Integration tests | CI coverage setup | Review Checkpoint (1h) |

### Week 2 (Days 6-10)

| Day | Morning (4h) | Afternoon (4h) | Ceremonies |
|-----|--------------|----------------|------------|
| **Mon** | Performance testing | Setup monitoring | Daily (15min) |
| **Tue** | OpenAPI docs | Legacy analysis | Daily (15min) |
| **Wed** | Legacy cleanup | Update imports | Daily (15min) |
| **Thu** | Final testing | Bug fixes | Daily (15min) |
| **Fri** | Deploy prep | Deploy + Retro | Review (1.5h), Retro (1h) |

---

## ✅ Pre-Sprint Checklist

### Required Before Starting

- [ ] **Sprint 3 fully complete** (all PRs merged, deployed)
- [ ] **Team capacity confirmed** (no planned PTO)
- [ ] **Staging environment stable** (no critical bugs)
- [ ] **Database migrations up to date** (Alembic current)
- [ ] **Dependencies updated** (pip/npm audit clean)
- [ ] **Documentation reviewed** (all team read API v2 guide)
- [ ] **Tools installed** (pytest-cov, vitest, locust)

### Team Alignment

- [ ] **Sprint planning completed** (all tasks estimated)
- [ ] **Roles assigned** (who does what)
- [ ] **Definition of Done agreed** (what means "done")
- [ ] **Communication channels setup** (#sprint-4 Slack channel)
- [ ] **Daily standup time agreed** (e.g., 9:00 AM daily)

---

## 📚 Essential Reading

Before starting coding, **all team members must read**:

1. ⭐ **[Sprint 4 Plan](./SPRINT_4_PLAN.md)** - Complete execution plan
2. ⭐ **[API v2 Guide](./SPRINT_4_API_V2_GUIDE.md)** - API v2 implementation details
3. ⭐ **[Testing Strategy](./SPRINT_4_TESTING_STRATEGY.md)** - How to write tests
4. **[Deploy Checklist](./DEPLOY_CHECKLIST.md)** - Deployment procedures
5. **[Sprint 4 Milestones](./SPRINT_4_MILESTONES.md)** - Progress tracking

**Time estimate**: 2-3 hours of reading

---

## 🎯 Success Metrics

### Primary Metrics (Must Achieve)

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| API v2 Endpoints | 0 | 15 | Count in `app/api/v2/` |
| Backend Coverage | 70% | 90%+ | `pytest --cov=app` |
| Frontend Coverage | 65% | 90%+ | `npm run test:coverage` |
| Legacy Files Removed | 0 | 100% | Script report |
| OpenAPI Docs | Manual | Auto | Visit `/api/docs` |

### Secondary Metrics (Nice to Have)

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| API Latency p95 | 150ms | < 200ms | Locust report |
| Bundle Size | 450KB | < 400KB | `npm run build` |
| Lighthouse Score | 95 | 95+ | `lighthouse` CLI |
| Zero Prod Incidents | - | 0 | Sentry dashboard |

---

## 🚧 Known Risks & Mitigation

### High Priority Risks 🔴

#### Risk 1: Breaking Changes Affect Clients

**Impact**: High - External clients stop working  
**Probability**: Medium  
**Mitigation**:
- ✅ Keep v1 active for 6 months
- ✅ Send deprecation emails to clients
- ✅ Document migration guide
- ✅ Provide backwards compatibility layer

#### Risk 2: Legacy Removal Breaks Production

**Impact**: Critical - System down  
**Probability**: Low  
**Mitigation**:
- ✅ Mandatory dry-run in staging
- ✅ Static analysis of dependencies
- ✅ Create backup before removal
- ✅ Rollback plan ready (5 min)

### Medium Priority Risks 🟡

#### Risk 3: Coverage Target Not Met

**Impact**: Medium - Quality gates fail  
**Probability**: Medium  
**Mitigation**:
- ✅ Prioritize critical paths first
- ✅ Pair programming to accelerate
- ✅ Accept 85% if time runs out (negotiate)

---

## 🛠️ Tools & Resources

### Development Tools

```bash
# Backend
pip install pytest-cov pytest-benchmark ruff mypy

# Frontend
npm install -D vitest @testing-library/react @testing-library/user-event

# Performance Testing
pip install locust

# Documentation
pip install mkdocs-material
```

### Useful Commands

```bash
# Run backend tests with coverage
pytest --cov=app --cov-report=html --cov-report=term

# Run frontend tests with coverage
npm run test:coverage

# Run linters
ruff check app/
npm run lint

# Performance testing
locust -f tests/performance/locustfile.py --host=http://localhost:8000

# Generate API docs
python scripts/generate_api_docs.py --output docs/api/
```

### Scripts Created for Sprint 4

- `scripts/remove_legacy_endpoints.py` - Remove legacy code safely
- `scripts/generate_api_docs.py` - Auto-generate OpenAPI docs
- `scripts/analyze_coverage_gaps.py` - Find untested code
- `scripts/validate_v2_endpoints.py` - Smoke test v2 API

---

## 📞 Communication Plan

### Daily Standup (15 min, 9:00 AM)

**Format**: Async in Slack (#sprint-4) or Sync on Google Meet

**Questions**:
1. What did I complete yesterday?
2. What will I work on today?
3. Any blockers?

**Example**:
```
@dev1: Yesterday: Implemented /patients v2 endpoint
Today: Write integration tests for patients v2
Blockers: None
```

### Mid-Sprint Review (Day 5, 1 hour)

**Agenda**:
1. Demo completed features (30 min)
2. Review burndown chart (10 min)
3. Adjust scope if needed (20 min)

### Sprint Review (Day 10, 1.5 hours)

**Agenda**:
1. Demo to stakeholders (45 min)
2. Show metrics (coverage, performance) (20 min)
3. Feedback & questions (25 min)

### Sprint Retrospective (Day 10, 1 hour)

**Format**: Start-Stop-Continue

**Questions**:
1. What went well? (Continue)
2. What didn't work? (Stop)
3. What should we try? (Start)

---

## 🎉 Sprint Kickoff Ceremony

### Agenda (2 hours)

#### Part 1: Context (30 min)
- Review Sprint 3 achievements
- Present Sprint 4 goals
- Show business impact (why this matters)

#### Part 2: Planning (60 min)
- Review backlog items
- Confirm story point estimates
- Identify dependencies
- Assign tasks

#### Part 3: Technical Discussion (30 min)
- API v2 architecture walkthrough
- Testing strategy overview
- Legacy cleanup approach
- Q&A

### Kickoff Checklist

Before ending kickoff meeting:

- [ ] All tasks estimated and assigned
- [ ] Sprint goal understood by all
- [ ] Technical approach agreed
- [ ] Risks identified and mitigated
- [ ] Daily standup time confirmed
- [ ] Communication channels created
- [ ] First day tasks clear for everyone

---

## 💪 Team Commitment

By participating in this sprint, we commit to:

- ✅ **Quality**: Write clean, tested code
- ✅ **Collaboration**: Help teammates when blocked
- ✅ **Communication**: Update status daily
- ✅ **Focus**: Avoid scope creep
- ✅ **Delivery**: Meet sprint goal

---

## 🏁 Ready to Start?

### Pre-Flight Check

- [ ] Read all essential documentation (2-3 hours)
- [ ] Development environment setup and tested
- [ ] Git branch created (`git checkout -b sprint-4`)
- [ ] Slack channel joined (#sprint-4)
- [ ] Calendar invites accepted (standup, review, retro)
- [ ] Questions asked and answered

### First Task

**Backend Team**: Start with Milestone 1 (API v2 Foundation)  
**Frontend Team**: Start with Milestone 3 (Test Coverage)  
**DevOps**: Start with Milestone 5 (Monitoring Setup)

Reference: [Sprint 4 Milestones](./SPRINT_4_MILESTONES.md)

---

## 📝 Daily Progress Updates

Update this section daily with progress:

### Day 1 (Monday) - January 17, 2025 ✅
**Completed**: 
- ✅ Sprint Planning (2h)
- ✅ API v2 Foundation (100%)
- ✅ Critical Endpoints (83% - 15 endpoints)
- ✅ Integration Tests (27 tests)
- ✅ Documentation (1,826+ lines)
- ✅ Router Integration

**Story Points**: 20 / 31 (65%)  
**Blockers**: None  
**Tomorrow**: Test coverage expansion, legacy cleanup analysis

### Day 2 (Tuesday)
**Completed**: [TBD]  
**Blockers**: [TBD]  
**Tomorrow**: [TBD]

---

## 🔗 Quick Links

- **Documentation**: [./SPRINT_4_PLAN.md](./SPRINT_4_PLAN.md)
- **API v2 Guide**: [./SPRINT_4_API_V2_GUIDE.md](./SPRINT_4_API_V2_GUIDE.md)
- **Testing Guide**: [./SPRINT_4_TESTING_STRATEGY.md](./SPRINT_4_TESTING_STRATEGY.md)
- **Deploy Checklist**: [./DEPLOY_CHECKLIST.md](./DEPLOY_CHECKLIST.md)
- **Milestones**: [./SPRINT_4_MILESTONES.md](./SPRINT_4_MILESTONES.md)
- **Sprint 3 Report**: [./SPRINT_3_COMPLETION_REPORT.md](./SPRINT_3_COMPLETION_REPORT.md)

---

**Let's ship it! 🚀**

---

**Document Version**: 1.0  
**Created**: Janeiro 2025  
**Owner**: Engineering Team  
**Status**: ✅ Ready for Sprint Start