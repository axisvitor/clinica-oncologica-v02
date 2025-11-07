# Flow Engine Hierarchy & Consolidation Plan
**Date**: 2025-11-07
**Status**: QW-021 Migration In Progress (95% Complete)

---

## Executive Summary

The backend currently has **6 overlapping FlowEngine implementations** totaling **2,256 lines of code**. A consolidation effort (QW-021) is 95% complete, targeting a **~47% code reduction** through strategic merging and deprecation.

---

## Current State

### All Flow Engine Implementations

| # | Location | Class | Lines | Status | Usage |
|---|----------|-------|-------|--------|-------|
| 1 | `app/domain/flows/engine/flow_engine.py` | FlowEngine | 693 | ✅ **CANONICAL** | 19+ files |
| 2 | `app/services/flow/core/engine.py` | FlowEngine | 102 | 🔄 **QW-021 TARGET** | 2 files |
| 3 | `app/services/enhanced_flow_engine.py` | EnhancedFlowEngine | 459 | ⚠️ **LEGACY** | 33+ files |
| 4 | `app/services/flow_core.py` | FlowCore | 671 | ⚠️ **LEGACY BASE** | 1 file |
| 5 | `app/services/flow_engine.py` | FlowEngine | 162 | 🚫 **DEPRECATED** | 19+ files |
| 6 | `app/services/flow.py` | FlowEngineIntegrationService | 169 | 🚫 **DEPRECATED** | 8+ files |

**Total**: 2,256 lines across 6 implementations

---

## Canonical Hierarchy

```
┌─────────────────────────────────────────────────┐
│  FUTURE (QW-021 - 95% Complete)                 │
│  app/services/flow/                             │
│  ├── FlowManager (734 LOC) ← Main Interface     │
│  └── FlowEngine (102 LOC) ← Stateless Executor  │
└─────────────────────────────────────────────────┘
                    ↓ Migration Path
┌─────────────────────────────────────────────────┐
│  CURRENT CANONICAL (Active)                     │
│  app/domain/flows/engine/                       │
│  └── FlowEngine (693 LOC) ← Primary Engine      │
│      ├── ContextBuilder (96 LOC)                │
│      ├── ConditionEvaluator (273 LOC)           │
│      ├── StepExecutor (208 LOC)                 │
│      └── TransitionManager (124 LOC)            │
│  Total: 1,394 LOC                               │
└─────────────────────────────────────────────────┘
                    ↑ Used By
┌─────────────────────────────────────────────────┐
│  LEGACY AI LAYER (To Be Refactored)             │
│  app/services/                                  │
│  ├── EnhancedFlowEngine (459 LOC)               │
│  │   └── Inherits FlowCore (671 LOC)            │
│  │       └── AI + Conversation features         │
│  └── Total: 1,130 LOC                           │
└─────────────────────────────────────────────────┘
                    ↑ Wrapped By
┌─────────────────────────────────────────────────┐
│  DEPRECATED WRAPPERS (Remove in v3.0)           │
│  ├── flow_engine.py (162 LOC)                   │
│  │   └── Delegates to domain/flows/engine       │
│  └── flow.py (169 LOC)                          │
│      └── Delegates to domain/flows/core         │
└─────────────────────────────────────────────────┘
```

---

## Overlap Analysis

| Feature | Domain Engine | QW-021 Engine | Enhanced Engine | FlowCore |
|---------|--------------|---------------|-----------------|----------|
| Flow Start | ✅ Primary | ✅ New | ❌ Delegates | ❌ Delegates |
| Flow Transitions | ✅ Primary | ✅ New | ❌ Delegates | ❌ Delegates |
| Step Execution | ✅ Primary | ✅ New | ❌ Delegates | ❌ Delegates |
| AI Message Gen | ❌ No | ❌ No | ✅ Primary | ❌ No |
| Sentiment Analysis | ❌ No | ❌ No | ✅ Primary | ❌ No |
| Template Loading | ✅ Yes | ✅ Yes | ❌ Delegates | ✅ Yes |
| Patient Enrollment | ❌ No | ❌ No | ❌ Delegates | ✅ Yes |
| Flow State Mgmt | ✅ Yes | ✅ Yes | ❌ Delegates | ✅ Yes |

---

## Consolidation Plan

### Phase 1: Immediate (Sprint 2-3)

**Goal**: Document and declare canonical hierarchy

**Actions**:
1. ✅ Create this documentation
2. Update import paths in 46+ files:
   ```python
   # OLD (deprecated)
   from app.services.flow_engine import FlowEngine

   # NEW (canonical)
   from app.domain.flows.engine import FlowEngine
   ```
3. Add deprecation warnings to wrappers
4. Extract AI features to separate `AIMessageService`

**Impact**: Clarify architecture, prepare for consolidation

---

### Phase 2: Consolidation (Sprint 4-5)

**Goal**: Merge FlowCore into Domain Engine

**Actions**:
1. Move shared operations from FlowCore → Domain Engine
2. Extract event broadcasting to `FlowEventService`
3. Remove inheritance hierarchy
4. Complete QW-021 migration (enable globally)

**Impact**: Eliminate 671 lines from FlowCore

---

### Phase 3: Cleanup (Sprint 6)

**Goal**: Remove deprecated wrappers

**Actions**:
1. Delete `app/services/flow_engine.py` (162 LOC)
2. Delete `app/services/flow.py` (169 LOC)
3. Update 27+ import references
4. Mark EnhancedFlowEngine as deprecated

**Impact**: Remove 331 lines of wrapper code

---

### Phase 4: Final Migration (Sprint 7-8)

**Goal**: Complete QW-021 migration

**Actions**:
1. Migrate all 33+ files using EnhancedFlowEngine
2. Enable `USE_CONSOLIDATED_FLOWS=True` globally
3. Create `AIMessageService` for AI operations
4. Final cleanup

**Expected Result**:
- **Before**: 2,256 LOC (6 engines)
- **After**: ~1,200 LOC (2 engines + services)
- **Savings**: 47% reduction

---

## Migration Checklist

### High Priority (38+ files)

**Using deprecated flow_engine.py wrapper (19 files)**:
- [ ] `app/services/patient.py`
- [ ] `app/services/webhook_processor.py`
- [ ] `app/tasks/flow_automation.py`
- [ ] `app/api/v2/patients_crud.py`
- [ ] `app/thread_safe_services.py`
- [ ] Test scripts (5 files)
- [ ] Other services (12 files)

**Using EnhancedFlowEngine (33 files)**:
- [ ] `app/agents/patient/flow_coordinator.py`
- [ ] `app/domain/quizzes/integration/` (2 files)
- [ ] `app/domain/flows/core/` (3 files)
- [ ] `app/tasks/flows.py`
- [ ] `app/services/hive_mind_integration.py`
- [ ] Other domain services (25 files)

**Using flow.py wrapper (8 files)**:
- [ ] `app/api/v1_archived_2025-11-07/flows.py`
- [ ] `app/services.py`
- [ ] `app/thread_safe_services.py`
- [ ] `app/services/flow_management.py`
- [ ] Other legacy services (4 files)

---

## Risk Assessment

| Component | Risk Level | Reason | Mitigation |
|-----------|-----------|---------|------------|
| EnhancedFlowEngine | 🔴 HIGH | 33+ dependents | Feature flag rollout, parallel run |
| Domain FlowEngine | 🟡 MEDIUM | Wrapped by deprecated layer | Gradual migration |
| QW-021 FlowEngine | 🟢 LOW | Isolated, new | Feature flag already in place |

---

## Recommended Approach

1. **Feature Flag Rollout**: 10% → 50% → 100%
2. **Parallel Run Period**: 2-4 weeks
3. **Gradual Deprecation**: Add warnings, monitor usage
4. **Final Cleanup**: After validation period

---

## Success Metrics

- [ ] Zero files importing deprecated wrappers
- [ ] All flows using canonical engine
- [ ] AI features in separate service
- [ ] ~47% LOC reduction achieved
- [ ] Zero regression in functionality
- [ ] Performance maintained or improved

---

## References

- **QW-021 Epic**: Flow system consolidation
- **Related Files**:
  - `app/domain/flows/engine/flow_engine.py` (canonical)
  - `app/services/flow/core/engine.py` (target)
  - `app/services/enhanced_flow_engine.py` (legacy)
  - `app/services/flow_core.py` (legacy base)
  - `app/services/flow_engine.py` (deprecated wrapper)
  - `app/services/flow.py` (deprecated wrapper)

---

**Last Updated**: 2025-11-07
**Owner**: Backend Architecture Team
**Status**: In Progress (Phase 1 Complete)
