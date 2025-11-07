# Service Layer Consolidation Strategy
**Date**: 2025-11-07
**Sprint**: 2
**Status**: In Progress

---

## Executive Summary

Analysis identified **18 Manager classes** across the service layer with **critical duplications**:
- **3 WebSocket managers** (60% duplication)
- **3 SessionManager classes** (name collision)
- **2 TemplateManager classes** (different purposes)

This document outlines consolidation strategy to eliminate duplication and improve architecture.

---

## Critical Issues

### Issue 1: WebSocket Manager Triple Duplication

**Problem**: Three overlapping WebSocket implementations

| File | Class | Lines | Status |
|------|-------|-------|--------|
| `services/websocket_manager.py` | ConnectionManager | 623 | ⚠️ ORIGINAL |
| `services/enhanced_websocket_manager.py` | EnhancedWebSocketConnectionManager | 980 | 🔴 DUPLICATE (60% overlap) |
| `services/redis_pubsub_manager.py` | RedisPubSubManager | 407 | ✅ DIFFERENT CONCERN |

**Evidence of Duplication**:
- Both have: connect, disconnect, authenticate_connection, join_patient_room, broadcast_to_user
- EnhancedVersion = Original + heartbeat + metrics + health monitoring
- Both used in 9+ files (same locations)

**Recommendation**: **MERGE** into single `WebSocketManager`

---

### Issue 2: SessionManager Name Collision

**Problem**: Three classes named "SessionManager" with completely different purposes

| File | Class | Purpose | Lines |
|------|-------|---------|-------|
| `core/session_manager.py` | SessionManager | Database sessions | 414 |
| `domain/quizzes/session_manager.py` | SessionManager | Quiz sessions | 968 |
| `domain/flows/state/state_manager.py` | FlowStateManager | Flow states | 253 |

**Recommendation**: **RENAME** quiz SessionManager → `QuizSessionManager`

---

### Issue 3: TemplateManager Confusion

**Problem**: Two TemplateManager classes with different responsibilities

| File | Class | Purpose | Lines |
|------|-------|---------|-------|
| `services/flow/templates/manager.py` | FlowTemplateManager | CRUD operations | 605 |
| `domain/flows/core/template_manager.py` | TemplateManager | Runtime loading | 232 |

**Recommendation**: **RENAME** domain version → `MessageTemplateLoader`

---

## Consolidation Plan

### Priority 1: WebSocket Managers (HIGH IMPACT)

**Goal**: Merge 2 overlapping managers into 1 unified manager

**Current State**:
- `ConnectionManager` (623 lines) - Basic WebSocket management
- `EnhancedWebSocketConnectionManager` (980 lines) - Superset with extras
- `RedisPubSubManager` (407 lines) - Distributed messaging (keep separate)

**Target State**:
```python
# services/websocket/
├── __init__.py
├── connection_manager.py     # Unified WebSocket manager (750 lines)
├── heartbeat_monitor.py      # Heartbeat logic (150 lines)
└── redis_pubsub_manager.py   # Keep separate (407 lines)
```

**Migration Steps**:
1. Create `services/websocket/` directory
2. Extract heartbeat logic to separate module
3. Merge ConnectionManager + Enhanced features
4. Update 9+ import references
5. Delete original files

**Impact**:
- **Before**: 1,603 lines (2 managers)
- **After**: ~900 lines (1 manager + heartbeat)
- **Savings**: 43% reduction
- **Files affected**: 9+ files

**Effort**: 2-3 days
**Risk**: Medium (multiple dependents)

---

### Priority 2: Rename Quiz SessionManager (MEDIUM IMPACT)

**Goal**: Eliminate name collision

**Migration**:
```python
# OLD
from app.domain.quizzes.session_manager import SessionManager

# NEW
from app.domain.quizzes.quiz_session_manager import QuizSessionManager
```

**Steps**:
1. Rename file: `session_manager.py` → `quiz_session_manager.py`
2. Rename class: `SessionManager` → `QuizSessionManager`
3. Update imports in domain/quizzes/__init__.py
4. Update docstrings and comments

**Impact**:
- **Files affected**: 1 file
- **Risk**: Low
- **Effort**: 1 hour

---

### Priority 3: Rename Domain TemplateManager (MEDIUM IMPACT)

**Goal**: Clarify distinction from CRUD manager

**Migration**:
```python
# OLD
from app.domain.flows.core.template_manager import TemplateManager

# NEW
from app.domain.flows.core.message_template_loader import MessageTemplateLoader
```

**Steps**:
1. Rename file: `template_manager.py` → `message_template_loader.py`
2. Rename class: `TemplateManager` → `MessageTemplateLoader`
3. Update imports in flow orchestration
4. Update docstrings

**Impact**:
- **Files affected**: 3-5 files
- **Risk**: Low
- **Effort**: 2 hours

---

### Priority 4: Remove ABTestManager Placeholder (LOW IMPACT)

**Goal**: Remove unused placeholder code

**Current**: `domain/flows/ab_testing/manager.py` (102 lines, not used)

**Options**:
1. **Remove entirely** (recommended - not used)
2. **Implement feature** (1-2 weeks effort)

**Recommendation**: Remove placeholder

**Impact**:
- **Lines removed**: 102
- **Risk**: None (not used)
- **Effort**: 30 minutes

---

## Implementation Timeline

### Sprint 2 (Current)
- ✅ Document consolidation plan
- ✅ Create architecture documentation
- ⏳ Priority 2: Rename quiz SessionManager
- ⏳ Priority 3: Rename domain TemplateManager
- ⏳ Priority 4: Remove ABTestManager

### Sprint 3
- ⏳ Priority 1: Consolidate WebSocket managers
- ⏳ Update all import references
- ⏳ Add migration warnings

### Sprint 4
- ⏳ Validate consolidations
- ⏳ Run comprehensive tests
- ⏳ Clean up deprecated code

---

## Testing Strategy

### Unit Tests
- [ ] Test merged WebSocketManager features
- [ ] Test renamed managers work correctly
- [ ] Verify no regressions

### Integration Tests
- [ ] WebSocket connection lifecycle
- [ ] Quiz session lifecycle
- [ ] Template loading in flows

### Migration Tests
- [ ] Gradual rollout (10% → 50% → 100%)
- [ ] Parallel run validation
- [ ] Performance benchmarks

---

## Rollback Plan

**If issues arise**:
1. Keep original files as `.backup`
2. Feature flag to toggle new/old managers
3. Immediate rollback capability
4. Post-mortem analysis

---

## Success Metrics

- [ ] Zero duplicate WebSocket managers
- [ ] No SessionManager name collisions
- [ ] Clear TemplateManager naming
- [ ] ~40% code reduction in managers
- [ ] Zero functionality regressions
- [ ] All tests passing

---

## Clean Architecture Map

### After Consolidation

```
services/
├── websocket/
│   ├── connection_manager.py       # Unified WebSocket (750 LOC)
│   ├── heartbeat_monitor.py        # Heartbeat logic (150 LOC)
│   └── redis_pubsub_manager.py     # Distributed (407 LOC)
│
├── flow/
│   ├── core/
│   │   └── manager.py              # FlowManager (735 LOC)
│   ├── templates/
│   │   └── manager.py              # FlowTemplateManager (605 LOC)
│   └── integrations/
│       └── manager.py              # IntegrationManager (537 LOC)
│
└── alerts/
    └── alert_manager.py            # AlertManager (608 LOC)

domain/
├── quizzes/
│   └── quiz_session_manager.py     # QuizSessionManager (968 LOC) ← RENAMED
│
└── flows/
    ├── core/
    │   └── message_template_loader.py  # MessageTemplateLoader (232 LOC) ← RENAMED
    ├── state/
    │   └── state_manager.py        # FlowStateManager (253 LOC)
    └── engine/
        └── transition_manager.py   # TransitionManager (125 LOC)

core/
├── session_manager.py              # DB SessionManager (414 LOC)
├── redis_manager.py                # RedisManager (1,161 LOC)
└── lifecycle_manager.py            # LifecycleManager (206 LOC)
```

---

## References

- **Related Documentation**:
  - `FLOW_ENGINE_HIERARCHY.md` - Flow consolidation
  - `backend-refactoring-analysis-2025-11-07.md` - Original analysis

- **Key Files**:
  - WebSocket managers (3 files)
  - SessionManager classes (3 files)
  - TemplateManager classes (2 files)

---

**Last Updated**: 2025-11-07
**Owner**: Backend Architecture Team
**Next Review**: After Sprint 2 completion
