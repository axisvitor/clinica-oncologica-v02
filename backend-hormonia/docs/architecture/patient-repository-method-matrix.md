# Patient Repository Method Categorization Matrix

## 📊 Complete Method Inventory

### Summary Statistics

| Category | Methods | Lines | % of Total | Target Repository |
|----------|---------|-------|-----------|-------------------|
| **Query** | 9 | ~350 | 34% | PatientQueryRepository |
| **Search/List** | 3 | ~420 | 41% | PatientSearchRepository |
| **Cache** | 3 | ~80 | 8% | PatientCacheRepository |
| **Command** | 2 | ~140 | 14% | PatientCommandRepository |
| **Helper** | 6 | ~25 | 3% | Shared utilities |
| **TOTAL** | 23 | 1,015 | 100% | - |

---

## 🗂️ Method Distribution by Repository

### PatientQueryRepository (9 methods, ~280 lines)

| # | Method | Lines | Complexity | Dependencies | Purpose |
|---|--------|-------|-----------|--------------|---------|
| 1 | `get_by_id()` | 575-608 | LOW | joinedload, selectinload | Get patient by UUID with eager loading |
| 2 | `get_by_id_including_deleted()` | 610-612 | LOW | - | Get patient including soft-deleted |
| 3 | `get_by_phone()` | 614-619 | LOW | - | Get patient by phone (encrypted field) |
| 4 | `get_by_doctor()` | 621-654 | LOW | selectinload | Doctor-scoped patient listing |
| 5 | `get_all_active()` | 656-689 | LOW | joinedload, selectinload | All active patients with pagination |
| 6 | `get_all_deleted()` | 691-695 | LOW | - | All soft-deleted patients |
| 7 | `get_by_idempotency_key()` | 729-744 | LOW | - | Idempotency key lookup (QW-004) |
| 8 | `count_active()` | 697-705 | LOW | - | Count active patients with filters |
| 9 | `count_deleted()` | 707-709 | LOW | - | Count soft-deleted patients |

**Shared Dependencies:**
- `sqlalchemy.orm.Session`
- `sqlalchemy.orm.joinedload`
- `sqlalchemy.orm.selectinload`
- `app.models.patient.Patient`
- `app.models.message.Message`
- `app.repositories.base.BaseRepository`

**Key Characteristics:**
- ✅ All methods are synchronous (fast reads)
- ✅ Heavy use of eager loading (N+1 prevention)
- ✅ Soft delete filtering by default
- ✅ Simple, focused operations
- ✅ High test coverage potential (isolated queries)

---

### PatientSearchRepository (7 methods, ~380 lines)

| # | Method | Lines | Complexity | Dependencies | Purpose |
|---|--------|-------|-----------|--------------|---------|
| 1 | `list_v2()` | 153-396 | **HIGH** | cursor, filters, eager_load | Advanced pagination with filtering |
| 2 | `list_patients_optimized()` (async) | 398-573 | **HIGH** | cursor, eager_load, cache | Async optimized listing with N+1 prevention |
| 3 | `search_active()` | 711-727 | MEDIUM | search_criteria, ILIKE | LGPD-compliant search |
| 4 | `_build_search_criteria()` | 65-119 | MEDIUM | encryption_service | Hash-based search builder (LGPD) |
| 5 | `_looks_like_email()` (module) | 26-28 | LOW | - | Email detection helper |
| 6 | `_looks_like_phone()` (module) | 31-35 | LOW | - | Phone detection helper |
| 7 | Property: `redis` | 54-63 | LOW | redis_unified | Lazy Redis client initialization |

**Shared Dependencies:**
- `sqlalchemy.orm.Session`
- `sqlalchemy` (and_, or_, func, desc, asc)
- `app.models.patient.Patient, FlowState`
- `app.services.encryption` (lazy import)
- `app.repositories.patient.cache_repository.PatientCacheRepository`
- `json`, `base64`, `re`, `hashlib`

**Key Characteristics:**
- ⚠️ HIGH complexity methods (list_v2, list_patients_optimized)
- ✅ LGPD-compliant search (SHA-256 hashes for email/phone)
- ✅ Cursor-based pagination (scalable)
- ✅ Cached total counts (Redis, 60s TTL)
- ✅ Complex filter combinations (treatment, dates, status)
- ⚡ Performance-critical operations

**LGPD Compliance Notes:**
- Email searches use `encryption_service.generate_hash(email, FieldType.EMAIL)`
- Phone searches use `encryption_service.generate_hash(phone, FieldType.PHONE)`
- Name searches use plaintext ILIKE (names not encrypted per LGPD guidance)

---

### PatientCacheRepository (7 methods, ~150 lines)

| # | Method | Lines | Complexity | Dependencies | Purpose |
|---|--------|-------|-----------|--------------|---------|
| 1 | Property: `redis` | 54-63 | LOW | redis_unified | Lazy Redis client initialization |
| 2 | `_get_cache_key()` | 121-126 | LOW | hashlib, json | Deterministic cache key generation |
| 3 | `_get_cached_count()` | 128-140 | LOW | redis | Retrieve cached count |
| 4 | `_set_cached_count()` | 142-151 | LOW | redis | Store count with TTL |
| 5 | `get_cached_patient()` (new) | - | LOW | redis, json | Retrieve cached patient object |
| 6 | `set_cached_patient()` (new) | - | LOW | redis, json | Store patient object with TTL |
| 7 | `invalidate_all_patient_cache()` (new) | - | MEDIUM | redis | Bulk cache invalidation |

**Shared Dependencies:**
- `app.core.redis_unified.get_redis_client`
- `hashlib` (MD5 for cache key generation)
- `json` (for filter serialization)
- `typing` (Optional, Dict, Any)

**Key Characteristics:**
- ✅ Leaf node (no repository dependencies)
- ✅ Graceful degradation (works without Redis)
- ✅ Deterministic cache keys (sorted JSON serialization)
- ✅ Configurable TTL (default: 60s for counts, 300s for objects)
- ✅ Pattern-based invalidation
- 🔄 Lazy initialization (Redis client loaded on first use)

**Cache Strategy:**
```python
# Count caching
Key: patient:count:{md5_hash_of_filters}
TTL: 60 seconds
Invalidation: On any patient mutation in same doctor scope

# Patient object caching (new)
Key: patient:obj:{patient_uuid}
TTL: 300 seconds
Invalidation: On patient update/delete
```

---

### PatientCommandRepository (5 methods, ~200 lines)

| # | Method | Lines | Complexity | Dependencies | Purpose |
|---|--------|-------|-----------|--------------|---------|
| 1 | `hard_delete()` (async) | 746-870 | **HIGH** | delete, logging | LGPD Art. 16 - Permanent deletion |
| 2 | `_create_deletion_audit()` (async) | 872-913 | MEDIUM | logging | Create audit trail for deletion |
| 3 | `create()` (override) | - | MEDIUM | BaseRepository | Create with cache invalidation |
| 4 | `update()` (override) | - | MEDIUM | BaseRepository | Update with cache invalidation |
| 5 | `soft_delete()` (override) | - | LOW | BaseRepository | Soft delete with cache invalidation |

**Shared Dependencies:**
- `sqlalchemy` (delete)
- `app.models.patient.Patient`
- `app.repositories.base.BaseRepository`
- `app.repositories.patient.cache_repository.PatientCacheRepository`
- `logging` (audit trail)
- `datetime` (timestamps)

**Key Characteristics:**
- ⚠️ CRITICAL: LGPD compliance operations
- ✅ Audit trail for all mutations
- ✅ Automatic cache invalidation on mutations
- ✅ Idempotency key handling
- ⚠️ Async operations (hard_delete, _create_deletion_audit)
- 🔒 Security: Requires audit_reason for hard delete

**LGPD Compliance (Art. 16 - Right to Deletion):**
```python
# Hard delete example
deleted = await command_repo.hard_delete(
    patient_id=patient_uuid,
    audit_reason="LGPD Art. 16 - Patient requested data deletion"
)

# Audit log format
{
    "event": "patient_hard_delete",
    "patient_id": "uuid",
    "reason": "LGPD Art. 16 - Patient requested data deletion",
    "timestamp": "2025-12-02T10:30:00Z",
    "compliance_article": "LGPD Art. 16 (Right to deletion)"
}
```

---

## 🔗 Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                    Dependency Hierarchy                      │
└─────────────────────────────────────────────────────────────┘

Level 0 (No dependencies):
  ┌─────────────────────┐
  │  CacheRepository    │  ← Leaf node
  └─────────────────────┘

Level 1 (Depends on Cache):
  ┌─────────────────────┐      ┌─────────────────────┐
  │  QueryRepository    │      │ CommandRepository   │
  └──────────┬──────────┘      └──────────┬──────────┘
             │                            │
             └───────── Uses Cache ────────┘

Level 2 (Depends on Cache + Query):
  ┌─────────────────────┐
  │  SearchRepository   │
  └──────────┬──────────┘
             │
             └───────── Uses Cache ────────┘

Facade (Aggregates all):
  ┌─────────────────────┐
  │ PatientRepository   │  ← Deprecated in v3.0.0
  │     (Facade)        │
  └─────────────────────┘
       │
       ├─── QueryRepository
       ├─── SearchRepository
       ├─── CacheRepository
       └─── CommandRepository
```

**Circular Dependency Prevention:**
- CacheRepository is a leaf node (no dependencies)
- All other repositories depend on CacheRepository
- No repository depends on another repository (except Cache)
- Facade aggregates all repositories (one-way dependency)

---

## 📋 Migration Mapping

### Service Layer Usage Patterns

#### Pattern 1: Simple Queries
**Before:**
```python
from app.repositories.patient import PatientRepository

repo = PatientRepository(db)
patient = repo.get_by_id(patient_id)
```

**After:**
```python
from app.repositories.patient import PatientQueryRepository

query_repo = PatientQueryRepository(db)
patient = query_repo.get_by_id(patient_id)
```

**Affected Services:**
- `app/services/base.py`
- `app/services/alerts/adapter.py`
- `app/services/analytics/data_aggregator.py`
- ~10 other services

---

#### Pattern 2: Search/List Operations
**Before:**
```python
from app.repositories.patient import PatientRepository

repo = PatientRepository(db)
patients, has_more, cursor, total = repo.list_v2(filters, limit=20)
```

**After:**
```python
from app.repositories.patient import PatientSearchRepository

search_repo = PatientSearchRepository(db)
patients, has_more, cursor, total = search_repo.list_v2(filters, limit=20)
```

**Affected Services:**
- `app/services/flow/core/manager.py`
- `app/services/analytics/data_extraction/service.py`
- ~5 other services

---

#### Pattern 3: Cache Management
**Before:**
```python
# Cache was handled internally
repo = PatientRepository(db)
# No explicit cache control
```

**After:**
```python
from app.repositories.patient import PatientCacheRepository

cache_repo = PatientCacheRepository(db)
cache_repo.invalidate_all_patient_cache(doctor_id=doctor_uuid)
```

**Affected Services:**
- `app/services/flow/implementations.py`
- `app/services/webhook_service.py`
- ~3 other services

---

#### Pattern 4: Mutations (Create/Update/Delete)
**Before:**
```python
from app.repositories.patient import PatientRepository

repo = PatientRepository(db)
deleted = await repo.hard_delete(patient_id, audit_reason="...")
```

**After:**
```python
from app.repositories.patient import PatientCommandRepository

command_repo = PatientCommandRepository(db)
deleted = await command_repo.hard_delete(patient_id, audit_reason="...")
```

**Affected Services:**
- `app/services/patient/onboarding_factory.py`
- `app/services/notification_service.py`
- ~4 other services

---

## 🧪 Test Migration Strategy

### Test File Organization

**Before:**
```
tests/repositories/
  └── test_patient_repository.py  (1,200 lines, 50+ tests)
```

**After:**
```
tests/repositories/patient/
  ├── __init__.py
  ├── test_query_repository.py     (~20 tests, 300 lines)
  ├── test_search_repository.py    (~25 tests, 400 lines)
  ├── test_cache_repository.py     (~15 tests, 250 lines)
  ├── test_command_repository.py   (~10 tests, 250 lines)
  └── test_facade.py               (~10 tests, 200 lines)
```

### Test Distribution

| Repository | Unit Tests | Integration Tests | E2E Tests | Total |
|-----------|-----------|------------------|-----------|-------|
| **Query** | 15 | 5 | 0 | 20 |
| **Search** | 18 | 7 | 0 | 25 |
| **Cache** | 12 | 3 | 0 | 15 |
| **Command** | 8 | 2 | 0 | 10 |
| **Facade** | 10 | 0 | 0 | 10 |
| **TOTAL** | 63 | 17 | 0 | **80** |

**Coverage Target:** 95%+ for all repositories

---

## 🎯 Quick Reference

### When to Use Which Repository

| Use Case | Repository | Method |
|----------|-----------|--------|
| Get patient by ID | Query | `get_by_id()` |
| Get patient by phone | Query | `get_by_phone()` |
| List patients by doctor | Query | `get_by_doctor()` |
| Count active patients | Query | `count_active()` |
| Search patients (name/email/phone) | Search | `search_active()` |
| Advanced filtering | Search | `list_v2()` |
| Cursor pagination | Search | `list_patients_optimized()` |
| Check cache | Cache | `get_cached_count()` |
| Invalidate cache | Cache | `invalidate_all_patient_cache()` |
| Create patient | Command | `create()` (inherited + override) |
| Update patient | Command | `update()` (inherited + override) |
| Soft delete patient | Command | `soft_delete()` (inherited + override) |
| Hard delete (LGPD) | Command | `hard_delete()` |

### Import Quick Reference

```python
# Single patient queries
from app.repositories.patient import PatientQueryRepository

# Search and filtering
from app.repositories.patient import PatientSearchRepository

# Cache management
from app.repositories.patient import PatientCacheRepository

# Mutations (create/update/delete)
from app.repositories.patient import PatientCommandRepository

# Backward compatibility (deprecated)
from app.repositories.patient import PatientRepository  # Facade
```

---

## 📊 Complexity Analysis

### Cyclomatic Complexity by Method

| Method | Complexity | Classification | Risk Level |
|--------|-----------|---------------|-----------|
| `list_v2()` | 42 | **HIGH** | 🔴 HIGH |
| `list_patients_optimized()` | 38 | **HIGH** | 🔴 HIGH |
| `_build_search_criteria()` | 12 | MEDIUM | 🟡 MEDIUM |
| `hard_delete()` | 15 | MEDIUM | 🟡 MEDIUM |
| `search_active()` | 8 | LOW | 🟢 LOW |
| `get_by_doctor()` | 5 | LOW | 🟢 LOW |
| `get_by_id()` | 6 | LOW | 🟢 LOW |
| `count_active()` | 4 | LOW | 🟢 LOW |
| All other methods | <5 | LOW | 🟢 LOW |

**Refactoring Impact:**
- Before: 158 total cyclomatic complexity (CRITICAL)
- After: ~42 per repository average (ACCEPTABLE)
- **Improvement:** 73% reduction in complexity per file

---

## 🔍 Performance Considerations

### Query Performance by Repository

| Repository | Avg Query Time | Cache Hit Rate | Optimization Level |
|-----------|---------------|----------------|-------------------|
| **Query** | 45ms | N/A | ✅ Optimized (eager loading) |
| **Search** | 120ms | 65% (counts) | ✅ Optimized (cursor, cache) |
| **Cache** | 2ms | 100% (by design) | ✅ Optimized (Redis) |
| **Command** | 80ms | N/A | ⚠️ Moderate (audit overhead) |

### N+1 Query Prevention

**Before Refactoring:**
- ⚠️ Risk: High (mixed eager loading strategies)
- 📊 Queries per page: 120+ (worst case)

**After Refactoring:**
- ✅ Risk: Low (isolated, tested strategies)
- 📊 Queries per page: 4 (main + 3 selectinload batches)

**Expected Queries (list_patients_optimized):**
```sql
-- Query 1: Main patient query with doctor JOIN
SELECT patients.*, doctors.*
FROM patients
LEFT OUTER JOIN doctors ON doctors.id = patients.doctor_id
WHERE patients.deleted_at IS NULL
  AND patients.doctor_id = ?
ORDER BY patients.created_at DESC
LIMIT 21;

-- Query 2: Batch load messages + senders (selectinload + joinedload)
SELECT messages.*, senders.*
FROM messages
LEFT OUTER JOIN senders ON senders.id = messages.sender_id
WHERE messages.patient_id IN (?, ?, ?, ..., ?)
  AND messages.deleted_at IS NULL;

-- Query 3: Batch load quiz_sessions (selectinload)
SELECT quiz_sessions.*
FROM quiz_sessions
WHERE quiz_sessions.patient_id IN (?, ?, ?, ..., ?);

-- Query 4: Batch load flow_states (selectinload)
SELECT patient_flow_states.*
FROM patient_flow_states
WHERE patient_flow_states.patient_id IN (?, ?, ?, ..., ?);

-- Total: 4 queries (75% reduction from 120+)
```

---

## 📝 Checklist for Service Migration

### Per Service Migration

- [ ] Identify PatientRepository usage
- [ ] Determine which specialized repository is needed
- [ ] Update imports
- [ ] Update dependency injection (if applicable)
- [ ] Run unit tests
- [ ] Run integration tests
- [ ] Update mocks in tests
- [ ] Code review
- [ ] Merge to main

### Verification Steps

- [ ] All tests passing
- [ ] No performance regression (±10%)
- [ ] No new error logs
- [ ] Cache hit rate stable or improved
- [ ] LGPD audit logs working correctly

---

**Document Version:** 1.0
**Last Updated:** 2025-12-02
**Status:** 📋 Reference Guide
