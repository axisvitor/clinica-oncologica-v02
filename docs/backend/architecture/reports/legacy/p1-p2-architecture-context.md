# P1/P2 Architecture Context - Clinica Oncologica v02

**Date:** 2025-12-23
**Agent:** Code Analyzer
**Purpose:** Architectural context for P1 (Version Standardization) and P2 (Transaction Management, Audit Logging, Code Quality) implementations

---

## Executive Summary

This document provides a comprehensive architectural overview of the Clinica Oncologica codebase to guide P1/P2 implementation priorities. The system is a FastAPI-based backend with React/TypeScript frontend, following Domain-Driven Design with clear service separation.

### Key Architecture Patterns
- **Backend:** FastAPI + SQLAlchemy (async) + PostgreSQL
- **Frontend:** React 18 + TypeScript + React Query
- **Security:** LGPD-compliant encryption, RBAC, CSRF protection
- **Testing:** Pytest with SQLite/PostgreSQL dual support
- **Version Control:** Semantic versioning (x.y.z) with legacy integer support

---

## 1. Backend Architecture (backend-hormonia/)

### 1.1 Core Models (`/app/models/`)

#### BaseModel Pattern
**File:** `/app/models/base.py` (33 lines)

```python
class BaseModel(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

**Usage:** All domain models inherit from BaseModel for consistent ID/timestamp handling.

**P1/P2 Integration Points:**
- **Version Standardization:** Add `version` column to templates (QuizTemplate, FlowTemplate)
- **Audit Logging:** `created_at`/`updated_at` already provide temporal audit trail
- **Transaction Management:** Works seamlessly with SQLAlchemy transaction context

#### Patient Model (LGPD Compliance Example)
**File:** `/app/models/patient.py` (602 lines)

**Key Features:**
- **Encryption:** CPF, email, phone stored encrypted with searchable hash indexes
- **JSONB Metadata:** Flexible `patient_data` field for dynamic attributes
- **Soft Delete:** `deleted_at` column instead of hard deletes
- **Validation:** ORM-level validators for birth_date (18-120 years) and JSONB schema

**Properties Pattern:**
```python
@property
def cpf_decrypted(self) -> Optional[str]:
    if self.cpf_encrypted:
        from app.services.encryption import get_cpf_encryption_service
        service = get_cpf_encryption_service()
        return service.decrypt_cpf(self.cpf_encrypted)
    return None

def set_cpf(self, cpf_value: Optional[str]) -> None:
    """Automatic encryption + hash generation"""
    service = get_cpf_encryption_service()
    encrypted_cpf, cpf_hash = service.encrypt_cpf(cpf_value)
    self.cpf_encrypted = encrypted_cpf
    self.cpf_hash = cpf_hash
```

**P1/P2 Integration:**
- **Audit Logging:** Track all PII access via `AuditLogger.log_access()`
- **Transaction Management:** Encryption hooks execute within transaction boundary
- **Code Quality:** Clear separation of concerns (encryption service layer)

#### Quiz Models
**File:** `/app/models/quiz.py` (362 lines)

**Models:**
1. **QuizTemplate** - Template definitions with versioning
2. **QuizSession** - Patient session tracking (status: started/completed/cancelled/expired)
3. **QuizResponse** - Individual question responses with JSONB storage

**Constraints:**
- Unique constraint: `(name, version)` on QuizTemplate
- Unique constraint: `(quiz_session_id, question_id)` on QuizResponse
- Partial unique index: Only one "started" session per patient+template

**P1 Priority:** QuizTemplate already has `version` column (String) - standardize to semantic versioning

---

### 1.2 Service Layer (`/app/services/`)

#### CRUD Service Pattern
**File:** `/app/services/patient/crud_service.py` (230 lines)

**Responsibilities:**
- Get patient by ID/phone
- List with pagination/filters
- Update patient data
- Soft delete/restore
- Cache invalidation

**Pattern:**
```python
class PatientCRUDService:
    def __init__(self, db: Any, repository: Optional[PatientRepository] = None):
        self.db = db
        self.repository = repository or PatientRepository(db)

    @with_db_retry(max_retries=3)
    def get_patient(self, patient_id: UUID) -> Patient:
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")
        return patient
```

**P1/P2 Integration:**
- **Transaction Management:** Already uses `@with_db_retry` decorator pattern
- **Audit Logging:** Add `AuditLogger.log()` calls to CRUD operations
- **Code Quality:** Clear SRP - only CRUD, no business logic

#### Service Separation Pattern
**Files:**
- `/app/services/patient/crud_service.py` - Basic CRUD (230 lines)
- `/app/services/patient/flow_service.py` - Flow state management
- `/app/services/patient/integrity_service.py` - Data validation
- `/app/services/patient/onboarding_factory.py` - Creation orchestration

**P2 Best Practice:** This separation pattern should be followed for all new services.

---

### 1.3 Utilities (`/app/utils/`)

#### Version Utils (P1 Foundation)
**File:** `/app/utils/version_utils.py` (356 lines)

**Functions:**
- `parse_version(version)` → `(major, minor, patch)`
- `normalize_version(version)` → `"x.y.z"`
- `compare_versions(v1, v2)` → `-1/0/1`
- `is_valid_version(version)` → `bool`
- `increment_major/minor/patch(version)` → `"x.y.z"`

**Usage Example:**
```python
from app.utils.version_utils import normalize_version, compare_versions

# Standardize version
template.version = normalize_version(template.version)  # "1" → "1.0.0"

# Compare versions
if compare_versions(current_version, required_version) < 0:
    raise ValueError("Version too old")
```

**P1 Implementation:** Use `normalize_version()` in all template loaders/validators.

#### Transaction Manager (P1 Foundation)
**File:** `/app/utils/transaction_manager.py` (218 lines)

**Features:**
- `async_transaction()` - Context manager for async DB operations
- `sync_transaction()` - Context manager for sync DB operations
- `@with_transaction()` - Decorator for automatic transaction wrapping

**Usage Example:**
```python
from app.utils.transaction_manager import async_transaction

async def create_patient_with_saga(db: AsyncSession, patient_data: dict):
    async with async_transaction(db, auto_commit=True) as session:
        patient = Patient(**patient_data)
        session.add(patient)
        # Auto-commits on success, auto-rolls back on exception
        return patient
```

**P1 Implementation:**
- Replace manual `db.commit()`/`db.rollback()` with context managers
- Use `@with_transaction()` decorator for service methods

#### Audit Logger (P2 Foundation)
**File:** `/app/utils/audit_logger.py` (237 lines)

**Classes:**
- `AuditAction` - Enum (CREATE, UPDATE, DELETE, READ, etc.)
- `AuditLogger` - Static methods for structured logging

**Usage Example:**
```python
from app.utils.audit_logger import AuditLogger, AuditAction

AuditLogger.log(
    action=AuditAction.UPDATE,
    resource_type="quiz_template",
    resource_id=str(template.id),
    user_id=current_user["id"],
    user_role=current_user["role"],
    details={"version": "1.2.0", "changes": ["questions updated"]},
    ip_address=request.client.host,
    success=True
)
```

**P2 Implementation:**
- Add audit calls to all CRUD operations
- Log all template version changes
- Track PII access (patient data views)

---

### 1.4 API Routes (`/app/api/v2/routers/`)

#### Router Pattern (Patients CRUD Example)
**File:** `/app/api/v2/routers/patients/crud.py` (528 lines)

**Endpoints:**
- `GET /` - List patients (cursor pagination, filters)
- `GET /{patient_id}` - Get patient by ID
- `POST /` - Create patient (saga orchestration)
- `PATCH /{patient_id}` - Update patient
- `DELETE /{patient_id}` - Soft delete

**RBAC Pattern:**
```python
@router.get("/", response_model=PatientV2List)
@require_permission(Permission.PATIENT_READ)
@limiter.limit("120/minute")
async def list_patients(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    pagination=Depends(get_pagination_params),
):
    # RBAC: Non-admin users can only see their own patients
    if role_enum != UserRole.ADMIN:
        filters["doctor_id"] = current_user_uuid
    # ...
```

**P1/P2 Integration:**
- **Audit Logging:** Add after all state-changing operations
- **Transaction Management:** Ensure all DB operations use context managers
- **Error Handling:** Use `HTTPException` with proper status codes

---

### 1.5 Test Infrastructure (`/tests/`)

#### Conftest Pattern
**File:** `/tests/conftest.py` (216 lines)

**Fixtures:**
- `test_engine` - SQLite/PostgreSQL engine with type compatibility
- `db_session` - Transactional session (auto-rollback)
- `client` - FastAPI TestClient with DB override
- `test_user` - User factory (pre-hashed password for speed)
- `test_patient` - Patient factory
- `authenticated_client` - Client with auth headers

**Key Feature - SQLite Compatibility:**
```python
class JSONBCompat(TypeDecorator):
    """JSONB → Text for SQLite"""
    impl = Text
    def process_bind_param(self, value, dialect):
        return json.dumps(value) if value is not None else value
    def process_result_value(self, value, dialect):
        return json.loads(value) if value is not None else value
```

**Critical Tests Conftest:**
**File:** `/tests/api/critical/conftest.py` (343 lines)

**Additional Features:**
- Firebase token caching (session scope)
- Lazy app loading (faster test startup)
- Mock saga coordinator (prevents transaction conflicts)
- Pre-computed bcrypt hash (27s → 0s per test)

**P1/P2 Testing:**
- Add version validation tests to `test_version_utils.py`
- Add transaction rollback tests to `test_transaction_manager.py`
- Add audit log verification to integration tests

---

## 2. Frontend Architecture (frontend-hormonia/)

### 2.1 API Client (`/src/lib/api-client/`)

#### Core Client Pattern
**File:** `/src/lib/api-client/core.ts` (518 lines)

**Features:**
- Request/response handling with retry logic (3 attempts, exponential backoff)
- CSRF token management (automatic fetch + header injection)
- Auth token management (Bearer token)
- Error handling with user-friendly messages (Portuguese)
- Timeout handling (15s default)

**HTTP Methods:**
```typescript
class ApiClientCore {
  async get<T>(endpoint: string, params?: Record<string, string | number | boolean>): Promise<T>
  async post<T, TData = unknown>(endpoint: string, data?: TData, params?): Promise<T>
  async put<T, TData = unknown>(endpoint: string, data?: TData, params?): Promise<T>
  async patch<T, TData = unknown>(endpoint: string, data?: TData, params?): Promise<T>
  async delete<T>(endpoint: string, params?): Promise<T>
}
```

**Error Handling:**
```typescript
export class ApiError extends Error {
  public userFriendlyMessage: string;  // Localized message
  public retryable: boolean;           // Auto-retry flag
  public status: number;
  public data: unknown;
}
```

#### Module Pattern
**File:** `/src/lib/api-client/index.ts` (972 lines)

**Domain Modules:**
- `auth` - Authentication (login, logout, session)
- `patients` - Patient CRUD + flow operations
- `monthlyQuiz` - Quiz link generation + session management
- `analytics` - Dashboard metrics
- `admin` - User management

**Modular Architecture:**
```typescript
export class ApiClient extends ApiClientCore {
  public readonly auth: ReturnType<typeof createAuthApi>;
  public readonly patients: ReturnType<typeof createPatientsApi>;
  public readonly monthlyQuiz: ReturnType<typeof createMonthlyQuizApi>;
  // ... 14 domain modules
}

// Singleton instance
export const apiClient = new ApiClient(getApiUrl());
```

**P1/P2 Frontend Integration:**
- Add version parameter to template endpoints
- Update error messages for version conflicts
- Add audit trail viewer components

---

## 3. Key Patterns for P1/P2 Implementation

### 3.1 Version Standardization (P1)

**Files to Update:**

1. **Template Models:**
   - `app/models/quiz.py` - `QuizTemplate.version` (already String)
   - `app/models/flow.py` - `FlowTemplate.version` (needs verification)

2. **Template Loaders:**
   - `app/services/quiz_template_loader.py`
   - `app/services/versioned_template_loader.py`
   - `app/services/template_loader.py`

3. **Template Validators:**
   - `app/services/flow/templates/validator.py`
   - `app/services/flow/validation/validator.py`

**Implementation Pattern:**
```python
from app.utils.version_utils import normalize_version, is_valid_version

class QuizTemplateLoader:
    def load_template(self, name: str, version: Union[str, int, None]) -> QuizTemplate:
        # Normalize version
        normalized = normalize_version(version)

        # Query with normalized version
        template = (
            db.query(QuizTemplate)
            .filter_by(name=name, version=normalized)
            .first()
        )

        if not template:
            raise NotFoundError(f"Template {name} v{normalized} not found")

        return template
```

### 3.2 Transaction Management (P1)

**Files to Update:**

1. **Service Methods:**
   - `app/services/patient/crud_service.py` - All CRUD methods
   - `app/services/quiz/quiz_service.py` - Session creation
   - `app/domain/quizzes/session/factory.py` - Session factory

2. **Repository Methods:**
   - `app/repositories/patient/base.py`
   - `app/repositories/quiz.py`

**Implementation Pattern:**
```python
from app.utils.transaction_manager import with_transaction

class PatientCRUDService:
    @with_transaction(auto_commit=True)
    async def update_patient(self, db: AsyncSession, patient_id: UUID, data: dict) -> Patient:
        """Auto-commits on success, auto-rolls back on error"""
        patient = await self.repository.get_by_id(patient_id)
        for key, value in data.items():
            setattr(patient, key, value)

        db.add(patient)
        # Transaction context manager handles commit/rollback
        return patient
```

### 3.3 Audit Logging (P2)

**Files to Update:**

1. **API Routes:**
   - `app/api/v2/routers/patients/crud.py` - All endpoints
   - `app/api/v2/routers/quiz_templates.py` - Template CRUD
   - `app/api/v2/routers/template_admin.py` - Admin operations

2. **Service Methods:**
   - `app/services/patient/crud_service.py`
   - `app/services/quiz/quiz_service.py`

**Implementation Pattern:**
```python
from app.utils.audit_logger import AuditLogger, AuditAction

@router.post("/", response_model=PatientV2Response)
@require_doctor_or_admin()
async def create_patient(
    request: Request,
    patient_data: PatientV2Create,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    try:
        patient = await coordinator.create_patient(patient_data, doctor_id)

        # Audit successful creation
        AuditLogger.log(
            action=AuditAction.CREATE,
            resource_type="patient",
            resource_id=str(patient.id),
            user_id=current_user["id"],
            user_role=current_user["role"],
            details={
                "name": patient.name,
                "phone_hash": patient.phone_hash[:8] + "..."  # Don't log PII
            },
            ip_address=request.client.host,
            success=True
        )

        return serialize_patient(patient)

    except Exception as e:
        # Audit failed creation
        AuditLogger.log(
            action=AuditAction.CREATE,
            resource_type="patient",
            resource_id="N/A",
            user_id=current_user["id"],
            details={"attempted_name": patient_data.name},
            ip_address=request.client.host,
            success=False,
            error_message=str(e)
        )
        raise
```

---

## 4. Integration Points

### 4.1 Database Schema

**Current State:**
- PostgreSQL 14+ with JSONB, UUID, full-text search
- SQLAlchemy 2.0 (async) with declarative models
- Alembic migrations in `/backend-hormonia/alembic/versions/`

**P1/P2 Changes Needed:**
- Migration: Add semantic version validation check to `quiz_templates.version`
- Migration: Add `audit_logs` table (or use existing `audit.py` model)
- Index: Create index on `(resource_type, resource_id, created_at)` for audit queries

### 4.2 Testing Strategy

**Unit Tests:**
- `test_version_utils.py` - Version parsing, comparison, validation
- `test_transaction_manager.py` - Transaction context managers, rollback
- `test_audit_logger.py` - Audit log formatting, batch operations

**Integration Tests:**
- `test_patient_crud.py` - CRUD with version tracking + audit
- `test_quiz_session.py` - Session creation with transaction + audit
- `test_template_versioning.py` - Template version conflicts

**Critical Path Tests:**
- `/tests/api/critical/test_patients_crud.py` - Real PostgreSQL with saga
- `/tests/api/critical/test_quiz_session.py` - Session flow with DB

### 4.3 Cache Invalidation

**Current Cache Layers:**
1. **Redis** - Session cache, quiz links, idempotency keys
2. **Application** - Template cache, user cache
3. **Query** - Patient lists, analytics

**P1/P2 Impact:**
- Template version changes must invalidate template cache
- Audit logs don't need caching (write-heavy, infrequent reads)
- Transaction failures must not leave stale cache entries

**Implementation:**
```python
from app.infrastructure.cache import get_unified_cache_manager

def update_template_with_versioning(template_id: UUID, new_version: str):
    cache_manager = get_unified_cache_manager()

    # Update with transaction
    async with async_transaction(db) as session:
        template.version = normalize_version(new_version)
        session.add(template)

    # Invalidate cache AFTER successful commit
    cache_manager.invalidate_pattern(
        f"quiz_template:*:{template_id}*",
        namespace="cache"
    )
```

---

## 5. Potential Conflicts & Challenges

### 5.1 Version Migration
**Challenge:** Existing templates have mixed version formats (int vs semantic)

**Solution:**
1. Data migration script to convert all versions to semantic format
2. Keep `to_int_version()` helper for backward compatibility
3. Add database constraint after migration

### 5.2 Transaction Boundaries
**Challenge:** Saga pattern uses multiple internal commits

**Solution:**
- Use Unit of Work pattern (already implemented in recent saga refactor)
- Single commit at saga completion
- Mock saga coordinator in tests (already in critical conftest)

### 5.3 Audit Log Volume
**Challenge:** Audit logging every CRUD operation could generate massive logs

**Solution:**
- Partition audit_logs table by month
- Implement log rotation (90-day retention for non-compliance logs)
- Use async background tasks for audit writes (don't block requests)
- Add sampling for high-frequency READ operations

### 5.4 LGPD Compliance
**Challenge:** Audit logs contain references to patient data

**Solution:**
- Store only hash/IDs in audit logs, never plaintext PII
- Example: `{"patient_id": "uuid", "phone_hash": "abc123...", "action": "view"}`
- Use `AuditLogger.log_access()` for PII access tracking
- Audit logs subject to same retention policies as patient data

---

## 6. Recommended Implementation Order

### Phase 1: Foundation (Week 1)
1. ✅ **Version Utils** - Already implemented (`version_utils.py`)
2. ✅ **Transaction Manager** - Already implemented (`transaction_manager.py`)
3. ✅ **Audit Logger** - Already implemented (`audit_logger.py`)
4. **Unit Tests** - Test all three utilities

### Phase 2: Database (Week 1-2)
1. **Migration** - Add semantic version constraint to templates
2. **Migration** - Add audit_logs table (if not using existing)
3. **Migration** - Add indexes for audit queries
4. **Data Migration** - Convert existing versions to semantic format

### Phase 3: Backend Integration (Week 2-3)
1. **Template Loaders** - Add `normalize_version()` to all loaders
2. **Template Validators** - Add version validation
3. **Service Methods** - Replace manual transactions with `@with_transaction()`
4. **CRUD Routes** - Add audit logging to all state-changing endpoints

### Phase 4: Testing (Week 3-4)
1. **Integration Tests** - Version conflicts, transaction rollback, audit trails
2. **Critical Path Tests** - End-to-end with real PostgreSQL
3. **Performance Tests** - Audit log write performance, cache invalidation timing

### Phase 5: Frontend (Week 4)
1. **API Client** - Add version parameter to template endpoints
2. **UI Components** - Display template versions, version history
3. **Error Handling** - User-friendly messages for version conflicts

---

## 7. Code Quality Metrics

### Current State (Representative Samples)

| Module | LOC | Complexity | Pattern Adherence |
|--------|-----|-----------|------------------|
| `version_utils.py` | 356 | Low | ✅ Well-documented, comprehensive tests |
| `transaction_manager.py` | 218 | Low | ✅ Clean context managers, decorator pattern |
| `audit_logger.py` | 237 | Low | ✅ Static methods, clear responsibility |
| `patient.py` (model) | 602 | Medium | ✅ LGPD compliance, property pattern |
| `crud_service.py` | 230 | Low | ✅ SRP, clear separation |
| `crud.py` (routes) | 528 | Medium | ⚠️ Large file, could split further |

### P2 Goals
- **Target LOC per file:** < 500 (currently 528 max in routers)
- **Cyclomatic Complexity:** < 10 per function
- **Test Coverage:** > 90% for utils, > 80% for services
- **Documentation:** All public methods have docstrings

---

## 8. Architecture Decision Records (ADRs)

### ADR-001: Semantic Versioning for Templates
**Decision:** Use semantic versioning (x.y.z) for all templates

**Rationale:**
- More expressive than integer versions
- Backward compatible with legacy int versions via `to_int_version()`
- Standard across industry (SemVer)

**Consequences:**
- Requires data migration for existing templates
- Query patterns change (string comparison vs integer)
- Benefits: Better version conflict resolution, clear breaking changes

### ADR-002: Context Manager Pattern for Transactions
**Decision:** Use `async_transaction()` context manager instead of manual commit/rollback

**Rationale:**
- Prevents transaction leaks
- Automatic rollback on errors
- Cleaner code (no try/finally blocks)

**Consequences:**
- Requires async/await support throughout stack
- Decorator pattern for services (`@with_transaction()`)
- Benefits: Fewer bugs, better error handling, consistent pattern

### ADR-003: Structured Audit Logging
**Decision:** Use `AuditLogger` static methods with JSON-structured logs

**Rationale:**
- Easier to parse and query (JSON format)
- Separate log stream from application logs
- Supports compliance requirements (LGPD)

**Consequences:**
- Additional write overhead on state-changing operations
- Log storage requirements increase
- Benefits: Full audit trail, security compliance, debugging support

---

## 9. Quick Reference

### File Locations
```
backend-hormonia/
├── app/
│   ├── models/
│   │   ├── base.py           # BaseModel (UUID, timestamps)
│   │   ├── patient.py        # LGPD encryption, validators
│   │   └── quiz.py           # Template versioning
│   ├── services/
│   │   ├── patient/
│   │   │   ├── crud_service.py       # CRUD operations
│   │   │   ├── flow_service.py       # Flow management
│   │   │   └── integrity_service.py  # Validation
│   │   └── quiz/
│   │       └── quiz_service.py
│   ├── api/v2/routers/
│   │   ├── patients/crud.py  # Patient CRUD endpoints
│   │   └── quiz_templates.py # Template management
│   ├── utils/
│   │   ├── version_utils.py         # P1 foundation ✅
│   │   ├── transaction_manager.py   # P1 foundation ✅
│   │   └── audit_logger.py          # P2 foundation ✅
│   └── repositories/
│       ├── patient/base.py
│       └── quiz.py
└── tests/
    ├── conftest.py              # Test fixtures
    ├── api/critical/conftest.py # Critical path fixtures
    └── utils/
        ├── test_version_utils.py
        ├── test_transaction_manager.py
        └── test_audit_logger.py
```

### Import Patterns
```python
# Version Standardization (P1)
from app.utils.version_utils import normalize_version, compare_versions

# Transaction Management (P1)
from app.utils.transaction_manager import async_transaction, with_transaction

# Audit Logging (P2)
from app.utils.audit_logger import AuditLogger, AuditAction
```

### Testing Patterns
```python
# Pytest fixture usage
def test_patient_crud(db_session, test_user, authenticated_client):
    """Test with pre-configured DB session and auth"""

# Mock saga for transaction isolation
def test_patient_creation(mock_saga_patient, authenticated_client):
    """Test without real saga commits"""
```

---

## 10. Next Steps for P1/P2 Implementation

### Immediate Actions
1. ✅ Review this architecture document
2. Create unit tests for `version_utils.py`, `transaction_manager.py`, `audit_logger.py`
3. Write Alembic migration for semantic version constraint
4. Update template loaders to use `normalize_version()`

### Coder Agent Handoff
- **Input:** This architecture context document
- **Output:** Implementation PRs with tests
- **Coordination:** Use memory store for progress tracking

### Reviewer Agent Handoff
- **Input:** Implementation PRs from Coder
- **Output:** Code review report with quality checks
- **Focus:** Pattern adherence, test coverage, documentation

---

**End of Architecture Context Document**

*Generated by Code Analyzer Agent - 2025-12-23*
