# Flow Engine Consolidation Migration Plan

**Plan ID**: P1-1
**Created**: 2025-10-07
**Status**: Planning Phase
**Priority**: High
**Complexity**: Medium-High

## Executive Summary

The codebase currently operates two parallel flow processing pipelines:
1. **Legacy FlowEngine** - Used by patient onboarding and webhook processor
2. **FlowEngineIntegrationService** - Used by REST endpoints with EnhancedFlowEngine

This dual-engine architecture creates:
- **State fragmentation** - Different engines don't share scheduling or state
- **Code duplication** - Similar logic in multiple places
- **Maintenance burden** - Changes require updates in multiple locations
- **Testing complexity** - Need to test both pipelines independently

**Goal**: Consolidate to single FlowEngineIntegrationService, eliminating legacy helpers.

---

## Current State Analysis

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     CURRENT ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌─────────────────────────┐  │
│  │  Patient Service │         │  Webhook Processor      │  │
│  │  (Onboarding)    │         │  (Inbound Messages)     │  │
│  └────────┬─────────┘         └───────────┬─────────────┘  │
│           │                               │                 │
│           │ Uses Legacy                   │ Uses Legacy     │
│           ▼                               ▼                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         FlowEngine (Legacy)                          │  │
│  │  - Basic flow state management                       │  │
│  │  - Template-based message generation                 │  │
│  │  - No AI personalization                             │  │
│  │  - Direct message scheduling                         │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────┐                                       │
│  │  REST Endpoints  │                                       │
│  │  (/api/v1/flows) │                                       │
│  └────────┬─────────┘                                       │
│           │                                                  │
│           │ Uses New                                        │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │   FlowEngineIntegrationService (New)                 │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  EnhancedFlowEngine                            │  │  │
│  │  │  - AI-powered message generation               │  │  │
│  │  │  - Gemini integration                          │  │  │
│  │  │  - Conversation memory (Redis)                 │  │  │
│  │  │  - Advanced personalization                    │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │  + Message Scheduler                                 │  │
│  │  + Flow Analytics                                    │  │
│  │  + Platform Synchronization                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│                   SHARED COMPONENTS                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  FlowCore (Base class)                               │  │
│  │  - Template handling                                 │  │
│  │  - Flow state management                             │  │
│  │  - Message operations                                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Files and Their Roles

#### Legacy FlowEngine Pipeline

**File**: `app/services/flow_engine.py` (1,160 lines)
- **Class**: `FlowEngine(AsyncFlowEngineBase)`
- **Usage**:
  - `app/services/patient.py:223-231` - Patient onboarding
  - `app/services/webhook_processor.py:61,256-274` - Webhook processing
  - `app/tasks/flow_automation.py:58,214` - Celery tasks
  - `app/services.py:209` - ServiceProvider instantiation
  - `app/thread_safe_services.py:228,232` - Thread-safe service creation

**Capabilities**:
- Basic flow state management (start, pause, resume, complete)
- Template-based message generation (no AI)
- Quiz integration
- Manual flow advancement
- State machine transitions
- Message scheduling via MessageService

**Dependencies**:
- FlowStateRepository
- FlowTemplateService
- MessageService
- QuizSessionService
- StateMachine
- FlowContext (local context builder)

#### New FlowEngineIntegrationService Pipeline

**File**: `app/services/flow.py` (FlowEngineIntegrationService)
- **Class**: `FlowEngineIntegrationService`
- **Usage**:
  - `app/api/v1/flows.py:1014-1084` - All REST flow endpoints
  - `app/dependencies/service_dependencies.py:81-83` - Dependency injection

**Capabilities**:
- AI-powered message generation (Gemini)
- Conversation memory (Redis)
- Advanced personalization
- Flow analytics and metrics
- Platform synchronization
- A/B testing integration
- Message preview functionality
- Health monitoring (Gemini, Redis)

**Dependencies**:
- EnhancedFlowEngine (inherits from FlowCore)
- MessageScheduler (advanced scheduling)
- UnifiedWhatsAppService (reliable delivery)
- FlowAnalyticsService
- FlowEventBroadcaster
- PlatformSynchronization
- TemplateLoader

#### Shared Foundation

**File**: `app/services/flow_core.py` (671 lines)
- **Class**: `FlowCore`
- **Purpose**: Base class with shared functionality
- **Provides**:
  - Patient enrollment
  - Flow type determination (initial/days_16_45/monthly)
  - Flow advancement logic
  - Pause/resume operations
  - Template handling with fallbacks
  - Message timing optimization
  - Health monitoring

**File**: `app/services/enhanced_flow_engine.py`
- **Class**: `EnhancedFlowEngine(FlowCore)`
- **Purpose**: AI-powered execution engine
- **Provides**:
  - Gemini AI integration
  - Conversation memory
  - Response processing
  - Sentiment analysis
  - Message personalization

---

## Problem Statement

### 1. State Fragmentation

**Issue**: Two engines manage flow state independently:
- Legacy FlowEngine directly updates PatientFlowState
- EnhancedFlowEngine uses FlowCore methods
- No shared scheduling coordination

**Impact**:
```python
# Patient onboarding (patient.py:223)
flow_engine = FlowEngine(db)
flow_state = flow_engine.start_flow(patient_id, "hormonia_fluxo_padrao")
# ❌ Schedules messages via MessageService.schedule_message()

# REST endpoint (flows.py:1014)
flow_service = FlowEngineIntegrationService(db)
preview = await flow_service.preview_flow_message(patient_id, template_id, day)
# ✅ Uses MessageScheduler with advanced queuing
```

**Result**: Messages scheduled by onboarding may conflict with API-scheduled messages.

### 2. Feature Disparity

| Feature | Legacy FlowEngine | FlowEngineIntegrationService |
|---------|-------------------|------------------------------|
| AI Personalization | ❌ No | ✅ Gemini |
| Conversation Memory | ❌ No | ✅ Redis |
| Analytics | ❌ Basic | ✅ Full metrics |
| A/B Testing | ❌ No | ✅ Yes |
| Platform Sync | ❌ No | ✅ Yes |
| Message Preview | ❌ No | ✅ Yes |
| Health Monitoring | ❌ No | ✅ Yes |

**Impact**: Patients onboarded via webhook get inferior experience vs. API-created flows.

### 3. Code Duplication

**Flow Start Logic**:
- `FlowEngine.start_flow()` - 111 lines (flow_engine.py:454-565)
- `FlowCore.enroll_patient()` - 51 lines (flow_core.py:77-126)

**Message Scheduling**:
- `FlowEngine._schedule_step()` - 82 lines (flow_engine.py:367-452)
- `FlowEngineIntegrationService._schedule_patient_message()` (flow.py)

**Flow Advancement**:
- `FlowEngine.process_patient_day()` - 93 lines (flow_engine.py:637-679)
- `FlowCore.advance_patient_flow()` - 79 lines (flow_core.py:167-258)

### 4. Testing Complexity

**Current State**:
- Must test both pipelines independently
- Need separate fixtures for each engine
- Integration tests must verify both paths
- Mock different dependencies for each

**Example Test Overhead**:
```python
# Test patient onboarding flow
def test_patient_onboarding_flow():
    flow_engine = FlowEngine(db)
    # Test legacy pipeline...

# Test API flow creation
async def test_api_flow_creation():
    flow_service = FlowEngineIntegrationService(db)
    # Test new pipeline...

# Both testing the same feature!
```

---

## Migration Strategy

### Phase 1: Analysis & Planning (Current)

**Tasks**:
- [x] Identify all FlowEngine usage points
- [x] Map dependencies and shared state
- [x] Document feature gaps
- [ ] Create migration test suite
- [ ] Design rollback strategy

**Deliverables**:
- This migration plan document
- Dependency graph
- Risk assessment
- Test coverage baseline

### Phase 2: Adapter Pattern Implementation

**Goal**: Create adapter to route legacy calls to new service without breaking changes.

**Implementation**:

```python
# app/services/flow_engine_adapter.py

class FlowEngineAdapter:
    """
    Adapter that implements legacy FlowEngine interface
    but delegates to FlowEngineIntegrationService.

    Allows drop-in replacement without changing callers.
    """

    def __init__(self, db: Session):
        self.db = db
        self.integration_service = FlowEngineIntegrationService(db)
        self.enhanced_engine = self.integration_service.enhanced_flow_engine

    def start_flow(
        self,
        patient_id: UUID,
        flow_type: str,
        initial_data: Optional[dict] = None,
        fallback_to_default: bool = True
    ) -> PatientFlowState:
        """Adapter for legacy start_flow calls."""
        # Convert legacy flow_type to FlowType enum
        flow_type_enum = self._convert_flow_type(flow_type)

        # Use new service
        return asyncio.run(
            self.enhanced_engine.enroll_patient(
                patient_id,
                flow_type_enum
            )
        )

    def process_patient_day(
        self,
        patient_id: UUID,
        force_transition: bool = False,
        additional_context: Optional[dict] = None
    ) -> dict[str, Any]:
        """Adapter for legacy process_patient_day calls."""
        return asyncio.run(
            self.enhanced_engine.advance_patient_flow(
                patient_id,
                force_day=None if not force_transition else additional_context.get('day')
            )
        )

    def get_flow_status(self, patient_id: UUID) -> dict[str, Any]:
        """Adapter for legacy get_flow_status calls."""
        return asyncio.run(
            self.enhanced_engine.get_flow_state(patient_id)
        )

    # ... implement remaining FlowEngine methods as adapters
```

**Benefits**:
- Zero breaking changes to callers
- Gradual migration path
- Easy rollback if issues arise
- Can A/B test new vs old

**Risks**:
- Sync/async impedance mismatch
- Performance overhead from `asyncio.run()`
- May hide incompatibilities

### Phase 3: Update Usage Points

**Files to Update**:

1. **Patient Service** (`app/services/patient.py`)
   - Lines 223-231: Replace `FlowEngine(db)` with `FlowEngineAdapter(db)`
   - Add error handling for adapter-specific exceptions
   - Update tests

2. **Webhook Processor** (`app/services/webhook_processor.py`)
   - Line 61: Replace `FlowEngine(db)` instantiation
   - Lines 256-274: Update flow processing logic
   - Ensure message handling uses unified service

3. **Celery Tasks** (`app/tasks/flow_automation.py`)
   - Lines 58, 214: Replace `FlowEngine()` with adapter
   - Update task signatures if needed
   - Add retry logic for async operations

4. **Service Provider** (`app/services.py`)
   - Line 209: Update `flow_engine` property to return adapter
   - Ensure singleton pattern still works
   - Update cleanup logic

5. **Thread-Safe Services** (`app/thread_safe_services.py`)
   - Lines 228, 232: Update FlowEngine creation
   - Ensure thread safety with adapter
   - Test concurrent access

**Migration Script**:

```python
# scripts/migrate_flow_engine_usages.py

import re
from pathlib import Path

USAGE_PATTERNS = [
    (r'from app\.services\.flow_engine import FlowEngine',
     'from app.services.flow_engine_adapter import FlowEngineAdapter as FlowEngine'),

    (r'self\.flow_engine = FlowEngine\(db\)',
     'self.flow_engine = FlowEngineAdapter(db)'),

    (r'flow_engine = FlowEngine\(db\)',
     'flow_engine = FlowEngineAdapter(db)'),
]

def migrate_file(file_path: Path):
    """Migrate a single file to use adapter."""
    content = file_path.read_text()
    original = content

    for pattern, replacement in USAGE_PATTERNS:
        content = re.sub(pattern, replacement, content)

    if content != original:
        # Backup original
        backup_path = file_path.with_suffix('.py.bak')
        backup_path.write_text(original)

        # Write migrated
        file_path.write_text(content)
        print(f"✅ Migrated: {file_path}")
        print(f"   Backup: {backup_path}")

# Run migration
files_to_migrate = [
    "app/services/patient.py",
    "app/services/webhook_processor.py",
    "app/tasks/flow_automation.py",
    "app/services.py",
    "app/thread_safe_services.py"
]

for file_path in files_to_migrate:
    migrate_file(Path(file_path))
```

### Phase 4: Centralize Scheduling

**Problem**: Two scheduling mechanisms:
- Legacy: `MessageService.schedule_message()` + Celery `send_scheduled_message`
- New: `MessageScheduler` with advanced queuing

**Solution**: Ensure adapter uses MessageScheduler for all operations.

**Implementation**:

```python
# In FlowEngineAdapter

def _schedule_message_via_new_system(
    self,
    patient_id: UUID,
    content: str,
    scheduled_for: datetime,
    message_type: MessageType,
    metadata: dict
) -> Message:
    """Use MessageScheduler instead of legacy MessageService."""
    return self.integration_service.message_scheduler.schedule_message(
        patient_id=patient_id,
        content=content,
        scheduled_for=scheduled_for,
        message_type=message_type,
        priority="normal",
        metadata=metadata,
        deduplication_enabled=True  # Prevent duplicate scheduling
    )
```

**Deduplication Strategy**:
- Use message content hash + patient_id + scheduled_time as deduplication key
- Store scheduled message IDs in Redis with 24h TTL
- Before scheduling, check if identical message already scheduled

### Phase 5: Testing & Validation

**Test Strategy**:

1. **Unit Tests**
   - Test adapter implements all FlowEngine methods
   - Verify correct delegation to integration service
   - Test error handling and edge cases

2. **Integration Tests**
   - Test patient onboarding via webhook → adapter → new service
   - Verify message scheduling works end-to-end
   - Test flow advancement and state transitions

3. **Regression Tests**
   - Run existing FlowEngine tests against adapter
   - Ensure backward compatibility
   - Verify no behavioral changes

4. **Performance Tests**
   - Benchmark adapter overhead
   - Compare legacy vs new message delivery times
   - Test concurrent flow processing

**Test Coverage Goals**:
- Adapter methods: 100%
- Integration paths: 90%
- Edge cases: 85%
- Regression suite: Pass 100%

**Test Files to Create**:
```
tests/unit/services/test_flow_engine_adapter.py
tests/integration/test_patient_onboarding_migration.py
tests/integration/test_webhook_flow_processing_migration.py
tests/performance/test_adapter_overhead.py
```

### Phase 6: Delete Legacy Code

**After Migration Complete & Stable**:

**Files to Delete**:
1. `app/services/flow_engine.py` (1,160 lines) - Legacy engine
2. Unused helper classes in flow_engine.py:
   - `FlowContext` (if replaced by EnhancedFlowEngine's context)
   - Legacy async helpers (if fully migrated)

**Files to Update**:
1. Remove `flow_engine` imports from:
   - `app/services/__init__.py`
   - `app/services.py` (ServiceProvider)
   - Any remaining references

**Verification Checklist**:
- [ ] All tests pass without legacy FlowEngine
- [ ] No import errors in production
- [ ] Grep confirms no remaining usages: `grep -r "from.*flow_engine import FlowEngine" --include="*.py"`
- [ ] Deployment smoke tests pass
- [ ] No runtime errors in logs for 7 days

**Rollback Plan** (if deletion causes issues):
1. Restore `flow_engine.py` from git
2. Revert adapter usage to direct FlowEngine calls
3. Redeploy previous version
4. Investigate root cause
5. Fix issues before re-attempting deletion

---

## Risk Assessment

### High Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Sync/Async Mismatch** | High - Runtime errors | Medium | Use asyncio.run() with timeout, comprehensive error handling |
| **State Corruption** | Critical - Data loss | Low | Extensive integration tests, database transactions, rollback plan |
| **Performance Degradation** | High - User experience | Medium | Benchmark before/after, optimize hot paths, caching |
| **Message Duplication** | High - Spam patients | Medium | Deduplication via Redis, idempotency keys, monitoring |

### Medium Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Feature Regression** | Medium - Missing functionality | Medium | Comprehensive regression tests, feature parity checklist |
| **Deployment Issues** | Medium - Downtime | Low | Blue-green deployment, canary rollout, quick rollback |
| **Dependency Conflicts** | Medium - Integration breaks | Low | Dependency injection testing, mocking |

### Low Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Documentation Drift** | Low - Confusion | High | Update docs in same PR, automated doc generation |
| **Test Maintenance** | Low - Tech debt | Medium | Consolidate duplicate tests, use fixtures |

---

## Rollback Strategy

### Immediate Rollback (< 5 minutes)

**Trigger**: Critical production error, data corruption, or service outage

**Steps**:
1. Revert deployment to previous version:
   ```bash
   git revert <migration-commit>
   git push origin main
   railway up  # Or your deployment command
   ```

2. Verify rollback:
   ```bash
   # Check legacy FlowEngine is active
   curl https://api.hormonia.com/api/v1/flows/health

   # Verify patient onboarding works
   # Verify webhook processing works
   ```

3. Monitor logs for 15 minutes
4. Post-mortem: Document what went wrong

### Gradual Rollback (< 1 hour)

**Trigger**: Elevated error rates, performance issues, or data inconsistencies

**Steps**:
1. Disable new features via feature flags:
   ```python
   # app/config.py
   USE_FLOW_ENGINE_ADAPTER = False  # Disable adapter
   ```

2. Route specific customers back to legacy:
   ```python
   if patient_id in LEGACY_CUSTOMER_IDS:
       use_legacy_flow_engine()
   else:
       use_adapter()
   ```

3. Investigate issues in non-production environment
4. Fix and redeploy incrementally

### Feature Flag Strategy

```python
# app/config.py
FLOW_ENGINE_MIGRATION_FLAGS = {
    "use_adapter": os.getenv("USE_FLOW_ENGINE_ADAPTER", "true").lower() == "true",
    "adapter_patients_whitelist": os.getenv("ADAPTER_WHITELIST", "").split(","),
    "adapter_rollout_percentage": int(os.getenv("ADAPTER_ROLLOUT_PCT", "100")),
}

# app/services/patient.py
def get_flow_engine(patient_id: UUID) -> Union[FlowEngine, FlowEngineAdapter]:
    """Factory with gradual rollout support."""
    if not FLOW_ENGINE_MIGRATION_FLAGS["use_adapter"]:
        return FlowEngine(db)

    # Whitelist check
    if str(patient_id) in FLOW_ENGINE_MIGRATION_FLAGS["adapter_patients_whitelist"]:
        return FlowEngineAdapter(db)

    # Percentage-based rollout
    patient_hash = int(hashlib.md5(str(patient_id).encode()).hexdigest(), 16)
    rollout_pct = FLOW_ENGINE_MIGRATION_FLAGS["adapter_rollout_percentage"]
    if (patient_hash % 100) < rollout_pct:
        return FlowEngineAdapter(db)

    # Default to legacy
    return FlowEngine(db)
```

---

## Success Criteria

### Functional Requirements

- [ ] All patient onboarding flows use FlowEngineIntegrationService
- [ ] All webhook flow processing uses FlowEngineIntegrationService
- [ ] Zero duplicate message scheduling
- [ ] AI personalization active for all flows
- [ ] Conversation memory tracking all interactions

### Performance Requirements

- [ ] Flow processing latency < 200ms (p95)
- [ ] Message scheduling throughput ≥ 1000 msg/min
- [ ] Memory usage stable (no leaks)
- [ ] Database connection pool utilization < 80%

### Quality Requirements

- [ ] Test coverage ≥ 85% for all modified code
- [ ] Zero critical bugs in production for 14 days
- [ ] All regression tests pass
- [ ] API contract compatibility maintained

### Operational Requirements

- [ ] Monitoring dashboards updated
- [ ] Alerting configured for adapter errors
- [ ] Documentation updated (README, API docs, architecture)
- [ ] Runbook created for troubleshooting

---

## Timeline & Effort Estimation

### Phase 1: Analysis & Planning
- **Effort**: 8 hours
- **Completed**: 50% (this document)
- **Remaining**: Test suite setup, risk mitigation planning

### Phase 2: Adapter Implementation
- **Effort**: 16 hours
- **Tasks**:
  - Create FlowEngineAdapter class (4h)
  - Implement all legacy method adapters (8h)
  - Write unit tests (4h)

### Phase 3: Update Usage Points
- **Effort**: 12 hours
- **Tasks**:
  - Update patient.py (2h)
  - Update webhook_processor.py (3h)
  - Update flow_automation.py (2h)
  - Update service providers (2h)
  - Integration testing (3h)

### Phase 4: Centralize Scheduling
- **Effort**: 8 hours
- **Tasks**:
  - Implement deduplication (3h)
  - Migrate scheduling calls (3h)
  - Test message delivery (2h)

### Phase 5: Testing & Validation
- **Effort**: 16 hours
- **Tasks**:
  - Write comprehensive tests (8h)
  - Run regression suite (2h)
  - Performance benchmarking (3h)
  - Production staging test (3h)

### Phase 6: Legacy Code Deletion
- **Effort**: 4 hours
- **Tasks**:
  - Remove legacy files (1h)
  - Update imports (1h)
  - Final verification (2h)

**Total Estimated Effort**: 64 hours (8 developer days)

**Recommended Schedule**:
- Week 1: Phases 1-2 (Planning + Adapter)
- Week 2: Phases 3-4 (Migration + Scheduling)
- Week 3: Phase 5 (Testing)
- Week 4: Phase 6 (Cleanup) + Buffer

---

## Dependencies & Blockers

### External Dependencies
- **None** - All code is internal

### Internal Dependencies
1. **ServiceProvider Refactor** - Already complete ✅
2. **Thread-Safe Session Management** - Already complete ✅
3. **FlowCore Base Class** - Already exists ✅
4. **EnhancedFlowEngine** - Already exists ✅

### Potential Blockers
1. **Async/Sync Conversion**: May need event loop management review
2. **Message Deduplication**: Requires Redis availability
3. **Testing Environment**: Need staging environment with realistic data

---

## Monitoring & Observability

### Metrics to Track

**Before Migration** (Baseline):
- Flow creation latency (p50, p95, p99)
- Message scheduling rate
- Error rates by service
- Database query performance

**During Migration**:
- Adapter vs legacy usage ratio
- Adapter error rates
- Message duplication incidents
- Flow state inconsistencies

**After Migration**:
- Overall flow processing latency
- AI personalization success rate
- Conversation memory hit rate
- User satisfaction metrics

### Dashboards to Create

1. **Flow Engine Migration Dashboard**
   - Adapter usage percentage
   - Error rate comparison (legacy vs adapter)
   - Performance metrics (latency distribution)

2. **Message Scheduling Dashboard**
   - Scheduling rate (msg/min)
   - Delivery success rate
   - Deduplication effectiveness
   - Queue depth and processing time

3. **Flow Health Dashboard**
   - Active flows by type
   - Flow completion rate
   - State transition success rate
   - AI service health (Gemini, Redis)

### Alerts to Configure

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| High Adapter Error Rate | Errors > 5% of requests | Critical | Page on-call, rollback |
| Message Duplication | Duplicate rate > 1% | High | Investigate, disable dedup if broken |
| Flow State Corruption | Orphaned states detected | High | Investigate, manual cleanup |
| Performance Degradation | p95 latency > 500ms | Medium | Optimize, scale resources |

---

## Next Steps

### Immediate Actions (This Week)
1. [ ] Create migration test suite baseline
2. [ ] Set up monitoring dashboards
3. [ ] Design FlowEngineAdapter interface
4. [ ] Review plan with team

### Short-Term (Next 2 Weeks)
1. [ ] Implement FlowEngineAdapter
2. [ ] Write comprehensive adapter tests
3. [ ] Update first usage point (patient.py)
4. [ ] Deploy to staging for validation

### Long-Term (Next Month)
1. [ ] Complete all usage point migrations
2. [ ] Run performance benchmarks
3. [ ] Production deployment with feature flags
4. [ ] Monitor for 2 weeks before legacy deletion

---

## Appendix

### A. File Modification Checklist

- [ ] `app/services/flow_engine_adapter.py` (NEW)
- [ ] `app/services/patient.py` (MODIFY)
- [ ] `app/services/webhook_processor.py` (MODIFY)
- [ ] `app/tasks/flow_automation.py` (MODIFY)
- [ ] `app/services.py` (MODIFY)
- [ ] `app/thread_safe_services.py` (MODIFY)
- [ ] `app/config.py` (ADD feature flags)
- [ ] `tests/unit/services/test_flow_engine_adapter.py` (NEW)
- [ ] `tests/integration/test_migration_*.py` (NEW)

### B. Database Schema Impact

**No schema changes required** - Both engines use same database tables:
- `patient_flow_states`
- `flow_template_versions`
- `flow_kinds`
- `messages`
- `quiz_sessions`

### C. API Contract Impact

**No breaking changes** - FlowEngineAdapter maintains exact same interface as legacy FlowEngine.

### D. Reference Implementation

See `app/services/flow.py` for FlowEngineIntegrationService implementation details.

---

**Document Version**: 1.0
**Last Updated**: 2025-10-07
**Author**: Strategic Planning Agent
**Reviewers**: [To be assigned]
