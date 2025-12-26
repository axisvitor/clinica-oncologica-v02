# Patient Registration Process - Debug Report

> **Date:** 2025-12-22
> **Scope:** Complete patient registration flow analysis
> **Analyzers:** 6 concurrent agents (model/schema, routes, services, saga, repository, domain)

---

## Executive Summary

| Category | Score | Status |
|----------|-------|--------|
| **Overall Quality** | 7.5/10 | Good with issues |
| **LGPD Compliance** | 9/10 | Excellent |
| **Error Handling** | 7/10 | Needs improvement |
| **Performance** | 8/10 | Good |
| **Technical Debt** | ~50-60 hours | Moderate |

---

## Patient Registration Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PATIENT REGISTRATION FLOW                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. POST /api/v2/patients/                                              │
│     └── crud.py:215-346                                                 │
│         ├── Idempotency check (DB + Redis)                              │
│         ├── Authorization (doctor self-assignment)                      │
│         └── Initialize SagaOrchestrator + OnboardingCoordinator         │
│                                                                         │
│  2. OnboardingCoordinator.create_patient()                              │
│     └── coordinator.py:110-186                                          │
│         ├── validate_patient_data() → IntegrityService                  │
│         └── execute_patient_onboarding_saga() → SagaOrchestrator        │
│                                                                         │
│  3. SagaOrchestrator.execute_patient_onboarding_saga()                  │
│     └── saga_orchestrator.py:76-171                                     │
│         ├── Acquire distributed lock (phone hash)                       │
│         ├── Create saga record                                          │
│         ├── STEP 1: Create patient (Repository)                         │
│         ├── STEP 2: DEPRECATED (Firebase)                               │
│         ├── STEP 3: Initialize flow (FlowService)                       │
│         └── STEP 4: Send welcome message (WhatsApp)                     │
│                                                                         │
│  4. PatientRepository.create()                                          │
│     └── base.py:36-136                                                  │
│         ├── Normalize metadata/patient_data                             │
│         ├── Encrypt PII (CPF, email, phone)                             │
│         └── Commit to database                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Critical Issues Found

### 1. Code Duplication (CRITICAL)
**Location:** `patients/crud.py` vs `patients.py`
**Impact:** High - ~430 lines of duplicate code

**Evidence:**
- `crud.py` (458 lines) - New modular structure
- `patients.py` (426 lines) - Legacy duplicate

**Risk:** Changes must be made twice, inconsistent behavior possible.

**Fix:** Delete or deprecate `patients.py`, keep only `patients/crud.py`.

---

### 2. Race Condition in Duplicate Detection (CRITICAL)
**Location:** `integrity_service.py:348-390`
**Impact:** High - Concurrent requests can bypass duplicate checks

**Problem:**
```python
# Advisory check (not atomic)
existing = await self._check_duplicate_cpf(cpf, doctor_id)
if existing:
    raise ValidationError("Patient with CPF already exists")
# TIME GAP - another request could insert here
# Later: database insert
```

**Current Mitigation:** Database constraints exist but error handling could be improved.

**Fix:**
1. Rely primarily on DB constraints (already in place)
2. Handle `IntegrityError` with user-friendly messages (partially done)
3. Use `SELECT FOR UPDATE` or `INSERT ... ON CONFLICT` for critical sections

---

### 3. Saga Step Numbering Inconsistency (HIGH)
**Location:** `saga_orchestrator.py:299, 329, 421`
**Impact:** Medium - Resume logic confusion

**Problem:**
```python
saga.current_step = 1  # Step 1 (Patient created)
# Step 2 SKIPPED (deprecated Firebase)
saga.current_step = 3  # Step 3 (Flow initialized)
saga.current_step = 4  # Step 4 (Message sent)
```

**Fix:** Remove `STEP_2_FIREBASE_USER_CREATED` from enum or renumber steps.

---

### 4. Schema Inconsistency: doctor_id (HIGH)
**Location:** `schemas/patient.py` vs `schemas/v2/patient.py`
**Impact:** Medium - API contract inconsistency

**Problem:**
- v1 `PatientCreate` does NOT require `doctor_id`
- v2 `PatientV2Create` DOES require `doctor_id`
- Model has `doctor_id` as NOT NULL

**Fix:** Add `doctor_id` to v1 schema or document injection from auth context.

---

### 5. Transaction Boundary Issues (HIGH)
**Location:** `creation_service.py:108-183`
**Impact:** High - Potential inconsistent state

**Problem:**
```python
except IntegrityError as e:
    await run_in_threadpool(self.db.rollback)  # DANGER
    # Patient may already be created!
```

**Fix:** Use `async with db.begin()` for atomic transactions.

---

### 6. Thread Safety Violations (HIGH)
**Location:** All services using `ThreadPoolExecutor`
**Impact:** High - SQLAlchemy sessions not thread-safe

**Problem:**
```python
patient = await run_in_threadpool(repository.create, patient_dict)
# Session shared across threads
```

**Fix:** Use `scoped_session` or create new sessions per thread.

---

### 7. Duplicate Validation Logic (MEDIUM)
**Location:** `integrity_service.py:56-252` vs `integrity_service.py:272-345`
**Impact:** Medium - Maintenance burden

**Problem:**
- `validate_patient_data()` - 197 lines
- `validate_patient_creation()` - 73 lines (duplicates 70%)

**Fix:** Remove `validate_patient_creation()`, use only `validate_patient_data()`.

---

### 8. Missing Orphan Detection (MEDIUM)
**Location:** `saga_orchestrator.py`
**Impact:** Medium - Stuck sagas not detected

**Missing:**
- No background job to detect stuck sagas
- No timeout for `IN_PROGRESS` state
- No auto-cleanup

**Fix:** Implement `detect_orphaned_sagas()` with timeout checks.

---

### 9. Phone Hash Collision Risk (MEDIUM)
**Location:** `saga_orchestrator.py:108-110`
**Impact:** Low-Medium - Collision at scale

**Problem:**
```python
phone_hash = hashlib.sha256(normalized_phone.encode()).hexdigest()[:16]
# 16 hex chars = 64 bits → 50% collision at 5 billion patients
```

**Fix:** Use full 32-char hash or minimum 24 chars (96 bits).

---

### 10. Missing Clinical Fields in v2 Schema (MEDIUM)
**Location:** `schemas/v2/patient.py`
**Impact:** Medium - Feature gap

**Missing in v2:**
- `allergies`
- `current_medications`
- `comorbidities`
- `blood_type`
- `emergency_contact_name`
- `emergency_contact_phone`

**Fix:** Add fields or document metadata storage approach.

---

## Bugs Detected

### Bug 1: CPF Normalization
**File:** `integrity_service.py:268`
**Issue:** Truncates to 11 digits without length validation
**Fix:** Add length check before truncation

### Bug 2: Nullable Phone in Duplicate Check
**File:** `integrity_service.py:321`
**Issue:** Could attempt hash of None
**Fix:** Add null check before hashing

### Bug 3: Resume Logic Off-by-One
**File:** `saga_orchestrator.py:244-250`
**Issue:** `< 3` check may skip/repeat steps
**Fix:** Use `<=` or map to constants

---

## LGPD Compliance (Excellent)

### Encryption Implementation
| Field | Storage Column | Search Column | Algorithm |
|-------|---------------|---------------|-----------|
| CPF | `cpf_encrypted` (Text) | `cpf_hash` (SHA-256) | AES-256-GCM |
| Email | `email_encrypted` (LargeBinary) | `email_hash` (SHA-256) | AES-256-GCM |
| Phone | `phone_encrypted` (LargeBinary) | `phone_hash` (SHA-256) | AES-256-GCM |

### Positive Findings
- No plaintext PII storage (removed in migration 030)
- Hash-based lookups for duplicate detection
- Backward-compatible property accessors
- Validation hooks prevent incomplete encryption

---

## Performance Analysis

### Optimizations Present
- Eager loading with `selectinload`/`joinedload`
- Redis caching for expensive operations
- Database retry decorator (`@with_db_retry`)
- Idempotency key support (DB + Redis)
- Distributed locking prevents race conditions

### Performance Risks
- Pattern-based cache invalidation (`patient_list:*:{doctor_id}*`) is O(n)
- Services instantiated per-request (could use DI)
- No circuit breaker for external services

---

## Recommendations by Priority

### P0 - Critical (This Week)
1. **Delete duplicate `patients.py`** - 0.5h
2. **Fix transaction boundaries** - 2h
3. **Add thread-safe session management** - 4h

### P1 - High (Next Sprint)
4. **Fix saga step numbering** - 4h
5. **Remove duplicate validation method** - 1h
6. **Add orphan saga detection** - 6h
7. **Extend phone hash length** - 1h

### P2 - Medium (Next Month)
8. **Split IntegrityService** - 8h
9. **Add missing v2 schema fields** - 2h
10. **Standardize async patterns** - 3h
11. **Add telemetry/tracing** - 4h

### P3 - Low (Technical Debt)
12. **Extract metadata merger utility** - 3h
13. **Create TreatmentPhase enum** - 1h
14. **Add circuit breaker for WhatsApp** - 4h

---

## Technical Debt Summary

| Component | Estimated Hours |
|-----------|----------------|
| Route cleanup | 4h |
| Service refactoring | 16h |
| Saga improvements | 14h |
| Schema standardization | 4h |
| Testing coverage | 12h |
| **Total** | **~50h** |

---

## Files Analyzed

### Models & Schemas
- `app/models/patient.py` (562 lines)
- `app/models/patient_onboarding_saga.py` (261 lines)
- `app/schemas/patient.py` (447 lines)
- `app/schemas/v2/patient.py` (210 lines)

### Routes
- `app/api/v2/routers/patients/crud.py` (458 lines)
- `app/api/v2/routers/patients.py` (426 lines) ⚠️ DUPLICATE
- `app/api/v2/routers/patients/__init__.py` (32 lines)

### Services
- `app/services/patient/crud_service.py` (193 lines)
- `app/services/patient/flow_service.py` (261 lines)
- `app/services/patient/integrity_service.py` (678 lines) ⚠️ GOD OBJECT
- `app/services/patient/onboarding_factory.py` (90 lines)

### Domain Layer
- `app/domain/patient/onboarding/coordinator.py` (186 lines)
- `app/domain/patient/onboarding/creation_service.py` (225 lines)
- `app/domain/patient/onboarding/validation_service.py` (347 lines)
- `app/domain/patient/onboarding/completion_service.py` (295 lines)

### Repository
- `app/repositories/patient/base.py` (434 lines)
- `app/repositories/patient/__init__.py` (88 lines)

### Orchestration
- `app/orchestration/saga_orchestrator.py` (785 lines)

**Total LOC Analyzed:** ~5,000+ lines

---

## Conclusion

The patient registration system is **functionally complete** with strong LGPD compliance and good separation of concerns. However, there are several **critical issues** that need attention:

1. **Code duplication** between old and new route files
2. **Race conditions** in duplicate detection
3. **Transaction boundary issues** that could cause inconsistent state
4. **Thread safety violations** in async/sync mixing

Addressing the P0 and P1 issues will significantly improve system reliability and maintainability.

---

*Report generated by Claude Code swarm analysis*
