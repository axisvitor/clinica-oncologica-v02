# Hive Mind Analysis: Bugs and Code Patterns

**Agent**: ANALYST (Hive Mind Swarm)
**Swarm ID**: swarm-1766517575567-t3g8mzmze
**Analysis Date**: 2025-12-23
**Total Files Analyzed**: 1,155 Python files
**Coordination**: Integration with RESEARCHER findings

---

## 🔴 P0 - CRITICAL BLOCKERS

### 1. Circular Import Breaking ALL Tests (SEVERITY: CRITICAL)

**Status**: 🚨 **BLOCKING 284 TEST FILES**

**Root Cause**: Module-level code execution in `app/utils/database_optimization.py:182-183`

```python
# CURRENT CODE (BROKEN):
default_settings = {
    "echo": settings.APP_ENABLE_DEBUG,  # ❌ Triggers circular import
    "echo_pool": settings.APP_ENABLE_DEBUG,  # ❌
}
```

**Import Chain**:
```
tests/conftest.py
  → app/db/base.py
    → app/models/base.py
      → app/database.py (line 47: engine = create_optimized_engine(...))
        → app/utils/database_optimization.py:182
          → settings.APP_ENABLE_DEBUG
            → AttributeError (partial module state)
```

**Impact Analysis**:
- 284 test files cannot run
- Zero test coverage possible
- CI/CD pipeline completely blocked
- All pytest commands fail at collection phase

**Evidence**:
- `backend-hormonia/tests/CRITICAL_FIX_CIRCULAR_IMPORT.md`
- `backend-hormonia/tests/TEST_FAILURE_ANALYSIS_REPORT.md`
- `backend-hormonia/docs/TEST_EXECUTION_REPORT_REAL_ENV.md`

**Fix** (5 minutes):
```python
import os

# Read debug setting directly from environment to avoid circular imports
debug_mode = os.getenv("APP_ENABLE_DEBUG", "false").lower() in ("true", "1", "yes", "on")

default_settings = {
    "poolclass": QueuePool,
    "pool_size": 20,
    "max_overflow": 30,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "pool_timeout": 30,
    "echo": debug_mode,  # ✅ Safe
    "echo_pool": debug_mode,  # ✅ Safe
}
```

**Verification**:
```bash
# Test that circular import is fixed
python3 -c "from app.db.base import Base; print('SUCCESS')"
python3 -m pytest tests/ --collect-only
```

---

### 2. FastAPI UploadFile ForwardRef Error (SEVERITY: CRITICAL)

**Status**: 🚨 **BLOCKS PATIENT CSV IMPORT & 19 ROUTERS**

**Root Cause**: PEP 563 (`from __future__ import annotations`) incompatibility with FastAPI's UploadFile

**Affected Files** (19 total):
```
✗ app/api/v2/routers/patients/import_export.py (PRIMARY)
✗ app/api/v2/routers/patients/crud.py
✗ app/api/v2/routers/patients/flow.py
✗ app/api/v2/routers/patients/integrity.py
✗ app/api/v2/routers/quiz_templates.py
✗ app/api/v2/routers/quiz_sessions.py
✗ app/api/v2/routers/enhanced_quiz.py
... (12 more)
```

**Error**:
```python
fastapi.exceptions.FastAPIError: Invalid args for response field!
Hint: check that ForwardRef('UploadFile') is a valid Pydantic field type.
```

**Technical Analysis**:
- PEP 563 converts `UploadFile` → `"UploadFile"` (string)
- FastAPI runtime needs actual `UploadFile` class, not ForwardRef
- Python 3.12.3 + FastAPI 0.115.5 + Pydantic 2.8.x affected

**Fix** (Pattern from working modules):
```python
# REMOVE THIS LINE from all 19 files:
# from __future__ import annotations

# Keep standard imports:
from fastapi import UploadFile, File

async def import_patients(
    file: UploadFile = File(..., description="CSV file"),
    ...
):
```

**Evidence**: `backend-hormonia/docs/BACKEND_STRUCTURAL_ANALYSIS_REPORT.md:13-56`

**Working Reference**: `app/api/v2/routers/upload/` (NO PEP 563, works correctly)

---

### 3. Initialization Timeout (SEVERITY: HIGH)

**Status**: ⚠️ **56s worst-case startup time**

**Bottlenecks Identified**:

1. **Firebase Admin SDK** (10-30s):
   - Synchronous network call to Google OAuth endpoint
   - No timeout protection
   - Blocks entire startup sequence

2. **Redis Connection** (15-20s cumulative):
   - Multiple sequential connection attempts (3x)
   - Long default timeouts (5-10s each)
   - No connection sharing during startup

3. **Sequential Initialization** (18-36s):
   - No parallelization of independent services
   - Monitoring system sequential component init
   - Database connectivity test during startup

**Timeline (Worst Case)**:
```
0s    - App creation starts
2s    - Sentry initialization
12s   - Firebase timeout (10s)
27s   - Redis timeouts (5s × 3 attempts)
37s   - Monitoring init (10s)
42s   - WebSocket manager (5s)
47s   - Redis Pub/Sub (5s)
52s   - Session manager + DB test (5s)
56s   - TOTAL
```

**Impact**:
- Test reliability: 60-70% (frequent timeouts)
- Development cycle delays
- CI/CD pipeline instability

**Evidence**: `backend-hormonia/docs/INITIALIZATION_TIMEOUT_ANALYSIS.md`

**Recommended Fixes**:

**Phase 1 - Quick Wins** (2 hours, 65% improvement):
```python
# 1. Firebase timeout wrapper
async def initialize_firebase_with_timeout(timeout=10):
    try:
        with ThreadPoolExecutor() as executor:
            future = executor.submit(firebase_admin.initialize_app, cred)
            return await asyncio.wait_for(
                asyncio.wrap_future(future),
                timeout=timeout
            )
    except asyncio.TimeoutError:
        logger.warning(f"Firebase timeout - continuing without")
        return None

# 2. Redis fast-fail during startup
STARTUP_REDIS_TIMEOUT = 2  # Reduce from 5-10s
settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = STARTUP_REDIS_TIMEOUT

# 3. Parallel initialization
await asyncio.gather(
    _initialize_redis_websocket_events(app, logger),
    _initialize_websocket_manager(app, logger),
    _initialize_ai_services(app, logger),
    _initialize_enum_validation(app, logger),
    return_exceptions=True
)
```

**Expected Results**:
- Best case: 14s → 6s (57% improvement)
- Worst case: 56s → 12s (79% improvement)
- Test reliability: 60% → 95%+

---

## 🟡 P1 - HIGH PRIORITY ISSUES

### 4. Architecture Violations: Domain → Services (67 occurrences)

**Status**: ⚠️ **VIOLATES CLEAN ARCHITECTURE**

**Pattern Detected**:
```python
# ANTI-PATTERN: Domain importing Services
# File: app/domain/flows/orchestrator/core.py
from app.services.flow_core import FlowCoreService  # ❌

class Orchestrator:
    def __init__(self):
        self.flow_service = FlowCoreService()  # ❌ Tight coupling
```

**Files with Most Violations**:
- `app/domain/flows/orchestrator/core.py` (5 service imports)
- `app/domain/flows/core/step_executor.py` (4 imports)
- `app/domain/flows/core/message_handler.py` (4 imports)
- `app/domain/flows/core/flow_service.py` (3 imports)
- `app/domain/quizzes/integration/flow_integration/trigger_service.py` (3 imports)

**Impact**:
- Tight coupling between layers
- Difficult to test in isolation
- Circular import risk (2 detected)
- Violates dependency inversion principle

**Correct Pattern**:
```python
# CORRECT: Use dependency injection with protocols
from typing import Protocol

class IFlowService(Protocol):
    """Domain interface - no implementation details."""
    async def execute_flow(self, flow_id: str) -> FlowResult: ...

class Orchestrator:
    def __init__(self, flow_service: IFlowService):
        self.flow_service = flow_service  # ✅ Injected dependency
```

**Refactoring Plan**:
1. Create `app/domain/interfaces/` package
2. Extract Protocol interfaces for all services used by domain
3. Update domain classes to accept interfaces
4. Services implement interfaces
5. Use dependency injection in routers/factories

**Estimated Effort**: 2-3 days

---

### 5. N+1 Query Problems (25+ files)

**Status**: ⚠️ **PERFORMANCE DEGRADATION**

**Problem Pattern**:
```python
# ANTI-PATTERN: N+1 queries
patients = session.query(Patient).all()
for patient in patients:  # 1 query
    print(patient.doctor.name)  # N queries (lazy load)
    print(patient.quiz_sessions)  # N queries
```

**Affected Areas**:
- `app/services/admin/admin_user_service/bulk_operations.py`
- `app/repositories/patient/__init__.py`
- `app/agents/patient/flow_coordinator/state_manager.py`
- `app/services/reporting/report.py`
- `app/services/analytics/data_aggregator.py`

**Evidence**:
- 25 files with N+1 query patterns
- `backend-hormonia/tests/repositories/test_patient_n1_optimization.py` (test exists!)
- `backend-hormonia/app/repositories/patient/eager_loading.py` (solution exists!)

**Correct Implementation** (ALREADY EXISTS):
```python
# ✅ OPTIMIZED: Using eager loading
from app.repositories.patient.eager_loading import PatientEagerLoadingMixin

class PatientRepository(PatientEagerLoadingMixin):
    def get_patients_with_relations(self):
        query = session.query(Patient)
        # Apply optimal loading strategies
        query = self._apply_eager_loading(query, [
            "doctor",  # joinedload (1:1)
            "quiz_sessions",  # selectinload (1:many)
            "messages",  # selectinload + nested joinedload
        ])
        return query.all()  # 2-3 queries instead of N+1
```

**Fix Status**:
- ✅ Solution implemented: `app/repositories/patient/eager_loading.py`
- ❌ Not consistently applied across codebase
- ✅ Test coverage exists

**Action Required**: Apply `_apply_eager_loading()` pattern to 25+ affected files

---

### 6. Saga Transaction Pattern Issues

**Status**: ⚠️ **PARTIAL IMPLEMENTATION**

**Current Saga Model**: `app/models/patient_onboarding_saga.py`

**Strengths**:
- ✅ Complete saga state machine (10 states)
- ✅ Retry logic with exponential backoff
- ✅ Compensation tracking
- ✅ JSONB execution log
- ✅ Proper indexes

**Issues Detected**:

1. **Deprecated Firebase Step** (Line 41):
```python
# @deprecated - Firebase integration removed
STEP_2_FIREBASE_USER_CREATED = "STEP_2_FIREBASE_USER_CREATED"
```
**Impact**: State machine has dead state, adds complexity

2. **Saga Orchestrator Not Found**:
```bash
$ find . -name "*saga_orchestrator*"
# No results - referenced in comments but doesn't exist
```

3. **Transaction Boundary Issues**:
- Saga spans multiple database transactions
- No clear compensation logic implementation
- Risk of partial commits

**Evidence**: `backend-hormonia/docs/SAGA_TRANSACTION_CONFLICT_ANALYSIS.md` (file not found, but referenced)

**Recommended Fixes**:
1. Remove deprecated STEP_2 or mark clearly as skipped
2. Implement saga orchestrator if missing
3. Add Unit of Work pattern for transaction boundaries
4. Document compensation actions

---

## 🟢 P2 - MEDIUM PRIORITY IMPROVEMENTS

### 7. Python 3.13 Compatibility (988 instances)

**Status**: ℹ️ **19.1% modernization complete**

**Deprecated Type Hints**:
- `Dict[]` → `dict[]` (506 files)
- `List[]` → `list[]` (400 files)
- `Tuple[]` → `tuple[]` (63 files)
- `Set[]` → `set[]` (19 files)

**Missing Future Annotations**: 756 files (80.9%)

**Impact**:
- Forward compatibility issues
- Larger bytecode (string annotations not deferred)
- Type checker performance degradation

**Automated Fix Available**:
```bash
# Add future annotations to all type-hinted files
python3 scripts/add_future_annotations.py

# Modernize type hints
python3 scripts/modernize_type_hints.py
```

**Estimated Effort**: 2-4 hours (automated + review)

---

### 8. Empty __init__.py Files (139 instances)

**Status**: ℹ️ **MODULE DISCOVERABILITY ISSUE**

**Critical Directories**:
- `app/core/__init__.py` (empty, 49 modules)
- `app/models/__init__.py` (empty, 35 modules)
- `app/repositories/__init__.py` (empty, 20 modules)
- `app/middleware/__init__.py` (empty, 35 modules)
- `app/monitoring/__init__.py` (empty, 26 modules)

**Impact**:
- Difficult to discover available classes
- Requires deep import paths
- No centralized module API

**Recommended Structure**:
```python
# app/models/__init__.py (SHOULD EXPORT)
"""Database models."""
from __future__ import annotations

from .patient import Patient
from .user import User, AdminUser
from .quiz import Quiz, QuizSession, QuizResponse, QuizTemplate
from .flow import Flow, FlowState

__all__ = [
    "Patient",
    "User",
    "AdminUser",
    "Quiz",
    "QuizSession",
    "QuizResponse",
    "QuizTemplate",
    "Flow",
    "FlowState",
]
```

**Estimated Effort**: 4-6 hours (manual review + generation)

---

### 9. Duplicate Imports (206 files)

**Status**: ℹ️ **CODE QUALITY ISSUE**

**Top Offenders**:

**celery_app.py**:
```python
Line 12:  from app.config import settings
Line 263: from app.config import settings  # ❌ DUPLICATE

Line 6:   import asyncio
Line 303: import asyncio  # ❌ DUPLICATE
```

**api/websockets.py**:
```python
Line 131: from app.database import get_db
Line 301: from app.database import get_db  # ❌ DUPLICATE
Line 477: from app.database import get_db  # ❌ DUPLICATE (3rd time!)
```

**core/lifespan.py**:
```python
Line 165: from app.services.websocket import get_websocket_manager
Line 340: from app.services.websocket import get_websocket_manager  # ❌ DUPLICATE

Line 240: import sys
Line 593: import sys  # ❌ DUPLICATE
```

**Impact**:
- Reduced code readability
- Slight parsing overhead
- Indicates poor refactoring/copy-paste

**Automated Fix**:
```bash
# Remove duplicate imports
python3 scripts/remove_duplicate_imports.py
```

**Estimated Effort**: 30 minutes (automated)

---

## 📊 CODE PATTERN ANALYSIS

### Exception Handling Patterns

**Custom Exception Hierarchy** (19 custom exceptions found):

```python
# app/core/exceptions.py - WELL STRUCTURED ✅

HormoniaException (base)
├── APIException
│   ├── BusinessRuleError
│   ├── ValidationError
│   ├── NotFoundError (404)
│   ├── ConflictError (409)
│   ├── UnauthorizedError (401)
│   ├── ForbiddenError (403)
│   ├── BadRequestError (400)
│   ├── RateLimitError (429)
│   ├── ServiceUnavailableError (503)
│   └── ExternalServiceError
├── DatabaseError
├── ProcessingError
├── FlowException
│   ├── FlowStateNotFoundError
│   ├── FlowValidationError
│   ├── FlowStateConflictError
│   └── FlowOperationError
└── CacheError
```

**Additional Specialized Exceptions**:
- `app/core/encryption.py`: `EncryptionError`, `DecryptionError`
- `app/core/database.py`: `RLSError`
- `app/core/distributed_lock.py`: `LockAcquisitionError`, `LockReleaseError`
- `app/core/retry.py`: `RetryExhaustedError`
- `app/domain/analytics/analytics_service.py`: `AnalyticsError`

**Pattern Quality**: ✅ **EXCELLENT**
- Proper inheritance hierarchy
- HTTP status code mapping
- Domain-specific exceptions
- Clear error classification

---

### Database Query Optimization Patterns

**Positive Patterns Detected**:

1. **Eager Loading Mixin** ✅:
```python
# app/repositories/patient/eager_loading.py
class PatientEagerLoadingMixin:
    def _apply_eager_loading(self, query, eager_load):
        # joinedload for 1:1 (doctor)
        query = query.options(joinedload(Patient.doctor))

        # selectinload for 1:many (quiz_sessions)
        if "quiz_sessions" in eager_load:
            query = query.options(selectinload(Patient.quiz_sessions))

        # Nested loading: selectinload + joinedload
        if "messages" in eager_load:
            query = query.options(
                selectinload(Patient.messages).joinedload(Message.sender)
            )

        return query
```

2. **Query Performance Monitoring** ✅:
```python
# app/utils/database_optimization.py
class DatabaseOptimizer:
    def log_query(self, query: str, duration_ms: float, row_count: int):
        stats = QueryStats(query=query, duration_ms=duration_ms, row_count=row_count)
        if duration_ms > self.slow_query_threshold_ms:
            logger.warning(f"Slow query detected: {duration_ms}ms")
```

3. **Connection Pooling** ✅:
```python
default_settings = {
    "poolclass": QueuePool,
    "pool_size": 20,
    "max_overflow": 30,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}
```

**Issues**:
- Query optimization patterns not consistently applied
- Some services still use lazy loading
- No automatic slow query alerting

---

### Testing Infrastructure

**Test Organization**: ✅ **WELL STRUCTURED**

```
tests/
├── api/                       # API endpoint tests (~80 files)
│   ├── critical/             # Critical path tests
│   └── v2/                   # V2 API tests
├── services/                 # Service layer tests (~45 files)
├── integration/              # Integration tests (~30 files)
├── unit/                     # Unit tests (~25 files)
├── security/                 # Security tests (~20 files)
├── domain/                   # Domain logic tests (~15 files)
└── ... (25+ categories)

Total: 284 test files
```

**Conftest Files** (8 found):
- `tests/conftest.py` (root - BLOCKS all tests due to circular import)
- `tests/api/critical/conftest.py`
- `tests/api/v2/conftest.py`
- `tests/e2e/conftest.py`
- `tests/integration/conftest.py`
- `tests/services/follow_up/conftest.py`
- `tests/services/webhook/conftest.py`
- `tests/services/websocket/conftest.py`

**Testing Patterns**:
- ✅ Comprehensive coverage planned
- ✅ Well-organized by layer/feature
- ❌ **BLOCKED** by circular import (P0 issue)
- ✅ N+1 query tests exist
- ✅ Performance benchmark tests exist

---

## 🎯 PRIORITIZED FIX RECOMMENDATIONS

### Phase 1: Emergency Fixes (Day 1 - 4 hours)

**P0-1: Fix Circular Import** (5 minutes)
- File: `app/utils/database_optimization.py:182-183`
- Change: Use `os.getenv()` instead of `settings.APP_ENABLE_DEBUG`
- Impact: Unblocks 284 test files

**P0-2: Remove PEP 563 from 19 Router Files** (2 hours)
- Files: `app/api/v2/routers/patients/*.py` + 14 others
- Change: Delete `from __future__ import annotations` line
- Impact: Fixes UploadFile ForwardRef error

**P0-3: Add Timeouts to Firebase/Redis** (2 hours)
- Files: `app/core/lifespan.py`, `app/services/firebase_auth_service.py`
- Change: Implement timeout wrappers (10s Firebase, 2s Redis startup)
- Impact: 56s → 20s startup time (65% improvement)

**Verification**:
```bash
# Test circular import fix
python3 -c "from app.db.base import Base; print('✅ Circular import fixed')"

# Test pytest collection
python3 -m pytest tests/ --collect-only

# Test router imports
python3 -c "from app.api.v2 import api_v2_router; print('✅ Routers work')"

# Measure startup time
time uvicorn app.main:app --help
```

---

### Phase 2: Structural Improvements (Week 1 - 2 days)

**P1-1: Implement Parallel Initialization** (4 hours)
- File: `app/core/lifespan.py`
- Change: Use `asyncio.gather()` for independent services
- Impact: 20s → 12s startup (40% additional improvement)

**P1-2: Apply Eager Loading Pattern** (8 hours)
- Files: 25 files with N+1 queries
- Change: Use `PatientEagerLoadingMixin._apply_eager_loading()`
- Impact: 50-90% query reduction in affected endpoints

**P1-3: Refactor Domain → Services** (2 days)
- Create: `app/domain/interfaces/` package
- Files: 67 domain files importing services
- Change: Extract protocols, use dependency injection
- Impact: Proper architectural layers, easier testing

---

### Phase 3: Quality Improvements (Week 2 - 1 week)

**P2-1: Python 3.13 Modernization** (4 hours)
- Files: 756 files missing future annotations
- Change: Automated script + review
- Impact: Forward compatibility, smaller bytecode

**P2-2: Populate __init__.py Files** (6 hours)
- Files: 139 empty __init__.py files
- Change: Generate exports for key modules
- Impact: Better module discoverability

**P2-3: Remove Duplicate Imports** (30 minutes)
- Files: 206 files with duplicates
- Change: Automated cleanup
- Impact: Code cleanliness

**P2-4: Fix Saga Transaction Boundaries** (8 hours)
- Files: `app/models/patient_onboarding_saga.py`, orchestrator
- Change: Implement Unit of Work pattern, document compensations
- Impact: Safer distributed transactions

---

## 📈 EXPECTED OUTCOMES

| Metric | Before | After Phase 1 | After Phase 2 | After Phase 3 |
|--------|--------|---------------|---------------|---------------|
| Test Execution | 0% (blocked) | 100% | 100% | 100% |
| Startup Time (worst) | 56s | 20s (-65%) | 12s (-79%) | 8s (-86%) |
| Startup Time (best) | 14s | 10s (-30%) | 6s (-57%) | 3s (-79%) |
| Test Reliability | 0% | 85% | 95% | 99%+ |
| N+1 Queries | Widespread | Widespread | Reduced 80% | Optimized |
| Architecture Violations | 67 | 67 | 0 | 0 |
| Python 3.13 Ready | ~20% | ~20% | ~25% | 100% |
| Future Annotations | 19.1% | 19.1% | 25% | 100% |
| Empty __init__.py | 139 | 139 | 139 | ~50 |
| Duplicate Imports | 206 | 206 | 206 | 0 |

---

## 🤝 COORDINATION WITH OTHER AGENTS

### Memory Keys Stored:
```bash
npx claude-flow@alpha hooks post-edit --memory-key "hive/analysis/p0_blockers" --value "Circular import + UploadFile ForwardRef"
npx claude-flow@alpha hooks post-edit --memory-key "hive/analysis/performance" --value "56s startup, Firebase+Redis bottlenecks"
npx claude-flow@alpha hooks post-edit --memory-key "hive/analysis/architecture" --value "67 domain→services violations"
npx claude-flow@alpha hooks post-edit --memory-key "hive/analysis/tests" --value "284 files blocked by circular import"
```

### Next Agent Handoffs:

**→ CODER Agent**:
- Implement P0-1: Circular import fix (5 minutes)
- Implement P0-2: Remove PEP 563 from 19 files (2 hours)
- Implement P0-3: Add timeout wrappers (2 hours)

**→ TESTER Agent**:
- Verify circular import fix
- Run full test suite after fixes
- Create regression tests for initialization timeouts
- Performance benchmarks for N+1 query improvements

**→ REVIEWER Agent**:
- Code review all P0 fixes
- Architecture review for domain/services refactoring
- Security review for timeout implementations

---

## 🔍 ANALYSIS METHODOLOGY

**Tools Used**:
- Python AST parsing for import analysis
- pytest collection for test structure
- Static code analysis for pattern detection
- Cross-referencing with existing debug reports

**Files Analyzed**:
- 1,155 Python source files
- 284 test files
- 20+ documentation/debug reports
- 8 conftest.py configurations

**Patterns Searched**:
- Circular import indicators
- N+1 query patterns (lazy load)
- Exception hierarchy
- Saga transaction patterns
- Initialization bottlenecks
- Type hint modernization

---

## 📚 REFERENCES

**Critical Documentation**:
- `backend-hormonia/tests/CRITICAL_FIX_CIRCULAR_IMPORT.md`
- `backend-hormonia/tests/TEST_FAILURE_ANALYSIS_REPORT.md`
- `backend-hormonia/docs/INITIALIZATION_TIMEOUT_ANALYSIS.md`
- `backend-hormonia/docs/BACKEND_STRUCTURAL_ANALYSIS_REPORT.md`
- `backend-hormonia/docs/CODEBASE_ANALYSIS_REPORT.md`
- `backend-hormonia/docs/CRITICAL_FILES_TO_FIX.md`

**Existing Solutions**:
- `app/repositories/patient/eager_loading.py` (N+1 fix pattern)
- `app/core/exceptions.py` (exception hierarchy)
- `app/models/patient_onboarding_saga.py` (saga pattern)
- `app/utils/database_optimization.py` (query monitoring)

---

**Report Complete** | ANALYST Agent | Hive Mind Swarm
**Coordination Status**: ✅ Ready for handoff to CODER agent
**Critical Path**: P0-1 → P0-2 → P0-3 (sequential, 4 hours total)
