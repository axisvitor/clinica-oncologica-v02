# Patient Repository Refactoring Plan

## Executive Summary

**Current State:** God Class with 1,015 lines containing 18 public methods + 5 private/helper methods
**Target State:** 4 specialized repositories with clear responsibilities
**Estimated Complexity Reduction:** 65% per file (from 1,015 → ~250 lines average)
**Migration Strategy:** Backward-compatible facade pattern with gradual migration

---

## 📊 Current Method Analysis

### Method Inventory (23 Total Methods)

#### Query Methods (9 methods - 40%)
1. `get_by_id(patient_id, eager_load, include)` - Line 575
2. `get_by_id_including_deleted(patient_id)` - Line 610
3. `get_by_phone(phone)` - Line 614
4. `get_by_doctor(doctor_id, skip, limit, eager_load)` - Line 621
5. `get_all_active(skip, limit, eager_load)` - Line 656
6. `get_all_deleted(skip, limit)` - Line 691
7. `get_by_idempotency_key(idempotency_key)` - Line 729
8. `count_active(**filters)` - Line 697
9. `count_deleted()` - Line 707

#### List/Search Methods (3 methods - 13%)
10. `list_v2(filters, cursor_data, limit, sort_by, sort_order, eager_load)` - Line 153
11. `list_patients_optimized(doctor_id, filters, cursor_data, limit, sort_by, sort_order)` - Line 398 (async)
12. `search_active(search_term, skip, limit)` - Line 711

#### Cache Methods (3 methods - 13%)
13. `_get_cache_key(prefix, filters)` - Line 121 (private)
14. `_get_cached_count(filters)` - Line 128 (private)
15. `_set_cached_count(filters, count, ttl)` - Line 142 (private)

#### Command Methods (1 method - 4%)
16. `hard_delete(patient_id, audit_reason)` - Line 746 (async)

#### Helper/Utility Methods (7 methods - 30%)
17. `__init__(db)` - Line 49
18. `redis` (property) - Line 54
19. `_build_search_criteria(search_term)` - Line 65 (private)
20. `_create_deletion_audit(patient_id, reason)` - Line 872 (async, private)
21. `_looks_like_email(search_term)` - Line 26 (module-level)
22. `_looks_like_phone(search_term)` - Line 31 (module-level)

**Note:** Methods from BaseRepository (create, update, delete, soft_delete) are inherited and not counted.

---

## 🎯 Proposed Architecture

### 1. **PatientQueryRepository** (Core Read Operations)
**File:** `app/repositories/patient/query_repository.py`
**Lines:** ~280
**Responsibility:** Single-record and batch retrieval operations

**Methods to Move:**
- `get_by_id(patient_id, eager_load, include)` ✓
- `get_by_id_including_deleted(patient_id)` ✓
- `get_by_phone(phone)` ✓
- `get_by_doctor(doctor_id, skip, limit, eager_load)` ✓
- `get_all_active(skip, limit, eager_load)` ✓
- `get_all_deleted(skip, limit)` ✓
- `get_by_idempotency_key(idempotency_key)` ✓
- `count_active(**filters)` ✓
- `count_deleted()` ✓

**Dependencies:**
```python
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func
from app.models.patient import Patient, FlowState
from app.models.message import Message
from app.repositories.base import BaseRepository
```

**Key Features:**
- Eager loading strategies (joinedload, selectinload)
- Soft delete filtering
- N+1 query prevention
- Doctor-scoped queries

---

### 2. **PatientSearchRepository** (Advanced Search & Filtering)
**File:** `app/repositories/patient/search_repository.py`
**Lines:** ~380
**Responsibility:** Complex filtering, pagination, and search operations

**Methods to Move:**
- `list_v2(filters, cursor_data, limit, sort_by, sort_order, eager_load)` ✓
- `list_patients_optimized(doctor_id, filters, cursor_data, limit, ...)` (async) ✓
- `search_active(search_term, skip, limit)` ✓
- `_build_search_criteria(search_term)` ✓ (private)

**Module-Level Functions to Include:**
- `_looks_like_email(search_term)` ✓
- `_looks_like_phone(search_term)` ✓

**Dependencies:**
```python
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, date
import json
import base64
import re
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, desc, asc, func
from app.models.patient import Patient, FlowState
from app.models.message import Message
from app.services.encryption import get_unified_encryption_service
from app.services.encryption.unified_encryption_service import FieldType
```

**Key Features:**
- LGPD-compliant search (hash-based email/phone lookup)
- Cursor-based pagination
- Advanced filtering (treatment, dates, status)
- Complex eager loading configurations
- Sort strategies

---

### 3. **PatientCacheRepository** (Redis Caching Layer)
**File:** `app/repositories/patient/cache_repository.py`
**Lines:** ~150
**Responsibility:** Redis caching for performance optimization

**Methods to Move:**
- `redis` (property) ✓
- `_get_cache_key(prefix, filters)` ✓ (private)
- `_get_cached_count(filters)` ✓ (private)
- `_set_cached_count(filters, count, ttl)` ✓ (private)

**New Methods to Add:**
```python
def invalidate_count_cache(self, filters: Dict[str, Any]) -> None:
    """Invalidate cached count for specific filters"""

def invalidate_all_patient_cache(self, doctor_id: Optional[UUID] = None) -> None:
    """Invalidate all patient-related cache entries"""

def get_cached_patient(self, patient_id: UUID) -> Optional[Patient]:
    """Get cached patient by ID"""

def set_cached_patient(self, patient: Patient, ttl: int = 300) -> None:
    """Cache patient object"""
```

**Dependencies:**
```python
from typing import Optional, Dict, Any
from uuid import UUID
import hashlib
import json
from app.core.redis_unified import get_redis_client
```

**Key Features:**
- Lazy Redis client initialization
- Deterministic cache key generation
- Count caching with 60s TTL
- Graceful degradation (no Redis = no cache)
- Patient object caching (new)

---

### 4. **PatientCommandRepository** (Write Operations)
**File:** `app/repositories/patient/command_repository.py`
**Lines:** ~200
**Responsibility:** Data mutation and LGPD compliance operations

**Methods to Move:**
- `hard_delete(patient_id, audit_reason)` (async) ✓
- `_create_deletion_audit(patient_id, reason)` (async, private) ✓

**Methods from BaseRepository to Override/Enhance:**
```python
async def create(self, obj_in: Dict[str, Any]) -> Patient:
    """Create patient with cache invalidation"""

async def update(self, db_obj: Patient, obj_in: Dict[str, Any]) -> Patient:
    """Update patient with cache invalidation"""

async def soft_delete(self, patient_id: UUID) -> bool:
    """Soft delete patient with cache invalidation"""
```

**Dependencies:**
```python
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import delete
from sqlalchemy.orm import Session
import logging
from app.models.patient import Patient
from app.repositories.base import BaseRepository
from app.repositories.patient.cache_repository import PatientCacheRepository
```

**Key Features:**
- LGPD Art. 16 compliance (hard delete)
- Audit trail creation
- Cache invalidation on mutations
- Idempotency key handling
- Encryption integration

---

## 🏗️ New File Structure

```
app/repositories/patient/
├── __init__.py                    # Facade pattern for backward compatibility
├── query_repository.py            # ~280 lines (27% of original)
├── search_repository.py           # ~380 lines (37% of original)
├── cache_repository.py            # ~150 lines (15% of original)
├── command_repository.py          # ~200 lines (20% of original)
└── shared/
    ├── __init__.py
    └── types.py                   # Shared types and constants
```

**Total New Lines:** ~1,010 lines (distributed)
**Complexity Reduction per File:** 65% average (1,015 → ~250 avg)

---

## 🔄 Migration Strategy (Backward Compatible)

### Phase 1: Create New Repositories (Week 1)

**Step 1.1:** Create directory structure
```bash
mkdir -p app/repositories/patient/shared
touch app/repositories/patient/__init__.py
touch app/repositories/patient/query_repository.py
touch app/repositories/patient/search_repository.py
touch app/repositories/patient/cache_repository.py
touch app/repositories/patient/command_repository.py
touch app/repositories/patient/shared/__init__.py
touch app/repositories/patient/shared/types.py
```

**Step 1.2:** Implement new repositories with tests
- Start with `PatientCacheRepository` (no dependencies)
- Then `PatientQueryRepository` (uses cache)
- Then `PatientSearchRepository` (uses cache and query)
- Finally `PatientCommandRepository` (uses cache)

**Step 1.3:** Create comprehensive test suites
```python
# tests/repositories/patient/test_query_repository.py
# tests/repositories/patient/test_search_repository.py
# tests/repositories/patient/test_cache_repository.py
# tests/repositories/patient/test_command_repository.py
```

### Phase 2: Backward-Compatible Facade (Week 2)

**File:** `app/repositories/patient/__init__.py`

```python
"""
Patient repository with backward-compatible facade pattern.

MIGRATION PHASE: This facade delegates to specialized repositories
while maintaining the original PatientRepository interface.
"""
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.repositories.base import BaseRepository

# Import specialized repositories
from .query_repository import PatientQueryRepository
from .search_repository import PatientSearchRepository
from .cache_repository import PatientCacheRepository
from .command_repository import PatientCommandRepository


class PatientRepository(BaseRepository[Patient]):
    """
    FACADE PATTERN: Backward-compatible interface that delegates to
    specialized repositories.

    DEPRECATION NOTICE: Direct instantiation is deprecated.
    Use specialized repositories:
    - PatientQueryRepository: Single-record queries
    - PatientSearchRepository: List, filter, search operations
    - PatientCacheRepository: Redis caching
    - PatientCommandRepository: Create, update, delete operations

    This facade will be removed in v3.0.0 (target: Q3 2025)
    """

    def __init__(self, db: Session):
        super().__init__(db, Patient)

        # Initialize specialized repositories
        self._query_repo = PatientQueryRepository(db)
        self._search_repo = PatientSearchRepository(db)
        self._cache_repo = PatientCacheRepository(db)
        self._command_repo = PatientCommandRepository(db)

        # Share cache repository across all repos
        self._query_repo._cache_repo = self._cache_repo
        self._search_repo._cache_repo = self._cache_repo
        self._command_repo._cache_repo = self._cache_repo

    # ========================================
    # QUERY METHODS (Delegated)
    # ========================================

    def get_by_id(self, patient_id: UUID, eager_load: bool = True,
                  include: List[str] = None) -> Optional[Patient]:
        """Delegate to PatientQueryRepository"""
        return self._query_repo.get_by_id(patient_id, eager_load, include)

    def get_by_phone(self, phone: str) -> Optional[Patient]:
        """Delegate to PatientQueryRepository"""
        return self._query_repo.get_by_phone(phone)

    def get_by_doctor(self, doctor_id: UUID, skip: int = 0,
                      limit: int = 100, eager_load: bool = True) -> List[Patient]:
        """Delegate to PatientQueryRepository"""
        return self._query_repo.get_by_doctor(doctor_id, skip, limit, eager_load)

    def get_all_active(self, skip: int = 0, limit: int = 100,
                       eager_load: bool = True) -> List[Patient]:
        """Delegate to PatientQueryRepository"""
        return self._query_repo.get_all_active(skip, limit, eager_load)

    def count_active(self, **filters) -> int:
        """Delegate to PatientQueryRepository"""
        return self._query_repo.count_active(**filters)

    # ========================================
    # SEARCH METHODS (Delegated)
    # ========================================

    def list_v2(self, filters: Dict[str, Any], cursor_data: Optional[Dict[str, Any]] = None,
                limit: int = 20, sort_by: str = "created_at",
                sort_order: str = "desc", eager_load: List[str] = None) -> Tuple:
        """Delegate to PatientSearchRepository"""
        return self._search_repo.list_v2(
            filters, cursor_data, limit, sort_by, sort_order, eager_load
        )

    async def list_patients_optimized(self, doctor_id: str,
                                      filters: Optional[Dict[str, Any]] = None,
                                      cursor_data: Optional[Dict[str, Any]] = None,
                                      limit: int = 20, sort_by: str = "created_at",
                                      sort_order: str = "desc") -> Tuple:
        """Delegate to PatientSearchRepository"""
        return await self._search_repo.list_patients_optimized(
            doctor_id, filters, cursor_data, limit, sort_by, sort_order
        )

    def search_active(self, search_term: str, skip: int = 0,
                      limit: int = 100) -> List[Patient]:
        """Delegate to PatientSearchRepository"""
        return self._search_repo.search_active(search_term, skip, limit)

    # ========================================
    # COMMAND METHODS (Delegated)
    # ========================================

    async def hard_delete(self, patient_id: UUID, *,
                          audit_reason: str = None) -> bool:
        """Delegate to PatientCommandRepository"""
        return await self._command_repo.hard_delete(patient_id, audit_reason=audit_reason)


# Export specialized repositories for direct use
__all__ = [
    "PatientRepository",           # Facade (deprecated)
    "PatientQueryRepository",      # Direct use recommended
    "PatientSearchRepository",     # Direct use recommended
    "PatientCacheRepository",      # Direct use recommended
    "PatientCommandRepository",    # Direct use recommended
]
```

### Phase 3: Service Layer Migration (Week 3-4)

**Migration Priority:**

**High Priority Services (Week 3):**
1. `app/services/base.py` - Base service class (removed in cleanup wave on 2026-02-10)
2. `app/services/container.py` - Dependency injection container
3. `app/services/flow/core/manager.py` - Flow management
4. `app/services/analytics/data_aggregator.py` - Analytics

**Medium Priority Services (Week 4):**
5. `app/services/alerts/adapter.py`
6. `app/services/alerts/alert_manager.py`
7. `app/services/analytics/data_extraction/service.py`
8. `app/services/flow/implementations.py`

**Migration Pattern:**

```python
# BEFORE (Old)
from app.repositories.patient import PatientRepository

class PatientService:
    def __init__(self, db: Session):
        self.patient_repo = PatientRepository(db)

    def get_patient(self, patient_id: UUID):
        return self.patient_repo.get_by_id(patient_id)

# AFTER (New - Specialized)
from app.repositories.patient import PatientQueryRepository

class PatientService:
    def __init__(self, db: Session):
        self.patient_query = PatientQueryRepository(db)

    def get_patient(self, patient_id: UUID):
        return self.patient_query.get_by_id(patient_id)
```

### Phase 4: Remove Facade (Week 8+ / v3.0.0)

**Prerequisites:**
- All services migrated to specialized repositories
- All tests passing with specialized repositories
- Performance benchmarks showing no regression
- Documentation updated

**Steps:**
1. Add deprecation warnings to facade methods
2. Monitor usage metrics (add telemetry)
3. Create migration guide for external consumers
4. Remove facade in major version bump (v3.0.0)

---

## 📈 Benefits & Metrics

### Complexity Reduction

| Repository | Lines | Methods | Responsibility Index* |
|-----------|-------|---------|---------------------|
| **Original** | 1,015 | 23 | 23.4 |
| **QueryRepository** | ~280 | 9 | 7.3 |
| **SearchRepository** | ~380 | 7 | 11.9 |
| **CacheRepository** | ~150 | 7 | 4.7 |
| **CommandRepository** | ~200 | 5 | 6.7 |

*Responsibility Index = (Lines × Methods) / 1000

### Performance Improvements

**Before:**
- God class loads all dependencies (encryption, Redis, complex filters)
- Hard to cache individual operations
- All relationships eager loaded by default

**After:**
- Specialized repositories load only what they need
- Cache repository isolated for better testing/mocking
- Granular control over eager loading
- Easier to optimize individual query patterns

### Maintainability Improvements

**Before:**
- Single file with 1,015 lines
- Mixed concerns (query, cache, search, command)
- Hard to test specific features
- Tight coupling to encryption service

**After:**
- 4 files averaging 250 lines each
- Clear separation of concerns
- Easy to test in isolation
- Dependency injection for cross-cutting concerns

### Testing Improvements

**Test Coverage Strategy:**

```python
# Easy to mock dependencies
def test_query_without_cache(mocker):
    cache_repo = mocker.Mock(spec=PatientCacheRepository)
    cache_repo.get_cached_count.return_value = None

    query_repo = PatientQueryRepository(db)
    query_repo._cache_repo = cache_repo

    patients = query_repo.get_all_active(limit=10)
    assert len(patients) <= 10
    cache_repo.get_cached_count.assert_called_once()
```

**Test Execution Time:**
- Before: ~12s for full repository test suite
- After: ~3s per specialized repository (parallel execution)
- Total: ~12s but can run in parallel (effective: ~4s)

---

## 🚨 Risk Assessment

### High Risk Items

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Breaking changes in production | **CRITICAL** | Use facade pattern for backward compatibility |
| Performance regression | **HIGH** | Comprehensive benchmarking before/after |
| Cache invalidation bugs | **HIGH** | Extensive testing of mutation + cache interplay |
| Missing migrations | **MEDIUM** | Gradual rollout with feature flags |

### Migration Risks

**Risk:** Services might instantiate multiple repository instances
**Mitigation:** Use dependency injection container to share instances

**Risk:** Circular dependencies between repositories
**Mitigation:** Cache repository is leaf node (no deps), others depend on it

**Risk:** Lost eager loading optimizations
**Mitigation:** Document and test all eager loading configurations

---

## 📋 Implementation Checklist

### Phase 1: New Repositories ✓
- [ ] Create directory structure
- [ ] Implement `PatientCacheRepository`
  - [ ] Unit tests
  - [ ] Integration tests with Redis
  - [ ] Graceful degradation tests
- [ ] Implement `PatientQueryRepository`
  - [ ] Unit tests
  - [ ] N+1 query prevention tests
  - [ ] Eager loading tests
- [ ] Implement `PatientSearchRepository`
  - [ ] Unit tests
  - [ ] LGPD compliance tests (hash search)
  - [ ] Cursor pagination tests
  - [ ] Performance benchmarks
- [ ] Implement `PatientCommandRepository`
  - [ ] Unit tests
  - [ ] LGPD hard delete tests
  - [ ] Audit trail tests
  - [ ] Cache invalidation tests

### Phase 2: Facade Pattern ✓
- [ ] Implement backward-compatible facade
- [ ] Add deprecation notices
- [ ] Update type hints and docstrings
- [ ] Create migration guide documentation

### Phase 3: Service Migration ✓
- [ ] Migrate high-priority services (Week 3)
- [ ] Migrate medium-priority services (Week 4)
- [ ] Update all tests
- [ ] Performance regression tests

### Phase 4: Documentation & Cleanup ✓
- [ ] Update API documentation
- [ ] Create architecture decision record (ADR)
- [ ] Update database optimization guide
- [ ] Remove old repository (v3.0.0)

---

## 🔍 Code Examples

### Example 1: Query Repository Usage

```python
from app.repositories.patient import PatientQueryRepository

# Initialize
query_repo = PatientQueryRepository(db)

# Get single patient with eager loading
patient = query_repo.get_by_id(
    patient_id=patient_uuid,
    eager_load=True,
    include=["quiz_sessions", "flow_states", "doctor"]
)

# Get patients by doctor
patients = query_repo.get_by_doctor(
    doctor_id=doctor_uuid,
    skip=0,
    limit=50,
    eager_load=True
)

# Count active patients
count = query_repo.count_active(doctor_id=doctor_uuid)
```

### Example 2: Search Repository Usage

```python
from app.repositories.patient import PatientSearchRepository

# Initialize
search_repo = PatientSearchRepository(db)

# Advanced filtering with cursor pagination
patients, has_more, next_cursor, total = search_repo.list_v2(
    filters={
        "doctor_id": doctor_uuid,
        "search": "john@example.com",  # LGPD-compliant hash search
        "status": FlowState.ACTIVE,
        "treatment_type": "chemotherapy",
        "created_after": datetime(2024, 1, 1)
    },
    cursor_data=None,  # First page
    limit=20,
    sort_by="created_at",
    sort_order="desc",
    eager_load=["messages", "quiz_sessions"]
)

# Optimized listing (async)
patients, has_more, cursor, total = await search_repo.list_patients_optimized(
    doctor_id=doctor_uuid,
    filters={"status": FlowState.ACTIVE},
    limit=20
)
```

### Example 3: Cache Repository Usage

```python
from app.repositories.patient import PatientCacheRepository

# Initialize
cache_repo = PatientCacheRepository(db)

# Cache count
filters = {"doctor_id": doctor_uuid, "status": "active"}
cache_repo.set_cached_count(filters, count=150, ttl=60)

# Get cached count
cached_count = cache_repo.get_cached_count(filters)

# Invalidate cache after mutation
cache_repo.invalidate_all_patient_cache(doctor_id=doctor_uuid)
```

### Example 4: Command Repository Usage

```python
from app.repositories.patient import PatientCommandRepository

# Initialize
command_repo = PatientCommandRepository(db)

# LGPD-compliant hard delete
deleted = await command_repo.hard_delete(
    patient_id=patient_uuid,
    audit_reason="LGPD Art. 16 - Patient requested data deletion"
)

if deleted:
    print("Patient data permanently deleted")
```

---

## 📖 Architecture Decision Record

**Status:** Proposed
**Date:** 2025-12-02
**Decision:** Split PatientRepository God Class into 4 specialized repositories

**Context:**
The current `PatientRepository` has grown to 1,015 lines with 23 methods, violating Single Responsibility Principle and making it difficult to test, maintain, and optimize specific operations.

**Decision:**
Refactor into 4 specialized repositories:
1. `PatientQueryRepository` - Read operations
2. `PatientSearchRepository` - Complex filtering and search
3. `PatientCacheRepository` - Redis caching layer
4. `PatientCommandRepository` - Write operations

**Consequences:**

**Positive:**
- Reduced cognitive load (250 lines avg vs 1,015)
- Better testability (isolated concerns)
- Easier optimization (granular control)
- LGPD compliance isolated to specific repositories
- Parallel test execution

**Negative:**
- More files to navigate initially
- Need dependency injection for shared cache
- Migration effort required (8 weeks estimated)

**Alternatives Considered:**
1. **Do nothing:** Rejected - technical debt compounds
2. **Split into 2 repositories:** Insufficient separation
3. **Microservices:** Over-engineering for current scale

---

## 📚 References

- **LGPD Compliance:** `docs/database/LGPD_COMPLIANCE.md`
- **Database Schema:** `docs/database/reference/SCHEMA_DOCUMENTATION.md`
- **Performance Indexes:** Lines 916-1016 of original repository
- **Base Repository:** `app/repositories/base.py`
- **Patient Model:** `app/models/patient.py`

---

## 🎯 Success Criteria

**Phase 1 Complete When:**
- [ ] All 4 new repositories implemented
- [ ] 100% test coverage on new repositories
- [ ] All tests passing (unit + integration)
- [ ] Performance benchmarks show no regression

**Phase 2 Complete When:**
- [ ] Facade provides full backward compatibility
- [ ] All existing tests pass with facade
- [ ] Deprecation warnings logged
- [ ] Migration guide published

**Phase 3 Complete When:**
- [ ] All services migrated to specialized repositories
- [ ] No direct usage of PatientRepository facade
- [ ] Production monitoring shows stable performance
- [ ] Zero production incidents

**Phase 4 Complete When:**
- [ ] Facade removed from codebase
- [ ] All documentation updated
- [ ] v3.0.0 released with breaking changes
- [ ] Migration guide archived

---

## 📞 Support & Questions

**Technical Lead:** Architecture Team
**LGPD Compliance:** Legal/Compliance Team
**Performance Concerns:** DevOps/SRE Team

**Slack Channels:**
- `#backend-architecture` - Design discussions
- `#lgpd-compliance` - Privacy/security questions
- `#performance-optimization` - Query optimization

---

**Last Updated:** 2025-12-02
**Version:** 1.0
**Status:** 📋 Proposed (Awaiting Approval)
