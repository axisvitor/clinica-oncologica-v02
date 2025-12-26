# Patient CRUD Architecture Research Report

**Date:** 2025-12-23
**Session ID:** swarm-patient-crud
**Research Agent:** Researcher
**Status:** ✅ Complete

---

## Executive Summary

This report provides a comprehensive mapping of the Patient CRUD architecture, documenting the complete data flow from API to database, all integration points, and architectural patterns. The system follows a clean architecture pattern with clear separation of concerns across multiple layers.

---

## 1. Architecture Overview

### Layer Structure

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                      │
│  /app/api/v2/routers/patients/                               │
│  ├── crud.py          (CRUD endpoints)                       │
│  ├── base.py          (Shared utilities)                     │
│  ├── flow.py          (Flow management)                      │
│  ├── integrity.py     (Data integrity)                       │
│  └── import_export.py (CSV operations)                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                            │
│  /app/services/patient/                                      │
│  ├── crud_service.py        (Basic CRUD)                     │
│  ├── integrity_service.py   (Validation - SINGLE SOURCE)     │
│  ├── flow_service.py        (Flow lifecycle)                 │
│  └── onboarding_factory.py (Dependency injection)            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Domain Layer (Onboarding)                   │
│  /app/domain/patient/onboarding/                             │
│  ├── coordinator.py         (Workflow orchestration)         │
│  ├── validation_service.py  (Duplicate detection)            │
│  ├── creation_service.py    (Patient creation logic)         │
│  ├── notification_service.py (WhatsApp notifications)        │
│  └── completion_service.py  (Flow completion)                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Repository Layer                            │
│  /app/repositories/patient/                                  │
│  ├── base.py              (Core CRUD operations)             │
│  ├── search.py            (Search queries)                   │
│  ├── pagination.py        (Pagination logic)                 │
│  ├── encryption_helpers.py (LGPD compliance)                 │
│  ├── eager_loading.py     (N+1 prevention)                   │
│  └── audit.py             (Audit trail)                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      Database Layer                           │
│  PostgreSQL + Supabase                                       │
│  ├── patients table (main data)                             │
│  ├── patient_flow_states (flow tracking)                    │
│  ├── patient_onboarding_sagas (saga orchestration)          │
│  └── messages (WhatsApp integration)                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Complete Data Flow Mapping

### 2.1 Patient Creation Flow (POST /patients/)

```
┌──────────────────────────────────────────────────────────────────┐
│                    1. API REQUEST ENTRY                          │
│  File: app/api/v2/routers/patients/crud.py:create_patient()     │
│  ────────────────────────────────────────────────────────────── │
│  Input:                                                          │
│   - PatientV2Create (schema)                                     │
│   - X-Idempotency-Key header (QW-004)                           │
│   - current_user (from session)                                  │
│                                                                  │
│  Validations:                                                    │
│   ✓ Idempotency check (database + Redis cache)                  │
│   ✓ Doctor ID format validation                                 │
│   ✓ Authorization (doctors can only create for themselves)      │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│              2. ONBOARDING COORDINATOR INITIALIZATION            │
│  File: app/services/patient/onboarding_factory.py              │
│  ────────────────────────────────────────────────────────────── │
│  Factory creates and wires:                                      │
│   - PatientRepository                                            │
│   - PatientIntegrityService (validation)                         │
│   - PatientFlowService (flow lifecycle)                          │
│   - ValidationService (duplicate detection)                      │
│   - NotificationService (WhatsApp)                               │
│   - CompletionService (flow completion)                          │
│   - CreationService (patient creation)                           │
│   - SagaOrchestrator (distributed transactions)                  │
│   - MessageService (message handling)                            │
│   - UnifiedWhatsAppService (WhatsApp API)                        │
│                                                                  │
│  Returns: Fully configured OnboardingCoordinator                 │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                 3. SAGA PATTERN EXECUTION                        │
│  File: app/orchestration/saga_orchestrator.py                   │
│  ────────────────────────────────────────────────────────────── │
│  Distributed Lock Acquisition:                                   │
│   - Lock key: saga:onboarding:{doctor_id}:{phone_hash}          │
│   - Timeout: 5.0s                                                │
│   - TTL: 60s                                                     │
│   - Purpose: Prevent concurrent creation of same patient         │
│                                                                  │
│  Saga Steps (ACID Transaction):                                  │
│   ┌───────────────────────────────────────────────┐             │
│   │ STEP 1: Create Patient in Database            │             │
│   │  - Validates all data via IntegrityService    │             │
│   │  - Encrypts PII (LGPD compliance)             │             │
│   │  - Sets idempotency_key (QW-004)              │             │
│   │  - Creates patient record (flush, no commit)  │             │
│   │  - Updates saga: current_step = 1             │             │
│   └───────────────────────────────────────────────┘             │
│                         ↓                                        │
│   ┌───────────────────────────────────────────────┐             │
│   │ STEP 2: Initialize Patient Flow               │             │
│   │  - Selects flow template based on treatment   │             │
│   │  - Creates PatientFlowState record            │             │
│   │  - Sets flow_state = ONBOARDING               │             │
│   │  - Updates saga: current_step = 2             │             │
│   └───────────────────────────────────────────────┘             │
│                         ↓                                        │
│   ┌───────────────────────────────────────────────┐             │
│   │ STEP 3: Send Welcome WhatsApp Message         │             │
│   │  - Creates welcome message record             │             │
│   │  - Sends via UnifiedWhatsAppService           │             │
│   │  - Updates saga: current_step = 3             │             │
│   └───────────────────────────────────────────────┘             │
│                                                                  │
│  SINGLE COMMIT (Unit of Work):                                   │
│   - All changes committed together                               │
│   - Saga status = COMPLETED                                      │
│   - OR full rollback on any failure                              │
│                                                                  │
│  Compensation (on failure):                                       │
│   - Deletes patient record                                       │
│   - Deletes flow state                                           │
│   - Marks saga as FAILED                                         │
│   - Logs error for monitoring                                    │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                    4. CACHE INVALIDATION                         │
│  Files: app/services/patient/crud_service.py                    │
│         app/infrastructure/cache.py                              │
│  ────────────────────────────────────────────────────────────── │
│  Redis Cache Keys Invalidated:                                   │
│   - idempotency:patient:create:{key} (TTL: 24h)                 │
│   - patient_by_id:*:{patient_id}*                               │
│   - patient_list:*:{doctor_id}*                                 │
│                                                                  │
│  Purpose: Ensure cache consistency after mutations               │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                    5. RESPONSE SERIALIZATION                     │
│  File: app/api/v2/routers/patients/base.py:serialize_patient()  │
│  ────────────────────────────────────────────────────────────── │
│  Response Format (PatientV2Response):                            │
│   {                                                              │
│     "id": "uuid",                                                │
│     "name": "string",                                            │
│     "email": "string" (decrypted),                               │
│     "phone": "string" (decrypted, E.164 format),                 │
│     "cpf": "string" (decrypted),                                 │
│     "doctor_id": "uuid",                                         │
│     "treatment_type": "string",                                  │
│     "treatment_start_date": "date",                              │
│     "flow_state": "onboarding",                                  │
│     "current_day": 0,                                            │
│     "created_at": "timestamp",                                   │
│     "updated_at": "timestamp"                                    │
│   }                                                              │
│                                                                  │
│  LGPD Compliance: All PII is decrypted on-the-fly for response  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Patient Listing Flow (GET /patients/)

```
API Request → PatientRepository.list_v2()
            ↓
  Build Filters (search, status, treatment, dates)
            ↓
  Apply RBAC (non-admins filtered by doctor_id)
            ↓
  Execute Query with:
    - Cursor-based pagination
    - Eager loading (prevents N+1)
    - Sorting (default: created_at desc)
            ↓
  Serialize Patients (decrypt PII)
            ↓
  Return PatientV2List:
    {
      "data": [...],
      "next_cursor": "string",
      "has_more": true,
      "total": 123
    }
```

### 2.3 Patient Update Flow (PATCH /patients/{id})

```
API Request → Validate patient_id (UUID format)
            ↓
  Check existence → PatientRepository.get_by_id()
            ↓
  Verify access → ensure_patient_access()
            ↓
  Validate update data → PatientIntegrityService.validate_patient_data()
            ↓
  Check doctor reassignment (RBAC)
            ↓
  Execute update → PatientCRUDService.update_patient()
            ↓
  Invalidate caches
            ↓
  Return updated patient (serialized)
```

### 2.4 Patient Deletion Flow (DELETE /patients/{id})

```
API Request → Validate patient_id
            ↓
  Check existence
            ↓
  Verify access (admin only)
            ↓
  Soft delete → PatientCRUDService.delete_patient()
    - Sets deleted_at = now()
    - Preserves data for audit
            ↓
  Invalidate caches
            ↓
  Return success message
```

---

## 3. Integration Points

### 3.1 WhatsApp Integration

**Component:** `UnifiedWhatsAppService`
**Location:** `/app/services/unified_whatsapp_service.py`

**Integration Flow:**
```
Patient Creation → Welcome Message
                ↓
  NotificationService → UnifiedWhatsAppService
                ↓
  EvolutionClient → Evolution API
                ↓
  WhatsApp Message Sent
                ↓
  Message record created in DB
```

**Tables:**
- `messages` - Stores all WhatsApp messages
- `message_templates` - Template definitions

**Features:**
- Template-based messaging
- Delivery status tracking
- Error handling with retries
- Webhook support for status updates

### 3.2 Flow System Integration

**Component:** `PatientFlowService`
**Location:** `/app/services/patient/flow_service.py`

**Flow Lifecycle:**
```
Patient Created → initialize_default_flow()
                ↓
  Select template based on treatment_type
                ↓
  EnhancedFlowEngine.enroll_patient()
                ↓
  Create PatientFlowState record
                ↓
  Set flow_state = ONBOARDING
                ↓
  Update patient metadata
```

**Flow Templates:**
- `INITIAL_15_DAYS` - Default onboarding
- `HORMONE_THERAPY` - Specific treatment flows
- `FOLLOW_UP` - Post-treatment monitoring

**Flow States (Enum):**
- `ONBOARDING` - Initial patient setup
- `ACTIVE` - Treatment in progress
- `PAUSED` - Temporarily stopped
- `COMPLETED` - Treatment finished
- `CANCELLED` - Flow terminated

### 3.3 Quiz System Integration

**Tables:**
- `quiz_sessions` - Quiz attempts
- `quiz_responses` - Individual answers

**Relationships:**
- Patient → QuizSession (1:many)
- Patient → QuizResponse (1:many)

**Eager Loading:**
```python
# app/repositories/patient/base.py
query.options(
    selectinload(Patient.quiz_sessions),
    selectinload(Patient.flow_states),
    joinedload(Patient.doctor)
)
```

### 3.4 Onboarding Saga Integration

**Component:** `SagaOrchestrator`
**Location:** `/app/orchestration/saga_orchestrator.py`

**Saga Pattern:**
- **Purpose:** Ensure distributed transaction consistency
- **Steps:** Patient creation → Flow initialization → Welcome message
- **Compensation:** Automatic rollback on any step failure
- **Idempotency:** QW-004 support via idempotency_key

**Saga States:**
- `STARTED` - Execution in progress
- `COMPLETED` - All steps successful
- `FAILED` - Error occurred, compensation executed
- `COMPENSATED` - Rollback completed

**Resume Capability:**
```python
# Resume failed saga
saga_orchestrator.resume_saga(saga_id)
```

---

## 4. Data Validation Patterns

### 4.1 Validation Layers

**Layer 1: Pydantic Schema Validation**
File: `/app/schemas/patient.py`

```python
class PatientCreate(PatientBase):
    @field_validator("cpf")
    def validate_cpf_number(cls, v):
        # CPF format and check digits

    @field_validator("birth_date")
    def validate_min_age(cls, v):
        # Minimum 18 years old (LOW-004)

    @field_validator("metadata")
    def validate_metadata_schema(cls, v):
        # JSON schema validation (LOW-007)
```

**Layer 2: Service Layer Validation (SINGLE SOURCE OF TRUTH)**
File: `/app/services/patient/integrity_service.py`

```python
class PatientIntegrityService:
    async def validate_patient_data():
        """
        Comprehensive validation:
        1. CPF normalization and validation
        2. Phone E.164 formatting
        3. Email validation
        4. Duplicate checks (CPF, phone, email)
        5. Doctor existence
        6. Treatment dates
        7. Birth date constraints
        8. Name length
        9. Treatment type
        10. Diagnosis/phase limits
        """
```

**Layer 3: Database Constraints**
File: `/app/models/patient.py`

```python
# Unique constraints (LGPD-compliant)
UniqueConstraint("cpf_hash", "doctor_id", name="uq_patient_cpf_hash_doctor")

# Partial unique indexes
Index("ix_patients_email_hash_doctor", "email_hash", "doctor_id",
      unique=True,
      postgresql_where=text("email_hash IS NOT NULL AND deleted_at IS NULL"))
```

### 4.2 LGPD Compliance (Data Encryption)

**Encrypted Fields:**
- `cpf_encrypted` - AES-256-GCM encrypted
- `email_encrypted` - AES-256-GCM encrypted
- `phone_encrypted` - AES-256-GCM encrypted

**Searchable Hash Fields:**
- `cpf_hash` - SHA-256 hash for queries
- `email_hash` - SHA-256 hash for queries
- `phone_hash` - SHA-256 hash for queries

**Migration History:**
- Migration 020: CPF encryption added
- Migration 024: CPF plaintext column removed
- Migration 028: Email/phone encryption added
- Migration 030: Email/phone plaintext columns removed

**Encryption Service:**
```python
# app/services/encryption.py
service = get_lgpd_encryption_service()
encrypted, hash = service.encrypt_email(email)

# Decryption (on-demand)
email = service.decrypt_email(encrypted)
```

**QW-003 Validation Hook:**
```python
@event.listens_for(Patient, "before_insert")
@event.listens_for(Patient, "before_update")
def validate_cpf_encryption(mapper, connection, target):
    """Ensure CPF is properly encrypted before DB operations"""
    if target.cpf_encrypted and not target.cpf_hash:
        raise ValueError("CPF encryption incomplete")
```

---

## 5. Error Handling Patterns

### 5.1 Exception Hierarchy

```
ValidationError (app.exceptions)
  └── Used for business logic validation failures

NotFoundError (app.exceptions)
  └── Patient not found errors

HTTPException (FastAPI)
  └── 400 - Invalid input
  └── 401 - Unauthorized
  └── 403 - Forbidden
  └── 404 - Not found
  └── 500 - Internal server error

SagaCompensationError (app.orchestration)
  └── Saga rollback failures (critical)

LockAcquisitionError (app.core.distributed_lock)
  └── Concurrent saga execution prevention
```

### 5.2 Error Handling Flow

```python
# API Layer
try:
    patient = await coordinator.create_patient(...)
except ValidationError as e:
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")
```

### 5.3 Saga Compensation

```python
# On any step failure:
try:
    # Execute saga steps
except Exception as e:
    logger.error(f"Saga failed: {e}")
    self.db.rollback()  # Rollback entire transaction
    saga.status = SagaStatus.FAILED
    await self._compensate_saga(saga)  # Execute compensation
    return None
```

---

## 6. Caching Strategy

### 6.1 Cache Layers

**Layer 1: Redis Cache**
- Session data (TTL: 900s)
- User data (TTL: 900s)
- Idempotency keys (TTL: 86400s)
- Patient lists (TTL: configurable)

**Layer 2: Database Query Cache**
- SQLAlchemy query cache
- Connection pooling

### 6.2 Cache Keys

```
idempotency:patient:create:{key}      # 24h TTL
patient_by_id:*:{patient_id}*         # Variable TTL
patient_list:*:{doctor_id}*           # Variable TTL
session:{session_id}                  # 15min TTL
user_by_uid:{firebase_uid}            # 15min TTL
```

### 6.3 Invalidation Strategy

```python
def _invalidate_patient_caches(patient_id: UUID, doctor_id: UUID):
    """Invalidate all caches related to patient"""
    # Individual patient cache
    invalidate_patient_cache(str(patient_id))

    # Pattern-based invalidation
    cache_manager.invalidate_pattern(f"patient_by_id:*:{patient_id}*")
    cache_manager.invalidate_pattern(f"patient_list:*:{doctor_id}*")
```

---

## 7. Performance Optimizations

### 7.1 N+1 Query Prevention

**Strategy: Eager Loading**

```python
# app/repositories/patient/base.py
def get_by_id(patient_id: UUID, eager_load: bool = True):
    query = db.query(Patient).filter(Patient.id == patient_id)

    if eager_load:
        query = query.options(
            selectinload(Patient.quiz_sessions),   # 1:many
            selectinload(Patient.flow_states),      # 1:many
            joinedload(Patient.doctor)              # 1:1
        )

    return query.first()
```

**Optimization Impact:**
- Before: 1 + N queries (N = number of related entities)
- After: 2-3 queries total (regardless of N)

### 7.2 Database Indexes

```sql
-- Performance indexes (migration 034)
CREATE INDEX ix_patients_cpf_hash ON patients(cpf_hash);
CREATE INDEX ix_patients_email_hash ON patients(email_hash);
CREATE INDEX ix_patients_phone_hash ON patients(phone_hash);
CREATE INDEX ix_patients_doctor_id ON patients(doctor_id);
CREATE INDEX ix_patients_flow_state ON patients(flow_state);
CREATE INDEX ix_patients_deleted_at ON patients(deleted_at);

-- Composite indexes
CREATE INDEX ix_patients_cpf_hash_doctor
  ON patients(cpf_hash, doctor_id)
  WHERE cpf_hash IS NOT NULL;

-- Partial unique indexes
CREATE UNIQUE INDEX ix_patients_email_hash_doctor
  ON patients(email_hash, doctor_id)
  WHERE email_hash IS NOT NULL AND deleted_at IS NULL;
```

### 7.3 Connection Pooling

```python
# app/core/database_config.py
SQLALCHEMY_DATABASE_URI = settings.DATABASE_URL
pool_size = 20
max_overflow = 10
pool_timeout = 30
pool_recycle = 3600
```

### 7.4 Retry Logic

```python
# app/utils/db_retry.py
@with_db_retry(max_retries=3)
def get_patient(patient_id: UUID):
    """Automatic retry on transient DB errors"""
```

---

## 8. Transaction Management

### 8.1 Unit of Work Pattern

**Saga Orchestrator:**
```python
# SINGLE COMMIT at the end
async def execute_patient_onboarding_saga():
    try:
        # Step 1: Create patient (flush, no commit)
        patient = create_patient()
        self.db.flush()

        # Step 2: Initialize flow (flush, no commit)
        flow_state = initialize_flow()
        self.db.flush()

        # Step 3: Send message (flush, no commit)
        message = send_welcome_message()
        self.db.flush()

        # Single commit for all steps
        self.db.commit()

    except Exception:
        # Rollback everything on any failure
        self.db.rollback()
        await compensate()
```

### 8.2 Transaction Isolation

**Default Level:** READ COMMITTED

**Special Cases:**
- Idempotency checks: READ COMMITTED (allows concurrent reads)
- Saga execution: SERIALIZABLE (via distributed lock)

---

## 9. Security Patterns

### 9.1 Authentication

**Method:** Firebase Session Tokens
**Storage:** Redis (TTL: 900s)
**Validation:** `get_current_user_from_session()`

```python
# Check session in Redis
session_data = redis_cache.get_session(session_id)

# Validate Firebase UID
user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
```

### 9.2 Authorization (RBAC)

**Roles:**
- `ADMIN` - Full access to all patients
- `DOCTOR` - Access only to own patients
- `PATIENT` - Read-only access to own data

**Permission Checks:**
```python
# Decorator-based
@require_permission(Permission.PATIENT_READ)
@require_doctor_or_admin()

# Function-based
ensure_patient_access(current_user, patient.doctor_id)
```

### 9.3 Rate Limiting

```python
@limiter.limit("120/minute")  # List patients
@limiter.limit("20/hour")     # Create patient
@limiter.limit("30/hour")     # Update patient
```

### 9.4 Input Sanitization

**Pydantic Validation:**
- Email format validation
- Phone E.164 normalization
- CPF format and check digits
- SQL injection prevention (ORM-based)
- XSS prevention (no HTML allowed)

---

## 10. Monitoring and Observability

### 10.1 Logging

**Levels:**
- `INFO` - Normal operations
- `WARNING` - Recoverable issues
- `ERROR` - Operation failures
- `DEBUG` - Detailed debugging

**Structured Logging:**
```python
logger.info(
    "Patient created successfully",
    extra={
        "patient_id": str(patient.id),
        "doctor_id": str(doctor_id),
        "saga_id": str(saga.id)
    }
)
```

### 10.2 Metrics

**Key Metrics:**
- Patient creation rate
- Saga completion rate
- Saga failure rate
- Average saga execution time
- Cache hit ratio
- Database query performance

### 10.3 WebSocket Events

```python
# Real-time updates
await websocket_events.publish_patient_event(
    event_type=WebSocketEventType.PATIENT_CREATED,
    patient_id=patient_id,
    doctor_id=doctor_id,
    changes={"flow_state": "onboarding"}
)
```

---

## 11. Identified Issues and Recommendations

### 11.1 Potential Issues

**Issue 1: CPF Normalization Truncation**
**Location:** `/app/services/patient/integrity_service.py:288`
**Severity:** LOW
**Description:** CPF normalization truncates to 11 chars without validation first
```python
# Current
return normalized[:11]  # Silent truncation

# Recommendation
if len(normalized) != 11:
    logger.warning(f"CPF length mismatch: {len(normalized)}")
return normalized if len(normalized) == 11 else None
```

**Issue 2: Saga Resume Skip Risk**
**Location:** `/app/orchestration/saga_orchestrator.py:256`
**Severity:** MEDIUM
**Description:** Use `<` instead of `<=` could skip steps on resume
```python
# Fixed version uses <=
if saga.current_step <= 1:  # Ensures step not skipped
    await self._step_initialize_flow(saga, patient, None)
```

**Issue 3: Missing Transaction Timeout**
**Location:** Saga execution
**Severity:** MEDIUM
**Description:** No timeout on saga transactions could cause locks
```python
# Recommendation
async with acquire_lock(lock_key, timeout=5.0, ttl=60):
    with transaction_timeout(max_duration=55):  # Added
        await execute_saga_steps()
```

### 11.2 Performance Recommendations

**Recommendation 1: Implement Query Result Caching**
- Cache frequently accessed patient lists
- TTL: 60 seconds
- Invalidate on mutation

**Recommendation 2: Add Database Query Monitoring**
- Track slow queries (>100ms)
- Identify missing indexes
- Optimize N+1 queries

**Recommendation 3: Implement Circuit Breaker for WhatsApp**
- Prevent cascade failures
- Fallback to async message queue
- Retry with exponential backoff

---

## 12. Dependencies Graph

```
API Layer
  ├── PatientRepository (direct)
  ├── PatientCRUDService
  │   └── PatientRepository
  ├── PatientIntegrityService
  │   └── PatientRepository
  └── OnboardingCoordinator
      ├── PatientIntegrityService
      ├── ValidationService
      ├── SagaOrchestrator
      │   ├── PatientRepository
      │   ├── PatientFlowService
      │   │   └── EnhancedFlowEngine
      │   ├── UnifiedWhatsAppService
      │   │   └── EvolutionClient
      │   └── MessageService
      ├── NotificationService
      │   ├── MessageService
      │   └── UnifiedWhatsApp Service
      ├── CompletionService
      │   ├── PatientFlowService
      │   └── NotificationService
      └── CreationService
          ├── PatientIntegrityService
          ├── CompletionService
          ├── NotificationService
          ├── ValidationService
          └── PatientFlowService
```

---

## 13. File Inventory

### API Layer
- `/app/api/v2/routers/patients/crud.py` (528 lines)
- `/app/api/v2/routers/patients/base.py` (450 lines)
- `/app/api/v2/routers/patients/flow.py`
- `/app/api/v2/routers/patients/integrity.py`
- `/app/api/v2/routers/patients/import_export.py`

### Service Layer
- `/app/services/patient/crud_service.py` (230 lines)
- `/app/services/patient/integrity_service.py` (651 lines)
- `/app/services/patient/flow_service.py` (267 lines)
- `/app/services/patient/onboarding_factory.py` (97 lines)

### Domain Layer
- `/app/domain/patient/onboarding/coordinator.py` (200+ lines)
- `/app/domain/patient/onboarding/validation_service.py`
- `/app/domain/patient/onboarding/creation_service.py`
- `/app/domain/patient/onboarding/notification_service.py`
- `/app/domain/patient/onboarding/completion_service.py`

### Repository Layer
- `/app/repositories/patient/base.py` (459 lines)
- `/app/repositories/patient/search.py`
- `/app/repositories/patient/pagination.py`
- `/app/repositories/patient/encryption_helpers.py`
- `/app/repositories/patient/eager_loading.py`
- `/app/repositories/patient/audit.py`

### Orchestration
- `/app/orchestration/saga_orchestrator.py` (300+ lines)

### Models
- `/app/models/patient.py` (602 lines)
- `/app/models/patient_onboarding_saga.py`
- `/app/models/flow.py`

### Schemas
- `/app/schemas/patient.py` (390 lines)
- `/app/schemas/v2/patient.py`

---

## 14. Testing Recommendations

### 14.1 Critical Test Paths

**Unit Tests:**
- PatientIntegrityService validation logic
- CPF/Email/Phone encryption/decryption
- Saga compensation logic
- Cache invalidation

**Integration Tests:**
- Full patient creation flow (API → DB)
- Saga resume functionality
- WhatsApp integration (mocked)
- Idempotency key handling

**E2E Tests:**
- Complete patient onboarding workflow
- Concurrent patient creation (same phone)
- Failed saga compensation
- Cache consistency after mutations

### 14.2 Test Data

**Valid Patient:**
```json
{
  "phone": "+5511987654321",
  "name": "João Silva",
  "email": "joao@example.com",
  "cpf": "12345678909",
  "birth_date": "1990-01-01",
  "treatment_type": "hormone_therapy",
  "doctor_id": "uuid-here"
}
```

**Edge Cases:**
- Duplicate CPF (same doctor)
- Duplicate phone (different doctors)
- Invalid CPF check digits
- Under 18 years old
- Concurrent creation attempts
- Saga failure at each step

---

## 15. Conclusion

The Patient CRUD architecture demonstrates a well-structured, clean architecture pattern with clear separation of concerns. The system implements sophisticated patterns including:

✅ **Clean Architecture** - Clear layer separation
✅ **SAGA Pattern** - Distributed transaction management
✅ **LGPD Compliance** - Full PII encryption
✅ **N+1 Prevention** - Comprehensive eager loading
✅ **Idempotency** - QW-004 duplicate prevention
✅ **RBAC** - Role-based access control
✅ **Caching** - Multi-layer caching strategy
✅ **Error Handling** - Comprehensive exception handling
✅ **Observability** - Structured logging and WebSocket events

### Next Steps for Debug

1. **Review Saga Execution Logs** - Check for partial failures
2. **Validate Cache Consistency** - Ensure proper invalidation
3. **Monitor Database Locks** - Identify transaction conflicts
4. **Test Idempotency** - Verify duplicate prevention
5. **Audit Encryption** - Confirm LGPD compliance

---

**Research Completed By:** Researcher Agent
**Session Duration:** 53.19 seconds
**Memory Key:** `patient-crud-debug/research/dataflow`
**Coordination:** Claude Flow Hooks
