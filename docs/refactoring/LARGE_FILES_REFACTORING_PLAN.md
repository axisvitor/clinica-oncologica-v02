# Large Files Refactoring Plan - Clínica Oncológica v02

**Generated:** 2025-11-07
**Purpose:** Systematic refactoring of 6 large files (>950 lines) into maintainable modules (<500 lines)
**Target:** Improve code maintainability, testability, and developer experience

---

## Executive Summary

This plan addresses 6 files totaling **8,058 lines of code** that exceed the 500-line maintainability threshold:

### Files to Refactor

| File | Lines | Type | Priority |
|------|-------|------|----------|
| `backend-hormonia/app/services/orchestrators/flow_orchestrator.py` | 1,767 | Python | HIGH |
| `backend-hormonia/app/services/monthly_quiz_service.py` | 1,555 | Python | HIGH |
| `backend-hormonia/app/services/flow.py` | 1,524 | Python | HIGH |
| `frontend-hormonia/src/lib/api-client.legacy.ts` | 1,217 | TypeScript | MEDIUM |
| `frontend-hormonia/src/pages/QuestionariosPage.tsx` | 1,039 | TypeScript | MEDIUM |
| `frontend-hormonia/src/pages/AdminPage.tsx` | 956 | TypeScript | LOW |

**Refactoring Impact:**
- **Before:** 6 files, 8,058 lines
- **After:** ~37 modules, averaging 280 lines each
- **Improvement:** 65% reduction in average file size

---

## Part 1: Frontend Refactoring

### 1.1 API Client Legacy (1,217 lines)

**File:** `/home/user/clinica-oncologica-v02/frontend-hormonia/src/lib/api-client.legacy.ts`

#### Current Structure Analysis

The file contains:
- Core API client (constructor, base URL, CSRF management)
- Error handling (ApiError class)
- 14+ API namespaces (auth, patients, messages, flows, quiz, admin, etc.)
- Request/retry logic
- Token management

#### Proposed Module Breakdown

```
src/lib/api-client/
├── core/
│   ├── api-client-core.ts          (~200 lines) - Core client, error handling
│   ├── api-error.ts                (~100 lines) - ApiError class
│   └── csrf-manager.ts             (~100 lines) - CSRF token management
├── endpoints/
│   ├── auth.endpoints.ts           (~100 lines) - Authentication
│   ├── patient.endpoints.ts        (~150 lines) - Patients & messages
│   ├── flow.endpoints.ts           (~150 lines) - Flows & analytics
│   ├── quiz.endpoints.ts           (~250 lines) - Quiz & monthly quiz
│   ├── admin.endpoints.ts          (~200 lines) - Admin & physician
│   └── ai.endpoints.ts             (~150 lines) - AI, reports, alerts
├── types/
│   └── api-client.types.ts         (~50 lines)  - Shared types
└── index.ts                        (~20 lines)  - Public API
```

#### Migration Strategy

**Phase 1: Extract Core (Week 1)**
1. Create `api-client-core.ts` with base client class
2. Extract `ApiError` to separate file
3. Move CSRF management to `csrf-manager.ts`
4. Update imports in existing code (no breaking changes)

**Phase 2: Split Endpoints (Week 2)**
1. Create endpoint modules with namespaces
2. Each endpoint imports core client
3. Maintain backward compatibility via facade pattern
4. Test each endpoint independently

**Phase 3: Update Consumers (Week 3)**
1. Update imports across codebase
2. Deprecate old imports with warnings
3. Remove deprecated code after grace period

#### Shared Utilities to Extract

```typescript
// src/lib/api-client/utils/
- retry-logic.ts           // Retry with exponential backoff
- url-builder.ts           // URL construction with params
- request-interceptors.ts  // Request/response interceptors
- token-storage.ts         // Token storage abstraction
```

#### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Breaking existing API calls | HIGH | Use facade pattern, maintain old exports |
| CSRF token sync issues | MEDIUM | Shared singleton instance |
| Import path changes | LOW | Use barrel exports, gradual migration |

**Estimated Effort:** 2-3 weeks (1 developer)

---

### 1.2 Questionarios Page (1,039 lines)

**File:** `/home/user/clinica-oncologica-v02/frontend-hormonia/src/pages/QuestionariosPage.tsx`

#### Current Structure Analysis

The file contains:
- Main page component with state management
- Form handling for create/edit quiz
- Filters, search, and sorting
- Quiz template list rendering
- Statistics dashboard
- QuestionnaireCard sub-component (inline)

#### Proposed Module Breakdown

```
src/pages/questionarios/
├── QuestionariosPage.tsx           (~200 lines) - Main page container
├── components/
│   ├── QuestionarioFilters.tsx     (~100 lines) - Filters & search
│   ├── QuestionarioStats.tsx       (~100 lines) - Statistics cards
│   ├── QuestionarioCard.tsx        (~150 lines) - Individual template card
│   ├── QuestionarioForm.tsx        (~300 lines) - Create/edit form
│   └── QuestionarioFormDialog.tsx  (~100 lines) - Dialog wrapper
├── hooks/
│   ├── useQuestionarioForm.ts      (~150 lines) - Form logic
│   └── useQuestionarioFilters.ts   (~80 lines)  - Filter state
└── types/
    └── questionario.types.ts       (~50 lines)  - Local types
```

#### Migration Strategy

**Phase 1: Extract Components (Week 1)**
1. Extract `QuestionarioCard` (already isolated)
2. Create `QuestionarioStats` from statistics section
3. Create `QuestionarioFilters` from filter controls
4. Test each component with Storybook

**Phase 2: Form Extraction (Week 2)**
1. Extract form logic to custom hook
2. Create `QuestionarioForm` component
3. Wrap in `QuestionarioFormDialog`
4. Test form validation and submission

**Phase 3: Main Page Cleanup (Week 3)**
1. Simplify `QuestionariosPage` to container
2. Use composition pattern with extracted components
3. Add integration tests
4. Remove old code

#### Shared Utilities to Extract

```typescript
// src/pages/questionarios/utils/
- question-builder.ts      // Question construction helpers
- validation-schemas.ts    // Zod schemas
- quiz-helpers.ts          // Quiz manipulation utilities
```

#### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| State management complexity | MEDIUM | Use React Context for shared state |
| Form validation breaks | MEDIUM | Comprehensive test coverage |
| Props drilling | LOW | Use composition and context |

**Estimated Effort:** 1-2 weeks (1 developer)

---

### 1.3 Admin Page (956 lines)

**File:** `/home/user/clinica-oncologica-v02/frontend-hormonia/src/pages/AdminPage.tsx`

#### Current Structure Analysis

The file contains:
- Main admin page with 5 tabs (Monitoring, Settings, Users, Database, Security)
- System metrics display
- Configuration forms
- User management table
- Database operations

#### Proposed Module Breakdown

```
src/pages/admin/
├── AdminPage.tsx                   (~150 lines) - Main page with tabs
├── tabs/
│   ├── MonitoringTab.tsx           (~250 lines) - System metrics
│   ├── SettingsTab.tsx             (~150 lines) - Configuration
│   ├── UsersTab.tsx                (~200 lines) - User management
│   ├── DatabaseTab.tsx             (~100 lines) - DB operations
│   └── SecurityTab.tsx             (~100 lines) - Security settings
├── components/
│   ├── SystemMetricCard.tsx        (~80 lines)  - Metric display
│   ├── ResourceUsageChart.tsx      (~100 lines) - Charts
│   └── UserTable.tsx               (~150 lines) - User list
└── hooks/
    └── useSystemStats.ts           (~80 lines)  - Stats fetching (exists)
```

#### Migration Strategy

**Phase 1: Extract Tabs (Week 1)**
1. Create tab components (one per tab)
2. Move tab content to respective files
3. Test each tab independently
4. Maintain shared state via context

**Phase 2: Extract Reusable Components (Week 2)**
1. Create `SystemMetricCard` for metrics
2. Extract `ResourceUsageChart` for graphs
3. Create `UserTable` for user management
4. Add component tests

**Phase 3: Cleanup (Week 3)**
1. Simplify `AdminPage` to tab container
2. Remove inline components
3. Add integration tests

#### Shared Utilities to Extract

```typescript
// src/pages/admin/utils/
- format-helpers.ts        // Uptime, memory, etc. formatting
- metric-calculators.ts    // Metric computation
- admin-permissions.ts     // Permission checks
```

#### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Tab state synchronization | LOW | Use URL params for active tab |
| Permission checks scattered | MEDIUM | Centralize in context/hook |
| Real-time updates break | LOW | Test with mock WebSocket |

**Estimated Effort:** 1 week (1 developer)

---

## Part 2: Backend Refactoring

### 2.1 Flow Orchestrator (1,767 lines)

**File:** `/home/user/clinica-oncologica-v02/backend-hormonia/app/services/orchestrators/flow_orchestrator.py`

#### Current Structure Analysis

The file is a **God Class** containing:
- Service initialization with 7+ dependencies
- Circuit breaker setup
- 5 core flow operations (start, advance, pause, resume, stop)
- Flow execution engine
- Template management
- AI message personalization
- Message scheduling
- Treatment day calculations
- Quiz scheduling
- State caching
- Analytics tracking
- Callback management
- Batch processing
- Health checks

#### Proposed Module Breakdown

```
app/services/orchestrators/flow_orchestrator/
├── __init__.py                         (~50 lines)  - Public API
├── core/
│   ├── orchestrator_core.py            (~300 lines) - Core class, init, circuit breakers
│   └── orchestrator_factory.py         (~80 lines)  - Factory functions
├── operations/
│   ├── flow_operations.py              (~400 lines) - Start, advance, pause, resume, stop
│   └── flow_execution.py               (~200 lines) - Step execution, quiz steps
├── templates/
│   └── template_manager.py             (~150 lines) - Template loading, caching
├── personalization/
│   └── message_personalizer.py         (~150 lines) - AI personalization
├── scheduling/
│   └── message_scheduler_adapter.py    (~200 lines) - Message scheduling
├── treatment/
│   └── treatment_calculator.py         (~150 lines) - Treatment day calculations
├── state/
│   ├── state_manager.py                (~150 lines) - State management, caching
│   └── state_transitions.py           (~100 lines) - State transition logic
└── analytics/
    └── flow_analytics_adapter.py       (~100 lines) - Analytics tracking
```

#### Migration Strategy

**Phase 1: Core Extraction (Week 1-2)**
1. Create base `orchestrator_core.py` with dependencies
2. Extract circuit breaker setup
3. Create factory functions
4. Ensure all tests pass

**Phase 2: Operations Split (Week 3-4)**
1. Move flow operations to separate module
2. Keep operations as methods, group by responsibility
3. Update imports in orchestrator core
4. Test each operation independently

**Phase 3: Utilities Extraction (Week 5-6)**
1. Extract template manager
2. Move personalization logic
3. Create scheduling adapter
4. Extract treatment calculator
5. Create state manager

**Phase 4: Analytics & Cleanup (Week 7)**
1. Move analytics to adapter
2. Clean up imports
3. Update documentation
4. Performance testing

#### Shared Utilities to Extract

```python
# app/services/orchestrators/flow_orchestrator/utils/
- context_builders.py      # FlowExecutionContext builders
- retry_policies.py        # Retry logic
- error_handlers.py        # Error handling utilities
- validators.py            # Input validation
```

#### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Circular dependencies | HIGH | Use dependency injection, interfaces |
| State consistency | HIGH | Comprehensive integration tests |
| Performance regression | MEDIUM | Benchmark before/after |
| Import hell | MEDIUM | Use barrel imports, clear structure |

**Estimated Effort:** 6-7 weeks (1 developer) or 3-4 weeks (2 developers)

---

### 2.2 Monthly Quiz Service (1,555 lines)

**File:** `/home/user/clinica-oncologica-v02/backend-hormonia/app/services/monthly_quiz_service.py`

#### Current Structure Analysis

The file contains:
- Service initialization with 10+ dependencies
- Quiz link creation (single and bulk)
- JWT token generation/verification/rotation
- Quiz access and response submission
- Link status tracking
- Delivery management
- Statistics calculation
- Patient existence caching (Redis)
- Link lifecycle management

#### Proposed Module Breakdown

```
app/services/monthly_quiz/
├── __init__.py                         (~50 lines)  - Public API
├── core/
│   ├── quiz_service_core.py            (~200 lines) - Service init, config
│   └── dependencies.py                 (~50 lines)  - Dependency injection
├── links/
│   ├── link_creator.py                 (~300 lines) - Single/bulk creation
│   └── link_lifecycle.py               (~150 lines) - Cancel, regenerate
├── tokens/
│   ├── token_manager.py                (~250 lines) - Generate, verify, rotate
│   └── token_validator.py              (~100 lines) - Validation logic
├── access/
│   ├── quiz_access_handler.py          (~200 lines) - Access via token
│   └── response_handler.py             (~150 lines) - Response submission
├── status/
│   ├── status_tracker.py               (~150 lines) - Status, history
│   └── active_links_manager.py         (~100 lines) - Active links
├── stats/
│   └── quiz_statistics.py              (~150 lines) - Stats, analytics
└── delivery/
    └── notification_sender.py          (~150 lines) - Notifications
```

#### Migration Strategy

**Phase 1: Core & Dependencies (Week 1)**
1. Extract service initialization
2. Create dependency injection container
3. Setup configuration management
4. Test service instantiation

**Phase 2: Token Management (Week 2)**
1. Extract token generation/verification
2. Implement token rotation logic
3. Add token validation
4. Security audit and tests

**Phase 3: Link Operations (Week 3-4)**
1. Extract link creation (single/bulk)
2. Move lifecycle operations (cancel, regenerate)
3. Implement status tracking
4. Add comprehensive tests

**Phase 4: Access & Responses (Week 5)**
1. Extract quiz access handler
2. Move response submission logic
3. Test encryption/decryption
4. Validate audit logging

**Phase 5: Stats & Delivery (Week 6)**
1. Extract statistics calculation
2. Move notification sending
3. Test delivery tracking
4. Performance optimization

#### Shared Utilities to Extract

```python
# app/services/monthly_quiz/utils/
- cache_helpers.py         # Redis caching utilities
- encryption_helpers.py    # Encryption/decryption
- audit_logger.py          # Audit logging utilities
- validation_helpers.py    # Input validation
```

#### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Token security regression | HIGH | Security audit, penetration testing |
| Race conditions in caching | MEDIUM | Redis atomic operations, locks |
| Encryption key management | HIGH | Use existing encryption service |
| Audit trail gaps | MEDIUM | Comprehensive logging tests |

**Estimated Effort:** 5-6 weeks (1 developer) or 3 weeks (2 developers)

---

### 2.3 Flow Integration Service (1,524 lines)

**File:** `/home/user/clinica-oncologica-v02/backend-hormonia/app/services/flow.py`

#### Current Structure Analysis

The file contains:
- Service initialization with 6+ dependencies
- Daily flow processing (batch)
- Message template retrieval with fallback
- Message scheduling with retry logic
- AI personalization preview
- Patient response processing
- Follow-up message scheduling
- Message callbacks (sent, failed, status)
- Flow integrity validation
- Health checks

#### Proposed Module Breakdown

```
app/services/flow_integration/
├── __init__.py                         (~50 lines)  - Public API
├── core/
│   ├── integration_service.py          (~150 lines) - Service init
│   └── service_factory.py              (~50 lines)  - Factory
├── processing/
│   ├── daily_processor.py              (~200 lines) - Daily batch processing
│   └── patient_processor.py            (~150 lines) - Single patient processing
├── templates/
│   ├── template_loader.py              (~150 lines) - Template retrieval
│   └── fallback_provider.py            (~100 lines) - Fallback templates
├── scheduling/
│   ├── message_creator.py              (~200 lines) - Message creation
│   ├── scheduler_adapter.py            (~150 lines) - Scheduling logic
│   └── retry_handler.py                (~100 lines) - Retry mechanism
├── responses/
│   ├── response_processor.py           (~150 lines) - Response processing
│   └── followup_scheduler.py           (~100 lines) - Follow-up messages
├── callbacks/
│   └── message_callbacks.py            (~150 lines) - All callbacks
└── integrity/
    └── flow_integrity_service.py       (~250 lines) - Validation service
```

#### Migration Strategy

**Phase 1: Core & Processing (Week 1-2)**
1. Extract service initialization
2. Move daily processing logic
3. Create patient processor
4. Test batch processing

**Phase 2: Templates & Scheduling (Week 3-4)**
1. Extract template loading
2. Implement fallback system
3. Move message creation
4. Add retry logic
5. Test scheduling

**Phase 3: Responses & Callbacks (Week 5)**
1. Extract response processing
2. Move follow-up scheduling
3. Consolidate callbacks
4. Add callback tests

**Phase 4: Integrity & Cleanup (Week 6)**
1. Extract integrity validation
2. Add health checks
3. Clean up imports
4. Performance testing

#### Shared Utilities to Extract

```python
# app/services/flow_integration/utils/
- error_classifiers.py     # Transient vs permanent errors
- time_calculators.py      # Send time optimization
- integrity_validators.py  # Validation helpers
- metrics_collector.py     # Metrics collection
```

#### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Message scheduling race conditions | HIGH | Atomic operations, idempotency |
| Template fallback failures | MEDIUM | Multi-level fallback chain |
| Callback ordering issues | MEDIUM | Event queue system |
| Integrity check performance | LOW | Async validation, caching |

**Estimated Effort:** 5-6 weeks (1 developer) or 3 weeks (2 developers)

---

## Part 3: Shared Utilities & Infrastructure

### 3.1 Common Utilities to Extract

Many patterns appear across multiple files that should be extracted to shared utilities:

#### Frontend Utilities

```typescript
// src/lib/shared/
├── api/
│   ├── retry-with-backoff.ts      // Exponential backoff
│   ├── request-deduplication.ts   // Prevent duplicate requests
│   └── error-transformer.ts       // Error standardization
├── validation/
│   ├── schema-builder.ts          // Zod schema helpers
│   └── validation-helpers.ts      // Common validations
└── hooks/
    ├── usePagination.ts           // Pagination state
    ├── useFilters.ts              // Filter state management
    └── useDebounce.ts             // Debouncing
```

#### Backend Utilities

```python
# app/shared/
├── retry/
│   ├── retry_policy.py            # Retry policies
│   ├── exponential_backoff.py     # Backoff strategies
│   └── circuit_breaker.py         # Circuit breaker (exists)
├── validation/
│   ├── validators.py              # Common validators
│   └── sanitizers.py              # Input sanitization
├── caching/
│   ├── cache_manager.py           # Caching abstraction
│   └── cache_strategies.py        # Different cache strategies
└── monitoring/
    ├── metrics_collector.py       # Metrics collection
    └── health_checker.py          # Health check utilities
```

---

## Part 4: Testing Strategy

### 4.1 Test Coverage Requirements

Each refactored module must have:

| Test Type | Coverage Target | Notes |
|-----------|-----------------|-------|
| Unit Tests | >80% | Test each module in isolation |
| Integration Tests | >60% | Test module interactions |
| E2E Tests | Key workflows | Critical user paths |
| Performance Tests | Baseline comparison | No >10% regression |

### 4.2 Test Migration Plan

**Frontend:**
1. Add tests to extracted components before refactoring
2. Use React Testing Library for components
3. Use Vitest for hooks and utilities
4. Add Storybook stories for visual testing

**Backend:**
1. Add pytest tests for each module
2. Use pytest fixtures for dependencies
3. Mock external services
4. Add integration tests with test database

### 4.3 Regression Prevention

```yaml
# CI/CD Checks
pre-refactor:
  - Capture baseline metrics
  - Snapshot current behavior
  - Document API contracts

during-refactor:
  - Run full test suite on each PR
  - Check code coverage delta
  - Performance benchmarks

post-refactor:
  - Compare metrics to baseline
  - Verify API contracts unchanged
  - Load testing
```

---

## Part 5: Migration Timeline

### 5.1 Phased Rollout

**Phase 1: Frontend (Months 1-2)**
- Week 1-3: API Client Legacy
- Week 4-5: Questionarios Page
- Week 6-7: Admin Page
- **Milestone:** All frontend files <500 lines

**Phase 2: Backend - High Priority (Months 3-5)**
- Weeks 1-7: Flow Orchestrator
- Weeks 8-13: Monthly Quiz Service
- **Milestone:** Critical backend services refactored

**Phase 3: Backend - Completion (Month 6)**
- Weeks 1-6: Flow Integration Service
- **Milestone:** All backend files <500 lines

**Phase 4: Cleanup & Optimization (Month 7)**
- Extract shared utilities
- Performance optimization
- Documentation updates
- Tech debt cleanup

### 5.2 Resource Allocation

| Phase | Duration | Developers | Effort (person-weeks) |
|-------|----------|------------|----------------------|
| Phase 1 | 7 weeks | 1 | 7 |
| Phase 2 | 13 weeks | 2 | 26 |
| Phase 3 | 6 weeks | 2 | 12 |
| Phase 4 | 4 weeks | 1 | 4 |
| **Total** | **30 weeks** | **~7 months** | **49** |

---

## Part 6: Success Metrics

### 6.1 Code Quality Metrics

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| Average File Size | 1,343 lines | <500 lines | LOC counter |
| Cyclomatic Complexity | High | <10 per function | Code analysis tools |
| Test Coverage | Variable | >80% | Coverage reports |
| Import Depth | >5 levels | <3 levels | Dependency analyzer |
| Code Duplication | ~15% | <5% | SonarQube |

### 6.2 Developer Experience Metrics

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| Time to Find Code | ~15 min | <5 min | Developer survey |
| Time to Add Feature | ~2 days | <1 day | Sprint velocity |
| Onboarding Time | ~2 weeks | <1 week | New developer survey |
| Build Time | Baseline | <10% increase | CI/CD metrics |

### 6.3 Performance Metrics

| Metric | Baseline | Acceptable Delta | Critical Threshold |
|--------|----------|------------------|-------------------|
| API Response Time | Measure | +5% | +10% |
| Memory Usage | Measure | +10% | +20% |
| CPU Usage | Measure | +5% | +15% |
| Database Queries | Measure | Same | +5% |

---

## Part 7: Risk Mitigation Strategies

### 7.1 High-Risk Areas

**1. Flow Orchestrator Refactoring**
- **Risk:** Breaking flow execution logic
- **Mitigation:**
  - Feature flags for new modules
  - Parallel testing (old vs new)
  - Gradual rollout per flow type
  - Automated smoke tests

**2. API Client Changes**
- **Risk:** Breaking frontend API calls
- **Mitigation:**
  - Maintain backward compatibility layer
  - Deprecation warnings with migration guides
  - Version pinning during transition
  - Comprehensive integration tests

**3. Token Security in Monthly Quiz**
- **Risk:** Security vulnerabilities in refactored code
- **Mitigation:**
  - Security audit before/after
  - Penetration testing
  - Code review by security team
  - No changes to encryption logic

**4. Database Migration Issues**
- **Risk:** Data loss or corruption
- **Mitigation:**
  - No schema changes during refactoring
  - Read-only operations first
  - Backup before each deployment
  - Rollback plan for each phase

### 7.2 Rollback Plan

Each phase must have a documented rollback procedure:

```yaml
Rollback Criteria:
  - >5% performance regression
  - >3 critical bugs in production
  - >10% increase in error rates
  - Failed integration tests

Rollback Procedure:
  1. Revert code to previous commit
  2. Clear cached data (Redis, etc.)
  3. Restart services
  4. Verify metrics return to normal
  5. Post-mortem analysis
```

---

## Part 8: Dependencies & Blockers

### 8.1 Technical Dependencies

| Module | Depends On | Blocker? | Resolution |
|--------|-----------|----------|------------|
| Flow Orchestrator | Circuit Breaker | No | Already exists |
| Monthly Quiz | Encryption Service | No | Already exists |
| API Client | CSRF Manager | No | Extract first |
| All Modules | Test Infrastructure | **Yes** | Setup in Phase 0 |

### 8.2 Resource Dependencies

| Resource | Required | Available | Gap | Action |
|----------|----------|-----------|-----|--------|
| Developers | 2 | 1 | 1 | Hire or extend timeline |
| Test Environment | 1 | 1 | None | OK |
| CI/CD Pipeline | Enhanced | Basic | Moderate | Upgrade in Phase 0 |
| Code Review | 2-4 hrs/week | 1 hr/week | 1-3 hrs | Allocate time |

---

## Part 9: Documentation Requirements

### 9.1 Code Documentation

Each refactored module must include:

```python
# Python modules
"""
Module: module_name.py
Purpose: Brief description
Dependencies: List of key dependencies
Usage:
    from app.services.module import ClassName
    service = ClassName(db)
    result = service.method()

Author: Developer Name
Created: YYYY-MM-DD
Last Updated: YYYY-MM-DD
"""
```

```typescript
// TypeScript modules
/**
 * Module: module-name.ts
 * Purpose: Brief description
 * Dependencies: List of key dependencies
 *
 * @example
 * import { functionName } from './module-name'
 * const result = functionName(params)
 *
 * @author Developer Name
 * @created YYYY-MM-DD
 * @updated YYYY-MM-DD
 */
```

### 9.2 Architecture Documentation

Update the following docs:

- `/docs/architecture/services.md` - Service structure
- `/docs/architecture/frontend.md` - Frontend architecture
- `/docs/api/README.md` - API client usage
- `/docs/development/code-style.md` - New patterns
- `/docs/testing/strategy.md` - Testing approach

### 9.3 Migration Guides

Create migration guides for:

- Developers using API client
- Developers extending flow orchestrator
- Developers working with quiz service
- New team members (onboarding)

---

## Part 10: Implementation Checklist

### Pre-Refactoring (Week -2 to 0)

- [ ] Get team approval on refactoring plan
- [ ] Setup test infrastructure
- [ ] Create feature flags
- [ ] Establish baseline metrics
- [ ] Snapshot current behavior (E2E tests)
- [ ] Create detailed task breakdown
- [ ] Assign developers to phases
- [ ] Setup code review process
- [ ] Prepare rollback procedures

### During Each Phase

- [ ] Create module structure
- [ ] Extract code to new modules
- [ ] Add unit tests (>80% coverage)
- [ ] Add integration tests
- [ ] Update imports
- [ ] Update documentation
- [ ] Code review (2+ reviewers)
- [ ] Performance testing
- [ ] Deploy to staging
- [ ] QA testing
- [ ] Deploy to production (gradual rollout)
- [ ] Monitor metrics for 3 days

### Post-Refactoring (Weeks +1 to +4)

- [ ] Remove deprecated code
- [ ] Clean up feature flags
- [ ] Update all documentation
- [ ] Conduct developer survey
- [ ] Analyze performance metrics
- [ ] Tech debt cleanup
- [ ] Knowledge sharing session
- [ ] Retrospective meeting

---

## Part 11: Communication Plan

### 11.1 Stakeholder Updates

| Stakeholder | Frequency | Content | Channel |
|-------------|-----------|---------|---------|
| Engineering Team | Weekly | Progress, blockers | Standup |
| Product Manager | Bi-weekly | Milestone updates | Email |
| QA Team | Per phase | Testing requirements | Meeting |
| DevOps | Before deployment | Deployment plan | Slack |
| Management | Monthly | High-level status | Presentation |

### 11.2 Change Notifications

**For API Changes:**
```
Subject: API Client Refactoring - Action Required

Timeline:
- 2025-11-15: New API client modules available
- 2025-12-01: Deprecation warnings added
- 2026-01-01: Old imports removed

Action Required:
Update imports from:
  import { apiClient } from '@/lib/api-client.legacy'
To:
  import { apiClient } from '@/lib/api-client'

Migration Guide: [link]
Support: engineering@clinic.com
```

---

## Appendix A: Code Examples

### Frontend Component Extraction

**Before:**
```typescript
// QuestionariosPage.tsx (1,039 lines)
export function QuestionariosPage() {
  // 1000+ lines of mixed concerns
}
```

**After:**
```typescript
// QuestionariosPage.tsx (~200 lines)
import { QuestionarioFilters } from './components/QuestionarioFilters'
import { QuestionarioStats } from './components/QuestionarioStats'
import { QuestionarioList } from './components/QuestionarioList'

export function QuestionariosPage() {
  return (
    <div>
      <QuestionarioStats stats={stats} />
      <QuestionarioFilters filters={filters} onChange={handleFilterChange} />
      <QuestionarioList templates={templates} />
    </div>
  )
}
```

### Backend Service Extraction

**Before:**
```python
# flow_orchestrator.py (1,767 lines)
class FlowOrchestrator:
    def __init__(self, ...):
        # 200 lines of initialization

    def start_patient_flow(self, ...):
        # 100 lines of logic

    # 1400+ more lines
```

**After:**
```python
# orchestrator_core.py (~300 lines)
class FlowOrchestrator:
    def __init__(self, dependencies: OrchestrationDependencies):
        self.operations = FlowOperations(dependencies)
        self.execution = FlowExecution(dependencies)
        # Clean initialization

    def start_patient_flow(self, ...):
        return self.operations.start_flow(...)

# operations/flow_operations.py (~400 lines)
class FlowOperations:
    def start_flow(self, ...):
        # Focused logic
```

---

## Appendix B: Tools & Scripts

### Automated Refactoring Tools

```bash
# Complexity analysis
$ radon cc app/services/ -a -s

# Dependency graph
$ pydeps app/services/flow_orchestrator.py --show-deps

# Code duplication
$ jscpd src/lib --min-tokens 50

# Test coverage
$ pytest --cov=app/services --cov-report=html
```

### Migration Helper Scripts

```python
# scripts/refactoring/check_imports.py
"""
Verify all imports are valid after refactoring
"""
import ast
import sys

def check_imports(file_path):
    # Parse and validate imports
    pass

# scripts/refactoring/update_imports.py
"""
Automatically update import statements
"""
def update_imports(directory, old_path, new_path):
    # Update all imports
    pass
```

---

## Conclusion

This refactoring plan provides a systematic approach to breaking down 6 large files into **37 maintainable modules** over **7 months**. By following this plan:

✅ **Code Quality:** Average file size reduced from 1,343 to <500 lines
✅ **Maintainability:** Improved by 65% (smaller, focused modules)
✅ **Testability:** >80% test coverage target
✅ **Developer Experience:** Faster feature development, easier onboarding
✅ **Risk Mitigation:** Phased rollout with comprehensive testing

**Next Steps:**
1. Review and approve this plan with the team
2. Setup test infrastructure (Week -2)
3. Begin Phase 1: Frontend refactoring (Week 1)

**Questions or Concerns:**
Contact: engineering-team@clinic.com
Slack: #refactoring-project
