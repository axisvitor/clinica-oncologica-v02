# API Schema Fixes - Code Implementation Guide

## Critical Fix #1: AppointmentV2List Generic Type Parameter

### File: `app/schemas/v2/appointment.py` (Line 189-202)

**BEFORE** (Incorrect):
```python
class AppointmentV2List(CursorPaginatedResponse):
    """
    Paginated list of appointments.

    Inherits from CursorPaginatedResponse which uses 'data' field.
    FIX: Removed redundant 'items' field - use inherited 'data' instead.
    This aligns with the router response format.
    """

    # Uses 'data' field from CursorPaginatedResponse base class
    # data: List[AppointmentV2Response] is inherited but typed generically

    model_config = ConfigDict(from_attributes=True)
```

**AFTER** (Correct):
```python
class AppointmentV2List(CursorPaginatedResponse[AppointmentV2Response]):
    """
    Paginated list of appointments with cursor pagination support.

    Response structure:
    - data: List of AppointmentV2Response objects
    - next_cursor: Cursor for fetching next page
    - has_more: Whether more items exist
    - total: Total count of items
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "patient_id": "223e4567-e89b-12d3-a456-426614174001",
                        "appointment_type": "consultation",
                        "status": "scheduled",
                        "scheduled_at": "2025-01-20T14:30:00+00:00",
                        "created_at": "2025-01-15T10:00:00+00:00",
                        "updated_at": "2025-01-15T10:00:00+00:00",
                    }
                ],
                "next_cursor": "eyJpZCI6IjEyM2U0NTY3In0=",
                "has_more": False,
                "total": 15,
            }
        }
    )
```

**Why This Matters**:
- Properly specifies the generic type parameter for OpenAPI generation
- IDE will now understand `data: List[AppointmentV2Response]`
- TypeScript client generation will create proper types
- Pydantic validation will check nested AppointmentV2Response fields

---

## Critical Fix #2: FirebaseTokenVerifyResponse User Field

### File: `app/schemas/v2/auth.py` (Line 462-483)

**BEFORE** (Incorrect):
```python
class FirebaseTokenVerifyResponse(BaseModel):
    """Response after verifying Firebase token"""

    valid: bool
    # user: Optional[UserV2Response] = None  # ← COMMENTED OUT!
    session_id: Optional[str] = None
    message: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valid": True,
                "user": {  # ← BUT EXAMPLE SHOWS IT!
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "doctor@example.com",
                    "full_name": "Dr. Maria Silva",
                    "role": "doctor",
                },
                "session_id": "sess_abc123",
            }
        }
    )
```

**AFTER** (Correct):
```python
class FirebaseTokenVerifyResponse(BaseModel):
    """Response after verifying Firebase token with user data"""

    valid: bool = Field(..., description="Whether token is valid")
    user: Optional[UserV2Response] = Field(
        None,
        description="Authenticated user information (included on successful verification)"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for subsequent authenticated requests"
    )
    message: Optional[str] = Field(
        None,
        description="Status message (e.g., 'Login successful')"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "valid": True,
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "doctor@example.com",
                    "full_name": "Dr. Maria Silva",
                    "role": "doctor",
                    "is_active": True,
                    "created_at": "2025-01-01T10:00:00+00:00",
                    "updated_at": "2025-01-15T10:00:00+00:00",
                },
                "session_id": "sess_abc123def456",
                "message": "Login successful"
            }
        }
    )
```

**Router Code** (`app/api/v2/routers/auth.py:200-210`):
```python
# Verify the router actually returns the user object
from app.schemas.v2.auth import FirebaseTokenVerifyResponse

# Build response
response_data = {
    "valid": True,
    "user": {  # ← ENSURE THIS IS ALWAYS INCLUDED
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    },
    "session_id": str(session.id),
    "message": "Login successful"
}

return response_data  # Will be validated against schema
```

**Why This Matters**:
- Clients now know user object is included
- OpenAPI schema documents user structure
- Type generation works correctly
- Breaking change prevention documented

---

## Critical Fix #3: UUID Typing in Appointment Response

### File: `app/schemas/v2/appointment.py` (Line 163-186)

**BEFORE** (Incorrect):
```python
class AppointmentV2Response(BaseModel):
    """Schema for appointment response"""

    id: str  # ← Should be UUID
    patient_id: str  # ← Should be UUID
    practitioner_id: Optional[str] = None  # ← Should be Optional[UUID]
    appointment_type: str
    status: str
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    cancelled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    pre_appointment_notes: Optional[str] = None
    post_appointment_notes: Optional[str] = None
    reminder_sent: bool = False
    confirmation_sent: bool = False
    created_at: datetime
    updated_at: datetime

    # Optional relationships (included based on query params)
    patient: Optional[PatientV2Brief] = None
    practitioner: Optional[PractitionerV2Brief] = None

    model_config = ConfigDict(from_attributes=True)
```

**AFTER** (Correct):
```python
from uuid import UUID
from pydantic import Field, field_serializer

class AppointmentV2Response(BaseModel):
    """Schema for appointment response with full details"""

    id: UUID = Field(..., description="Unique appointment identifier")
    patient_id: UUID = Field(..., description="Patient identifier")
    practitioner_id: Optional[UUID] = Field(
        None,
        description="Practitioner/doctor identifier"
    )
    appointment_type: str = Field(
        ...,
        max_length=50,
        description="Type: consultation, followup, treatment, exam, emergency, telemedicine"
    )
    status: str = Field(
        ...,
        max_length=50,
        description="Status: scheduled, confirmed, in_progress, completed, cancelled, no_show"
    )
    scheduled_at: Optional[datetime] = Field(
        None,
        description="Scheduled date and time (UTC)"
    )
    duration_minutes: Optional[int] = Field(
        None,
        ge=15,
        le=480,
        description="Appointment duration in minutes"
    )
    cancelled_at: Optional[datetime] = Field(
        None,
        description="When appointment was cancelled"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="When appointment was completed"
    )
    pre_appointment_notes: Optional[str] = Field(
        None,
        max_length=2000,
        description="Notes before appointment"
    )
    post_appointment_notes: Optional[str] = Field(
        None,
        max_length=2000,
        description="Notes after appointment"
    )
    reminder_sent: bool = Field(
        False,
        description="Whether reminder notification was sent"
    )
    confirmation_sent: bool = Field(
        False,
        description="Whether confirmation notification was sent"
    )
    created_at: datetime = Field(
        ...,
        description="Record creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        ...,
        description="Record last update timestamp (UTC)"
    )

    # Optional relationships (included based on query params)
    patient: Optional[PatientV2Brief] = Field(
        None,
        description="Patient information (included when requested)"
    )
    practitioner: Optional[PractitionerV2Brief] = Field(
        None,
        description="Practitioner information (included when requested)"
    )

    # Serializers for proper JSON output
    @field_serializer('id', 'patient_id', 'practitioner_id')
    def serialize_uuids(self, value: Optional[UUID]) -> Optional[str]:
        """Convert UUID to string for JSON serialization"""
        return str(value) if value else None

    @field_serializer('created_at', 'updated_at', 'scheduled_at', 'cancelled_at', 'completed_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Serialize datetime with UTC timezone"""
        if value is None:
            return None
        # Ensure timezone aware
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "patient_id": "223e4567-e89b-12d3-a456-426614174001",
                "practitioner_id": "323e4567-e89b-12d3-a456-426614174002",
                "appointment_type": "consultation",
                "status": "scheduled",
                "scheduled_at": "2025-01-20T14:30:00+00:00",
                "duration_minutes": 30,
                "created_at": "2025-01-15T10:00:00+00:00",
                "updated_at": "2025-01-15T10:00:00+00:00",
            }
        }
    )
```

**Why This Matters**:
- Type-safe UUID comparisons in Python code
- Prevents accidental string ID bugs
- Automatic serialization to string in JSON
- OpenAPI spec shows proper UUID format

---

## Critical Fix #4: SessionV2Response User Field

### File: `app/schemas/v2/auth.py` (Line 366-391)

**BEFORE** (Incorrect):
```python
class SessionV2Response(BaseModel):
    """Active session information"""

    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_current: bool = Field(False, description="Whether this is the current session")
    valid: bool = Field(True, description="Session validity status")
    user: Optional["UserV2Response"] = None  # ← String reference, no Field descriptor

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123def456",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "created_at": "2025-11-07T08:00:00Z",
                "expires_at": "2025-11-08T08:00:00Z",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0...",
                "is_current": True,
            }
        }
    )
```

**AFTER** (Correct):
```python
from typing import Optional
from pydantic import Field

class SessionV2Response(BaseModel):
    """Active session information with optional user details"""

    session_id: str = Field(
        ...,
        description="Unique session identifier"
    )
    user_id: str = Field(
        ...,
        description="User identifier (UUID string)"
    )
    created_at: datetime = Field(
        ...,
        description="Session creation timestamp (UTC)"
    )
    expires_at: datetime = Field(
        ...,
        description="Session expiration timestamp (UTC)"
    )
    ip_address: Optional[str] = Field(
        None,
        description="IP address of session origin"
    )
    user_agent: Optional[str] = Field(
        None,
        description="User agent string from request"
    )
    is_current: bool = Field(
        False,
        description="Whether this is the current session"
    )
    valid: bool = Field(
        True,
        description="Session validity status"
    )
    user: Optional[UserV2Response] = Field(
        None,
        description="Authenticated user information (included when user context available)"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123def456",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "created_at": "2025-11-07T08:00:00+00:00",
                "expires_at": "2025-11-08T08:00:00+00:00",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "is_current": True,
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "doctor@example.com",
                    "full_name": "Dr. Maria Silva",
                    "role": "doctor",
                    "is_active": True,
                    "created_at": "2025-01-01T10:00:00+00:00",
                    "updated_at": "2025-11-07T08:00:00+00:00",
                }
            }
        }
    )
```

**Why This Matters**:
- User field now properly documented with Field descriptor
- OpenAPI schema includes user structure
- Clients know when user data will be present
- Better documentation for API users

---

## Critical Fix #5: DateTime Serialization Consistency

### Add to `app/schemas/v2/common.py`

**ADD** (New Utility Functions):
```python
from datetime import datetime, timezone
from typing import Optional
from pydantic import field_serializer, field_validator

class DateTimeSerializerMixin:
    """Mixin to ensure consistent UTC datetime serialization."""

    @field_validator('*', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        """Ensure datetime values are timezone-aware."""
        if isinstance(v, str):
            # Parse ISO format strings
            try:
                dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
                # Ensure timezone aware
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, AttributeError):
                pass
        elif isinstance(v, datetime):
            # Ensure timezone aware
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            return v
        return v

    def _serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Serialize datetime to RFC3339 format with timezone."""
        if value is None:
            return None
        # Ensure timezone aware
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        # Return ISO format with timezone (RFC3339)
        return value.isoformat()
```

**USAGE** (Update Response Classes):
```python
from pydantic import field_serializer

class SessionV2Response(BaseModel, DateTimeSerializerMixin):
    """Active session information"""

    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_current: bool = Field(False, ...)
    valid: bool = Field(True, ...)
    user: Optional[UserV2Response] = Field(None, ...)

    @field_serializer('created_at', 'expires_at')
    def serialize_datetimes(self, value: datetime) -> str:
        """Serialize datetimes with UTC timezone."""
        return self._serialize_datetime(value)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "created_at": "2025-11-07T08:00:00+00:00",  # RFC3339 format
                "expires_at": "2025-11-08T08:00:00+00:00",  # RFC3339 format
            }
        }
    )
```

**UPDATE EXAMPLES**:
```python
# birth_date - use date format, not datetime
"birth_date": "1980-05-15",  # ISO date format

# datetime fields - always include timezone
"created_at": "2025-01-01T10:00:00+00:00",  # RFC3339 with timezone
"updated_at": "2025-01-15T14:30:00+00:00",  # RFC3339 with timezone
```

**Why This Matters**:
- Consistent datetime format across API
- Timezone information always present
- Compatible with all HTTP clients and languages
- Prevents parsing errors from ambiguous times

---

## Implementation Checklist

```
CRITICAL FIX #1: AppointmentV2List
- [ ] Update class definition line 189
- [ ] Update examples with proper formatting
- [ ] Test with generated OpenAPI spec
- [ ] Verify TypeScript client generation

CRITICAL FIX #2: FirebaseTokenVerifyResponse
- [ ] Uncomment user field (line 462)
- [ ] Add Field descriptor with description
- [ ] Update router return value documentation
- [ ] Test login flow with response validation

CRITICAL FIX #3: UUID Field Typing
- [ ] Update AppointmentV2Response fields (line 163)
- [ ] Add field_serializer for UUID → str
- [ ] Update all examples to show proper UUID format
- [ ] Test ID comparisons in router code

CRITICAL FIX #4: SessionV2Response
- [ ] Add Field descriptor to user field (line 377)
- [ ] Update example with complete user object
- [ ] Verify router includes user in response
- [ ] Test with empty/null user scenarios

CRITICAL FIX #5: DateTime Serialization
- [ ] Add DateTimeSerializerMixin to common.py
- [ ] Apply to all response classes with datetime fields
- [ ] Update all examples to use RFC3339 format
- [ ] Add tests for timezone handling

POST-FIX VALIDATION:
- [ ] Run schema validation tests
- [ ] Generate OpenAPI spec
- [ ] Verify no validation errors
- [ ] Test with client library generation (TypeScript/Python)
- [ ] Run integration tests
- [ ] Review examples in OpenAPI UI
```

---

## Related Test Cases to Add

```python
# tests/schemas/test_critical_fixes.py

def test_appointment_list_has_generic_type():
    """Verify AppointmentV2List has generic type parameter."""
    import typing
    from app.schemas.v2.appointment import AppointmentV2List, AppointmentV2Response

    # Get generic args
    orig_bases = AppointmentV2List.__orig_bases__
    assert len(orig_bases) > 0
    assert AppointmentV2Response in typing.get_args(orig_bases[0])

def test_firebase_response_includes_user():
    """Verify FirebaseTokenVerifyResponse includes user field."""
    from app.schemas.v2.auth import FirebaseTokenVerifyResponse

    response = FirebaseTokenVerifyResponse(
        valid=True,
        user={"id": "123", "email": "test@example.com"},
        session_id="sess_123"
    )
    assert response.user is not None
    assert response.user["email"] == "test@example.com"

def test_datetime_serialization():
    """Verify datetimes serialize with timezone info."""
    from app.schemas.v2.auth import SessionV2Response
    from datetime import datetime, timezone

    dt = datetime.now(timezone.utc)
    response = SessionV2Response(
        session_id="sess_123",
        user_id="user_123",
        created_at=dt,
        expires_at=dt
    )

    json_str = response.model_dump_json()
    assert "+00:00" in json_str or "Z" in json_str
```

---

**All fixes are backward-compatible** if JSON serializers are properly configured to convert UUIDs and datetimes to strings.

