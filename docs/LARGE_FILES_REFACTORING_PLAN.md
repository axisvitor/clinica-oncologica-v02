# Large Files Refactoring Plan

**Status:** 🟡 **PLANNING** - Ready for Sprint 2-6 Execution
**Last Updated:** November 7, 2025
**Target:** 37 modules from 30 large files
**Priority:** Medium (Code Quality & Maintainability)

---

## 📊 Executive Summary

This document outlines a comprehensive refactoring plan for large files (>1000 lines) in the Hormonia Backend System. Large files contribute to technical debt, reduce maintainability, and make testing more difficult. This plan breaks down each large file into smaller, focused modules following single responsibility principle.

### Current State

- **30 files >1000 lines** (57,489 total lines)
- **Largest file:** 1,767 lines (`flow_orchestrator.py`)
- **Average large file:** 1,916 lines
- **Total refactoring target:** 57,489 lines → 37 modules

### Target State

- **Maximum file size:** 500 lines
- **Average module size:** 250-350 lines
- **Total modules:** 37 new focused modules
- **Estimated reduction:** 30-40% code through deduplication

---

## 🎯 Large Files Inventory

### Critical Priority (>1500 lines) - 6 files

| File | Lines | Module | Complexity | Refactoring Estimate |
|------|-------|--------|------------|---------------------|
| `/app/services/orchestrators/flow_orchestrator.py` | 1,767 | Flow orchestration | Very High | 3-4 weeks |
| `/app/api/v2/messages.py` | 1,706 | Message API | High | 2 weeks |
| `/app/services/monthly_quiz_service.py` | 1,555 | Quiz service | High | 2-3 weeks |
| `/app/api/v2/flows.py` | 1,543 | Flow API | High | 2 weeks |
| `/app/services/flow.py` | 1,524 | Flow core | Very High | 3 weeks |
| `/app/services/analytics.py` | 1,461 | Analytics | Medium | 2 weeks |

**Total:** 9,556 lines → 18 modules

### High Priority (1200-1500 lines) - 9 files

| File | Lines | Module | Complexity | Refactoring Estimate |
|------|-------|--------|------------|---------------------|
| `/app/agents/communication/quiz_conductor.py` | 1,459 | Quiz agent | High | 2 weeks |
| `/app/services/flow_error_handler.py` | 1,444 | Error handling | Medium | 1-2 weeks |
| `/app/utils/unified_cache.py` | 1,430 | Caching | Medium | 1-2 weeks |
| `/app/services/flow_engine.py` | 1,367 | Flow engine | Very High | 3 weeks |
| `/app/coordination/saga_orchestrator.py` | 1,293 | Saga patterns | High | 2-3 weeks |
| `/app/services/quiz_flow_integration.py` | 1,261 | Quiz-flow integration | High | 2 weeks |
| `/app/services/webhook_processor.py` | 1,233 | Webhook processing | Medium | 1-2 weeks |
| `/app/api/v1/flows.py` | 1,201 | V1 Flow API | Medium | 1 week (deprecating) |
| `/app/services/follow_up_system.py` | 1,188 | Follow-up logic | Medium | 1-2 weeks |

**Total:** 12,076 lines → 12 modules

### Medium Priority (1000-1200 lines) - 15 files

| File | Lines | Module | Complexity | Refactoring Estimate |
|------|-------|--------|------------|---------------------|
| `/app/api/v2/patients.py` | 1,184 | Patient API | Low | 1 week (already good) |
| `/app/api/v1/admin/users.py` | 1,179 | Admin users | Medium | 1 week |
| `/app/api/v1/quiz.py` | 1,173 | V1 Quiz API | Medium | 1 week (deprecating) |
| `/app/core/redis_manager.py` | 1,160 | Redis management | Medium | 1-2 weeks |
| `/app/api/v1/ai.py` | 1,134 | AI integration | High | 2 weeks |
| `/app/services/admin_user_service.py` | 1,132 | Admin service | Medium | 1 week |
| `/app/services/data_extraction.py` | 1,131 | Data extraction | Medium | 1-2 weeks |
| `/app/services/response_processor.py` | 1,102 | Response processing | High | 2 weeks |
| `/app/services/message_scheduler.py` | 1,099 | Message scheduling | Medium | 1-2 weeks |
| `/app/agents/patient/flow_coordinator.py` | 1,089 | Flow coordinator | High | 2 weeks |
| `/app/services/ab_testing.py` | 1,086 | A/B testing | Medium | 1-2 weeks |
| `/app/api/v2/auth.py` | 1,072 | Auth API | Low | 1 week (already good) |
| `/app/agents/communication/response_processor.py` | 1,040 | Response agent | Medium | 1-2 weeks |
| `/app/services/quiz.py` | 1,032 | Quiz core | High | 2 weeks |

**Total:** 15,613 lines → 7+ modules

**Overall Total:** 30 files, 37,245 lines → 37+ modules

---

## 🏗️ Refactoring Strategy

### 1. Single Responsibility Principle

**Each module should have ONE clear purpose:**

❌ **Bad:** `flow_orchestrator.py` (1,767 lines)
- Flow state management
- Message sending
- Quiz scheduling
- Error handling
- Analytics collection
- Template rendering
- A/B testing
- Rule engine

✅ **Good:** Split into 8 focused modules
- `flow_state_manager.py` (200 lines) - State transitions only
- `flow_message_sender.py` (150 lines) - Message sending only
- `flow_quiz_scheduler.py` (180 lines) - Quiz scheduling only
- `flow_error_handler.py` (220 lines) - Error handling only
- `flow_analytics_collector.py` (150 lines) - Analytics only
- `flow_template_renderer.py` (180 lines) - Template rendering only
- `flow_ab_test_manager.py` (200 lines) - A/B testing only
- `flow_rule_engine.py` (220 lines) - Rule evaluation only

### 2. Layer-Based Organization

**Organize code into logical layers:**

```
app/
├── api/               # HTTP layer (thin controllers)
│   ├── v1/           # V1 endpoints (deprecating)
│   └── v2/           # V2 endpoints (keep lean)
│
├── services/         # Business logic layer
│   ├── core/         # Core domain services
│   ├── orchestration/ # Orchestration services
│   └── integration/  # External integrations
│
├── domain/           # Domain models & logic (NEW)
│   ├── flows/
│   ├── messages/
│   ├── quizzes/
│   └── patients/
│
├── repositories/     # Data access layer (NEW)
│   ├── flow_repository.py
│   ├── message_repository.py
│   └── ...
│
└── utils/            # Utilities (keep small)
    ├── cache/        # Caching utilities
    ├── validation/   # Validation utilities
    └── ...
```

### 3. Domain-Driven Design (DDD)

**Group related functionality by domain:**

**Flow Domain:**
```
app/domain/flows/
├── __init__.py
├── state_manager.py      (200 lines) - State transitions
├── template_manager.py   (180 lines) - Template handling
├── rule_engine.py        (220 lines) - Business rules
├── ab_test_manager.py    (200 lines) - A/B testing
└── analytics.py          (150 lines) - Flow analytics
```

**Message Domain:**
```
app/domain/messages/
├── __init__.py
├── sender.py             (150 lines) - Message sending
├── scheduler.py          (180 lines) - Scheduling
├── template_renderer.py  (150 lines) - Template rendering
├── conversation_manager.py (200 lines) - Conversation threading
└── delivery_tracker.py   (120 lines) - Delivery status
```

### 4. Extract Common Patterns

**Identify and extract repeated patterns:**

**Before:**
```python
# Repeated in 15+ files
def get_with_cache(key: str, fetch_fn, ttl: int):
    cached = redis.get(key)
    if cached:
        return cached
    data = fetch_fn()
    redis.set(key, data, ttl)
    return data
```

**After:**
```python
# app/utils/cache/decorators.py
from functools import wraps

def cached(key_pattern: str, ttl: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = key_pattern.format(*args, **kwargs)
            cached = await redis.get(key)
            if cached:
                return cached
            result = await func(*args, **kwargs)
            await redis.set(key, result, ttl)
            return result
        return wrapper
    return decorator

# Usage
@cached("analytics:overview:{user_id}", ttl=900)
async def get_analytics_overview(user_id: str):
    return compute_analytics(user_id)
```

---

## 📋 Detailed Refactoring Plans

### Priority 1: Flow Orchestrator (1,767 lines → 8 modules)

**File:** `/app/services/orchestrators/flow_orchestrator.py`

**Current Responsibilities (Too Many!):**
1. Flow state management (300 lines)
2. Message composition and sending (250 lines)
3. Quiz scheduling (200 lines)
4. Template rendering (180 lines)
5. Rule engine execution (220 lines)
6. A/B test management (200 lines)
7. Analytics collection (150 lines)
8. Error handling (220 lines)
9. Coordination logic (47 lines)

**Refactoring Plan:**

```
app/domain/flows/
├── __init__.py                        # Public API
├── orchestrator.py                    # Thin orchestrator (200 lines)
├── state/
│   ├── __init__.py
│   ├── state_manager.py              # State transitions (200 lines)
│   └── state_validator.py            # Validation rules (150 lines)
├── messaging/
│   ├── __init__.py
│   ├── message_composer.py           # Message creation (150 lines)
│   └── message_sender.py             # Sending logic (100 lines)
├── scheduling/
│   ├── __init__.py
│   ├── quiz_scheduler.py             # Quiz scheduling (180 lines)
│   └── follow_up_scheduler.py        # Follow-up scheduling (120 lines)
├── templates/
│   ├── __init__.py
│   ├── renderer.py                   # Template rendering (180 lines)
│   └── context_builder.py            # Context creation (100 lines)
├── rules/
│   ├── __init__.py
│   ├── engine.py                     # Rule execution (220 lines)
│   └── evaluator.py                  # Condition evaluation (150 lines)
├── ab_testing/
│   ├── __init__.py
│   ├── manager.py                    # A/B test management (200 lines)
│   └── variant_selector.py           # Variant selection (100 lines)
├── analytics/
│   ├── __init__.py
│   ├── collector.py                  # Event collection (150 lines)
│   └── metrics.py                    # Metric computation (100 lines)
└── error_handling/
    ├── __init__.py
    ├── handler.py                    # Error handling (220 lines)
    └── recovery.py                   # Recovery strategies (150 lines)
```

**Migration Steps:**
1. Week 1: Extract state management
2. Week 2: Extract messaging and scheduling
3. Week 3: Extract templates, rules, and A/B testing
4. Week 4: Extract analytics and error handling, update tests

**Backwards Compatibility:**
```python
# app/services/orchestrators/flow_orchestrator.py (DEPRECATED)
from app.domain.flows import FlowOrchestrator as NewOrchestrator

class FlowOrchestrator:
    """DEPRECATED: Use app.domain.flows.FlowOrchestrator instead."""

    def __init__(self):
        warnings.warn(
            "FlowOrchestrator is deprecated. Use app.domain.flows.FlowOrchestrator",
            DeprecationWarning
        )
        self._new_orchestrator = NewOrchestrator()

    def __getattr__(self, name):
        return getattr(self._new_orchestrator, name)
```

### Priority 2: Message API V2 (1,706 lines → 4 modules)

**File:** `/app/api/v2/messages.py`

**Current Structure:**
- 26 endpoints in one file
- Mixed concerns (CRUD, analytics, templates, conversations)
- Duplicate validation logic

**Refactoring Plan:**

```
app/api/v2/messages/
├── __init__.py                    # Router aggregation
├── core.py                        # Core CRUD (450 lines)
│   ├── list_messages
│   ├── get_message
│   ├── send_message
│   ├── cancel_message
│   └── retry_message
├── conversations.py               # Conversation management (400 lines)
│   ├── get_conversation
│   ├── list_conversations
│   ├── mark_read
│   ├── unread_count
│   └── search
├── analytics.py                   # Analytics endpoints (350 lines)
│   ├── message_statistics
│   ├── patient_stats
│   ├── delivery_rate
│   └── response_time
└── templates.py                   # Template management (500 lines)
    ├── list_templates
    ├── get_template
    ├── create_template
    ├── update_template
    └── delete_template
```

**Benefits:**
- ✅ Each file <500 lines
- ✅ Clear separation of concerns
- ✅ Easier to test
- ✅ Easier to understand
- ✅ Better code navigation

### Priority 3: Monthly Quiz Service (1,555 lines → 5 modules)

**File:** `/app/services/monthly_quiz_service.py`

**Current Responsibilities:**
1. Quiz session management (400 lines)
2. Question rendering (300 lines)
3. Answer validation (250 lines)
4. Score calculation (200 lines)
5. Progress tracking (200 lines)
6. Notification sending (205 lines)

**Refactoring Plan:**

```
app/domain/quizzes/
├── __init__.py
├── session_manager.py             # Session CRUD (350 lines)
├── question_manager.py            # Question rendering (300 lines)
├── answer_validator.py            # Answer validation (250 lines)
├── scoring_engine.py              # Score calculation (250 lines)
├── progress_tracker.py            # Progress tracking (200 lines)
└── notification_sender.py         # Notifications (200 lines)
```

### Priority 4: Flow API V2 (1,543 lines → 4 modules)

**File:** `/app/api/v2/flows.py`

**Refactoring Plan:**

```
app/api/v2/flows/
├── __init__.py                    # Router aggregation
├── state.py                       # Flow state operations (400 lines)
├── templates.py                   # Template management (400 lines)
├── analytics.py                   # Analytics & dashboard (450 lines)
└── ab_testing.py                  # A/B testing endpoints (300 lines)
```

### Priority 5: Flow Core Service (1,524 lines → 5 modules)

**File:** `/app/services/flow.py`

**Refactoring Plan:**

```
app/domain/flows/core/
├── __init__.py
├── engine.py                      # Core flow engine (350 lines)
├── state_machine.py               # State transitions (300 lines)
├── event_handler.py               # Event handling (300 lines)
├── scheduler.py                   # Flow scheduling (300 lines)
└── coordinator.py                 # Multi-flow coordination (270 lines)
```

### Priority 6: Analytics Service (1,461 lines → 4 modules)

**File:** `/app/services/analytics.py`

**Refactoring Plan:**

```
app/domain/analytics/
├── __init__.py
├── aggregator.py                  # Data aggregation (400 lines)
├── metrics_calculator.py          # Metric computation (400 lines)
├── report_generator.py            # Report generation (350 lines)
└── dashboard_builder.py           # Dashboard data (310 lines)
```

### Priority 7-15: Remaining High Priority Files

**Similar patterns for:**
- `quiz_conductor.py` → 4 modules
- `flow_error_handler.py` → 3 modules
- `unified_cache.py` → 4 modules
- `flow_engine.py` → 5 modules
- `saga_orchestrator.py` → 4 modules
- `quiz_flow_integration.py` → 3 modules
- `webhook_processor.py` → 3 modules
- `follow_up_system.py` → 3 modules

---

## 🔄 Backwards Compatibility Strategy

### 1. Deprecation Warnings

```python
# Old file (deprecated)
import warnings
from app.domain.flows import FlowOrchestrator as NewFlowOrchestrator

warnings.warn(
    "app.services.orchestrators.flow_orchestrator is deprecated. "
    "Use app.domain.flows.FlowOrchestrator instead.",
    DeprecationWarning,
    stacklevel=2
)

# Proxy to new implementation
FlowOrchestrator = NewFlowOrchestrator
```

### 2. Import Aliases

```python
# app/services/__init__.py
from app.domain.flows import FlowOrchestrator
from app.domain.messages import MessageSender
from app.domain.quizzes import QuizSessionManager

# Keep old imports working
__all__ = ['FlowOrchestrator', 'MessageSender', 'QuizSessionManager']
```

### 3. Gradual Migration

**Phase 1:** Create new modules alongside old (Weeks 1-8)
**Phase 2:** Add deprecation warnings (Week 9)
**Phase 3:** Migrate internal usage (Weeks 10-16)
**Phase 4:** Update documentation (Week 17)
**Phase 5:** Remove old files (Week 24 - Sprint 6)

### 4. Migration Checklist Per File

- [ ] Create new modular structure
- [ ] Migrate core functionality
- [ ] Add comprehensive tests (new modules)
- [ ] Add deprecation warnings (old file)
- [ ] Update internal imports
- [ ] Update documentation
- [ ] Run full test suite
- [ ] Monitor production for issues
- [ ] Remove old file (after 3-month deprecation)

---

## ⚠️ Risk Mitigation

### High Risks

**1. Breaking Changes**
- **Risk:** Imports break for existing code
- **Mitigation:**
  - Keep old files with proxy imports
  - Deprecation warnings for 3 months
  - Gradual migration path
  - Comprehensive testing
- **Status:** 🟢 Mitigated

**2. Test Coverage Gaps**
- **Risk:** New modules lack tests
- **Mitigation:**
  - Write tests BEFORE refactoring
  - Maintain >90% coverage
  - Test old and new implementations in parallel
- **Status:** 🟡 Monitoring

**3. Performance Regression**
- **Risk:** More imports = slower performance
- **Mitigation:**
  - Benchmark before/after
  - Use lazy imports where appropriate
  - Profile critical paths
- **Status:** 🟢 Mitigated

### Medium Risks

**4. Increased Complexity**
- **Risk:** More files = harder to navigate
- **Mitigation:**
  - Clear directory structure
  - Comprehensive documentation
  - IDE-friendly organization
- **Status:** 🟢 Mitigated

**5. Merge Conflicts**
- **Risk:** Refactoring conflicts with feature work
- **Mitigation:**
  - Coordinate with team
  - Feature freeze during major refactors
  - Use feature flags
- **Status:** 🟡 Monitoring

---

## 📅 Refactoring Timeline

### Sprint 2 (Weeks 5-8) - Foundation

**Focus:** Extract common patterns and utilities

**Tasks:**
- Extract caching utilities from `unified_cache.py` (1 week)
- Extract error handling patterns (1 week)
- Extract validation utilities (1 week)
- Create domain directory structure (1 week)

**Deliverables:**
- `app/utils/cache/` module (4 files, ~400 lines)
- `app/utils/errors/` module (3 files, ~300 lines)
- `app/utils/validation/` module (3 files, ~250 lines)
- `app/domain/` structure created

### Sprint 3 (Weeks 9-12) - Flow Domain

**Focus:** Refactor flow-related large files

**Tasks:**
- Refactor `flow_orchestrator.py` (2 weeks)
- Refactor `flow.py` (1 week)
- Refactor `flow_engine.py` (1 week)

**Deliverables:**
- `app/domain/flows/` complete (20+ modules)
- Old files deprecated with warnings
- 95% test coverage

### Sprint 4 (Weeks 13-16) - Message & Quiz Domains

**Focus:** Refactor message and quiz large files

**Tasks:**
- Refactor `messages.py` API (1 week)
- Refactor `monthly_quiz_service.py` (2 weeks)
- Refactor `quiz_conductor.py` (1 week)

**Deliverables:**
- `app/domain/messages/` complete (8 modules)
- `app/domain/quizzes/` complete (6 modules)
- `app/api/v2/messages/` split (4 files)

### Sprint 5 (Weeks 17-20) - Services & Agents

**Focus:** Refactor remaining services and agents

**Tasks:**
- Refactor `analytics.py` (1 week)
- Refactor `saga_orchestrator.py` (1 week)
- Refactor agent files (2 weeks)

**Deliverables:**
- `app/domain/analytics/` complete (4 modules)
- `app/domain/coordination/` complete (4 modules)
- `app/agents/` refactored

### Sprint 6 (Weeks 21-24) - Cleanup & V1 Deprecation

**Focus:** Remove deprecated files and finalize

**Tasks:**
- Remove old flow files (1 week)
- Migrate remaining V1 files (2 weeks)
- Final documentation update (1 week)

**Deliverables:**
- All large files refactored
- Old files removed
- Documentation complete
- 90%+ test coverage

---

## 📊 Success Criteria

### Code Quality Metrics

| Metric | Current | Target | Sprint 6 |
|--------|---------|--------|----------|
| **Max File Size** | 1,767 lines | 500 lines | <500 lines |
| **Avg File Size** | 1,916 lines | 300 lines | <350 lines |
| **Files >1000 lines** | 30 files | 0 files | 0 files |
| **Modules Created** | 0 | 37 | 37+ |
| **Code Duplication** | High | <5% | <5% |
| **Test Coverage** | ~40% | >90% | >90% |

### Maintainability Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| **Cyclomatic Complexity** | High | <10 | TBD |
| **Coupling** | High | Low | TBD |
| **Cohesion** | Low | High | TBD |
| **Technical Debt** | High | Low | 🟡 |

---

## 🛠️ Tools & Automation

### Static Analysis

```bash
# Measure file complexity
radon cc app/ -a -nb

# Detect code duplication
pylint app/ --disable=all --enable=duplicate-code

# Measure maintainability index
radon mi app/
```

### Refactoring Tools

```bash
# Automatic import updates
python scripts/update_imports.py --old app.services.flow --new app.domain.flows

# Move and update
python scripts/safe_move.py \
  --source app/services/orchestrators/flow_orchestrator.py \
  --dest app/domain/flows/orchestrator.py \
  --update-imports
```

### Testing

```bash
# Run tests for old and new implementations
pytest tests/ -k "flow_orchestrator or FlowOrchestrator" -v

# Coverage comparison
pytest tests/ --cov=app.services.orchestrators --cov=app.domain.flows \
  --cov-report=html
```

---

## 📚 Related Documents

- [V1 to V2 Migration Status](./V1_TO_V2_MIGRATION_STATUS.md)
- [Test Coverage Analysis](./TEST_COVERAGE_ANALYSIS.md)
- [V2 Migration Complete Report](./V2_MIGRATION_COMPLETE.md)

---

## 🔄 Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-11-07 | 1.0 | Initial refactoring plan | Claude Code |

---

**Document Status:** 🟢 Active
**Next Update:** Sprint 2 Start (Week 5)
**Maintained By:** Backend Team
**Review Frequency:** Monthly
