# QW-021: Flow Services - Target Architecture Design

**Date**: 2025-01-21  
**Status**: 🎨 ARCHITECTURE DESIGN COMPLETE  
**Version**: 1.0  
**Risk Level**: 🔴 VERY HIGH (Core business logic redesign)

---

## 📊 Executive Summary

### Design Goals

This document defines the target architecture for consolidating 18 flow service files (~15,000 LOC) into a unified, maintainable module (~7,500 LOC after optimization).

**Primary Objectives**:
1. ✅ Eliminate 40% code duplication (~4,500-6,000 LOC)
2. ✅ Clear separation of concerns
3. ✅ 100% backward compatibility during migration
4. ✅ Zero-downtime deployment capability
5. ✅ Improved testability (95%+ coverage target)
6. ✅ Enhanced maintainability and extensibility

**Design Principles**:
- **SOLID Principles**: Single responsibility, Open/closed, Dependency inversion
- **Clean Architecture**: Domain logic isolated from infrastructure
- **Plugin Architecture**: Easy to extend with new integrations
- **Event-Driven**: Loose coupling via event system
- **Feature Flags**: Safe gradual migration

---

## 🏗️ Current State Problems

### Problem 1: Multiple Conflicting "Engines" 🔴

**Current State**:
```
flow_engine.py (1,359 LOC)
  - Old engine implementation
  - Uses state machine pattern
  - Unclear when to use

enhanced_flow_engine.py (450 LOC)
  - "Enhanced" version
  - Different API
  - Wrapper around flow_core?

flow_core.py (670 LOC)
  - Core flow logic
  - Template-based execution
  - Another engine?

flow_orchestrator.py (1,767 LOC)
  - Orchestrates everything
  - Also executes flows?
  - Too many responsibilities
```

**Problem**: Developers don't know which to use, leading to inconsistent usage.

---

### Problem 2: Tangled Dependencies 🔴

**Circular Dependencies Detected**:
```
flow.py → enhanced_flow_engine.py → flow_core.py → flow_template.py
   ↑                                                        ↓
   └────────────────────────────────────────────────────────┘
```

**Problem**: Hard to test, hard to modify, high coupling.

---

### Problem 3: Unclear Boundaries 🟡

**Responsibilities Mixed**:
- Orchestration + Execution mixed in same file
- Validation + Integrity checks scattered
- Quiz integration embedded, not pluggable
- Error handling duplicated across files

**Problem**: Hard to maintain, changes cascade.

---

### Problem 4: Code Duplication 🟡

**Identified Duplications**:
- 3 engine files: ~40% overlap (990 LOC)
- 3 validation files: ~35% overlap (650 LOC)
- 2 quiz integration files: ~60% overlap (980 LOC)
- Error handling: Repeated patterns

**Total Waste**: ~3,740 LOC duplicated code

---

## 🎯 Target Architecture

### High-Level Structure

```
app/services/flow/                          # New unified module
│
├── __init__.py                            # Public API + Factory
├── types.py                               # Types, enums, constants
├── config.py                              # Configuration management
├── exceptions.py                          # Flow-specific exceptions
│
├── core/                                  # Core domain logic
│   ├── __init__.py
│   ├── manager.py                         # FlowManager (orchestration)
│   ├── engine.py                          # FlowEngine (execution)
│   ├── state_machine.py                   # State transitions
│   ├── context.py                         # Execution context
│   └── lifecycle.py                       # Flow lifecycle management
│
├── execution/                             # Execution layer
│   ├── __init__.py
│   ├── executor.py                        # Step executor
│   ├── conditions.py                      # Conditional logic
│   ├── transitions.py                     # Transition handlers
│   └── scheduler.py                       # Flow scheduling
│
├── validation/                            # Validation layer
│   ├── __init__.py
│   ├── validator.py                       # Flow validation
│   ├── integrity.py                       # Data integrity
│   ├── rules.py                           # Validation rules
│   └── constraints.py                     # Business constraints
│
├── templates/                             # Template management
│   ├── __init__.py
│   ├── manager.py                         # Template manager
│   ├── loader.py                          # Template loader
│   ├── cache.py                           # Template cache
│   └── versioning.py                      # Version management
│
├── integrations/                          # External integrations
│   ├── __init__.py
│   ├── base.py                            # Integration interface
│   ├── quiz.py                            # Quiz integration
│   ├── ai.py                              # AI integration
│   ├── messaging.py                       # WhatsApp integration
│   └── analytics.py                       # Analytics integration
│
├── monitoring/                            # Monitoring & analytics
│   ├── __init__.py
│   ├── analytics.py                       # Flow analytics
│   ├── metrics.py                         # Performance metrics
│   ├── health.py                          # Health checks
│   └── dashboard.py                       # Dashboard data
│
└── errors/                                # Error handling
    ├── __init__.py
    ├── handler.py                         # Error handler
    ├── recovery.py                        # Recovery strategies
    ├── circuit_breaker.py                 # Circuit breaker
    └── retry.py                           # Retry logic
```

**File Count**: 18 files → 38 modules (but organized!)  
**LOC Target**: 15,000 → 7,500 (50% reduction after deduplication + refactoring)

---

## 📐 Core Components Design

### 1. FlowManager (Orchestrator)

**File**: `app/services/flow/core/manager.py`  
**Responsibility**: High-level flow orchestration and coordination  
**Target LOC**: ~800 lines

**API Design**:
```python
class FlowManager:
    """
    Main orchestrator for flow operations.
    
    Coordinates between engine, validator, integrations, and monitoring.
    Entry point for all flow operations.
    """
    
    def __init__(
        self,
        db: Session,
        engine: FlowEngine,
        validator: FlowValidator,
        integrations: List[FlowIntegration],
        monitor: FlowMonitor
    ):
        self.db = db
        self.engine = engine
        self.validator = validator
        self.integrations = integrations
        self.monitor = monitor
    
    async def start_flow(
        self,
        patient_id: UUID,
        flow_type: FlowType,
        metadata: Optional[Dict] = None
    ) -> FlowExecutionResult:
        """Start a new flow for a patient."""
        pass
    
    async def advance_flow(
        self,
        flow_id: UUID,
        steps: int = 1
    ) -> FlowExecutionResult:
        """Advance flow by N steps."""
        pass
    
    async def pause_flow(self, flow_id: UUID) -> FlowState:
        """Pause an active flow."""
        pass
    
    async def resume_flow(self, flow_id: UUID) -> FlowExecutionResult:
        """Resume a paused flow."""
        pass
    
    async def stop_flow(
        self,
        flow_id: UUID,
        reason: str
    ) -> FlowState:
        """Stop a flow (terminal state)."""
        pass
    
    async def get_flow_state(self, flow_id: UUID) -> FlowState:
        """Get current flow state."""
        pass
```

**Dependencies**:
- FlowEngine (execution)
- FlowValidator (validation)
- FlowIntegration[] (plugins)
- FlowMonitor (observability)

---

### 2. FlowEngine (Execution)

**File**: `app/services/flow/core/engine.py`  
**Responsibility**: Flow execution logic (state machine + step execution)  
**Target LOC**: ~600 lines

**API Design**:
```python
class FlowEngine:
    """
    Core flow execution engine.
    
    Handles state machine, step execution, transitions.
    Pure business logic, no I/O.
    """
    
    def __init__(
        self,
        state_machine: StateMachine,
        executor: StepExecutor,
        template_manager: TemplateManager
    ):
        self.state_machine = state_machine
        self.executor = executor
        self.templates = template_manager
    
    async def execute_step(
        self,
        flow_state: FlowState,
        context: ExecutionContext
    ) -> StepResult:
        """Execute a single flow step."""
        pass
    
    async def evaluate_conditions(
        self,
        step: FlowStep,
        context: ExecutionContext
    ) -> bool:
        """Evaluate step conditions."""
        pass
    
    async def transition_state(
        self,
        current: FlowState,
        event: FlowEvent
    ) -> FlowState:
        """Transition to next state."""
        pass
    
    def get_next_step(
        self,
        flow_state: FlowState
    ) -> Optional[FlowStep]:
        """Determine next step to execute."""
        pass
```

**Design Patterns**:
- State Machine Pattern (for state transitions)
- Strategy Pattern (for step execution)
- Template Method (for execution flow)

---

### 3. FlowValidator (Validation)

**File**: `app/services/flow/validation/validator.py`  
**Responsibility**: Unified validation logic  
**Target LOC**: ~400 lines

**API Design**:
```python
class FlowValidator:
    """
    Unified flow validation.
    
    Consolidates validation, integrity checks, business rules.
    """
    
    def __init__(
        self,
        integrity_checker: IntegrityChecker,
        rules: List[ValidationRule]
    ):
        self.integrity = integrity_checker
        self.rules = rules
    
    async def validate_start(
        self,
        patient_id: UUID,
        flow_type: FlowType
    ) -> ValidationResult:
        """Validate flow can be started."""
        pass
    
    async def validate_transition(
        self,
        flow_state: FlowState,
        target_state: FlowState
    ) -> ValidationResult:
        """Validate state transition is valid."""
        pass
    
    async def validate_data_integrity(
        self,
        flow_state: FlowState
    ) -> IntegrityResult:
        """Check data integrity."""
        pass
    
    async def validate_business_rules(
        self,
        flow_state: FlowState,
        operation: FlowOperation
    ) -> ValidationResult:
        """Validate business constraints."""
        pass
```

**Consolidates**:
- `flow_validation.py` (527 LOC)
- `flow_integrity.py` (474 LOC)
- `flow_data_integrity.py` (855 LOC)
- **Total**: 1,856 LOC → 400 LOC (78% reduction)

---

### 4. FlowIntegration (Plugin System)

**File**: `app/services/flow/integrations/base.py`  
**Responsibility**: Integration plugin interface  
**Target LOC**: ~200 lines

**API Design**:
```python
class FlowIntegration(ABC):
    """
    Base class for flow integrations.
    
    Enables plugin architecture for external systems.
    """
    
    @abstractmethod
    async def on_flow_start(
        self,
        flow_state: FlowState,
        context: ExecutionContext
    ) -> None:
        """Hook: Flow started."""
        pass
    
    @abstractmethod
    async def on_step_execute(
        self,
        step: FlowStep,
        context: ExecutionContext
    ) -> Optional[StepModification]:
        """Hook: Before step execution."""
        pass
    
    @abstractmethod
    async def on_step_complete(
        self,
        step: FlowStep,
        result: StepResult
    ) -> None:
        """Hook: After step completion."""
        pass
    
    @abstractmethod
    async def on_flow_complete(
        self,
        flow_state: FlowState
    ) -> None:
        """Hook: Flow completed."""
        pass
    
    @abstractmethod
    async def on_error(
        self,
        error: FlowError,
        context: ExecutionContext
    ) -> Optional[RecoveryAction]:
        """Hook: Error occurred."""
        pass


class QuizFlowIntegration(FlowIntegration):
    """Quiz integration plugin."""
    
    async def on_step_execute(self, step, context):
        if step.type == StepType.QUIZ:
            # Trigger quiz
            await self.quiz_service.trigger_quiz(...)
    
    async def on_step_complete(self, step, result):
        if step.type == StepType.QUIZ:
            # Process quiz completion
            await self.quiz_service.process_completion(...)
```

**Benefits**:
- Loose coupling (integrations are plugins)
- Easy to test (mock integrations)
- Easy to extend (add new integrations)
- Clear boundaries

**Consolidates**:
- `quiz_flow_integration.py` (1,261 LOC)
- `quiz_flow_integration_service.py` (371 LOC)
- **Total**: 1,632 LOC → 600 LOC (63% reduction)

---

## 🔄 Migration Strategy

### Phase 1: Internal Consolidation (Week 2)

**Goal**: Consolidate internal code, no external API changes

**Steps**:
1. Create new `app/services/flow/` module structure
2. Implement FlowManager (consolidate orchestration logic)
3. Implement FlowEngine (consolidate execution logic)
4. Implement FlowValidator (consolidate validation logic)
5. Implement plugin system (base + quiz integration)
6. Add comprehensive unit tests (95%+ coverage)

**Risk**: LOW - No external changes yet

---

### Phase 2: Backward Compatibility Layer (Week 3)

**Goal**: Create facades for old APIs

**Implementation**:
```python
# app/services/enhanced_flow_engine.py (legacy wrapper)
import warnings
from app.services.flow import get_flow_manager
from app.config.settings import Settings

settings = Settings()

def get_enhanced_flow_engine(db: Session):
    """
    Legacy function - DEPRECATED.
    
    Use app.services.flow.get_flow_manager() instead.
    """
    if settings.ALERTS_LEGACY_DEPRECATION_WARNING:
        warnings.warn(
            "get_enhanced_flow_engine is deprecated. "
            "Use app.services.flow.get_flow_manager() instead.",
            DeprecationWarning,
            stacklevel=2
        )
    
    return get_flow_manager(db)


class EnhancedFlowEngine:
    """Legacy wrapper - forwards to FlowManager."""
    
    def __init__(self, db: Session):
        warnings.warn("Use FlowManager instead", DeprecationWarning)
        self._manager = get_flow_manager(db)
    
    def start_flow(self, *args, **kwargs):
        return self._manager.start_flow(*args, **kwargs)
    
    # ... other methods forward to FlowManager
```

**Benefits**:
- Old imports still work
- Deprecation warnings guide developers
- Zero breaking changes

**Risk**: LOW - Maintains compatibility

---

### Phase 3: Feature Flag Implementation (Week 3)

**Goal**: Enable gradual rollout

**Configuration**:
```python
# app/config/settings/features.py

class FeaturesSettings(BaseAppSettings):
    """Feature flags."""
    
    USE_CONSOLIDATED_FLOWS: bool = Field(
        default=False,
        description="Use new consolidated flow system (QW-021)"
    )
    
    FLOWS_LEGACY_DEPRECATION_WARNING: bool = Field(
        default=True,
        description="Show deprecation warnings for legacy flow services"
    )
```

**Factory Pattern**:
```python
# app/services/flow/__init__.py

def get_flow_manager(db: Session) -> FlowManager:
    """
    Factory function for FlowManager.
    
    Returns consolidated system if feature flag enabled,
    otherwise returns legacy system wrapper.
    """
    from app.config.settings import Settings
    settings = Settings()
    
    if settings.USE_CONSOLIDATED_FLOWS:
        # New system
        from .core.manager import FlowManager
        from .core.engine import FlowEngine
        # ... initialize all components
        return FlowManager(db, ...)
    else:
        # Legacy system (backward compatible)
        from app.services.flow import FlowEngineIntegrationService
        # Wrap legacy in new interface
        return LegacyFlowManagerAdapter(
            FlowEngineIntegrationService(db)
        )
```

**Risk**: LOW - Feature flag provides safety net

---

### Phase 4: Update Consumers (Week 4)

**Goal**: Update all 56+ files to use new system

**Priority Order**:
1. **Critical Path** (Week 4 Days 1-2):
   - API endpoints (8 files) - 8 hours
   - Background tasks (6 files) - 6 hours
   
2. **High Priority** (Week 4 Days 3-4):
   - Service dependencies (15 files) - 12 hours
   - DI layer (5 files) - 4 hours
   
3. **Medium Priority** (Week 4 Day 5):
   - Agent system (4 files) - 4 hours
   - Monitoring services (5 files) - 4 hours

**Update Pattern**:
```python
# Before
from app.services.enhanced_flow_engine import get_enhanced_flow_engine

engine = get_enhanced_flow_engine(db)
result = engine.start_flow(patient_id, flow_type)

# After
from app.services.flow import get_flow_manager

manager = get_flow_manager(db)
result = await manager.start_flow(patient_id, flow_type)
```

**Risk**: MEDIUM - Wide-ranging changes

---

### Phase 5: Testing & Validation (Week 5)

**Goal**: Comprehensive testing before production

**Test Plan**:

1. **Unit Tests** (95%+ coverage)
   - FlowManager: 150+ tests
   - FlowEngine: 100+ tests
   - FlowValidator: 80+ tests
   - Integrations: 60+ tests
   - **Total**: 400+ tests

2. **Integration Tests**
   - End-to-end flow execution
   - All integration plugins
   - Error recovery scenarios
   - State transitions

3. **Performance Tests**
   - Benchmark: Old vs New
   - Load testing (1000+ flows)
   - Memory profiling
   - Database query optimization

4. **Staging Deployment**
   - Deploy with USE_CONSOLIDATED_FLOWS=False (1 day)
   - Switch to USE_CONSOLIDATED_FLOWS=True (3 days)
   - Monitor metrics, logs, errors
   - Performance validation

**Risk**: MEDIUM - Critical validation phase

---

### Phase 6: Production Rollout (Week 6)

**Goal**: Gradual production deployment

**Rollout Plan**:

1. **Day 1: Canary 10%**
   - Enable on 10% of servers
   - Monitor for 12 hours
   - Metrics: error rate, performance, user impact

2. **Day 2: Expand 50%**
   - If canary successful, expand to 50%
   - Monitor for 24 hours
   - Compare metrics with baseline

3. **Day 3-4: Full 100%**
   - Full rollout to all servers
   - Monitor for 48 hours
   - Alert on any anomalies

4. **Day 5-7: Monitoring & Stabilization**
   - Monitor deprecation warnings
   - Track usage of legacy vs new
   - Fix any issues found
   - Prepare for cleanup phase

**Rollback Plan**:
- Set `USE_CONSOLIDATED_FLOWS=False`
- Restart services
- Verify legacy system operational
- **Rollback Time**: < 5 minutes

**Risk**: HIGH - Production deployment

---

## 📊 Component Consolidation Map

### Before → After

| Component | Old Files | Old LOC | New File | New LOC | Reduction |
|-----------|-----------|---------|----------|---------|-----------|
| **Orchestration** | flow_orchestrator.py, flow.py, flow_management.py | 3,729 | core/manager.py | 800 | 78% |
| **Execution** | flow_engine.py, enhanced_flow_engine.py, flow_core.py | 2,479 | core/engine.py | 600 | 76% |
| **Validation** | flow_validation.py, flow_integrity.py, flow_data_integrity.py | 1,856 | validation/validator.py | 400 | 78% |
| **Quiz Integration** | quiz_flow_integration.py, quiz_flow_integration_service.py | 1,632 | integrations/quiz.py | 600 | 63% |
| **Analytics** | flow_analytics.py, flow_monitoring.py | 1,473 | monitoring/analytics.py | 500 | 66% |
| **Error Handling** | flow_error_handler.py | 1,444 | errors/handler.py | 400 | 72% |
| **Templates** | flow_template.py | 343 | templates/manager.py | 300 | 13% |
| **Dashboard** | flow_dashboard.py | 797 | monitoring/dashboard.py | 300 | 62% |
| **Event System** | flow_event_broadcaster.py | 506 | (embedded in core) | 100 | 80% |
| **AI Integration** | flow_engine_ai_integration.py | 259 | integrations/ai.py | 200 | 23% |
| **Total** | **18 files** | **14,518** | **10-12 files** | **~7,500** | **48%** |

---

## 🎯 API Compatibility Matrix

### Public API (Must Maintain)

| Legacy API | New API | Compatibility Layer |
|------------|---------|---------------------|
| `get_enhanced_flow_engine(db)` | `get_flow_manager(db)` | ✅ Wrapper function |
| `FlowEngineIntegrationService(db)` | `FlowManager(db, ...)` | ✅ Adapter class |
| `flow.start_flow(...)` | `manager.start_flow(...)` | ✅ Same signature |
| `flow.advance_flow(...)` | `manager.advance_flow(...)` | ✅ Same signature |
| `FlowType` enum | `FlowType` enum | ✅ Re-exported |
| `FlowState` model | `FlowState` model | ✅ Same model |

### Internal API (Can Break)

- Internal helper functions
- Private methods
- Implementation details

**Strategy**: Use deprecation warnings for 2 weeks before breaking.

---

## 🧪 Testing Strategy

### Test Coverage Targets

| Component | Unit Tests | Integration Tests | Total |
|-----------|-----------|-------------------|-------|
| FlowManager | 150 | 20 | 170 |
| FlowEngine | 100 | 15 | 115 |
| FlowValidator | 80 | 10 | 90 |
| Integrations | 60 | 15 | 75 |
| Monitoring | 40 | 5 | 45 |
| Error Handling | 50 | 10 | 60 |
| **Total** | **480** | **75** | **555** |

**Target Coverage**: 95%+ (matching QW-020)

---

### Test Pyramid

```
        /\
       /  \      E2E Tests (10%)
      /────\     - Full flow execution
     /      \    - Real database
    /────────\   Integration Tests (25%)
   /          \  - Component integration
  /────────────\ - Mock external services
 /              \
/────────────────\ Unit Tests (65%)
   Fast, Isolated    - Pure logic
   Mock everything   - No I/O
```

---

## 📈 Performance Targets

### Benchmarks (vs Legacy)

| Metric | Legacy | Target | Improvement |
|--------|--------|--------|-------------|
| Flow Start | 150ms | ≤ 150ms | Maintain |
| Step Execution | 80ms | ≤ 80ms | Maintain |
| State Transition | 20ms | ≤ 15ms | 25% faster |
| Memory per Flow | 2MB | ≤ 1.5MB | 25% less |
| Query Count per Step | 5 | ≤ 3 | 40% less |
| Test Suite Runtime | N/A | < 2 min | New |

---

## 🔒 Security Considerations

### Data Access

- ✅ Row-Level Security (RLS) maintained
- ✅ User authorization checks
- ✅ Audit logging for all operations
- ✅ No sensitive data in logs

### Input Validation

- ✅ All inputs validated via Pydantic schemas
- ✅ SQL injection prevention (parameterized queries)
- ✅ XSS prevention (sanitized outputs)

### Error Handling

- ✅ No sensitive data in error messages
- ✅ Errors logged securely
- ✅ Rate limiting on public endpoints

---

## 📝 Documentation Plan

### Developer Documentation

1. **Migration Guide** (for developers)
   - How to update imports
   - API changes
   - Breaking changes list
   - Code examples

2. **Architecture Guide** (this document)
   - Component overview
   - Design decisions
   - Extension points

3. **API Reference**
   - All public APIs documented
   - Code examples
   - Type signatures

4. **Testing Guide**
   - How to write tests
   - Test patterns
   - Mock strategies

### Operational Documentation

1. **Deployment Guide**
   - Feature flag configuration
   - Rollout procedure
   - Rollback procedure

2. **Monitoring Guide**
   - Key metrics to watch
   - Alert thresholds
   - Troubleshooting steps

3. **Runbook**
   - Common issues
   - Resolution steps
   - Escalation paths

---

## ✅ Success Criteria

### Must Have

- [x] Architecture design complete
- [ ] 48% code reduction (15,000 → 7,500 LOC)
- [ ] Zero functionality loss
- [ ] 95%+ test coverage
- [ ] All existing tests pass
- [ ] Performance maintained or improved
- [ ] Feature flag implementation
- [ ] Backward compatibility layer
- [ ] Comprehensive documentation

### Nice to Have

- [ ] 50%+ code reduction
- [ ] 10%+ performance improvement
- [ ] Plugin system for integrations
- [ ] Enhanced monitoring
- [ ] Better error messages

---

## 🚨 Risk Mitigation

### Risk 1: Breaking Changes
- **Mitigation**: Backward compatibility layer + deprecation warnings
- **Rollback**: Feature flag allows instant rollback

### Risk 2: Performance Regression
- **Mitigation**: Performance benchmarking before/after
- **Rollback**: Monitor metrics, rollback if degradation

### Risk 3: Bugs in Core Logic
- **Mitigation**: 95%+ test coverage + staging validation
- **Rollback**: Feature flag + comprehensive monitoring

### Risk 4: Timeline Overrun
- **Mitigation**: Phased approach, can pause after each phase
- **Rollback**: N/A (planning risk)

---

## 📊 Timeline Summary

| Phase | Duration | Effort | Risk |
|-------|----------|--------|------|
| Week 1: Analysis | 5 days | 40h | ✅ DONE |
| Week 2: Implementation | 5 days | 40h | MEDIUM |
| Week 3: Compatibility | 5 days | 30h | LOW |
| Week 4: Migration | 5 days | 34h | MEDIUM |
| Week 5: Testing | 5 days | 40h | MEDIUM |
| Week 6: Production | 5 days | 30h | HIGH |
| **Total** | **6 weeks** | **214h** | **MEDIUM** |

---

## 🎓 Design Decisions

### Decision 1: Layered Architecture

**Options Considered**:
- A) Flat structure (all in one level)
- B) Layered structure (core/execution/validation/etc.)
- C) Hexagonal architecture (ports & adapters)

**Chosen**: B (Layered structure)

**Rationale**:
- Clear separation of concerns
- Easy to understand
- Aligns with team's experience
- Simpler than hexagonal for this use case

---

### Decision 2: Plugin System for Integrations

**Options Considered**:
- A) Tight coupling (integrations in core)
- B) Plugin system (interface + implementations)
- C) Event-driven (pub/sub)

**Chosen**: B (Plugin system)

**Rationale**:
- Loose coupling
- Easy to test (mock plugins)
- Easy to extend (add new plugins)
- Clear boundaries
- Better than event-driven for this use case (synchronous flow)

---

### Decision 3: Feature Flag Migration

**Options Considered**:
- A) Big bang (replace all at once)
- B) Feature flag (gradual rollout)
- C) Blue-green deployment

**Chosen**: B (Feature flag)

**Rationale**:
- Proven success in QW-020
- Instant rollback capability
- Gradual validation
- Lower risk than big bang
- Simpler than blue-green

---

## 💡 Extension Points

### How to Add New Integration

```python
# 1. Create new integration class
class MyIntegration(FlowIntegration):
    async def on_flow_start(self, flow_state, context):
        # Custom logic
        pass

# 2. Register in factory
def get_flow_manager(db: Session):
    integrations = [
        QuizFlowIntegration(db),
        AIFlowIntegration(db),
        MyIntegration(db),  # Add here
    ]
    return FlowManager(db, ..., integrations)
```

### How to Add New Validation Rule

```python
# 1. Create rule class
class MyValidationRule(ValidationRule):
    def validate(self, flow_state: FlowState) -> ValidationResult:
        # Custom validation
        pass

# 2. Register in validator
validator = FlowValidator(
    integrity_checker,
    rules=[
        StartConditionsRule(),
        TransitionRule(),
        MyValidationRule(),  # Add here
    ]
)
```

---

## 📞 Next Steps

### Immediate Actions (Week 2)

**Day 1-2: Core Implementation**
- [ ] Create module structure
- [ ] Implement FlowManager
- [ ] Implement FlowEngine
- [ ] Add unit tests

**Day 3-4: Supporting Components**
- [ ] Implement FlowValidator
- [ ] Implement plugin system
- [ ] Implement monitoring
- [ ] Add integration tests

**Day 5: Testing & Documentation**
- [ ] Comprehensive test suite
- [ ] API documentation
- [ ] Code review
- [ ] Refactoring

### Week 3 & Beyond

Follow migration plan outlined in Phase 2-6.

---

## ✅ Conclusion

This architecture design provides:

1. ✅ **Clear structure**: Layered architecture with clear boundaries
2. ✅ **Maintainability**: 48% code reduction, clear responsibilities
3. ✅ **Extensibility**: Plugin system for integrations
4. ✅ **Testability**: 95%+ coverage target
5. ✅ **Safety**: Feature flags + backward compatibility
6. ✅ **Performance**: Optimized queries and caching

**Recommendation**: **PROCEED** with implementation in Week 2.

**Confidence Level**: 🟢 **HIGH** - Design is solid, risks are mitigated.

---

## 📚 References

- Q