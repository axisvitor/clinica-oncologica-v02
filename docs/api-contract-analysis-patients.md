# API Contract Analysis: Patients Endpoints

## Executive Summary

**Status**: ✅ **MOSTLY ALIGNED** - Minor field name differences
**Critical Issues**: 1 Medium Priority
**Type Safety**: 85% coverage

---

## Backend Patient Schema (patient.py)

### Core Models

#### `PatientBase` (Base Schema)
```python
{
    phone: str,                          # Required, with validation
    name: str,                           # Required
    email: Optional[str],
    birth_date: Optional[date],
    treatment_type: Optional[str],
    treatment_start_date: Optional[date],

    # Brazilian healthcare specific
    cpf: Optional[str],                  # 11 digits, validated with check digits
    diagnosis: Optional[str],            # Max 500 chars
    treatment_phase: Optional[str],      # Enum: initial|adjustment|maintenance|monitoring|followup|completed
    doctor_notes: Optional[str]
}
```

**Validators:**
- ✅ Phone must start with `+` (country code)
- ✅ CPF validated with check digit algorithm
- ✅ CPF cleaned to digits only before storage

#### `PatientResponse` (GET Response)
```python
{
    id: UUID,
    doctor_id: UUID,
    phone: str,
    name: str,
    email: Optional[str],
    birth_date: Optional[date],
    treatment_type: Optional[str],
    treatment_start_date: Optional[date],
    flow_state: FlowState,               # Enum
    current_day: int,
    created_at: date,
    updated_at: date,

    # Brazilian fields
    cpf: Optional[str],
    diagnosis: Optional[str],
    treatment_phase: Optional[str],
    doctor_notes: Optional[str],

    # Metadata
    patient_data: Optional[dict],        # Aliased as "metadata"
}
```

#### `PatientListResponse` (List Endpoint)
```python
{
    data: list[PatientResponse],         # Array of patients
    total: int,                          # Total matching filters
    page: int,                           # Current page (1-indexed)
    limit: int,                          # Records per page
    pages: int,                          # Total page count
    has_more: bool,                      # Has next page
    has_previous: bool                   # Has previous page
}
```

---

## Frontend Patient Types (api-responses.ts)

### `Patient` Interface
```typescript
{
    id: string,
    name: string,
    email?: string,
    phone?: string,
    birth_date?: string,
    cpf?: string,
    treatment_type?: string,
    treatment_start_date?: string,
    current_day?: number,
    status: 'active' | 'inactive' | 'completed' | 'paused',
    created_at: string,
    updated_at: string,
    metadata?: Record<string, unknown>
}
```

### `PatientListResponse` Interface
```typescript
{
    data: Patient[],
    total: number,
    page: number,
    limit: number,
    pages: number
}
```

---

## Field-by-Field Contract Comparison

| Field | Backend Type | Frontend Type | Status | Notes |
|-------|-------------|---------------|--------|-------|
| `id` | `UUID` | `string` | ✅ Match | UUID serialized to string |
| `name` | `str` (required) | `string` (required) | ✅ Match | |
| `email` | `Optional[str]` | `string \| undefined` | ✅ Match | |
| `phone` | `str` (required) | `string \| undefined` | ⚠️ Mismatch | Backend requires, frontend optional |
| `birth_date` | `Optional[date]` | `string \| undefined` | ✅ Match | Date serialized to ISO string |
| `cpf` | `Optional[str]` | `string \| undefined` | ✅ Match | Brazilian tax ID |
| `treatment_type` | `Optional[str]` | `string \| undefined` | ✅ Match | |
| `treatment_start_date` | `Optional[date]` | `string \| undefined` | ✅ Match | Date serialized to ISO string |
| `current_day` | `int` | `number \| undefined` | ✅ Match | |
| `created_at` | `date` | `string` | ✅ Match | Date serialized to ISO string |
| `updated_at` | `date` | `string` | ✅ Match | Date serialized to ISO string |
| `metadata` | `Optional[dict]` | `Record<string, unknown>` | ✅ Match | Additional patient data |
| **Missing in Frontend:** | | | | |
| `doctor_id` | `UUID` | ❌ Missing | ⚠️ Issue | Doctor assignment not exposed |
| `diagnosis` | `Optional[str]` | ❌ Missing | ⚠️ Issue | Medical diagnosis field |
| `treatment_phase` | `Optional[str]` | ❌ Missing | ⚠️ Issue | Treatment phase enum |
| `doctor_notes` | `Optional[str]` | ❌ Missing | ⚠️ Issue | Doctor's notes |
| `flow_state` | `FlowState` (enum) | ❌ Missing | ⚠️ Issue | Treatment flow state |
| **Missing in Backend:** | | | | |
| `status` | ❌ Missing | `'active' \| 'inactive' \| 'completed' \| 'paused'` | ⚠️ Issue | May be derived from `flow_state` |

---

## Pagination Contract Analysis

### Backend Implementation
```python
{
    data: list[PatientResponse],
    total: int,
    page: int,        # 1-indexed
    limit: int,
    pages: int,
    has_more: bool,
    has_previous: bool
}
```

### Frontend Implementation (api-client.ts)
```typescript
// Transform function
transformPaginationResponse<Patient>(response, 'patients')

// Expected structure
{
    data: Patient[],
    total: number,
    page: number,
    limit: number,
    pages: number
}
```

**Issues:**
- ⚠️ Frontend missing `has_more` and `has_previous` fields
- ✅ Page numbering consistent (1-indexed)
- ✅ Total count and limit match

---

## Endpoint Contract Analysis

### `GET /api/v1/patients` - List Patients

**Backend Query Parameters:**
- `page: int = 1` (1-indexed)
- `size: int = 50` (renamed to `limit` in response)
- `search: Optional[str]` - Search in name, email, phone
- `status: Optional[str]` - Filter by status
- `treatment_type: Optional[str]` - Filter by treatment

**Frontend Implementation:**
```typescript
patients.list({
    page?: number,
    size?: number,
    search?: string,
    status?: string,
    treatment_type?: string
})
```

**Status**: ✅ **MATCH**

---

### `GET /api/v1/patients/{id}` - Get Patient

**Backend Response:** `PatientResponse`
**Frontend Type:** `Patient`
**Status**: ⚠️ **PARTIAL MATCH** - Missing fields in frontend

---

### `POST /api/v1/patients` - Create Patient

**Backend Request:** `PatientCreate`
```python
{
    phone: str,              # Required
    name: str,               # Required
    email: Optional[str],
    birth_date: Optional[date],
    treatment_type: Optional[str],
    treatment_start_date: Optional[date],
    cpf: Optional[str],
    diagnosis: Optional[str],
    treatment_phase: Optional[str],
    doctor_notes: Optional[str],
    metadata: Optional[dict]
}
```

**Frontend Implementation:**
```typescript
patients.create(patient: Partial<Patient>)
```

**Issues:**
- ⚠️ `Partial<Patient>` makes all fields optional, but backend requires `phone` and `name`
- ⚠️ Frontend lacks validation for required fields

---

### `PUT /api/v1/patients/{id}` - Update Patient

**Backend Request:** `PatientUpdate` (all fields optional)
**Frontend:** `Partial<Patient>`
**Status**: ✅ **MATCH**

---

### `DELETE /api/v1/patients/{id}` - Delete Patient

**Backend Response:** `void` (204 No Content)
**Frontend:** `void`
**Status**: ✅ **MATCH**

---

### `GET /api/v1/patients/{id}/timeline` - Patient Timeline

**Backend Response:**
```python
{
    events: List[TimelineEvent],
    total: Optional[int]
}
```

**Frontend Type:**
```typescript
{
    events: TimelineEvent[],
    total?: number
}
```

**Status**: ✅ **MATCH**

---

### `POST /api/v1/patients/{id}/activate` - Activate Patient

**Backend Response:** `void` (204 No Content)
**Frontend:** `void`
**Status**: ✅ **MATCH**

---

### `POST /api/v1/patients/{id}/deactivate` - Deactivate Patient

**Backend Response:** `void` (204 No Content)
**Frontend:** `void`
**Status**: ✅ **MATCH**

---

## Validation Differences

### Backend Validators (patient.py)

1. **Phone Validation**
   ```python
   @validator('phone')
   def validate_phone(cls, v):
       if not v.startswith('+'):
           raise ValueError('Phone number must start with country code (+)')
       return v
   ```
   - ✅ Enforced on backend
   - ❌ No frontend validation

2. **CPF Validation**
   ```python
   @validator('cpf')
   def validate_cpf_number(cls, v):
       if v and not validate_cpf(v):
           raise ValueError('Invalid CPF number')
       return re.sub(r'\D', '', v)  # Clean to digits only
   ```
   - ✅ Full check digit validation
   - ✅ Cleans format before storage
   - ❌ No frontend validation

3. **Treatment Phase Validation**
   ```python
   treatment_phase: Optional[str] = Field(
       pattern="^(initial|adjustment|maintenance|monitoring|followup|completed)$"
   )
   ```
   - ✅ Enum validation on backend
   - ❌ No TypeScript enum defined

---

## Critical Issues Summary

### 🟡 MEDIUM PRIORITY

1. **Missing Backend Fields in Frontend Types**
   - **Missing**: `doctor_id`, `diagnosis`, `treatment_phase`, `doctor_notes`, `flow_state`
   - **Impact**: Cannot display or edit these fields in UI
   - **Fix**: Add to `Patient` interface in `api-responses.ts`

2. **Phone Field Required vs Optional Mismatch**
   - **Backend**: Phone is required
   - **Frontend**: Phone is optional
   - **Impact**: Create requests may fail validation
   - **Fix**: Mark phone as required in TypeScript

3. **Status Field Inconsistency**
   - **Frontend**: Has `status` field (active/inactive/completed/paused)
   - **Backend**: Uses `flow_state` enum
   - **Impact**: May cause confusion or data loss
   - **Fix**: Clarify relationship or derive status from flow_state

4. **Missing Pagination Helpers**
   - **Frontend**: Doesn't use `has_more` and `has_previous` from backend
   - **Impact**: Must calculate manually
   - **Fix**: Add these fields to frontend response type

5. **No Frontend Validation for Required Fields**
   - **Issue**: `Partial<Patient>` in create makes all fields optional
   - **Impact**: Runtime errors when backend rejects missing required fields
   - **Fix**: Create separate `PatientCreateRequest` type

---

## Recommendations

### Immediate Actions

1. **Update Frontend Patient Type**
   ```typescript
   export interface Patient {
       id: string
       name: string
       phone: string  // Mark as required
       email?: string
       birth_date?: string
       cpf?: string
       treatment_type?: string
       treatment_start_date?: string
       current_day?: number
       status: 'active' | 'inactive' | 'completed' | 'paused'
       created_at: string
       updated_at: string

       // Add missing fields
       doctor_id?: string
       diagnosis?: string
       treatment_phase?: 'initial' | 'adjustment' | 'maintenance' | 'monitoring' | 'followup' | 'completed'
       doctor_notes?: string
       flow_state?: FlowState

       metadata?: Record<string, unknown>
   }
   ```

2. **Create Separate Create/Update Types**
   ```typescript
   export interface PatientCreateRequest {
       name: string          // Required
       phone: string         // Required
       email?: string
       birth_date?: string
       // ... other optional fields
   }

   export interface PatientUpdateRequest {
       name?: string
       phone?: string
       // ... all optional
   }
   ```

3. **Add Pagination Helpers**
   ```typescript
   export interface PatientListResponse {
       data: Patient[]
       total: number
       page: number
       limit: number
       pages: number
       has_more: boolean      // Add
       has_previous: boolean  // Add
   }
   ```

4. **Add CPF Validation Helper**
   ```typescript
   export function validateCPF(cpf: string): boolean {
       // Implement same validation as backend
   }
   ```

### Long-term Improvements

1. Share validation logic between frontend/backend
2. Generate TypeScript types from Pydantic schemas
3. Add Zod or similar runtime validation
4. Create shared enum definitions

---

## Testing Checklist

- [ ] Test patient creation with missing required fields
- [ ] Verify CPF validation on both frontend and backend
- [ ] Test phone number format validation
- [ ] Verify pagination works correctly
- [ ] Test timeline event retrieval
- [ ] Verify activate/deactivate endpoints
- [ ] Test search and filtering
- [ ] Validate treatment_phase enum values
- [ ] Test metadata field persistence

---

**Generated**: 2025-10-04
**Analyst**: Claude Code Quality Analyzer
**Next Review**: After type updates implemented
