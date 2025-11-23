# API Error Responses

**Reference**: LOW-017 - Inconsistent Error Handling
**Middleware**: `app/middleware/exception_handler.py`
**Exceptions**: `app/core/exceptions.py`

## Overview

All API endpoints return errors in a standardized JSON format, ensuring consistent error handling across the entire application.

## Standard Error Response Format

All errors follow this structure:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "status_code": 400,
  "details": {
    "field": "optional field name",
    "additional": "context"
  }
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `error` | string | Machine-readable error code (UPPERCASE_SNAKE_CASE) |
| `message` | string | Human-readable error message |
| `status_code` | integer | HTTP status code (same as response status) |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `details` | object | Additional error context (field-specific errors, etc.) |

---

## HTTP Status Codes

| Status Code | Error Code | Exception Class | Description |
|-------------|------------|-----------------|-------------|
| 400 | `BAD_REQUEST` | `BadRequestError` | Malformed request |
| 400 | `BUSINESS_RULE_VIOLATION` | `BusinessRuleError` | Business logic violation |
| 401 | `UNAUTHORIZED` | `UnauthorizedError` | Authentication required |
| 403 | `FORBIDDEN` | `ForbiddenError` | Insufficient permissions |
| 404 | `NOT_FOUND` | `NotFoundError` | Resource not found |
| 409 | `CONFLICT` | `ConflictError` | Resource conflict (duplicate) |
| 409 | `DUPLICATE_RESOURCE` | (IntegrityError) | Database unique constraint violation |
| 422 | `VALIDATION_ERROR` | `ValidationError` | Input validation failed |
| 429 | `RATE_LIMIT_EXCEEDED` | `RateLimitError` | Too many requests |
| 500 | `INTERNAL_ERROR` | (Exception) | Unexpected server error |
| 503 | `SERVICE_UNAVAILABLE` | `ServiceUnavailableError` | Service temporarily down |
| 503 | `EXTERNAL_SERVICE_ERROR` | `ExternalServiceError` | External API failed |

---

## Error Types and Examples

### 1. Validation Errors (422)

**When**: Input data fails validation rules (Pydantic, schema, etc.)

**Example Request**:
```http
POST /api/v2/patients
Content-Type: application/json

{
  "name": "Test Patient",
  "phone": "+5511999999999",
  "birth_date": "2010-01-01",  // Under 18
  "cpf": "invalid"
}
```

**Response** (`422 Unprocessable Entity`):
```json
{
  "error": "VALIDATION_ERROR",
  "message": "Input validation failed",
  "status_code": 422,
  "details": {
    "errors": {
      "birth_date": "Patient must be at least 18 years old. Birth date 2010-01-01 indicates age of 15.1 years.",
      "cpf": "Invalid CPF number"
    }
  }
}
```

**Usage in Code**:
```python
from app.core.exceptions import ValidationError

raise ValidationError(
    "Input validation failed",
    errors={
        "cpf": "Invalid CPF format",
        "birth_date": "Must be at least 18 years old"
    }
)
```

---

### 2. Not Found Errors (404)

**When**: Requested resource doesn't exist

**Example Request**:
```http
GET /api/v2/patients/123e4567-e89b-12d3-a456-426614174000
```

**Response** (`404 Not Found`):
```json
{
  "error": "NOT_FOUND",
  "message": "Patient not found",
  "status_code": 404,
  "details": {
    "resource": "Patient",
    "identifier": "123e4567-e89b-12d3-a456-426614174000"
  }
}
```

**Usage in Code**:
```python
from app.core.exceptions import NotFoundError, PatientNotFoundError

# Generic
raise NotFoundError("Patient", patient_id)

# Specialized
raise PatientNotFoundError(patient_id)
```

---

### 3. Business Rule Violations (400)

**When**: Operation violates business logic rules

**Example Request**:
```http
POST /api/v2/patients
Content-Type: application/json

{
  "name": "Test Patient",
  "phone": "+5511999999999",
  "cpf": "12345678901"  // Already exists
}
```

**Response** (`400 Bad Request`):
```json
{
  "error": "duplicate_cpf",
  "message": "Patient with this CPF already exists",
  "status_code": 400,
  "details": {
    "field": "cpf",
    "code": "duplicate_cpf"
  }
}
```

**Usage in Code**:
```python
from app.core.exceptions import BusinessRuleError

raise BusinessRuleError(
    "Patient with this CPF already exists",
    field="cpf",
    code="duplicate_cpf"
)
```

---

### 4. Conflict Errors (409)

**When**: Resource already exists or state conflict

**Example Request**:
```http
POST /api/v2/patients
Content-Type: application/json

{
  "email": "existing@example.com",  // Already in database
  ...
}
```

**Response** (`409 Conflict`):
```json
{
  "error": "CONFLICT",
  "message": "Patient with this email already exists",
  "status_code": 409,
  "details": {
    "field": "email"
  }
}
```

**Usage in Code**:
```python
from app.core.exceptions import ConflictError

raise ConflictError(
    "Patient with this email already exists",
    {"field": "email"}
)
```

---

### 5. Unauthorized Errors (401)

**When**: Authentication required or invalid

**Example Request**:
```http
GET /api/v2/patients
Authorization: Bearer invalid_token
```

**Response** (`401 Unauthorized`):
```json
{
  "error": "UNAUTHORIZED",
  "message": "Invalid or expired token",
  "status_code": 401,
  "details": {}
}
```

**Usage in Code**:
```python
from app.core.exceptions import UnauthorizedError

raise UnauthorizedError("Invalid or expired token")
```

---

### 6. Forbidden Errors (403)

**When**: User authenticated but lacks permissions

**Example Request**:
```http
DELETE /api/v2/patients/123
Authorization: Bearer valid_doctor_token  // Doctors can't delete
```

**Response** (`403 Forbidden`):
```json
{
  "error": "FORBIDDEN",
  "message": "Only admins can delete patients",
  "status_code": 403,
  "details": {}
}
```

**Usage in Code**:
```python
from app.core.exceptions import ForbiddenError

raise ForbiddenError("Only admins can delete patients")
```

---

### 7. Database Errors (409/500)

**When**: Database constraint violations

**Example**: Unique constraint violation (duplicate)

**Response** (`409 Conflict`):
```json
{
  "error": "DUPLICATE_RESOURCE",
  "message": "Resource already exists",
  "status_code": 409,
  "details": {
    "field": "cpf"  // Extracted from constraint name
  }
}
```

**Handled Constraints**:
- `uq_patient_cpf_doctor` → `"field": "cpf"`
- `uq_patient_email_doctor` → `"field": "email"`
- `uq_patient_phone_doctor` → `"field": "phone"`

---

### 8. External Service Errors (503)

**When**: External APIs fail (WhatsApp, Firebase, etc.)

**Response** (`503 Service Unavailable`):
```json
{
  "error": "EXTERNAL_SERVICE_ERROR",
  "message": "WhatsApp service error: Connection timeout",
  "status_code": 503,
  "details": {
    "service": "WhatsApp",
    "error": "Connection timeout"
  }
}
```

**Usage in Code**:
```python
from app.core.exceptions import ExternalServiceError

raise ExternalServiceError("WhatsApp", "Connection timeout")
```

---

### 9. Rate Limiting (429)

**When**: Too many requests from same client

**Response** (`429 Too Many Requests`):
```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Too many login attempts. Please try again in 60 seconds.",
  "status_code": 429,
  "details": {
    "retry_after": 60
  }
}
```

**Usage in Code**:
```python
from app.core.exceptions import RateLimitError

raise RateLimitError("Too many login attempts", retry_after=60)
```

---

### 10. Internal Server Errors (500)

**When**: Unexpected exceptions

**Response** (`500 Internal Server Error`):
```json
{
  "error": "INTERNAL_ERROR",
  "message": "An unexpected error occurred",
  "status_code": 500,
  "details": {}
}
```

All unhandled exceptions are caught and returned as 500 errors. Details are logged but not exposed to clients.

---

## Error Code Reference

### Client Errors (4xx)

| Error Code | Status | Description |
|------------|--------|-------------|
| `BAD_REQUEST` | 400 | Malformed request or invalid parameters |
| `BUSINESS_RULE_VIOLATION` | 400 | Business logic violation |
| `UNAUTHORIZED` | 401 | Authentication required or failed |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource conflict (state/duplicate) |
| `DUPLICATE_RESOURCE` | 409 | Database unique constraint |
| `VALIDATION_ERROR` | 422 | Input validation failed |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |

### Server Errors (5xx)

| Error Code | Status | Description |
|------------|--------|-------------|
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `DATABASE_ERROR` | 500 | Database operation failed |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily down |
| `EXTERNAL_SERVICE_ERROR` | 503 | External API failure |

---

## Best Practices

### 1. Use Specific Exception Classes

```python
# ✅ Good
raise PatientNotFoundError(patient_id)
raise ValidationError("Invalid input", errors={"cpf": "Invalid CPF"})

# ❌ Bad
raise HTTPException(404, "Not found")
raise Exception("Error")
```

### 2. Provide Detailed Error Context

```python
# ✅ Good
raise ValidationError(
    "Input validation failed",
    errors={
        "cpf": "Invalid CPF format",
        "birth_date": "Must be at least 18 years old"
    }
)

# ❌ Bad
raise ValidationError("Invalid input")
```

### 3. Use Appropriate Status Codes

- **400**: Client error (bad input, business rule)
- **404**: Resource not found
- **409**: Conflict (duplicate, state)
- **422**: Validation error (schema, format)
- **500**: Server error (unexpected)

### 4. Include Field Information

```python
# ✅ Good
raise BusinessRuleError(
    "Patient already exists",
    field="cpf",
    code="duplicate_cpf"
)

# ❌ Bad
raise BusinessRuleError("Duplicate")
```

---

## Testing

See `tests/api/test_error_responses.py` for comprehensive error response tests.

---

## Migration from Old Error Handling

### Before (Inconsistent)

```python
# Various inconsistent patterns
raise HTTPException(404, "Patient not found")
raise ValueError("Invalid CPF")
return {"error": "Something went wrong"}
```

### After (Standardized)

```python
from app.core.exceptions import NotFoundError, ValidationError, BusinessRuleError

raise NotFoundError("Patient", patient_id)
raise ValidationError("Invalid input", errors={"cpf": "Invalid CPF format"})
raise BusinessRuleError("Patient already exists", field="cpf", code="duplicate_cpf")
```

---

## References

- **Exception Classes**: `backend-hormonia/app/core/exceptions.py`
- **Middleware**: `backend-hormonia/app/middleware/exception_handler.py`
- **Tests**: `backend-hormonia/tests/api/test_error_responses.py`
- **Issue**: LOW-017 - Inconsistent Error Handling
