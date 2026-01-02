# Patient Repository Implementation Guide

## 🎯 Quick Start for Developers

This guide provides step-by-step instructions for implementing the Patient Repository refactoring.

---

## 📐 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Service Layer                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │PatientService│  │ FlowService  │  │AlertService  │  │ Analytics   │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ │
└─────────┼──────────────────┼──────────────────┼──────────────────┼───────┘
          │                  │                  │                  │
          ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Repository Layer (Facade Pattern)                    │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │              PatientRepository (Facade) [DEPRECATED]            │    │
│  │                 Backward Compatible Interface                   │    │
│  └────┬───────────────┬────────────────┬────────────────┬────────┘    │
│       │               │                │                │              │
│       │  Delegates    │   Delegates    │   Delegates    │  Delegates   │
│       │               │                │                │              │
│       ▼               ▼                ▼                ▼              │
│  ┌────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │   Query    │  │   Search    │  │    Cache    │  │   Command    │  │
│  │ Repository │  │ Repository  │  │ Repository  │  │ Repository   │  │
│  └─────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘  │
│        │                │                 │                 │           │
│        │         Uses ◄─┴─────────────────┼─────────────────┘           │
│        │                                  │                             │
│        └──────────────── Uses ◄───────────┘                             │
└─────────────────────────────────────────────────────────────────────────┘
          │                │                 │                 │
          ▼                ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Data Layer                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  PostgreSQL  │  │    Redis     │  │  Encryption  │  │ LGPD Audit  │ │
│  │   Database   │  │    Cache     │  │   Service    │  │   Logs      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Method Distribution

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Original PatientRepository                        │
│                         1,015 lines                                  │
│                         23 methods                                   │
└─────┬───────────────┬──────────────────┬──────────────┬─────────────┘
      │               │                  │              │
      │ 9 methods     │ 3 methods        │ 3 methods    │ 1 method
      │ Query ops     │ Search/List ops  │ Cache ops    │ Commands
      │               │                  │              │
      ▼               ▼                  ▼              ▼
┌──────────┐    ┌──────────┐      ┌──────────┐   ┌──────────┐
│  Query   │    │  Search  │      │  Cache   │   │ Command  │
│   Repo   │    │   Repo   │      │   Repo   │   │   Repo   │
│ 280 lines│    │ 380 lines│      │ 150 lines│   │ 200 lines│
│    9 M   │    │    7 M   │      │    7 M   │   │    5 M   │
└──────────┘    └──────────┘      └──────────┘   └──────────┘
   -72%             -63%              -85%            -80%
```

**M = Methods**

---

## 🔧 Implementation Steps

### Step 1: Create PatientCacheRepository (No Dependencies)

**File:** `app/repositories/patient/cache_repository.py`

```python
"""
Redis caching layer for patient operations.

This repository handles all caching logic, providing:
- Count caching with TTL
- Patient object caching
- Cache key generation
- Invalidation strategies
"""
from typing import Optional, Dict, Any
from uuid import UUID
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class PatientCacheRepository:
    """
    Redis caching repository for patient data.

    Features:
    - Deterministic cache key generation
    - Graceful degradation (works without Redis)
    - Configurable TTL
    - Pattern-based invalidation
    """

    def __init__(self, db=None):
        """
        Initialize cache repository.

        Args:
            db: SQLAlchemy session (not used, kept for interface consistency)
        """
        self._redis_client = None

    @property
    def redis(self):
        """Lazy load Redis client for caching"""
        if self._redis_client is None:
            try:
                from app.core.redis_unified import get_redis_client
                self._redis_client = get_redis_client('sync')
            except Exception as e:
                logger.warning(f"Redis unavailable, caching disabled: {e}")
                # Redis optional - gracefully degrade if unavailable
                self._redis_client = False
        return self._redis_client if self._redis_client else None

    def _get_cache_key(self, prefix: str, filters: Dict[str, Any]) -> str:
        """
        Generate deterministic cache key from filters.

        Args:
            prefix: Cache key prefix (e.g., "count", "patient")
            filters: Filter dictionary to hash

        Returns:
            Cache key string: "patient:{prefix}:{hash}"
        """
        # Sort filters for consistent hashing
        filter_str = json.dumps(filters, sort_keys=True, default=str)
        filter_hash = hashlib.md5(filter_str.encode()).hexdigest()[:12]
        return f"patient:{prefix}:{filter_hash}"

    def get_cached_count(self, filters: Dict[str, Any]) -> Optional[int]:
        """
        Get cached total count if available.

        Args:
            filters: Filter dictionary used for count query

        Returns:
            Cached count or None if cache miss
        """
        if not self.redis:
            return None

        try:
            cache_key = self._get_cache_key("count", filters)
            cached = self.redis.get(cache_key)
            if cached:
                return int(cached)
        except Exception as e:
            logger.debug(f"Cache read error: {e}")
            pass  # Cache miss or error - continue without cache
        return None

    def set_cached_count(self, filters: Dict[str, Any], count: int, ttl: int = 60):
        """
        Cache total count with TTL.

        Args:
            filters: Filter dictionary used for count query
            count: Count value to cache
            ttl: Time to live in seconds (default: 60)
        """
        if not self.redis:
            return

        try:
            cache_key = self._get_cache_key("count", filters)
            self.redis.setex(cache_key, ttl, str(count))
            logger.debug(f"Cached count: {cache_key} = {count} (TTL: {ttl}s)")
        except Exception as e:
            logger.debug(f"Cache write error: {e}")
            pass  # Cache write failure - continue without cache

    def get_cached_patient(self, patient_id: UUID) -> Optional[Dict]:
        """
        Get cached patient object.

        Args:
            patient_id: Patient UUID

        Returns:
            Cached patient dict or None
        """
        if not self.redis:
            return None

        try:
            cache_key = f"patient:obj:{patient_id}"
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.debug(f"Patient cache read error: {e}")
        return None

    def set_cached_patient(self, patient_id: UUID, patient_data: Dict,
                           ttl: int = 300):
        """
        Cache patient object.

        Args:
            patient_id: Patient UUID
            patient_data: Patient data dictionary
            ttl: Time to live in seconds (default: 300)
        """
        if not self.redis:
            return

        try:
            cache_key = f"patient:obj:{patient_id}"
            self.redis.setex(cache_key, ttl, json.dumps(patient_data, default=str))
            logger.debug(f"Cached patient: {patient_id} (TTL: {ttl}s)")
        except Exception as e:
            logger.debug(f"Patient cache write error: {e}")

    def invalidate_count_cache(self, filters: Dict[str, Any]) -> None:
        """
        Invalidate cached count for specific filters.

        Args:
            filters: Filter dictionary to invalidate
        """
        if not self.redis:
            return

        try:
            cache_key = self._get_cache_key("count", filters)
            self.redis.delete(cache_key)
            logger.debug(f"Invalidated count cache: {cache_key}")
        except Exception as e:
            logger.debug(f"Cache invalidation error: {e}")

    def invalidate_patient_cache(self, patient_id: UUID) -> None:
        """
        Invalidate cached patient object.

        Args:
            patient_id: Patient UUID
        """
        if not self.redis:
            return

        try:
            cache_key = f"patient:obj:{patient_id}"
            self.redis.delete(cache_key)
            logger.debug(f"Invalidated patient cache: {patient_id}")
        except Exception as e:
            logger.debug(f"Patient cache invalidation error: {e}")

    def invalidate_all_patient_cache(self, doctor_id: Optional[UUID] = None) -> None:
        """
        Invalidate all patient-related cache entries.

        Args:
            doctor_id: Optional doctor UUID to scope invalidation
        """
        if not self.redis:
            return

        try:
            if doctor_id:
                # Invalidate all count caches for this doctor
                pattern = f"patient:count:*"
                keys = self.redis.keys(pattern)
                for key in keys:
                    if f'"doctor_id": "{doctor_id}"' in key:
                        self.redis.delete(key)
                logger.info(f"Invalidated all patient cache for doctor: {doctor_id}")
            else:
                # Nuclear option: invalidate all patient cache
                pattern = f"patient:*"
                keys = self.redis.keys(pattern)
                if keys:
                    self.redis.delete(*keys)
                logger.warning("Invalidated ALL patient cache")
        except Exception as e:
            logger.error(f"Bulk cache invalidation error: {e}")
```

**Test File:** `tests/repositories/patient/test_cache_repository.py`

```python
import pytest
from unittest.mock import Mock, patch
from uuid import uuid4

from app.repositories.patient.cache_repository import PatientCacheRepository


@pytest.fixture
def cache_repo():
    return PatientCacheRepository()


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = Mock()
    redis.get.return_value = None
    redis.setex.return_value = True
    redis.delete.return_value = 1
    redis.keys.return_value = []
    return redis


def test_cache_key_generation_deterministic(cache_repo):
    """Test cache keys are deterministic for same filters"""
    filters1 = {"doctor_id": "123", "status": "active"}
    filters2 = {"status": "active", "doctor_id": "123"}  # Different order

    key1 = cache_repo._get_cache_key("count", filters1)
    key2 = cache_repo._get_cache_key("count", filters2)

    assert key1 == key2
    assert key1.startswith("patient:count:")


def test_get_cached_count_hit(cache_repo, mock_redis):
    """Test cache hit returns cached value"""
    cache_repo._redis_client = mock_redis
    mock_redis.get.return_value = "150"

    filters = {"doctor_id": "123"}
    count = cache_repo.get_cached_count(filters)

    assert count == 150
    mock_redis.get.assert_called_once()


def test_get_cached_count_miss(cache_repo, mock_redis):
    """Test cache miss returns None"""
    cache_repo._redis_client = mock_redis
    mock_redis.get.return_value = None

    filters = {"doctor_id": "123"}
    count = cache_repo.get_cached_count(filters)

    assert count is None


def test_get_cached_count_no_redis(cache_repo):
    """Test graceful degradation when Redis unavailable"""
    cache_repo._redis_client = False

    filters = {"doctor_id": "123"}
    count = cache_repo.get_cached_count(filters)

    assert count is None  # Should not raise exception


def test_set_cached_count(cache_repo, mock_redis):
    """Test count caching with TTL"""
    cache_repo._redis_client = mock_redis

    filters = {"doctor_id": "123"}
    cache_repo.set_cached_count(filters, 150, ttl=60)

    mock_redis.setex.assert_called_once()
    args = mock_redis.setex.call_args[0]
    assert args[1] == 60  # TTL
    assert args[2] == "150"  # Value


def test_invalidate_count_cache(cache_repo, mock_redis):
    """Test count cache invalidation"""
    cache_repo._redis_client = mock_redis

    filters = {"doctor_id": "123"}
    cache_repo.invalidate_count_cache(filters)

    mock_redis.delete.assert_called_once()


def test_invalidate_all_patient_cache(cache_repo, mock_redis):
    """Test bulk cache invalidation"""
    cache_repo._redis_client = mock_redis
    mock_redis.keys.return_value = ["patient:count:abc123", "patient:obj:xyz789"]

    cache_repo.invalidate_all_patient_cache()

    mock_redis.keys.assert_called_with("patient:*")
    mock_redis.delete.assert_called()
```

---

### Step 2: Create PatientQueryRepository (Uses Cache)

**File:** `app/repositories/patient/query_repository.py`

```python
"""
Query repository for patient single-record and batch retrieval operations.

Responsibilities:
- Single patient queries (by ID, phone, idempotency key)
- Batch queries (by doctor, all active/deleted)
- Count operations
- Eager loading strategies
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_

from app.models.patient import Patient, FlowState
from app.models.message import Message
from app.repositories.base import BaseRepository
from app.repositories.patient.cache_repository import PatientCacheRepository


class PatientQueryRepository(BaseRepository[Patient]):
    """
    Patient query repository for read operations.

    PERFORMANCE OPTIMIZATIONS:
    - N+1 query prevention via joinedload/selectinload
    - Optional Redis caching
    - Batch loading for relationships
    - Optimized eager loading strategies
    """

    def __init__(self, db: Session):
        super().__init__(db, Patient)
        self._cache_repo = PatientCacheRepository(db)

    def get_by_id(self, patient_id: UUID, eager_load: bool = True,
                  include: List[str] = None) -> Optional[Patient]:
        """
        Get patient by ID (only active patients) with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading prevents N+1 queries.

        Relationships loaded when eager_load=True:
        - quiz_sessions: Patient's quiz sessions (selectinload - 1:many)
        - flow_states: Patient's flow states (selectinload - 1:many)
        - doctor: Patient's assigned doctor (joinedload - 1:1)

        Args:
            patient_id: UUID of the patient
            eager_load: Enable eager loading (default: True for performance)
            include: Specific relationships to load (overrides eager_load)

        Returns:
            Patient with relationships pre-loaded or None
        """
        query = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.deleted_at.is_(None)
        )

        if eager_load or include:
            relationships = include or ["quiz_sessions", "flow_states", "doctor"]

            if "doctor" in relationships:
                query = query.options(joinedload(Patient.doctor))
            if "quiz_sessions" in relationships:
                query = query.options(selectinload(Patient.quiz_sessions))
            if "flow_states" in relationships:
                query = query.options(selectinload(Patient.flow_states))
            if "messages" in relationships:
                query = query.options(
                    selectinload(Patient.messages).joinedload(Message.sender)
                )
            if "treatments" in relationships:
                query = query.options(selectinload(Patient.treatments))
            if "appointments" in relationships:
                query = query.options(selectinload(Patient.appointments))
            if "medications" in relationships:
                query = query.options(selectinload(Patient.medications))

        return query.first()

    def get_by_id_including_deleted(self, patient_id: UUID) -> Optional[Patient]:
        """
        Get patient by ID including soft-deleted patients.

        Args:
            patient_id: UUID of the patient

        Returns:
            Patient or None
        """
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def get_by_phone(self, phone: str) -> Optional[Patient]:
        """
        Get patient by phone (only active patients).

        NOTE: This searches encrypted phone field.

        Args:
            phone: Phone number

        Returns:
            Patient or None
        """
        return self.db.query(Patient).filter(
            Patient.phone == phone,
            Patient.deleted_at.is_(None)
        ).first()

    def get_by_doctor(self, doctor_id: UUID, skip: int = 0, limit: int = 100,
                      eager_load: bool = True) -> List[Patient]:
        """
        Get active patients for a doctor with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading prevents N+1 queries.

        Relationships loaded when eager_load=True:
        - quiz_sessions: Patient's quiz sessions (selectinload - 1:many)
        - flow_states: Patient's flow states (selectinload - 1:many)

        Args:
            doctor_id: UUID of the doctor
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of patients with relationships pre-loaded
        """
        query = self.db.query(Patient).filter(
            Patient.doctor_id == doctor_id,
            Patient.deleted_at.is_(None)
        )

        if eager_load:
            query = query.options(
                selectinload(Patient.quiz_sessions),
                selectinload(Patient.flow_states)
            )

        return query.offset(skip).limit(limit).all()

    def get_all_active(self, skip: int = 0, limit: int = 100,
                       eager_load: bool = True) -> List[Patient]:
        """
        Get all active (non-deleted) patients with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading prevents N+1 queries.

        Relationships loaded when eager_load=True:
        - quiz_sessions: Patient's quiz sessions (selectinload - 1:many)
        - flow_states: Patient's flow states (selectinload - 1:many)
        - doctor: Patient's assigned doctor (joinedload - 1:1)

        Args:
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of active patients with relationships pre-loaded
        """
        query = self.db.query(Patient).filter(
            Patient.deleted_at.is_(None)
        )

        if eager_load:
            query = query.options(
                selectinload(Patient.quiz_sessions),
                selectinload(Patient.flow_states),
                joinedload(Patient.doctor)
            )

        return query.offset(skip).limit(limit).all()

    def get_all_deleted(self, skip: int = 0, limit: int = 100) -> List[Patient]:
        """
        Get all soft-deleted patients.

        Args:
            skip: Pagination offset
            limit: Maximum records to return

        Returns:
            List of deleted patients
        """
        return self.db.query(Patient).filter(
            Patient.deleted_at.isnot(None)
        ).offset(skip).limit(limit).all()

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Patient]:
        """
        Get patient by idempotency key.

        QW-004: Database-level idempotency support

        Args:
            idempotency_key: Unique request identifier

        Returns:
            Patient if found, None otherwise
        """
        return self.db.query(Patient).filter(
            Patient.idempotency_key == idempotency_key,
            Patient.deleted_at.is_(None)
        ).first()

    def count_active(self, **filters) -> int:
        """
        Count active patients with optional filters.

        Args:
            **filters: Field filters (e.g., doctor_id=uuid, status="active")

        Returns:
            Count of matching active patients
        """
        query = self.db.query(Patient).filter(Patient.deleted_at.is_(None))

        for field, value in filters.items():
            if hasattr(Patient, field) and value is not None:
                query = query.filter(getattr(Patient, field) == value)

        return query.count()

    def count_deleted(self) -> int:
        """
        Count soft-deleted patients.

        Returns:
            Count of deleted patients
        """
        return self.db.query(Patient).filter(Patient.deleted_at.isnot(None)).count()
```

---

### Step 3: Create PatientSearchRepository (Complex)

This is the largest repository. Due to space constraints, I'll provide the structure:

```python
"""
Search and advanced filtering repository for patients.

Responsibilities:
- Complex list operations with filtering
- LGPD-compliant search (hash-based)
- Cursor pagination
- Optimized batch operations
"""
# Contains:
# - list_v2() method (153-396)
# - list_patients_optimized() method (398-573)
# - search_active() method (711-727)
# - _build_search_criteria() helper (65-119)
# - Module-level helpers: _looks_like_email(), _looks_like_phone()
```

---

### Step 4: Create PatientCommandRepository

```python
"""
Command repository for patient write operations.

Responsibilities:
- Hard delete (LGPD compliance)
- Audit trail creation
- Cache invalidation on mutations
"""
# Contains:
# - hard_delete() method (746-870)
# - _create_deletion_audit() method (872-913)
# Plus overrides for create/update/soft_delete with cache invalidation
```

---

## 🧪 Testing Strategy

### Test Coverage Requirements

| Repository | Unit Tests | Integration Tests | E2E Tests |
|-----------|-----------|------------------|-----------|
| CacheRepository | 15+ tests | 5 Redis tests | - |
| QueryRepository | 20+ tests | 10 DB tests | - |
| SearchRepository | 25+ tests | 15 DB tests | 5 API tests |
| CommandRepository | 10+ tests | 8 DB tests | 3 API tests |

### Testing Checklist

**Cache Repository:**
- [ ] Cache key generation is deterministic
- [ ] Cache hit/miss scenarios
- [ ] TTL expiration
- [ ] Graceful degradation without Redis
- [ ] Invalidation strategies
- [ ] Concurrent access patterns

**Query Repository:**
- [ ] Eager loading configurations
- [ ] N+1 query prevention (use SQLAlchemy echo)
- [ ] Soft delete filtering
- [ ] Idempotency key lookup
- [ ] Count accuracy
- [ ] Performance benchmarks

**Search Repository:**
- [ ] LGPD hash-based search
- [ ] Cursor pagination correctness
- [ ] Sort order consistency
- [ ] Filter combinations
- [ ] Edge cases (empty results, single page)
- [ ] Performance with large datasets

**Command Repository:**
- [ ] Hard delete cascade behavior
- [ ] Audit trail creation
- [ ] Cache invalidation triggers
- [ ] LGPD compliance validation
- [ ] Error handling (missing audit reason)

---

## 📊 Performance Benchmarks

### Before Refactoring

```python
# Benchmark script
def benchmark_original():
    from app.repositories.patient import PatientRepository

    repo = PatientRepository(db)

    # Test 1: List patients
    start = time.time()
    patients, _, _, _ = repo.list_v2(
        filters={"doctor_id": doctor_id},
        limit=20
    )
    list_time = time.time() - start

    # Test 2: Search
    start = time.time()
    results = repo.search_active("john@example.com", limit=20)
    search_time = time.time() - start

    print(f"List: {list_time:.3f}s, Search: {search_time:.3f}s")
```

**Expected Results:**
- List: ~0.120s (120ms)
- Search: ~0.085s (85ms)

### After Refactoring

```python
def benchmark_new():
    from app.repositories.patient import PatientSearchRepository

    search_repo = PatientSearchRepository(db)

    # Test 1: List patients
    start = time.time()
    patients, _, _, _ = search_repo.list_v2(
        filters={"doctor_id": doctor_id},
        limit=20
    )
    list_time = time.time() - start

    # Test 2: Search
    start = time.time()
    results = search_repo.search_active("john@example.com", limit=20)
    search_time = time.time() - start

    print(f"List: {list_time:.3f}s, Search: {search_time:.3f}s")
```

**Target Results:**
- List: ~0.110s (110ms) - 8% improvement
- Search: ~0.078s (78ms) - 8% improvement

**Improvement Factors:**
- Specialized imports (no unused dependencies)
- Focused caching strategy
- Optimized query building

---

## 🚀 Deployment Checklist

### Pre-Deployment

- [ ] All tests passing (100% coverage)
- [ ] Performance benchmarks show no regression
- [ ] Code review approved by 2+ developers
- [ ] LGPD compliance review
- [ ] Documentation updated

### Deployment (Blue-Green Strategy)

**Phase 1: Green Deployment**
- [ ] Deploy new repositories alongside old
- [ ] Feature flag: `use_new_patient_repositories = False`
- [ ] Monitor error rates and performance

**Phase 2: Gradual Rollout**
- [ ] Enable for 10% of traffic
- [ ] Monitor for 24 hours
- [ ] Increase to 50% if stable
- [ ] Monitor for 48 hours
- [ ] Increase to 100%

**Phase 3: Blue Shutdown**
- [ ] Verify 100% traffic on new repositories
- [ ] Keep old repository for 1 week (rollback capability)
- [ ] Remove old repository after success validation

### Post-Deployment

- [ ] Monitor query performance (24h)
- [ ] Check cache hit rates
- [ ] Validate LGPD audit logs
- [ ] Review error logs for edge cases
- [ ] Update runbooks and documentation

---

## 📞 Rollback Procedure

### If Critical Issues Detected

1. **Immediate Rollback:**
   ```python
   # In feature_flags.py
   USE_NEW_PATIENT_REPOSITORIES = False
   ```

2. **Verify Rollback:**
   - Check all services using old repository
   - Monitor error rates return to baseline
   - Verify data consistency

3. **Post-Mortem:**
   - Document what went wrong
   - Create bug report with reproduction steps
   - Schedule fix and re-deployment

### Rollback Triggers

- **CRITICAL:** Any data loss or corruption
- **HIGH:** >5% increase in error rate
- **MEDIUM:** >20% performance degradation
- **LOW:** Non-critical bugs (can be fixed forward)

---

## 📚 Additional Resources

- **Architecture Decision Record:** `docs/architecture/ADR_PATIENT_REPOSITORY_SPLIT.md`
- **LGPD Compliance Guide:** `docs/database/LGPD_COMPLIANCE.md`
- **Performance Optimization:** Lines 916-1016 of original repository
- **Database Indexes:** `alembic/versions/031_add_performance_indexes.py`

---

**Last Updated:** 2025-12-02
**Version:** 1.0
**Status:** 📋 Implementation Ready
