# Clinical Metadata Schema - Patient JSONB Fields

**Status**: ✅ Implemented
**Version**: 1.1.0
**Reference**: V2 API Evolution - Clinical Fields
**Files**:
- `/app/utils/patient_metadata_schema.py` - Clinical validation
- `/app/utils/jsonb_validator.py` - Base metadata validation
- `/app/models/patient.py` - Patient model with `patient_data` field

---

## Overview

This document describes the clinical fields stored in the `patient.patient_data` JSONB column (database column name: `metadata`). These fields extend the base patient model with flexible clinical information without requiring schema migrations.

## Key Principles

1. **No Database Migration Required**: All clinical fields are stored in the existing `metadata` JSONB column
2. **Backward Compatible**: New fields are optional and don't break existing data
3. **Validated**: Pydantic schemas ensure data integrity
4. **API-Friendly**: Helper functions provide flattened data for frontend consumption

---

## Clinical Fields Structure

### Complete Example

```json
{
  "medical_history": {
    "allergies": ["Penicillin", "Latex"],
    "medications": ["Metformin 500mg", "Lisinopril 10mg"],
    "conditions": ["Type 2 Diabetes", "Hypertension"],
    "family_history": ["Breast Cancer (mother)", "Heart Disease (father)"],
    "surgeries": [
      {
        "type": "Appendectomy",
        "date": "2015-06-15",
        "notes": "No complications"
      }
    ]
  },
  "blood_type": "A+",
  "emergency_contact": {
    "name": "Maria Silva",
    "phone": "+5511987654321",
    "relationship": "Spouse",
    "email": "maria@example.com"
  },
  "preferences": {
    "language": "pt-BR",
    "timezone": "America/Sao_Paulo",
    "notification_enabled": true
  },
  "onboarding": {
    "completed": true,
    "completed_at": "2024-01-15T10:00:00Z"
  }
}
```

---

## Field Definitions

### 1. Medical History (`medical_history`)

Container for all medical history information.

#### Properties

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `allergies` | `string[]` | No | Known allergies (medications, foods, environmental) |
| `medications` | `string[]` | No | Current medications with dosage |
| `conditions` | `string[]` | No | Pre-existing medical conditions (comorbidities) |
| `family_history` | `string[]` | No | Family medical history |
| `surgeries` | `object[]` | No | Past surgical procedures |

#### Example

```json
{
  "medical_history": {
    "allergies": ["Penicillin", "Peanuts", "Latex"],
    "medications": [
      "Metformin 500mg - 2x daily",
      "Lisinopril 10mg - 1x daily morning"
    ],
    "conditions": [
      "Type 2 Diabetes",
      "Hypertension",
      "Hypothyroidism"
    ],
    "family_history": [
      "Breast Cancer (mother)",
      "Type 2 Diabetes (father)"
    ],
    "surgeries": [
      {
        "type": "Appendectomy",
        "date": "2015-06-15",
        "notes": "Emergency surgery, no complications"
      }
    ]
  }
}
```

#### Validation Rules

- All array fields automatically remove duplicates
- Arrays maintain insertion order
- Each string should be descriptive (e.g., "Aspirin 100mg" not just "Aspirin")

---

### 2. Blood Type (`blood_type`)

Patient's blood type in standard ABO/Rh notation.

#### Format

```
Pattern: ^(A|B|AB|O)[+-]$
```

#### Valid Values

- `A+`, `A-`
- `B+`, `B-`
- `AB+`, `AB-`
- `O+`, `O-`

#### Example

```json
{
  "blood_type": "A+"
}
```

---

### 3. Emergency Contact (`emergency_contact`)

Emergency contact information for the patient.

#### Properties

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | Yes* | Emergency contact name |
| `phone` | `string` | Yes* | Phone in E.164 format |
| `relationship` | `string` | No | Relationship to patient |
| `email` | `string` | No | Emergency contact email |

*Required together: If `emergency_contact` is present, both `name` and `phone` are required.

#### Phone Format (E.164)

```
Pattern: ^\+[1-9]\d{1,14}$

Examples:
- Brazil: +5511987654321
- USA: +15551234567
- UK: +447700900123
```

#### Example

```json
{
  "emergency_contact": {
    "name": "Maria Silva",
    "phone": "+5511987654321",
    "relationship": "Spouse",
    "email": "maria@example.com"
  }
}
```

---

## Python API Usage

### Importing

```python
from app.utils.patient_metadata_schema import (
    validate_clinical_metadata,
    validate_blood_type,
    validate_emergency_contact,
    get_clinical_fields,
    merge_clinical_metadata,
    extract_clinical_summary,
)
```

### 1. Validate Clinical Metadata

```python
# Validate complete metadata
metadata = {
    "medical_history": {
        "allergies": ["Penicillin"],
        "medications": ["Aspirin 100mg"]
    },
    "blood_type": "A+",
    "emergency_contact": {
        "name": "Maria Silva",
        "phone": "+5511987654321"
    }
}

# Strict mode (raises ValidationError on failure)
validated = validate_clinical_metadata(metadata, strict=True)

# Non-strict mode (returns original data on failure)
validated = validate_clinical_metadata(metadata, strict=False)
```

### 2. Validate Specific Fields

```python
# Validate blood type
is_valid = validate_blood_type("A+")  # True
is_valid = validate_blood_type("Invalid")  # False

# Validate emergency contact
contact = {
    "name": "Maria",
    "phone": "+5511987654321"
}
is_valid = validate_emergency_contact(contact)  # True
```

### 3. Extract Clinical Fields

```python
# Extract only clinical fields from metadata
metadata = {
    "medical_history": {"allergies": ["Penicillin"]},
    "blood_type": "A+",
    "preferences": {"language": "pt-BR"}  # Not clinical
}

clinical_only = get_clinical_fields(metadata)
# Result: {"medical_history": {...}, "blood_type": "A+"}
```

### 4. Merge Clinical Metadata

```python
# Safely merge updates into existing metadata
existing = {
    "medical_history": {"allergies": ["Penicillin"]},
    "preferences": {"language": "pt-BR"}
}

updates = {
    "medical_history": {"medications": ["Aspirin"]},
    "blood_type": "A+"
}

merged = merge_clinical_metadata(existing, updates)
# Result: Preserves allergies, adds medications and blood_type
```

### 5. Extract API-Friendly Summary

```python
# Get flattened structure for API responses
metadata = {
    "medical_history": {
        "allergies": ["Penicillin"],
        "medications": ["Aspirin"],
        "conditions": ["Diabetes"]
    },
    "blood_type": "A+",
    "emergency_contact": {
        "name": "Maria",
        "phone": "+5511987654321"
    }
}

summary = extract_clinical_summary(metadata)
# Result:
# {
#     "allergies": ["Penicillin"],
#     "current_medications": ["Aspirin"],
#     "comorbidities": ["Diabetes"],
#     "blood_type": "A+",
#     "emergency_contact_name": "Maria",
#     "emergency_contact_phone": "+5511987654321"
# }
```

---

## API Endpoint Integration

### Example: Update Patient Clinical Data

```python
from app.utils.patient_metadata_schema import merge_clinical_metadata, validate_clinical_metadata

@router.patch("/patients/{patient_id}/clinical")
async def update_patient_clinical_data(
    patient_id: UUID,
    clinical_updates: dict,
    db: Session = Depends(get_db)
):
    """Update patient clinical information."""
    # Get patient
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Validate updates
    validate_clinical_metadata(clinical_updates, strict=True)

    # Merge with existing metadata
    updated_metadata = merge_clinical_metadata(
        existing=patient.patient_data,
        updates=clinical_updates,
        validate_result=True
    )

    # Update patient
    patient.patient_data = updated_metadata
    db.commit()
    db.refresh(patient)

    # Return API-friendly summary
    from app.utils.patient_metadata_schema import extract_clinical_summary
    return {
        "patient_id": patient.id,
        "clinical_data": extract_clinical_summary(patient.patient_data)
    }
```

---

## API Response Format

### Flattened Clinical Data (Recommended)

```json
{
  "patient_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "João Silva",
  "clinical_data": {
    "allergies": ["Penicillin", "Latex"],
    "current_medications": ["Metformin 500mg"],
    "comorbidities": ["Type 2 Diabetes"],
    "blood_type": "A+",
    "emergency_contact_name": "Maria Silva",
    "emergency_contact_phone": "+5511987654321"
  }
}
```

### Full Nested Structure (Internal Use)

```json
{
  "patient_id": "123e4567-e89b-12d3-a456-426614174000",
  "patient_data": {
    "medical_history": {
      "allergies": ["Penicillin"],
      "medications": ["Metformin 500mg"],
      "conditions": ["Type 2 Diabetes"]
    },
    "blood_type": "A+",
    "emergency_contact": {
      "name": "Maria Silva",
      "phone": "+5511987654321"
    }
  }
}
```

---

## Database Queries

### Query Patients with Specific Allergies

```sql
-- Find patients allergic to Penicillin
SELECT id, name, phone
FROM patients
WHERE patient_data->'medical_history'->'allergies' ? 'Penicillin';
```

### Query by Blood Type

```sql
-- Find all A+ patients
SELECT id, name
FROM patients
WHERE patient_data->>'blood_type' = 'A+';
```

### Query Patients with Emergency Contacts

```sql
-- Find patients with emergency contact defined
SELECT id, name,
       patient_data->'emergency_contact'->>'name' as emergency_contact_name
FROM patients
WHERE patient_data->'emergency_contact' IS NOT NULL;
```

---

## Migration from Legacy Fields

If you have legacy data stored in different formats, here's how to migrate:

```python
# Example: Migrate from flat allergies field to nested structure
from app.utils.patient_metadata_schema import merge_clinical_metadata

def migrate_patient_allergies(patient):
    """Migrate legacy allergies to new structure."""
    if hasattr(patient, 'allergies_legacy') and patient.allergies_legacy:
        # Convert legacy format
        clinical_updates = {
            "medical_history": {
                "allergies": patient.allergies_legacy.split(',')
            }
        }

        # Merge into metadata
        patient.patient_data = merge_clinical_metadata(
            existing=patient.patient_data,
            updates=clinical_updates
        )

        # Clear legacy field
        patient.allergies_legacy = None
```

---

## Testing

### Unit Tests

Run tests:
```bash
pytest tests/unit/test_patient_metadata_schema.py -v
```

### Example Test

```python
def test_clinical_metadata_validation():
    """Test clinical metadata validation."""
    metadata = {
        "medical_history": {
            "allergies": ["Penicillin"]
        },
        "blood_type": "A+"
    }

    validated = validate_clinical_metadata(metadata)
    assert validated == metadata
```

---

## Error Handling

### Common Validation Errors

1. **Invalid Blood Type**
   ```python
   metadata = {"blood_type": "Invalid"}
   # Raises: ValidationError with details about pattern mismatch
   ```

2. **Invalid Phone Format**
   ```python
   contact = {"name": "Maria", "phone": "11987654321"}  # Missing +
   # Raises: ValidationError about E.164 format
   ```

3. **Missing Required Emergency Contact Fields**
   ```python
   contact = {"name": "Maria"}  # Missing phone
   # Raises: ValidationError about missing required field
   ```

---

## Best Practices

1. **Always Validate Before Saving**
   ```python
   validate_clinical_metadata(metadata, strict=True)
   ```

2. **Use Merge Functions for Updates**
   ```python
   # Don't overwrite entire metadata
   patient.patient_data = merge_clinical_metadata(
       patient.patient_data,
       updates
   )
   ```

3. **Extract Summaries for APIs**
   ```python
   # Return flattened data to frontend
   return extract_clinical_summary(patient.patient_data)
   ```

4. **Handle None Gracefully**
   ```python
   # All functions handle None input
   summary = extract_clinical_summary(patient.patient_data or {})
   ```

---

## Related Documentation

- [JSONB Base Validation](/docs/reference/JSONB_VALIDATION.md)
- [Patient Model Reference](/docs/reference/PATIENT_MODEL.md)
- [V2 API Evolution Guide](/docs/guides/V2_API_EVOLUTION.md)

---

## Changelog

### Version 1.1.0 (Current)
- ✅ Added `blood_type` field
- ✅ Enhanced `emergency_contact` validation
- ✅ Added Pydantic schemas for clinical fields
- ✅ Added helper functions for API integration

### Version 1.0.0
- Initial schema with `medical_history` and `emergency_contact`
