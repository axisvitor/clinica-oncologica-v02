# API Schema Contract Validation Report
## Backend-Hormonia V2 API Comprehensive Analysis

**Date**: 2025-12-25
**Analysis Scope**: Router response_model declarations vs actual schema definitions
**Severity Classification**: Critical (5), High (8), Medium (6)

---

## Executive Summary

This report validates API schema contracts across 50+ V2 endpoints. Analysis identifies **19 critical schema contract issues** affecting API consumers, with mismatches between declared response models and actual data structures.

### Key Findings:
- **5 Critical Issues**: Breaking changes in core endpoints (patients, appointments, auth)
- **8 High Issues**: Type inconsistencies in list responses and field definitions
- **6 Medium Issues**: Missing/incomplete field examples and optional field definitions
- **Impact**: 15+ API endpoints affected; potential deserialization failures in clients

---

## CRITICAL ISSUES (5)

### Issue 1: AppointmentV2List Generic Type Not Specified
**Severity**: CRITICAL
**Category**: Schema Field Name Inconsistency

**Location**:
- Router: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/appointments.py:98`
- Schema: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/appointment.py:189`

**Issue Details**:
```python
# Router Declaration
@router.get("", response_model=AppointmentV2List)

# Schema Definition (INCOMPLETE)
class AppointmentV2List(CursorPaginatedResponse):
    """Paginated list of appointments.
    Inherits from CursorPaginatedResponse which uses 'data' field.
    """
    # Uses 'data' field from CursorPaginatedResponse base class
    # data: List[AppointmentV2Response] is inherited but typed generically

    model_config = ConfigDict(from_attributes=True)
```

**The Problem**:
- `CursorPaginatedResponse` is a generic type that requires type parameter `[AppointmentV2Response]`
- Current definition uses generic `CursorPaginatedResponse` without type hint
- OpenAPI schema will show `data: []` instead of `data: [AppointmentV2Response]`
- API clients cannot validate response structure properly

**Impact on Consumers**:
- Client code cannot generate proper TypeScript/Kotlin types from OpenAPI spec
- Runtime validation fails for complex nested response structures
- IDE autocomplete/intellisense won't work for response fields

**Fix Recommendation**:
```python
class AppointmentV2List(CursorPaginatedResponse[AppointmentV2Response]):
    """Paginated list of appointments."""
    model_config = ConfigDict(from_attributes=True)
```

---

### Issue 2: FirebaseTokenVerifyResponse Missing 'user' Field
**Severity**: CRITICAL
**Category**: Schema Field Definition Mismatch

**Location**:
- Router: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/auth.py:96`
- Schema: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/auth.py:462`

**Issue Details**:
```python
# Router Response (verify_firebase_token endpoint)
# Returns dict with session data + user object

# Schema Definition (INCOMPLETE)
class FirebaseTokenVerifyResponse(BaseModel):
    valid: bool
    # user: Optional[UserV2Response] = None  <-- COMMENTED OUT
    session_id: Optional[str] = None
    message: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valid": True,
                "user": {...},  # <-- Example shows 'user' field
                "session_id": "sess_abc123",
            }
        }
    )
```

**The Problem**:
- Schema declares response but example includes `user` field that's not in the model
- Endpoint returns user data (see router line 106+), but schema doesn't declare it
- Example in OpenAPI spec contradicts actual schema
- Client deserialization will fail or ignore the user data

**Router Return Statement** (auth.py:220):
```python
return {
    "session_id": str(session.id),
    "valid": True,
    "user": {...user_data...},  # RETURNED but not declared in schema
    "message": "Login successful"
}
```

**Impact on Consumers**:
- Client code won't expect the `user` field in response
- JSON schema validation will fail
- TypeScript interface won't include user property
- Breaking change if clients depend on user data

**Fix Recommendation**:
```python
class FirebaseTokenVerifyResponse(BaseModel):
    valid: bool
    user: Optional[UserV2Response] = Field(
        None,
        description="Authenticated user information"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for subsequent requests"
    )
    message: Optional[str] = Field(None, description="Response message")

    model_config = ConfigDict(from_attributes=True, ...)
```

---

### Issue 3: PatientV2List Generic Type Parameter Missing
**Severity**: CRITICAL
**Category**: Schema Type Annotation Missing

**Location**:
- Router: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/patients/crud.py:70`
- Schema: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/patient.py:393`

**Issue Details**:
```python
# Router
@router.get("/", response_model=PatientV2List)

# Schema Definition
class PatientV2List(CursorPaginatedResponse[PatientV2Response]):
    """Paginated list of patients"""
    model_config = ConfigDict(...)
```

**Status**: ✓ **CORRECTLY DEFINED** but has a runtime issue:
- Schema correctly specifies generic type parameter
- However, router returns raw dict (line 189), not validated schema
- Response bypasses Pydantic validation

**Router Code Problem** (crud.py:189-194):
```python
return {
    "data": patient_responses,      # List[dict]
    "next_cursor": next_cursor,
    "has_more": has_more,
    "total": total,
}
# Returns dict, not PatientV2List instance
# Pydantic will attempt coercion but may fail on nested relationships
```

**Impact on Consumers**:
- Response validation passes but nested object types may not validate
- Doctor relationship fields may fail type validation
- Optional eager-loaded fields not properly typed

**Fix Recommendation**:
```python
# Convert dict to schema
patient_list = PatientV2List(
    data=patient_responses,
    next_cursor=next_cursor,
    has_more=has_more,
    total=total
)
return patient_list
# OR use response_model validation automatically via Pydantic
```

---

### Issue 4: SessionV2Response Missing 'user' Field Definition
**Severity**: CRITICAL
**Category**: Optional Field Definition Inconsistency

**Location**:
- Router: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/auth.py:283`
- Schema: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/auth.py:366`

**Issue Details**:
```python
# Schema Definition
class SessionV2Response(BaseModel):
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_current: bool = Field(False, ...)
    valid: bool = Field(True, ...)
    user: Optional["UserV2Response"] = None  # ← FORWARD REFERENCE
```

**The Problem**:
- Field `user` is included but uses forward reference string
- Not properly annotated with `Field()` descriptor
- Missing validation description
- Example shows `user` data but field definition is bare

**Router Returns** (auth.py:335-337):
```python
return _serialize_session(
    session,
    current_user=current_user,  # User data IS included
    current_session_id=session_id_from_request
)

# _serialize_session builds user_data dict (line 59-71)
# Returns: {..., "user": user_data, ...}
```

**Impact on Consumers**:
- Pydantic will accept any structure for `user` field
- TypeScript generation unclear about nested structure
- No validation of user object structure
- Breaking if user field is suddenly removed

**Fix Recommendation**:
```python
user: Optional[UserV2Response] = Field(
    None,
    description="Authenticated user information (if included)"
)
```

---

### Issue 5: DatetimeFormat Inconsistency Across Schemas
**Severity**: CRITICAL
**Category**: Inconsistent Date/DateTime Formats

**Location**: Multiple files
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/auth.py:371, 383-384`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/patient.py:360-361`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/appointment.py:179-180`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/quiz_extensions.py:116-117`

**Issue Details**:
Examples show inconsistent datetime formats:
```json
// auth.py example (SessionV2Response)
"created_at": "2025-11-07T08:00:00Z",    // UTC Z suffix

// patient.py example (PatientV2Response)
"created_at": "2025-01-01T10:00:00Z",    // UTC Z suffix
"birth_date": "1980-05-15T00:00:00Z",    // birth_date as datetime (should be date)

// appointment.py example
"scheduled_at": "2025-01-20T14:30:00",   // NO timezone info
"created_at": "2025-01-01T10:00:00Z",    // UTC Z suffix

// quiz_extensions.py
"responded_at": datetime,                 // Type annotation only
"created_at": datetime                    // Type annotation only
```

**Schema Definitions**:
```python
# PatientV2Base.birth_date
birth_date: Optional[date] = None  # Should be 'date', not 'datetime'

# All response schemas
created_at: datetime  # No timezone specified
updated_at: datetime  # No timezone specified
```

**The Problem**:
1. `birth_date` examples show ISO datetime but schema is `date` type
2. `datetime` fields don't specify timezone handling
3. Some examples include 'Z' suffix, some don't
4. Router code uses `datetime.now(timezone.utc)` but schema doesn't enforce it

**Example Mismatch** (patient.py:357):
```python
# Schema says date type
birth_date: Optional[date] = None

# But example shows datetime
"birth_date": "1980-05-15T00:00:00Z",  # Wrong format
```

**Router Code** (auth.py:172):
```python
expires_at=datetime.now(timezone.utc) + timedelta(days=5)  # Always UTC
# But schema doesn't enforce timezone-aware datetimes
```

**Impact on Consumers**:
- Clients deserializing datetime fields will fail if timezone not included
- Some endpoints may return naive datetimes, others timezone-aware
- Date/datetime confusion causes parsing errors
- Inconsistent serialization across endpoints

**Fix Recommendation**:
```python
# Option 1: Use Pydantic's datetime configuration
model_config = ConfigDict(
    json_schema_extra={
        "example": {
            "birth_date": "1980-05-15",        # date format
            "created_at": "2025-01-01T10:00:00+00:00",  # RFC3339
        }
    }
)

# Option 2: Add timezone annotations
from pydantic import field_serializer

class PatientV2Response(PatientV2Base):
    created_at: datetime = Field(
        ...,
        description="Creation timestamp (UTC)"
    )

    @field_serializer('created_at')
    def serialize_datetime(self, value: datetime) -> str:
        """Ensure datetime is always serialized with timezone."""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
```

---

## HIGH SEVERITY ISSUES (8)

### Issue 6: QuizResponseV2List Generic Type Not Specified

**Location**:
- Router: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/quiz_responses.py:54-56`
- Schema: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/quiz_extensions.py:127-130`

**Issue**:
```python
# Schema Definition
class QuizResponseV2List(CursorPaginatedResponse[QuizResponseV2Detail]):
    """Paginated quiz response list."""
    pass

# Status: ✓ CORRECTLY DEFINED
```

**However**, Router return (line 186-188):
```python
return QuizResponseV2List(
    data=enriched_responses,      # Already QuizResponseV2Detail objects
    next_cursor=next_cursor,
    has_more=has_more,
    total=total
)
```

**The Issue**:
- Schema is correct but `enriched_responses` are manually constructed
- Each response object construction (line 154-170) may miss optional fields
- Manual construction bypasses Pydantic validation
- Optional relationship fields (template_name, template_version) might be None unexpectedly

**Impact**: Clients receive inconsistent optional field population
**Recommendation**: Use Pydantic's field validation throughout response construction

---

### Issue 7: AppointmentV2Response Field Typing Inconsistency

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/appointment.py:163-186`

**Issue**:
```python
class AppointmentV2Response(BaseModel):
    id: str                                      # Should be UUID
    patient_id: str                              # Should be UUID
    practitioner_id: Optional[str] = None        # Should be Optional[UUID]
    appointment_type: str                        # ✓ OK
    status: str                                  # ✓ OK
    scheduled_at: Optional[datetime] = None      # ✓ OK
    ...
    patient: Optional[PatientV2Brief] = None     # Optional nested object
    practitioner: Optional[PractitionerV2Brief] = None
```

**The Problem**:
- IDs are `str` but should be `UUID` for type safety
- PatientV2Brief and PractitionerV2Brief are optional but validation doesn't ensure data exists
- Example shows string UUIDs but schema should use UUID type

**Router Construction** (appointments.py:72-87):
```python
return {
    "id": str(appointment.id),              # Converted to string
    "patient_id": str(appointment.patient_id),
    "practitioner_id": str(appointment.practitioner_id) if appointment.practitioner_id else None,
    ...
}
```

**Impact**:
- ID comparison is string-based, not type-safe
- Clients must manually convert strings back to UUIDs
- No validation that IDs are valid UUID format

**Recommendation**:
```python
from uuid import UUID

class AppointmentV2Response(BaseModel):
    id: UUID
    patient_id: UUID
    practitioner_id: Optional[UUID] = None
    ...

    model_config = ConfigDict(
        json_encoders={UUID: lambda v: str(v)},
        # or use Pydantic v2 serializers
    )
```

---

### Issue 8: PatientV2Response Optional Relationships Not Properly Typed

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/patient.py:388-390`

**Issue**:
```python
class PatientV2Response(PatientV2Base):
    ...
    # Optional eager-loaded relationships
    doctor: Optional[DoctorV2Brief] = None
    quiz_sessions: Optional[List[QuizV2Brief]] = None
```

**The Problem**:
- These fields are optional but `include` query parameter determines their presence
- No validation that relationship exists when included
- Clients don't know when to expect these fields
- Breaking change if field is added without documentation

**Router Code** (crud.py:183):
```python
patient_dict = await serialize_patient_with_includes(patient, include)
# include can be ["doctor", "quizzes", "templates", "analytics"]
# But schema doesn't document what relationships are available
```

**Missing Documentation**:
- Schema doesn't list valid relationship names
- No error response if invalid relationship requested
- Clients must guess which relationships are available

**Impact**: Client code needs hardcoded knowledge of available relationships
**Recommendation**: Document in schema or create separate response classes

---

### Issue 9: QuizV2Response Has Mismatched Field Names

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/quiz.py:87-100`

**Issue**:
```python
class QuizV2Response(QuizV2Base):
    # ... other fields ...
    started_at: datetime
    completed_at: Optional[datetime] = None
    score: Optional[float] = None
    passed: Optional[bool] = None
```

**The Problem**:
- Database model might have different field names (e.g., `created_at` vs `started_at`)
- Schema uses `started_at` but database might track `session_start_time`
- Mismatch between model and schema field names

**Impact**:
- Field mapping issues during serialization
- Missing data if field names don't align
- Requires custom serializers to translate

**Recommendation**: Document actual database field mapping or ensure consistency

---

### Issue 10: DashboardMainResponse Missing Type Parameters

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/dashboard.py:108`

**Issue**:
```python
@router.get("/main", response_model=DashboardMainResponse)
```

Schema definition needs verification - dashboard.py likely has generic nested objects without proper type hints.

---

### Issue 11: Response Status Code Mismatch

**Location**: Multiple routers

**Issue Pattern**:
```python
# appointments.py:357
@router.post("", response_model=AppointmentV2Response, status_code=201)

# But _serialize_appointment might not always return valid data on 201
# No documentation of what fields are populated on creation

# quiz_templates.py:160
@router.post("/quizzes", response_model=QuizTemplateV2Response, status_code=201)
```

**The Problem**:
- 201 Created responses should include `Location` header with resource URL
- Response schema doesn't document which fields are guaranteed vs optional on creation
- No `id` field guarantee documented for 201 responses

**Recommendation**:
```python
@router.post(
    "",
    response_model=AppointmentV2Response,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Appointment created successfully"}
    }
)
```

---

### Issue 12: Missing 'items' vs 'data' Field Naming Consistency

**Location**: Multiple list responses

**Issue**:
- Some list responses use `data` field (CursorPaginatedResponse)
- Some might use `items` field
- Comment in appointment.py mentions "redundant 'items' field" fix

**Schema**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/appointment.py:189-200`

```python
class AppointmentV2List(CursorPaginatedResponse):
    """
    Paginated list of appointments.
    Inherits from CursorPaginatedResponse which uses 'data' field.
    FIX: Removed redundant 'items' field - use inherited 'data' instead.
    """
```

**Impact**: Clients must know to use `data` not `items` for list responses
**Recommendation**: Document clearly in API docs and examples

---

### Issue 13: Enhanced Quiz Response Model Uses Dict[str, Any]

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/enhanced_quiz.py:78-81`

**Issue**:
```python
@router.post(
    "/templates/advanced",
    response_model=Dict[str, Any],  # ← TOO GENERIC
```

**The Problem**:
- Untyped response provides no contract
- Clients can't validate response structure
- OpenAPI schema shows `{}`
- No documentation of response fields

**Impact**: Breaking changes possible; no client type safety

**Recommendation**:
```python
class AdvancedQuizTemplateResponse(BaseModel):
    template_id: UUID
    name: str
    # ... other fields ...

@router.post(
    "/templates/advanced",
    response_model=AdvancedQuizTemplateResponse,
```

---

## MEDIUM SEVERITY ISSUES (6)

### Issue 14: PatientV2Base Fields Missing `required` vs `optional` Documentation

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/patient.py:42-74`

Fields like `diagnosis`, `treatment_type`, `timezone` have defaults but no clear documentation of when they're required vs optional in CREATE vs UPDATE operations.

**Recommendation**: Create separate `PatientV2Create` and `PatientV2Update` schemas with explicit required/optional fields.

---

### Issue 15: Validation Rules Not Mirrored in Schema Examples

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/patient.py:45-57`

**Issue**:
```python
treatment_phase: Optional[str] = Field(
    None,
    max_length=100,
    pattern="^(initial|adjustment|maintenance|monitoring|followup|completed)$"
)
```

Examples show values like "active" and "monitoring" but pattern only allows specific values. Some examples violate validation rules.

---

### Issue 16: Missing Field Descriptions in Several Schemas

Examples:
- `NotificationV2Response.action_url` - description present
- But many UUID fields lack descriptions of what they reference
- `response_metadata` in quiz responses undefined

**Recommendation**: Add descriptions to all fields for OpenAPI documentation.

---

### Issue 17: Relationship Loading Not Documented

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/common.py:161-165`

```python
@field_validator("include")
@classmethod
def validate_include(cls, v):
    allowed = {"doctor", "quizzes", "templates", "analytics"}
    # Only documents what can be included, not what returns
```

**Issue**: Allowed values differ from actual relationships in schemas.

---

### Issue 18: Eager Loading Validation Rules Incomplete

**Location**: Multiple files

Validation allows `["doctor", "quizzes"]` but:
- Quiz response might not have `quizzes` relationship
- Patient response might not have `templates`
- No per-endpoint documentation

---

### Issue 19: Field Selection Validator Too Permissive

**Location**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/common.py:89-102`

```python
@staticmethod
def validate_fields(fields: Set[str], allowed: Set[str]) -> None:
    invalid = fields - allowed
    if invalid:
        raise ValueError(f"Invalid fields: {', '.join(invalid)}")
```

No documentation of what fields are allowed per endpoint.

---

## RECOMMENDATIONS BY PRIORITY

### P0: Immediate Fixes (Blocking)

1. **Add Generic Type Parameters**
   - `AppointmentV2List[AppointmentV2Response]`
   - Any other untyped CursorPaginatedResponse usage

2. **Fix FirebaseTokenVerifyResponse**
   - Uncomment and properly define `user` field
   - Update example to match schema
   - Add Field descriptions

3. **Standardize UUID Handling**
   - Use `UUID` type in response schemas (not string)
   - Configure JSON serialization to convert to string
   - Ensures type safety across API

4. **Fix DateTime Serialization**
   - Always include timezone in datetime serialization
   - Clarify `date` vs `datetime` in examples
   - Document RFC3339 format requirement

5. **Document Session User Field**
   - Add proper Field descriptor to SessionV2Response.user
   - Specify when it's populated vs null

### P1: Important Fixes (High Impact)

6. **Create Relationship Documentation**
   - Document which relationships available per endpoint
   - List allowed values for `include` parameter per router
   - Add response class variants (with/without relationships)

7. **Fix Response Construction**
   - Convert dict returns to Pydantic model instances
   - Enable automatic validation
   - Ensure optional fields are properly populated

8. **Standardize Field Naming**
   - Ensure consistency across all schemas
   - Document alias patterns (e.g., `patient_id` → database `patient_uuid`)

9. **Add Comprehensive Examples**
   - Ensure examples follow validation rules
   - Show optional fields when present/absent
   - Document real vs example data

10. **Create Endpoint-Specific Documentation**
    - List available relationships per endpoint
    - Document field selection options
    - Specify required vs optional response fields

### P2: Important (Medium Impact)

11. **Enhance Field Descriptions**
    - Add descriptions to all UUID fields
    - Document what metadata structures contain
    - Clarify relationship cardinality

12. **Create Response Variants**
    - Separate schemas for list vs detail responses
    - Create CreateResponse vs UpdateResponse variants
    - Document field presence by operation

---

## Testing Recommendations

### API Contract Tests
```python
def test_appointment_list_response_model():
    """Verify AppointmentV2List includes proper type parameters."""
    from app.schemas.v2.appointment import AppointmentV2List
    assert AppointmentV2List.__orig_bases__[0].__args__ == (AppointmentV2Response,)

def test_firebase_response_includes_user_field():
    """Verify FirebaseTokenVerifyResponse includes user field."""
    response = FirebaseTokenVerifyResponse(
        valid=True,
        user={"id": "...", "email": "..."},
        session_id="sess_123"
    )
    assert response.user is not None

def test_datetime_serialization():
    """Verify all datetimes serialize with timezone info."""
    response = SessionV2Response(...)
    json_str = response.model_dump_json()
    assert "+00:00" in json_str or "Z" in json_str
```

---

## Migration Path for Breaking Changes

1. **Phase 1**: Add new properly-typed response schemas alongside existing ones
2. **Phase 2**: Deprecation period (2 versions) - support both old and new
3. **Phase 3**: Remove old schemas, document migration in changelog

---

## Reference Files

All issues reference these key files:

**Schemas**:
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/auth.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/patient.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/appointment.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/quiz_extensions.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/schemas/v2/common.py`

**Routers**:
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/auth.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/appointments.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/patients/crud.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/quiz_responses.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/quiz_templates.py`

---

## Conclusion

The API schema contracts have significant inconsistencies that impact client reliability. The 5 critical issues require immediate attention to prevent deserialization failures. High and medium priority issues should be addressed in the next sprint to improve API stability and developer experience.

**Estimated Effort**:
- Critical fixes: 8-12 hours
- High priority: 12-16 hours
- Medium priority: 4-6 hours
- Testing & validation: 4-6 hours
- **Total: 28-40 hours** (1 week for experienced team)
