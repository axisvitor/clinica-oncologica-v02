# Patient Registration Flow Analysis - Complete Workflow Documentation

**Analysis Date**: 2025-12-24
**Scope**: Patient CRUD operations from API to database persistence
**Purpose**: Debug patient registration workflow and identify bottlenecks

---

## 🎯 Executive Summary

The patient registration workflow follows a **Saga Pattern** for distributed transactions with comprehensive orchestration across:
- **API Layer**: FastAPI routers with RBAC, rate limiting, and field selection
- **Service Layer**: Onboarding coordinator with specialized domain services
- **Repository Layer**: LGPD-compliant data access with encryption
- **Integration Layer**: WhatsApp (Evolution API), Flow engine, Firebase (deprecated)

**Key Architecture**: Unit of Work pattern with single transaction commit at saga completion.

---

## 📊 Complete Patient Registration Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    API ENTRY POINT (POST /api/v2/patients/)         │
│  File: app/api/v2/routers/patients/crud.py:291 (create_patient)    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    IDEMPOTENCY CHECK (QW-004)                       │
│  1. Check X-Idempotency-Key header                                  │
│  2. DB lookup: PatientRepository.get_by_idempotency_key()           │
│  3. Redis cache fallback (24h TTL)                                  │
│  4. Return existing patient if found                                │
└─────────────────────────────────────────────────────────────────────┘
                              │ (new request)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AUTHORIZATION CHECK                              │
│  1. Extract user context: extract_user_context(current_user)        │
│  2. Validate doctor_id matches current user (non-admin)             │
│  3. Convert doctor_id to UUID                                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                INITIALIZE SAGA ORCHESTRATOR                         │
│  File: app/orchestration/saga_orchestrator.py:58                    │
│  Dependencies: DB, Redis, EvolutionClient                           │
│  Services: PatientRepository, PatientFlowService,                   │
│            UnifiedWhatsAppService, MessageService                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              GET ONBOARDING COORDINATOR (Factory)                   │
│  File: app/services/patient/onboarding_factory.py:47               │
│  Creates: ValidationService, NotificationService,                   │
│           CompletionService, CreationService, OnboardingCoordinator │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│            COORDINATOR: CREATE PATIENT WORKFLOW                     │
│  File: app/domain/patient/onboarding/coordinator.py:124            │
│                                                                     │
│  Step 1: VALIDATE DATA (IntegrityService)                          │
│    ├─ CPF/Email/Phone format validation                            │
│    ├─ Birth date age check (18-120 years)                          │
│    ├─ Treatment phase normalization                                │
│    └─ Integrity hash generation                                    │
│                                                                     │
│  Step 2: EXECUTE SAGA PATTERN (SagaOrchestrator)                   │
│    └─ coordinator.saga_orchestrator.execute_patient_onboarding_saga│
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌═════════════════════════════════════════════════════════════════════┐
║                    SAGA ORCHESTRATION (CORE)                        ║
║  File: app/orchestration/saga_orchestrator.py:76                   ║
║                                                                     ║
║  🔒 DISTRIBUTED LOCK ACQUISITION                                    ║
║    Lock Key: saga:onboarding:{doctor_id}:{phone_hash}              ║
║    Timeout: 5s | TTL: 60s                                           ║
║    Phone normalization + SHA-256 hash (32 chars)                   ║
║                                                                     ║
║  📝 SAGA RECORD INITIALIZATION                                      ║
║    ├─ Create PatientOnboardingSaga record                          ║
║    ├─ Status: STARTED                                               ║
║    ├─ Store patient_data JSON                                       ║
║    └─ db.flush() (no commit yet)                                    ║
║                                                                     ║
║  ┌───────────────────────────────────────────────────────┐         ║
║  │  STEP 1: CREATE PATIENT IN DATABASE                  │         ║
║  │  File: saga_orchestrator.py:286 (_step_create_patient)│        ║
║  │                                                        │         ║
║  │  1. Convert PatientCreate to dict                     │         ║
║  │  2. Extract metadata, add doctor_id                   │         ║
║  │  3. Add idempotency_key if provided (QW-004)          │         ║
║  │  4. PatientRepository.create(auto_commit=False)       │         ║
║  │     └─ Encryption: CPF, Email, Phone → AES-256-GCM    │         ║
║  │     └─ Hash generation for searchable indexes         │         ║
║  │     └─ db.flush() + refresh (no commit)               │         ║
║  │  5. Update saga: patient_id, current_step=1           │         ║
║  │  6. Saga status → STEP_1_PATIENT_CREATED               │         ║
║  │  7. Add log entry, db.flush()                          │         ║
║  └────────────────────────────────────────────────────────┘         ║
║                          │                                          ║
║                          ▼                                          ║
║  ┌───────────────────────────────────────────────────────┐         ║
║  │  STEP 2: INITIALIZE FLOW STATE                       │         ║
║  │  File: saga_orchestrator.py:331 (_step_initialize_flow)│        ║
║  │                                                        │         ║
║  │  1. PatientFlowService.initialize_default_flow()      │         ║
║  │     └─ auto_commit=False (Unit of Work)               │         ║
║  │  2. PatientFlowService.activate_patient()             │         ║
║  │     └─ Set flow_state to ACTIVE                       │         ║
║  │     └─ auto_commit=False                              │         ║
║  │  3. Update saga: current_step=3                        │         ║
║  │  4. Saga status → STEP_3_FLOW_INITIALIZED              │         ║
║  │  5. Add log entry, db.flush()                          │         ║
║  │                                                        │         ║
║  │  NOTE: STEP_2_FIREBASE_USER_CREATED is DEPRECATED     │         ║
║  │        (Firebase integration removed but enum kept     │         ║
║  │         for DB compatibility)                          │         ║
║  └────────────────────────────────────────────────────────┘         ║
║                          │                                          ║
║                          ▼                                          ║
║  ┌───────────────────────────────────────────────────────┐         ║
║  │  STEP 3: SEND WELCOME MESSAGE                        │         ║
║  │  File: saga_orchestrator.py:364 (_step_send_welcome_message)│  ║
║  │                                                        │         ║
║  │  1. Load MessageTemplate "welcome_message" from DB    │         ║
║  │  2. Format with patient.name (fallback to default)    │         ║
║  │  3. MessageService.schedule_message()                 │         ║
║  │     └─ Type: TEXT, Status: PENDING                    │         ║
║  │     └─ Metadata: {message_type: "welcome", saga_id}   │         ║
║  │  4. UnifiedWhatsAppService.send_message()             │         ║
║  │     └─ Best-effort: failure doesn't fail saga         │         ║
║  │  5. On success: mark_as_sent("queued")                │         ║
║  │  6. On failure: keep PENDING for retry task           │         ║
║  │  7. Update saga: current_step=4, status=STEP_4_MESSAGE_SENT│    ║
║  │  8. Add log entry (success or failed_nonfatal)        │         ║
║  │  9. db.flush()                                         │         ║
║  │                                                        │         ║
║  │  ⚠️  NON-BLOCKING: Message failure doesn't rollback   │         ║
║  └────────────────────────────────────────────────────────┘         ║
║                          │                                          ║
║                          ▼                                          ║
║  ┌───────────────────────────────────────────────────────┐         ║
║  │  SAGA COMPLETION                                      │         ║
║  │                                                        │         ║
║  │  1. saga.status = SagaStatus.COMPLETED                │         ║
║  │  2. saga.completed_at = now()                          │         ║
║  │  3. 🎯 UNIT OF WORK: db.commit()                       │         ║
║  │     └─ ATOMIC: All steps committed in single transaction│        ║
║  │  4. Return patient object                              │         ║
║  └────────────────────────────────────────────────────────┘         ║
║                                                                     ║
║  💥 ERROR HANDLING (saga_orchestrator.py:163)                       ║
║    ├─ ROLLBACK: db.rollback() (atomic undo)                        ║
║    ├─ Update saga status → FAILED                                  ║
║    ├─ Record error_message, error_type, failed_at                  ║
║    ├─ Commit failure state (separate transaction)                  ║
║    └─ Execute compensation (_compensate_saga)                      ║
║                                                                     ║
║  🔄 COMPENSATION LOGIC (saga_orchestrator.py:507)                   ║
║    ├─ Distributed lock: saga:compensate:{saga_id}                  ║
║    ├─ Reverse order with retry (3 attempts, exp backoff)           ║
║    ├─ Step 4: Cancel message (mark MessageStatus.CANCELLED)        ║
║    ├─ Step 3: Delete flow states (PatientFlowState hard delete)    ║
║    ├─ Step 1: Delete patient (hard delete, LGPD compliant)         ║
║    ├─ Track failures: Redis + saga.execution_log                   ║
║    └─ Status → COMPENSATED or FAILED                               ║
╚═════════════════════════════════════════════════════════════════════╝
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  POST-SAGA OPERATIONS (ROUTER)                      │
│  File: app/api/v2/routers/patients/crud.py:392                     │
│                                                                     │
│  1. Serialize patient: await serialize_patient(created)             │
│     └─ Convert ORM → dict with FlowState.value                      │
│                                                                     │
│  2. CACHE IDEMPOTENCY KEY (Redis, 24h TTL) (QW-006)                │
│     └─ Key: idempotency:patient:create:{x_idempotency_key}          │
│     └─ Value: Serialized patient JSON                               │
│                                                                     │
│  3. Return HTTP 201 Created with patient data                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Critical Files and Their Roles

### **API Layer** (`/app/api/v2/routers/patients/`)

| File | Role | Key Functions | LOC |
|------|------|---------------|-----|
| `crud.py` | CRUD operations router | `create_patient()`, `update_patient()`, `list_patients()`, `get_patient()`, `delete_patient()` | 528 |
| `flow.py` | Flow state management | `activate_patient()`, `deactivate_patient()`, `archive_patient()`, `get_patient_timeline()`, `get_patient_saga_status()` | 525 |
| `base.py` | Shared utilities | `serialize_patient()`, `ensure_patient_access()`, `validate_and_format_phone()`, `extract_user_context()` | 449 |
| `import_export.py` | CSV operations | Patient bulk import/export | ~300 |
| `integrity.py` | Data validation | CPF/email validation endpoints | ~200 |

**Key Features**:
- **Rate Limiting**: `@limiter.limit("20/hour")` on create, `"120/minute"` on list
- **RBAC**: `@require_doctor_or_admin()`, `@require_permission(Permission.PATIENT_READ)`
- **Field Selection**: `fields` query param for partial responses
- **Eager Loading**: `include=["doctor", "quiz_sessions"]` to prevent N+1 queries
- **Idempotency**: `X-Idempotency-Key` header support (QW-004)

### **Service Layer** (`/app/services/patient/`)

| File | Role | Key Functions | LOC |
|------|------|---------------|-----|
| `crud_service.py` | Basic CRUD operations | `get_patient()`, `update_patient()`, `delete_patient()`, `list_patients()` | 347 |
| `onboarding_factory.py` | Dependency injection | `get_onboarding_coordinator()` | 104 |
| `flow_service.py` | Flow state management | `activate_patient()`, `pause_patient()`, `initialize_default_flow()` | ~400 |
| `integrity_service.py` | Data integrity validation | `validate_patient_data()`, `generate_patient_hash()` | ~300 |

**Design Patterns**:
- **Unit of Work**: Transaction management with single commit
- **Factory Pattern**: `onboarding_factory` for service composition
- **Repository Pattern**: Data access abstraction

### **Domain Layer** (`/app/domain/patient/onboarding/`)

| File | Role | Key Functions | LOC |
|------|------|---------------|-----|
| `coordinator.py` | Orchestration controller | `create_patient()` - delegates to saga | 203 |
| `creation_service.py` | Direct patient creation | `create_patient_direct()` - without saga | 250 |
| `validation_service.py` | Duplicate detection | `find_existing_patient()`, `validate_patient_uniqueness()` | 361 |
| `notification_service.py` | WhatsApp/WebSocket | `send_welcome_message()`, `publish_patient_created_event()` | 301 |
| `completion_service.py` | Partial onboarding | Complete incomplete onboarding flows | ~200 |

**Responsibilities**:
- **Coordinator**: Pure orchestration, no business logic
- **CreationService**: Alternative path without saga (legacy support)
- **ValidationService**: Threaded duplicate checks with hash-based lookups
- **NotificationService**: Best-effort messaging (failures don't fail creation)

### **Orchestration Layer** (`/app/orchestration/`)

| File | Role | Key Functions | LOC |
|------|------|---------------|-----|
| `saga_orchestrator.py` | Saga pattern implementation | `execute_patient_onboarding_saga()`, `resume_saga()`, `_compensate_saga()` | 814 |

**Saga Pattern Features**:
- **Distributed Locks**: Redis-based with `acquire_lock()` (5s timeout, 60s TTL)
- **Idempotency**: Phone normalization + SHA-256 hash prevents duplicate locks
- **Unit of Work**: Single `db.commit()` at saga completion
- **Compensation**: Reverse-order rollback with retry (3 attempts, exponential backoff)
- **Non-blocking Steps**: WhatsApp message failure doesn't fail saga
- **Retry Logic**: `resume_saga()` for failed sagas with checkpoint recovery

### **Repository Layer** (`/app/repositories/patient/`)

| File | Role | Key Functions | LOC |
|------|------|---------------|-----|
| `base.py` | Core CRUD with encryption | `create()`, `update()`, `get_by_id()`, `get_by_phone()`, `get_by_idempotency_key()` | 504 |
| `search.py` | Advanced filtering | Search by name, email, status, treatment type | ~300 |
| `pagination.py` | Cursor-based pagination | `list_v2()` with `next_cursor` and `has_more` | ~200 |
| `eager_loading.py` | N+1 query prevention | Relationship pre-loading strategies | ~150 |
| `encryption_helpers.py` | LGPD compliance | CPF/email/phone encryption helpers | ~100 |

**LGPD Compliance (Post-Migration 030)**:
- **AES-256-GCM Encryption**: CPF, email, phone stored encrypted
- **SHA-256 Hashing**: Searchable indexes on hash columns
- **Plaintext Removal**: `cpf`, `email`, `phone` columns dropped in migration 030
- **Unique Constraints**: Hash-based (`cpf_hash`, `email_hash`, `phone_hash`)

### **Data Models** (`/app/models/`)

| File | Role | Key Attributes | LOC |
|------|------|----------------|-----|
| `patient.py` | Patient SQLAlchemy model | `cpf_encrypted`, `phone_hash`, `email_hash`, `flow_state`, `patient_data` (JSONB) | 602 |
| `patient_onboarding_saga.py` | Saga state tracking | `status`, `current_step`, `retry_count`, `execution_log` | 263 |
| `enums.py` | Shared enumerations | `FlowState`, `SagaStatus` | ~50 |

**Patient Model Fields**:
- **Encrypted**: `cpf_encrypted`, `email_encrypted`, `phone_encrypted` (bytea)
- **Searchable**: `cpf_hash`, `email_hash`, `phone_hash` (varchar(64), indexed)
- **Flow**: `flow_state` (enum), `current_day` (integer)
- **Metadata**: `patient_data` (JSONB) - flexible additional data
- **Soft Delete**: `deleted_at` (timestamptz, indexed)
- **Idempotency**: `idempotency_key` (varchar(64), unique, indexed)

### **Schemas** (`/app/schemas/v2/`)

| File | Role | Key Schemas | LOC |
|------|------|-------------|-----|
| `patient.py` | Request/Response validation | `PatientV2Create`, `PatientV2Update`, `PatientV2Response`, `PatientV2List` | 415 |

**Validation Features**:
- **CPF**: Check digits verification via `validate_cpf_check_digits()`
- **Phone**: Hybrid E.164/Brazilian format via `normalize_phone()` (PhoneValidationMode.HYBRID)
- **Age**: Birth date validation (18-120 years) with timedelta calculations
- **Treatment Phase**: Normalization to lowercase, pattern validation
- **Blood Type**: Uppercase normalization, regex pattern `^(A|B|AB|O)[+-]$`

---

## 🔄 Transaction Boundaries

### **Saga Transaction Strategy (Unit of Work)**

```python
# File: saga_orchestrator.py:158
try:
    # Step 1: Create Patient (db.flush() - no commit)
    patient = await self._step_create_patient(saga, patient_data, doctor_id, idempotency_key)

    # Step 2: Initialize Flow (db.flush() - no commit)
    await self._step_initialize_flow(saga, patient, current_user)

    # Step 3: Send Welcome Message (db.flush() - no commit, non-blocking)
    await self._step_send_welcome_message(saga, patient)

    # Update saga status
    saga.status = SagaStatus.COMPLETED
    saga.completed_at = datetime.now(timezone.utc)

    # 🎯 SINGLE ATOMIC COMMIT
    self.db.commit()  # All or nothing

    return patient
except Exception as e:
    # Rollback entire transaction
    self.db.rollback()

    # Update saga failure state (separate transaction)
    saga.status = SagaStatus.FAILED
    saga.error_message = str(e)
    saga.failed_at = datetime.now(timezone.utc)
    self.db.commit()  # Commit failure state

    # Execute compensation
    await self._compensate_saga(saga)
    return None
```

**Key Benefits**:
1. **Atomicity**: All saga steps commit together
2. **Consistency**: Database always in valid state
3. **Isolation**: Lock prevents concurrent modifications
4. **Durability**: Single commit ensures data persistence

### **Repository auto_commit Parameter**

```python
# File: repositories/patient/base.py:61
def create(self, obj_in: Dict[str, Any], auto_commit: bool = True) -> Patient:
    """
    Create patient with optional auto-commit.

    Args:
        auto_commit: If True (default), commits immediately.
                     If False, only flush() - caller commits (saga pattern).
    """
    patient = Patient(**data)
    self.db.add(patient)

    if auto_commit:
        self.db.commit()  # Standard behavior
        self.db.refresh(patient)
    else:
        self.db.flush()  # Saga/Unit of Work: caller commits
        self.db.refresh(patient)

    return patient
```

---

## 🔐 LGPD Compliance & Encryption

### **Encryption Flow** (Migration 020, 024, 028, 030)

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT: patient_data.cpf = "123.456.789-00"                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Patient.set_cpf(cpf_value)                                 │
│  File: models/patient.py:336                                │
│                                                              │
│  1. CPFEncryptionService.encrypt_cpf(cpf_value)             │
│     ├─ Normalize: "12345678900" (remove formatting)         │
│     ├─ AES-256-GCM encryption with Fernet                   │
│     └─ Returns: (encrypted_bytes, sha256_hash)              │
│                                                              │
│  2. Set database fields:                                    │
│     ├─ patient.cpf_encrypted = encrypted_bytes (Text)       │
│     └─ patient.cpf_hash = sha256_hash (varchar(64), indexed)│
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  DATABASE STORAGE (PostgreSQL)                              │
│                                                              │
│  cpf_encrypted: "gAAAAABh..." (AES-256 ciphertext)          │
│  cpf_hash: "5d41402abc4b2a76b9719d911017c592..." (SHA-256)  │
│                                                              │
│  ⚠️  Plaintext 'cpf' column REMOVED in migration 030        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  RETRIEVAL: patient.cpf (property)                          │
│  File: models/patient.py:322                                │
│                                                              │
│  @property                                                   │
│  def cpf(self) -> Optional[str]:                            │
│      """Backward compatibility alias for cpf_decrypted."""  │
│      return self.cpf_decrypted                              │
│                                                              │
│  @property                                                   │
│  def cpf_decrypted(self) -> Optional[str]:                  │
│      if self.cpf_encrypted:                                 │
│          service = get_cpf_encryption_service()             │
│          return service.decrypt_cpf(self.cpf_encrypted)     │
│      return None                                            │
│                                                              │
│  OUTPUT: "12345678900" (decrypted plaintext)                │
└─────────────────────────────────────────────────────────────┘
```

**Same pattern for**:
- **Email**: `email_encrypted` + `email_hash` (migration 028)
- **Phone**: `phone_encrypted` + `phone_hash` (migration 028)

### **Searchable Indexes (Hash-based)**

```python
# File: models/patient.py:199
__table_args__ = (
    # Unique constraint on hash for duplicate prevention
    UniqueConstraint("cpf_hash", "doctor_id", name="uq_patient_cpf_hash_doctor"),

    # Partial indexes for uniqueness (exclude deleted)
    Index(
        "ix_patients_email_hash_doctor",
        "email_hash", "doctor_id",
        unique=True,
        postgresql_where=sa.text("email_hash IS NOT NULL AND deleted_at IS NULL")
    ),
    Index(
        "ix_patients_phone_hash_doctor",
        "phone_hash", "doctor_id",
        unique=True,
        postgresql_where=sa.text("phone_hash IS NOT NULL AND deleted_at IS NULL")
    ),
)
```

**Hash-based Queries**:
```python
# File: repositories/patient/base.py:378
def get_by_phone(self, phone: str) -> Optional[Patient]:
    """Get patient by phone (LGPD compliant)."""
    service = get_lgpd_encryption_service()
    phone_hash = service.hash_phone(phone)

    return (
        self.db.query(Patient)
        .filter(
            Patient.phone_hash == phone_hash,
            Patient.deleted_at.is_(None)
        )
        .first()
    )
```

---

## 🔗 Integration Points

### **1. WhatsApp (Evolution API)**

**Service**: `UnifiedWhatsAppService`
**File**: `/app/services/unified_whatsapp_service.py`

```python
# Saga Step 3: Send Welcome Message
await self.whatsapp_service.send_message(message)
```

**Flow**:
1. Saga creates `Message` record (status: PENDING)
2. `UnifiedWhatsAppService.send_message()` calls Evolution API
3. Success: `MessageStatus.SENT`, external_id stored
4. Failure: Kept as PENDING for retry task (`retry_pending_welcome_messages`)

**Error Handling**: Non-blocking (message failure doesn't fail patient creation)

### **2. Flow Engine**

**Service**: `PatientFlowService`
**File**: `/app/services/patient/flow_service.py`

```python
# Saga Step 2: Initialize Flow
await self.flow_service.initialize_default_flow(patient, current_user_id, auto_commit=False)
await self.flow_service.activate_patient(patient.id, auto_commit=False)
```

**Flow States** (enum: `FlowState`):
- `ONBOARDING`: Initial registration
- `ACTIVE`: Treatment in progress
- `PAUSED`: Temporarily suspended
- `COMPLETED`: Treatment finished
- `CANCELLED`: Archived/deactivated

**Database**: `PatientFlowState` table (separate from patient record)

### **3. WebSocket Events**

**Service**: `WebSocketEventService`
**File**: `/app/services/websocket_events.py`

```python
# Post-creation event broadcast
await websocket_events.publish_patient_event(
    event_type=WebSocketEventType.PATIENT_UPDATED,
    patient_id=patient.id,
    doctor_id=doctor_id,
    changes={"action": "created"}
)
```

**Use Case**: Real-time frontend updates (patient list refresh without polling)

### **4. Firebase (DEPRECATED)**

**Status**: Removed in recent refactoring
**Evidence**: `STEP_2_FIREBASE_USER_CREATED` enum still exists in `SagaStatus` for DB compatibility but is **skipped** in saga execution

---

## 🚨 Validation & Error Handling

### **Validation Layers**

#### **1. Pydantic Schema Validation** (`PatientV2Create`)

```python
# File: schemas/v2/patient.py:76
@field_validator("cpf")
@classmethod
def validate_cpf(cls, v):
    """Validate CPF with check digits verification."""
    if not v.replace(".", "").replace("-", "").isdigit():
        raise ValueError("CPF deve conter apenas dígitos, pontos e traços")

    if not validate_cpf_check_digits(v):
        raise ValueError("CPF inválido: dígitos verificadores incorretos")

    return re.sub(r"\D", "", v)  # Return digits only

@field_validator("birth_date")
@classmethod
def validate_min_age(cls, v: Optional[date]) -> Optional[date]:
    """Validate patient is at least 18 years old."""
    if v is None:
        return v

    today = date.today()
    min_date = today - timedelta(days=int(18 * 365.25))

    if v > min_date:
        age_years = (today - v).days / 365.25
        raise ValueError(f"Patient must be at least 18 years old. Age: {age_years:.1f}")

    # Also check max 120 years
    max_date = today - timedelta(days=int(120 * 365.25))
    if v < max_date:
        raise ValueError(f"Birth date invalid (over 120 years old)")

    return v
```

#### **2. IntegrityService Validation**

```python
# File: services/patient/integrity_service.py
await self.integrity_service.validate_patient_data(
    patient_data=patient_data,
    doctor_id=doctor_id,
    is_update=False
)
```

**Checks**:
- CPF/Email/Phone format and uniqueness
- Data integrity hash generation
- Cross-field validation (treatment dates, etc.)

#### **3. ORM-Level Validation** (`Patient` model)

```python
# File: models/patient.py:240
@validates("birth_date")
def validate_birth_date_age(self, key, value: Optional[date]) -> Optional[date]:
    """Validate patient age at ORM level (18-120 years)."""
    if value is None:
        return value

    today = date.today()
    min_date = today - timedelta(days=int(18 * 365.25))

    if value > min_date:
        age_years = (today - value).days / 365.25
        raise ValueError(f"Patient must be at least 18 years old. Age: {age_years:.1f}")

    return value

@validates("patient_data")
def validate_metadata_schema(self, key, value: Optional[Dict[str, Any]]):
    """Validate patient_data (metadata) against JSON schema."""
    if value is None or value == {}:
        return value or {}

    from app.utils.jsonb_validator import validate_patient_metadata
    return validate_patient_metadata(value)
```

#### **4. Database Constraints** (PostgreSQL)

```sql
-- File: alembic/versions/033_fix_user_sync_log_schema.py

-- Unique constraints (hash-based for LGPD)
ALTER TABLE patients
ADD CONSTRAINT uq_patient_cpf_hash_doctor
UNIQUE (cpf_hash, doctor_id);

-- Partial unique indexes (exclude soft-deleted)
CREATE UNIQUE INDEX ix_patients_phone_hash_doctor
ON patients (phone_hash, doctor_id)
WHERE phone_hash IS NOT NULL AND deleted_at IS NULL;

CREATE UNIQUE INDEX ix_patients_email_hash_doctor
ON patients (email_hash, doctor_id)
WHERE email_hash IS NOT NULL AND deleted_at IS NULL;

-- Idempotency key (QW-004)
CREATE UNIQUE INDEX ix_patients_idempotency_key
ON patients (idempotency_key)
WHERE idempotency_key IS NOT NULL;
```

### **Error Propagation Chain**

```
Pydantic ValidationError
    ↓
HTTP 422 Unprocessable Entity

IntegrityService ValidationError
    ↓
HTTP 400 Bad Request

Database IntegrityError (duplicate CPF/email/phone)
    ↓
Saga rollback + compensation
    ↓
HTTP 400 Bad Request (ValidationError with code)

Saga Exception (any step failure)
    ↓
db.rollback() + _compensate_saga()
    ↓
saga.status = FAILED
    ↓
HTTP 400 Bad Request (or 500 if unexpected)
```

---

## 🔍 Potential Bottlenecks & Failure Points

### **1. Distributed Lock Contention**

**Location**: `saga_orchestrator.py:117`

```python
lock_key = f"saga:onboarding:{str(doctor_id)[:8]}:{phone_hash}"
async with acquire_lock(lock_key, timeout=5.0, ttl=60):
    # Saga execution (avg 2-5 seconds)
```

**Risk**:
- **Concurrent requests** for same patient (duplicate form submission)
- **Lock timeout** (5s) may be too short for slow network/DB

**Mitigation**:
- Phone normalization + SHA-256 hash reduces collision risk
- TTL (60s) covers saga execution with margin
- Idempotency key provides secondary protection

### **2. WhatsApp API Failures**

**Location**: `saga_orchestrator.py:409`

```python
try:
    success = await self.whatsapp_service.send_message(message)
except Exception as send_exc:
    # NON-FATAL: Keep message PENDING for retry
    message.status = MessageStatus.PENDING
    message.message_metadata["welcome_send_failed"] = True
```

**Risk**:
- Evolution API downtime
- Network timeouts
- Rate limiting (if enabled)

**Mitigation**:
- **Best-effort delivery**: WhatsApp failure doesn't fail saga
- **Retry task**: `retry_pending_welcome_messages` Celery task
- **Message status tracking**: PENDING messages retried periodically

### **3. Database Transaction Timeouts**

**Location**: `saga_orchestrator.py:158`

```python
# Long-running transaction (3 steps + commit)
try:
    patient = await self._step_create_patient(...)  # Step 1: ~200ms
    await self._step_initialize_flow(...)           # Step 2: ~150ms
    await self._step_send_welcome_message(...)      # Step 3: ~500ms (WhatsApp call)
    self.db.commit()  # Total: ~850ms + network latency
```

**Risk**:
- **PostgreSQL lock wait timeout** (default: 30s)
- **Slow WhatsApp API** delays commit
- **Row-level locks** on doctor/user FK during FK checks

**Mitigation**:
- Unit of Work pattern minimizes transaction duration
- `db.flush()` instead of `commit()` per step (no locks)
- WhatsApp call is async (non-blocking)

### **4. Compensation Failures**

**Location**: `saga_orchestrator.py:595`

```python
async def _compensate_step_with_retry(self, saga, step_num, compensate_fn, ...):
    """Execute compensation with retry (3 attempts, exponential backoff)."""
    for attempt in range(max_retries):
        try:
            await compensate_fn(saga)
            return  # Success
        except Exception as e:
            wait_time = (2**attempt) * 0.5  # 0.5s, 1s, 2s
            await asyncio.sleep(wait_time)

    # All retries exhausted
    compensation_errors.append((step_num, last_error))
    await self._track_compensation_failure(saga.id, step_num, last_error)
```

**Risk**:
- **Cascading failures**: If compensation fails, database left inconsistent
- **Orphaned records**: Patient/flow states not cleaned up
- **Manual intervention required**: Redis tracking for ops team

**Mitigation**:
- **3 retry attempts** with exponential backoff
- **Redis failure tracking** (7-day retention)
- **Saga execution log** (`saga.execution_log`) for audit trail
- **SagaCompensationError** exception with detailed context

### **5. Idempotency Key Collisions**

**Location**: `crud.py:316`

```python
if x_idempotency_key:
    existing = repo.get_by_idempotency_key(x_idempotency_key)
    if existing:
        return await serialize_patient(existing)  # Return cached
```

**Risk**:
- **Hash collision** (unlikely with 64-char SHA-256)
- **TTL expiration**: Redis cache expires after 24h, DB key persists forever
- **Key reuse**: Different patients with same key (API client error)

**Mitigation**:
- **Database unique constraint**: `ix_patients_idempotency_key` prevents duplicates
- **Redis + DB dual check**: Fast cache, persistent DB
- **Client-generated UUIDs**: Recommended key format

---

## 📈 Performance Optimizations

### **1. Eager Loading (N+1 Prevention)**

```python
# File: repositories/patient/base.py:364
query = query.options(
    selectinload(Patient.quiz_sessions),  # 1:many - separate query
    selectinload(Patient.flow_states),     # 1:many - separate query
    joinedload(Patient.doctor),            # 1:1 - join
)
```

**Benefit**: Reduces queries from `N+1` to `2` (quiz_sessions, flow_states) + `1` (doctor join)

### **2. Cursor-based Pagination**

```python
# File: api/v2/routers/patients/crud.py:171
patients, has_more, next_cursor, total = repo.list_v2(
    filters=filters,
    cursor_data=pagination["cursor_data"],
    limit=pagination["limit"],
    sort_by=sort_by,
    sort_order=sort_order,
)
```

**Benefit**: Consistent performance with large datasets (no OFFSET scan)

### **3. Partial Field Selection**

```python
# File: api/v2/dependencies.py
if fields:
    patient_dict = apply_field_selection(patient_dict, fields)
```

**Benefit**: Reduces payload size (exclude `doctor_notes`, large JSONB, etc.)

### **4. Redis Caching**

- **Idempotency keys**: 24h TTL for fast duplicate detection
- **Session data**: User context cached (900s TTL)
- **Lock keys**: Distributed locks with auto-expiry

---

## 🎯 Key Takeaways for Debugging

### **1. Saga Pattern Benefits**
✅ **Atomic Operations**: All or nothing - database always consistent
✅ **Distributed Locks**: Prevents duplicate patient creation
✅ **Compensation Logic**: Automatic rollback on failure
✅ **Retry Support**: `resume_saga()` for failed sagas
✅ **Audit Trail**: `execution_log` tracks every step

### **2. LGPD Compliance**
✅ **AES-256-GCM Encryption**: CPF, email, phone stored encrypted
✅ **SHA-256 Hashing**: Searchable indexes without plaintext
✅ **Migration 030**: Plaintext columns fully removed
✅ **Validation Hooks**: `validate_cpf_encryption` prevents incomplete encryption

### **3. Error Resilience**
✅ **Non-blocking WhatsApp**: Message failure doesn't fail creation
✅ **Retry Tasks**: `retry_pending_welcome_messages` recovers failed sends
✅ **Compensation Retry**: 3 attempts with exponential backoff
✅ **Redis Tracking**: Compensation failures logged for ops

### **4. Performance Optimizations**
✅ **Eager Loading**: `selectinload`, `joinedload` prevent N+1 queries
✅ **Cursor Pagination**: Efficient for large patient lists
✅ **Field Selection**: Reduce API payload size
✅ **Auto-commit Parameter**: Repository supports saga pattern

### **5. Integration Points**
✅ **WhatsApp**: Evolution API via `UnifiedWhatsAppService`
✅ **Flow Engine**: State machine via `PatientFlowService`
✅ **WebSocket**: Real-time events via `WebSocketEventService`
✅ **Firebase**: Deprecated (STEP_2 skipped)

---

## 🔧 Debugging Checklist

When investigating patient registration issues:

### **Before Saga Execution**
- [ ] Check `X-Idempotency-Key` header (duplicate request?)
- [ ] Verify user permissions (`@require_doctor_or_admin()`)
- [ ] Validate input schema (`PatientV2Create` validation errors)
- [ ] Check phone normalization (E.164 format)

### **During Saga Execution**
- [ ] Check distributed lock acquisition (Redis logs)
- [ ] Verify `PatientOnboardingSaga` record created
- [ ] Monitor `current_step` progression (1 → 3 → 4)
- [ ] Check `execution_log` for step failures
- [ ] Verify `auto_commit=False` on repository calls

### **On Saga Failure**
- [ ] Check `saga.status` (FAILED vs COMPENSATING)
- [ ] Review `saga.error_message` and `error_type`
- [ ] Verify compensation executed (`execution_log` entries)
- [ ] Check Redis for compensation failure tracking
- [ ] Look for orphaned records (patient without flow state)

### **Post-Creation**
- [ ] Verify `Message` record created (status: SENT or PENDING)
- [ ] Check WhatsApp service logs (Evolution API response)
- [ ] Confirm WebSocket event broadcast (frontend refresh)
- [ ] Validate cache invalidation (patient list updated)
- [ ] Check idempotency key stored in Redis (24h TTL)

---

## 📚 Related Documentation

- **Database Schema**: `/docs/database/01_SCHEMA_MODELS.md`
- **LGPD Compliance**: `/docs/database/03_SECURITY_COMPLIANCE.md`
- **Performance Optimization**: `/docs/database/04_PERFORMANCE.md`
- **Saga Pattern**: `SAGA_DEBUG_FINAL_REPORT.md`
- **Transaction Management**: `TRANSACTION_MANAGEMENT_CRUD_SERVICE.md`

---

**Document Version**: 1.0
**Last Updated**: 2025-12-24
**Maintained By**: Research Agent (Patient Registration Analysis)
