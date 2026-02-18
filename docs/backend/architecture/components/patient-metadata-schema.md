# Patient Metadata JSON Schema

**Reference**: LOW-007 - JSONB Schema Validation
**Version**: 1.0.0
**File**: `app/utils/jsonb_validator.py`

## Overview

This document describes the JSON schema for the `patient.patient_data` (metadata) JSONB field. The schema ensures data integrity and consistent structure across the application.

## Schema Validation

All patient metadata is validated against a strict JSON schema at three levels:

1. **Pydantic Schema**: `PatientCreate` and `PatientUpdate` validate on API input
2. **ORM Validation**: `Patient` model validates on database writes
3. **Manual Validation**: `validate_patient_metadata()` for programmatic checks

## Top-Level Fields

The schema allows the following top-level fields (**additionalProperties: false**):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `preferences` | object | No | Patient preferences and settings |
| `medical_history` | object | No | Medical history information |
| `emergency_contact` | object | No | Emergency contact details |
| `insurance` | object | No | Insurance policy information |
| `onboarding` | object | No | Onboarding process metadata |
| `custom_fields` | object | No | Clinic-specific custom data |
| `doctor_name` | string | No | Cached doctor name (performance) |
| `system` | object | No | System-managed metadata |

---

## Field Schemas

### 1. `preferences`

Patient preferences and communication settings.

```json
{
  "preferences": {
    "language": "pt-BR",
    "timezone": "America/Sao_Paulo",
    "notification_enabled": true,
    "notification_time": "09:00",
    "communication_channel": "whatsapp"
  }
}
```

**Fields**:

| Field | Type | Allowed Values | Description |
|-------|------|----------------|-------------|
| `language` | string (enum) | `"pt-BR"`, `"en-US"`, `"es-ES"` | Preferred language |
| `timezone` | string (pattern) | `"Continent/City"` | Patient timezone (e.g., `"America/Sao_Paulo"`) |
| `notification_enabled` | boolean | `true`, `false` | Whether notifications are enabled |
| `notification_time` | string (pattern) | `"HH:MM"` (24-hour) | Preferred notification time (e.g., `"09:00"`) |
| `communication_channel` | string (enum) | `"whatsapp"`, `"email"`, `"sms"`, `"phone"` | Preferred channel |

**Constraints**:
- `timezone`: Must match pattern `^[A-Za-z]+/[A-Za-z_]+$`
- `notification_time`: Must match pattern `^([01]?[0-9]|2[0-3]):[0-5][0-9]$`

---

### 2. `medical_history`

Medical history and health information.

```json
{
  "medical_history": {
    "allergies": ["penicillin", "latex"],
    "medications": ["metformin", "aspirin"],
    "conditions": ["diabetes", "hypertension"],
    "family_history": ["cancer", "heart disease"],
    "surgeries": [
      {
        "type": "appendectomy",
        "date": "2020-05-15",
        "notes": "No complications"
      }
    ]
  }
}
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `allergies` | array[string] (unique) | Known allergies |
| `medications` | array[string] (unique) | Current medications |
| `conditions` | array[string] (unique) | Pre-existing medical conditions |
| `family_history` | array[string] (unique) | Family medical history |
| `surgeries` | array[object] | Past surgical procedures |

**Surgery Object**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | **Yes** | Surgery type (e.g., "appendectomy") |
| `date` | string (date) | **Yes** | Surgery date (ISO 8601: `"YYYY-MM-DD"`) |
| `notes` | string | No | Additional notes |

---

### 3. `emergency_contact`

Emergency contact information.

```json
{
  "emergency_contact": {
    "name": "Maria Silva",
    "relationship": "daughter",
    "phone": "+5511988888888",
    "email": "maria@example.com"
  }
}
```

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | **Yes** | Contact name (min length: 1) |
| `relationship` | string | No | Relationship to patient |
| `phone` | string (E.164) | **Yes** | Phone in E.164 format (`+[1-9]\d{1,14}`) |
| `email` | string (email) | No | Email address |

**Constraints**:
- `phone`: Must match E.164 format (e.g., `"+5511999999999"`)
- `email`: Must be valid email format

---

### 4. `insurance`

Insurance policy information.

```json
{
  "insurance": {
    "provider": "SulAmerica",
    "policy_number": "12345678",
    "group_number": "G123",
    "expiration_date": "2025-12-31"
  }
}
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `provider` | string | Insurance provider name |
| `policy_number` | string | Policy number |
| `group_number` | string | Group number (if applicable) |
| `expiration_date` | string (date) | Policy expiration (ISO 8601) |

---

### 5. `onboarding`

Onboarding process metadata.

```json
{
  "onboarding": {
    "completed": true,
    "completed_at": "2024-01-15T10:30:00-03:00",
    "steps_completed": ["welcome", "assessment", "preferences"],
    "welcome_sent": true,
    "initial_assessment_done": true
  }
}
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `completed` | boolean | Whether onboarding is complete |
| `completed_at` | string (datetime) | Completion timestamp (ISO 8601) |
| `steps_completed` | array[string] | List of completed steps |
| `welcome_sent` | boolean | Whether welcome message was sent |
| `initial_assessment_done` | boolean | Whether initial assessment is done |

---

### 6. `custom_fields`

Clinic-specific custom data (**additionalProperties: true**).

```json
{
  "custom_fields": {
    "referral_source": "website",
    "vip_status": true,
    "notes": "Patient requires special attention",
    "any_custom_field": "any value"
  }
}
```

This section allows **any** additional properties for clinic-specific needs.

---

### 7. `doctor_name`

Cached doctor name for performance (simple string).

```json
{
  "doctor_name": "Dr. João Santos"
}
```

**Type**: string
**Purpose**: Cache doctor name to avoid JOIN queries

---

### 8. `system`

System-managed metadata (internal use).

```json
{
  "system": {
    "source": "whatsapp",
    "version": "1.0.0",
    "last_sync": "2024-01-20T14:30:00-03:00"
  }
}
```

**Fields**:

| Field | Type | Allowed Values | Description |
|-------|------|----------------|-------------|
| `source` | string (enum) | `"whatsapp"`, `"web"`, `"api"`, `"import"` | Creation source |
| `version` | string | Any | Schema version for migrations |
| `last_sync` | string (datetime) | ISO 8601 | Last sync timestamp |

---

## Usage Examples

### Python Validation

```python
from app.utils.jsonb_validator import validate_patient_metadata

# Validate metadata
metadata = {
    "preferences": {"language": "pt-BR"},
    "medical_history": {"allergies": ["penicillin"]}
}

validated = validate_patient_metadata(metadata)  # Raises ValidationError if invalid
```

### Check Validity Without Exception

```python
from app.utils.jsonb_validator import is_valid_metadata, get_validation_errors

if not is_valid_metadata(metadata):
    errors = get_validation_errors(metadata)
    for error in errors:
        print(f"Field: {error['field']}, Error: {error['message']}")
```

### Sanitize Invalid Metadata

```python
from app.utils.jsonb_validator import sanitize_metadata

# Remove unknown fields
dirty_metadata = {
    "preferences": {"language": "pt-BR"},
    "unknown_field": "will be removed"
}

clean = sanitize_metadata(dirty_metadata)
# Result: {"preferences": {"language": "pt-BR"}}
```

### Merge Metadata

```python
from app.utils.jsonb_validator import merge_metadata

existing = {"preferences": {"language": "pt-BR"}}
updates = {"preferences": {"timezone": "America/Sao_Paulo"}}

merged = merge_metadata(existing, updates)
# Result: {"preferences": {"language": "pt-BR", "timezone": "America/Sao_Paulo"}}
```

---

## Common Validation Errors

### Unknown Top-Level Field

```json
{
  "unknown_field": "value"  // ❌ Not allowed
}
```

**Error**: `Additional properties are not allowed ('unknown_field' was unexpected)`

---

### Invalid Language Enum

```json
{
  "preferences": {
    "language": "fr-FR"  // ❌ Not in enum
  }
}
```

**Error**: `'fr-FR' is not one of ['pt-BR', 'en-US', 'es-ES']`

---

### Invalid Phone Format

```json
{
  "emergency_contact": {
    "name": "Test",
    "phone": "123"  // ❌ Not E.164 format
  }
}
```

**Error**: `'123' does not match '^\\+[1-9]\\d{1,14}$'`

---

## Migration Guide

### Existing Data Validation

```sql
-- Migration 014: Validate existing patient metadata
-- See: alembic/versions/014_validate_patient_metadata.py
```

The migration validates all existing patient metadata and reports violations without failing (logs warnings).

---

## Schema Version

**Current Version**: `1.0.0`

To check schema version programmatically:

```python
from app.utils.jsonb_validator import get_schema_version

version = get_schema_version()  # "1.0.0"
```

---

## References

- **Implementation**: `backend-hormonia/app/utils/jsonb_validator.py`
- **Tests**: `backend-hormonia/tests/utils/test_jsonb_validator.py`
- **Migration**: `backend-hormonia/alembic/versions/014_validate_patient_metadata.py`
- **Issue**: LOW-007 - JSONB Schema Validation
