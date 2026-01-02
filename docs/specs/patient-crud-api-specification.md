# Patient CRUD API Specification

**Research Agent:** Researcher
**Session ID:** swarm-patient-crud-research
**Date:** 2025-12-23
**Status:** ✅ Complete

---

## Executive Summary

This document provides the complete API specification for patient CRUD operations based on comprehensive analysis of:
- 15+ documentation files
- Database migrations (33+ migration files)
- API route handlers (5 router files)
- Service layer (4 service files)
- Repository layer (6 repository files)
- Test suites (40+ test files)

The system implements a **clean architecture pattern** with **LGPD-compliant encryption**, **saga-based orchestration**, and **comprehensive validation**.

---

## 1. API Endpoints Overview

### Base URL
```
/api/v2/patients
```

### Endpoints

| Method | Endpoint | Description | Auth | Rate Limit |
|--------|----------|-------------|------|------------|
| GET | `/` | List patients with pagination | Doctor/Admin | 120/min |
| GET | `/{patient_id}` | Get patient by ID | Doctor/Admin | 120/min |
| POST | `/` | Create new patient | Doctor/Admin | 20/hour |
| PATCH | `/{patient_id}` | Update patient | Doctor/Admin | 30/hour |
| DELETE | `/{patient_id}` | Soft delete patient | Admin only | N/A |

---

## 2. Data Models

### 2.1 PatientV2Create (Request)

```typescript
{
  // Required fields
  "phone": string,              // E.164 format: +5511999999999
  "name": string,               // 1-200 characters
  "doctor_id": string,          // UUID format

  // Optional fields
  "email": string | null,       // Valid email format
  "birth_date": date | null,    // ISO 8601 date
  "cpf": string | null,         // Brazilian CPF with check digits
  "treatment_type": string | null,     // Max 150 chars
  "treatment_start_date": date | null, // ISO 8601 date
  "doctor_notes": string | null,       // Max 2000 chars
  "diagnosis": string | null,          // Max 500 chars
  "treatment_phase": string | null,    // Max 100 chars
  "timezone": string            // Default: "America/Sao_Paulo"
}
```

**Validation Rules:**
- `phone`: Must be E.164 format (`+5511999999999`) or Brazilian format (10-11 digits)
- `name`: Required, 1-200 characters
- `email`: Optional, valid email format with MX record validation
- `cpf`: Optional, 11 digits with valid check digits
- `birth_date`: Optional, must be 18+ years old (LOW-004)
- `doctor_id`: Required, valid UUID, must exist in database

### 2.2 PatientV2Response (Response)

```typescript
{
  // Identity
  "id": string,                 // UUID
  "name": string,
  "doctor_id": string,          // UUID

  // Contact (decrypted PII)
  "email": string | null,       // Decrypted from email_encrypted
  "phone": string,              // Decrypted from phone_encrypted
  "cpf": string | null,         // Decrypted from cpf_encrypted

  // Demographics
  "birth_date": date | null,
  "timezone": string,

  // Treatment
  "treatment_type": string | null,
  "treatment_start_date": date | null,
  "diagnosis": string | null,
  "treatment_phase": string | null,
  "doctor_notes": string | null,

  // Flow state
  "flow_state": string,         // Enum: onboarding, active, paused, completed, cancelled
  "current_day": number,        // Default: 0

  // Timestamps
  "created_at": datetime,
  "updated_at": datetime,

  // Optional eager-loaded relationships
  "doctor": {
    "id": string,
    "name": string,
    "email": string | null
  } | null,

  "quiz_sessions": [
    {
      "id": string,
      "status": string,
      "started_at": datetime,
      "completed_at": datetime | null,
      "score": number | null,
      "passed": boolean | null
    }
  ] | null
}
```

### 2.3 PatientV2List (Paginated Response)

```typescript
{
  "data": PatientV2Response[],  // Array of patients
  "next_cursor": string | null, // Base64-encoded cursor for next page
  "has_more": boolean,          // True if more results available
  "total": number               // Total count (may be estimated)
}
```

### 2.4 PatientV2Update (Request)

```typescript
{
  // All fields optional (partial update)
  "name": string | null,
  "email": string | null,
  "phone": string | null,
  "birth_date": date | null,
  "cpf": string | null,
  "doctor_id": string | null,         // Admin only
  "treatment_type": string | null,
  "treatment_start_date": date | null,
  "doctor_notes": string | null,
  "diagnosis": string | null,
  "treatment_phase": string | null
}
```

---

## 3. Endpoint Specifications

### 3.1 List Patients

```http
GET /api/v2/patients/
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cursor` | string | No | Pagination cursor (base64) |
| `limit` | integer | No | Page size (1-100, default: 20) |
| `fields` | string[] | No | Field selection (comma-separated) |
| `include` | string[] | No | Eager load relationships: `doctor`, `quiz_sessions` |
| `search` | string | No | Search by name or email (partial match) |
| `status` | string | No | Filter by flow_state |
| `treatment_type` | string | No | Filter by treatment type |
| `treatment_phase` | string | No | Filter by treatment phase |
| `start_date_from` | date | No | Filter by treatment_start_date >= |
| `start_date_to` | date | No | Filter by treatment_start_date <= |
| `has_active_flow` | boolean | No | Filter by active flow state |
| `created_after` | datetime | No | Filter by created_at >= |
| `created_before` | datetime | No | Filter by created_at <= |
| `sort_by` | string | No | Sort field (default: `created_at`) |
| `sort_order` | string | No | `asc` or `desc` (default: `desc`) |

**RBAC Rules:**
- **Admin**: Can see all patients
- **Doctor**: Can only see own patients (filtered by `doctor_id`)

**Response:**
```json
{
  "data": [...],
  "next_cursor": "eyJpZCI6IjEyM2U0NTY3LWU4OWItMTJkMy1hNDU2LTQyNjYxNDE3NDAwMCJ9",
  "has_more": true,
  "total": 150
}
```

**Status Codes:**
- `200 OK`: Success
- `403 Forbidden`: Unable to determine user context (non-admin)
- `500 Internal Server Error`: Unexpected error

---

### 3.2 Get Patient by ID

```http
GET /api/v2/patients/{patient_id}
```

**Path Parameters:**
- `patient_id` (string, required): Patient UUID

**Query Parameters:**
- `fields` (string[], optional): Field selection
- `include` (string[], optional): Eager load relationships

**RBAC Rules:**
- **Admin**: Can access any patient
- **Doctor**: Can only access own patients

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "João Silva",
  "phone": "+5511987654321",
  "email": "joao@example.com",
  "doctor_id": "223e4567-e89b-12d3-a456-426614174001",
  "flow_state": "active",
  "current_day": 12,
  "created_at": "2025-01-01T10:00:00Z",
  "updated_at": "2025-01-15T14:30:00Z"
}
```

**Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid patient ID format
- `403 Forbidden`: User lacks permissions
- `404 Not Found`: Patient not found
- `500 Internal Server Error`: Unexpected error

---

### 3.3 Create Patient

```http
POST /api/v2/patients/
```

**Headers:**
- `X-Idempotency-Key` (optional): Unique key for duplicate request prevention (QW-004)

**Request Body:**
```json
{
  "name": "João Silva",
  "phone": "+5511987654321",
  "email": "joao@example.com",
  "birth_date": "1980-05-15",
  "cpf": "12345678909",
  "doctor_id": "223e4567-e89b-12d3-a456-426614174001",
  "treatment_type": "Reposição Hormonal",
  "treatment_start_date": "2025-01-10",
  "doctor_notes": "Paciente apresentou boa resposta ao tratamento.",
  "timezone": "America/Sao_Paulo"
}
```

**RBAC Rules:**
- **Admin**: Can create patients for any doctor
- **Doctor**: Can only create patients for themselves

**Saga Orchestration Flow:**
1. **Idempotency Check** (DB + Redis)
2. **Authorization** (doctor self-assignment)
3. **Distributed Lock** (phone hash, 5s timeout, 60s TTL)
4. **Saga Step 1**: Create patient in database
   - Validate via `IntegrityService`
   - Encrypt PII (LGPD)
   - Set `idempotency_key`
5. **Saga Step 2**: DEPRECATED (Firebase user creation)
6. **Saga Step 3**: Initialize patient flow
   - Select template based on `treatment_type`
   - Create `PatientFlowState` record
   - Set `flow_state = ONBOARDING`
7. **Saga Step 4**: Send welcome WhatsApp message
   - Create message record
   - Send via `UnifiedWhatsAppService`
8. **Single Commit** (Unit of Work pattern)

**Compensation (on failure):**
- Delete patient record
- Delete flow state
- Mark saga as FAILED
- Log error

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "João Silva",
  "phone": "+5511987654321",
  "email": "joao@example.com",
  "doctor_id": "223e4567-e89b-12d3-a456-426614174001",
  "flow_state": "onboarding",
  "current_day": 0,
  "created_at": "2025-01-01T10:00:00Z",
  "updated_at": "2025-01-01T10:00:00Z"
}
```

**Status Codes:**
- `201 Created`: Success
- `400 Bad Request`: Invalid data or validation error
- `403 Forbidden`: Doctor creating for another doctor
- `409 Conflict`: Duplicate CPF/email/phone for same doctor
- `500 Internal Server Error`: Saga execution failed

**Cache Behavior:**
- Idempotency key cached in Redis (24h TTL)
- Patient list cache invalidated
- Patient by ID cache invalidated

---

### 3.4 Update Patient

```http
PATCH /api/v2/patients/{patient_id}
```

**Path Parameters:**
- `patient_id` (string, required): Patient UUID

**Request Body (all fields optional):**
```json
{
  "name": "João Silva Updated",
  "email": "joao.novo@example.com",
  "phone": "+5511912345678",
  "treatment_type": "Tratamento Personalizado",
  "doctor_notes": "Ajuste de dosagem realizado em 12/02."
}
```

**RBAC Rules:**
- **Admin**: Can update any patient, including `doctor_id` reassignment
- **Doctor**: Can only update own patients, cannot reassign

**Validation:**
- All update data validated via `IntegrityService.validate_patient_data()`
- Normalized data (CPF, phone, email) applied
- Duplicate checks performed (excluding current patient)

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "João Silva Updated",
  "email": "joao.novo@example.com",
  "phone": "+5511912345678",
  "updated_at": "2025-01-15T14:30:00Z",
  ...
}
```

**Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid patient ID or validation error
- `403 Forbidden`: Doctor attempting reassignment
- `404 Not Found`: Patient not found
- `500 Internal Server Error`: Failed to update

**Cache Behavior:**
- Patient by ID cache invalidated
- Patient list cache invalidated

---

### 3.5 Delete Patient

```http
DELETE /api/v2/patients/{patient_id}
```

**Path Parameters:**
- `patient_id` (string, required): Patient UUID

**RBAC Rules:**
- **Admin only**: Only admins can delete patients

**Soft Delete:**
- Sets `deleted_at = now()`
- Preserves data for audit purposes
- Excluded from list queries (WHERE deleted_at IS NULL)

**Response:**
```json
{
  "message": "Patient soft deleted"
}
```

**Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid patient ID
- `403 Forbidden`: Non-admin attempting delete
- `404 Not Found`: Patient not found
- `500 Internal Server Error`: Failed to delete

**Cache Behavior:**
- Patient by ID cache invalidated
- Patient list cache invalidated

---

## 4. Database Schema

### 4.1 Patients Table

```sql
CREATE TABLE patients (
  -- Primary key
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Foreign keys
  doctor_id UUID NOT NULL REFERENCES users(id),

  -- Basic information
  name VARCHAR NOT NULL,
  birth_date DATE,

  -- Treatment
  treatment_type VARCHAR(150),
  treatment_start_date DATE,
  diagnosis VARCHAR(500),
  treatment_phase VARCHAR(100),
  doctor_notes TEXT,

  -- Flow control
  flow_state flow_state NOT NULL DEFAULT 'onboarding',
  current_day INTEGER NOT NULL DEFAULT 0,

  -- LGPD encrypted fields
  cpf_encrypted TEXT,
  cpf_hash VARCHAR(64),
  email_encrypted BYTEA,
  email_hash VARCHAR(64),
  phone_encrypted BYTEA,
  phone_hash VARCHAR(64),

  -- Metadata
  metadata JSONB DEFAULT '{}',

  -- Idempotency (QW-004)
  idempotency_key VARCHAR(255),

  -- Timezone
  timezone VARCHAR NOT NULL DEFAULT 'America/Sao_Paulo',

  -- Soft delete
  deleted_at TIMESTAMPTZ,

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 4.2 Indexes

```sql
-- Performance indexes (migration 034)
CREATE INDEX idx_patients_doctor_id ON patients(doctor_id);
CREATE INDEX idx_patients_flow_state ON patients(flow_state);
CREATE INDEX idx_patients_treatment_type ON patients(treatment_type);
CREATE INDEX idx_patients_treatment_start_date ON patients(treatment_start_date);
CREATE INDEX idx_patients_created_at ON patients(created_at);
CREATE INDEX idx_patients_deleted_at ON patients(deleted_at);

-- Hash-based search indexes
CREATE INDEX idx_patients_cpf_hash ON patients(cpf_hash);
CREATE INDEX idx_patients_email_hash ON patients(email_hash);
CREATE INDEX idx_patients_phone_hash ON patients(phone_hash);

-- Partial unique indexes (LGPD-compliant)
CREATE UNIQUE INDEX ix_patients_email_hash_doctor
  ON patients(email_hash, doctor_id)
  WHERE email_hash IS NOT NULL AND deleted_at IS NULL;

CREATE UNIQUE INDEX ix_patients_phone_hash_doctor
  ON patients(phone_hash, doctor_id)
  WHERE phone_hash IS NOT NULL AND deleted_at IS NULL;

-- Unique constraints
ALTER TABLE patients ADD CONSTRAINT uq_patient_cpf_hash_doctor
  UNIQUE (cpf_hash, doctor_id);

ALTER TABLE patients ADD CONSTRAINT uq_patient_idempotency_key
  UNIQUE (idempotency_key);
```

### 4.3 Flow States Enum

```sql
CREATE TYPE flow_state AS ENUM (
  'onboarding',   -- Initial patient setup
  'active',       -- Treatment in progress
  'paused',       -- Temporarily stopped
  'completed',    -- Treatment finished
  'cancelled'     -- Flow terminated
);
```

---

## 5. Validation Rules

### 5.1 Phone Number Validation

**Format:** E.164 or Brazilian format

**Rules:**
- E.164: `+` followed by 10-15 digits (e.g., `+5511987654321`)
- Brazilian: 10-11 digits (DDD + number)
- Normalization: Remove spaces, dashes, parentheses
- Storage: E.164 format (always normalized to `+55...`)

**Validation Code:**
```python
@field_validator("phone")
def validate_phone_format(cls, v):
    if not v:
        return v

    cleaned = re.sub(r"[\s\-\(\)]", "", v)

    if cleaned.startswith("+"):
        digits_only = cleaned[1:]
        if not digits_only.isdigit():
            raise ValueError("Telefone E.164 deve conter apenas + e dígitos")
        if len(digits_only) < 10 or len(digits_only) > 15:
            raise ValueError("Telefone E.164 deve ter entre 10-15 dígitos")
        return cleaned

    digits_only = re.sub(r"\D", "", v)
    if len(digits_only) < 10 or len(digits_only) > 11:
        raise ValueError("Telefone brasileiro deve ter 10-11 dígitos")

    return v
```

### 5.2 CPF Validation

**Format:** 11 digits with check digits

**Rules:**
- Format: `123.456.789-00` or `12345678900`
- Check digits validation (modulo 11 algorithm)
- Normalization: Remove dots and dashes
- Storage: Encrypted with AES-256-GCM

**Validation Code:**
```python
@field_validator("cpf")
def validate_cpf(cls, v):
    if not v:
        return v

    if not v.replace(".", "").replace("-", "").isdigit():
        raise ValueError("CPF deve conter apenas dígitos, pontos e traços")

    if not validate_cpf_check_digits(v):
        raise ValueError("CPF inválido: dígitos verificadores incorretos")

    return v
```

### 5.3 Email Validation

**Format:** Valid email with MX record validation

**Rules:**
- RFC 5322 email format
- Domain must have valid MX records (in production)
- Normalization: Lowercase
- Storage: Encrypted with AES-256-GCM

### 5.4 Birth Date Validation

**Rules:**
- Must be 18+ years old (LOW-004)
- Cannot be future date
- Format: ISO 8601 date

**Validation Code:**
```python
@field_validator("birth_date")
def validate_min_age(cls, v):
    if not v:
        return v

    today = date.today()
    age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))

    if age < 18:
        raise ValueError("Paciente deve ter pelo menos 18 anos")

    return v
```

### 5.5 Duplicate Detection

**Rules:**
- CPF: Unique per doctor (same CPF can exist for different doctors)
- Email: Unique per doctor (same email can exist for different doctors)
- Phone: Unique per doctor (same phone can exist for different doctors)

**Implementation:**
- Database constraints enforce uniqueness
- `IntegrityService` performs advisory checks before insert
- Hash-based lookups for encrypted fields

---

## 6. Error Responses

### 6.1 Validation Error (400)

```json
{
  "detail": "CPF inválido: dígitos verificadores incorretos"
}
```

### 6.2 Unauthorized (401)

```json
{
  "detail": "Not authenticated"
}
```

### 6.3 Forbidden (403)

```json
{
  "detail": "Doctors can only create patients for themselves"
}
```

### 6.4 Not Found (404)

```json
{
  "detail": "Patient with id 123e4567-e89b-12d3-a456-426614174000 not found"
}
```

### 6.5 Conflict (409)

```json
{
  "detail": "Patient with this CPF already exists for this doctor"
}
```

### 6.6 Internal Server Error (500)

```json
{
  "detail": "Internal server error"
}
```

### 6.7 Validation Error with Field Details (422)

```json
{
  "detail": [
    {
      "loc": ["body", "phone"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## 7. LGPD Compliance

### 7.1 Encryption Algorithm

**Algorithm:** AES-256-GCM
**Library:** `cryptography.fernet`
**Key Management:** Environment variable `ENCRYPTION_KEY`

### 7.2 Encrypted Fields

| Field | Encrypted Column | Hash Column | Purpose |
|-------|------------------|-------------|---------|
| CPF | `cpf_encrypted` (TEXT) | `cpf_hash` (VARCHAR(64)) | Searchable hash for queries |
| Email | `email_encrypted` (BYTEA) | `email_hash` (VARCHAR(64)) | Searchable hash for queries |
| Phone | `phone_encrypted` (BYTEA) | `phone_hash` (VARCHAR(64)) | Searchable hash for queries |

### 7.3 Migration History

- **Migration 020**: CPF encryption added
- **Migration 024**: CPF plaintext column removed
- **Migration 028**: Email/phone encryption added
- **Migration 030**: Email/phone plaintext columns removed

### 7.4 Encryption Service

**Location:** `/app/services/encryption.py`

```python
from app.services.encryption import get_lgpd_encryption_service

service = get_lgpd_encryption_service()

# Encryption
encrypted, hash_value = service.encrypt_email(email)

# Decryption (on-demand)
email = service.decrypt_email(encrypted)
```

### 7.5 Validation Hook (QW-003)

```python
@event.listens_for(Patient, "before_insert")
@event.listens_for(Patient, "before_update")
def validate_cpf_encryption(mapper, connection, target):
    """Ensure CPF is properly encrypted before DB operations"""
    if target.cpf_encrypted and not target.cpf_hash:
        raise ValueError("CPF encryption incomplete")
```

---

## 8. Performance Optimizations

### 8.1 Eager Loading

**Strategy:** `selectinload()` and `joinedload()`

```python
query = query.options(
    selectinload(Patient.quiz_sessions),   # 1:many
    selectinload(Patient.flow_states),      # 1:many
    joinedload(Patient.doctor)              # 1:1
)
```

**Impact:** Prevents N+1 queries

### 8.2 Cursor Pagination

**Implementation:** Cursor-based pagination using `created_at` and `id`

```python
cursor_data = {
    "created_at": "2025-01-15T14:30:00Z",
    "id": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Benefits:**
- More efficient than offset pagination
- Consistent results during data changes
- Better performance for large datasets

### 8.3 Redis Caching

**Cache Keys:**
- `idempotency:patient:create:{key}` (TTL: 24h)
- `patient_by_id:*:{patient_id}*` (Variable TTL)
- `patient_list:*:{doctor_id}*` (Variable TTL)

**Invalidation:** Pattern-based invalidation on mutations

### 8.4 Database Indexes

**See Section 4.2** for complete index list.

---

## 9. Testing Guidelines

### 9.1 Test Data

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

### 9.2 Test Coverage

**Critical Paths:**
- Patient creation with saga orchestration
- Idempotency key handling
- RBAC enforcement
- Duplicate detection
- Saga compensation
- Cache invalidation

**Test Files:**
- `/tests/api/critical/test_patients_crud.py`
- `/tests/api/critical/test_patients_list.py`
- `/tests/api/v2/test_patients_rbac.py`
- `/tests/services/patient/test_onboarding_happy_path.py`

---

## 10. Known Issues and Limitations

### 10.1 Issues from Debug Reports

**Issue 1: N+1 Query in Statistics Endpoint** (CRITICAL)
- **Location:** `/app/api/v2/routers/patients/flow.py:503-516`
- **Impact:** 8 separate COUNT queries for single request
- **Fix:** Use single aggregation query

**Issue 2: Transaction Management Inconsistency** (CRITICAL)
- **Location:** Multiple files
- **Impact:** Data integrity risk, race conditions
- **Fix:** Use `@transactional` decorator consistently

**Issue 3: Race Condition in Duplicate Detection** (HIGH)
- **Location:** `integrity_service.py:348-390`
- **Impact:** Concurrent requests can bypass checks
- **Mitigation:** Database constraints exist, improve error handling

**Issue 4: Saga Step Numbering Inconsistency** (MEDIUM)
- **Location:** `saga_orchestrator.py`
- **Impact:** Resume logic confusion (Step 2 deprecated)
- **Fix:** Remove STEP_2_FIREBASE_USER_CREATED or renumber

**Issue 5: Code Duplication** (MEDIUM)
- **Location:** `patients/crud.py` vs `patients.py`
- **Impact:** ~430 lines duplicate code
- **Fix:** Delete legacy `patients.py`

### 10.2 Pending Improvements

**P0 - Critical:**
1. Fix N+1 query in statistics endpoint
2. Standardize transaction management
3. Add thread-safe session management

**P1 - High:**
4. Fix saga step numbering
5. Remove duplicate validation method
6. Add orphan saga detection
7. Extend phone hash length (16 → 24 chars)

**P2 - Medium:**
8. Split IntegrityService (god object)
9. Add missing v2 schema fields
10. Standardize async patterns

---

## 11. Architecture Components

### 11.1 Layer Structure

```
API Layer (FastAPI)
  ↓
Service Layer (Business Logic)
  ↓
Domain Layer (Onboarding Orchestration)
  ↓
Repository Layer (Data Access)
  ↓
Database Layer (PostgreSQL + Supabase)
```

### 11.2 Key Services

**OnboardingCoordinator:**
- Orchestrates patient creation workflow
- Delegates to specialized services
- Coordinates saga execution

**IntegrityService:**
- Single source of truth for validation
- Duplicate detection
- Data normalization

**PatientCRUDService:**
- Basic CRUD operations
- Cache management
- Transaction coordination

**SagaOrchestrator:**
- Distributed transaction management
- Compensation on failure
- Resume capability

**PatientRepository:**
- Data access layer
- LGPD encryption/decryption
- Query optimization

---

## 12. Integration Points

### 12.1 WhatsApp Integration

**Service:** `UnifiedWhatsAppService`
**Location:** `/app/services/unified_whatsapp_service.py`

**Flow:**
```
Patient Creation → Welcome Message
                ↓
  NotificationService → UnifiedWhatsAppService
                ↓
  EvolutionClient → Evolution API
                ↓
  WhatsApp Message Sent
```

**Tables:**
- `messages` - All WhatsApp messages
- `message_templates` - Template definitions

### 12.2 Flow System Integration

**Service:** `PatientFlowService`
**Location:** `/app/services/patient/flow_service.py`

**Flow Templates:**
- `INITIAL_15_DAYS` - Default onboarding
- `HORMONE_THERAPY` - Specific treatment flows
- `FOLLOW_UP` - Post-treatment monitoring

**Flow States:**
- `ONBOARDING` - Initial setup
- `ACTIVE` - Treatment in progress
- `PAUSED` - Temporarily stopped
- `COMPLETED` - Treatment finished
- `CANCELLED` - Flow terminated

### 12.3 Quiz System Integration

**Tables:**
- `quiz_sessions` - Quiz attempts
- `quiz_responses` - Individual answers

**Relationships:**
- Patient → QuizSession (1:many)
- Patient → QuizResponse (1:many)

---

## 13. Conclusion

The Patient CRUD API demonstrates:

✅ **Clean Architecture** - Clear layer separation
✅ **LGPD Compliance** - Full PII encryption
✅ **SAGA Pattern** - Distributed transaction management
✅ **N+1 Prevention** - Comprehensive eager loading
✅ **Idempotency** - QW-004 duplicate prevention
✅ **RBAC** - Role-based access control
✅ **Caching** - Multi-layer caching strategy
✅ **Error Handling** - Comprehensive exception handling
✅ **Observability** - Structured logging and WebSocket events

### Next Steps

1. Address critical performance issues (N+1 queries)
2. Standardize transaction management
3. Implement comprehensive integration tests
4. Add distributed tracing
5. Document saga compensation flows

---

**Research Completed By:** Researcher Agent
**Memory Key:** `research/patient-crud/spec`
**Coordination:** Claude Flow Hooks
**Files Analyzed:** 50+ files, 5000+ LOC
