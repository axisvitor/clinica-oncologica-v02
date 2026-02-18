# Patient V2 Schema - Clinical Fields Update

## Summary

Added missing clinical fields to patient v2 schemas (`backend-hormonia/app/schemas/v2/patient.py`) to align with v1 schema and database model capabilities.

## Changes Made

### New Fields Added

All fields added to the following schemas: `PatientV2Base`, `PatientV2Create`, `PatientV2Update`, and `PatientV2Response`

#### 1. **allergies**: `Optional[str]`
- Description: Known allergies (medications, foods)
- Validation: None (free-text field)
- Example: "Penicilina, Dipirona"

#### 2. **medications**: `Optional[str]`
- Description: Current medications
- Validation: None (free-text field)
- Example: "Levotiroxina 100mcg, Metformina 500mg"

#### 3. **blood_type**: `Optional[str]`
- Description: Blood type
- Validation: Pattern `^(A|B|AB|O)[+-]$`
- Valid values: A+, A-, B+, B-, AB+, AB-, O+, O-
- Normalization: Automatically converts to uppercase (e.g., "a+" → "A+")
- Example: "A+", "O-", "AB+"

#### 4. **emergency_contact**: `Optional[str]`
- Description: Emergency contact information
- Validation: Max length 200 characters
- Example: "Maria Silva - (11) 99999-9999"

#### 5. **patient_data**: `Optional[Dict[str, Any]]`
- Description: Additional patient metadata (JSONB field)
- Validation: None (accepts any valid JSON structure)
- Purpose: Store dynamic/custom patient information not covered by dedicated fields
- Example: `{"insurance": "Unimed", "preferred_contact": "whatsapp"}`

### Validators Added

#### Blood Type Normalization
```python
@field_validator("blood_type", mode="before")
@classmethod
def normalize_blood_type(cls, v):
    """Normalize blood type to uppercase."""
    if isinstance(v, str):
        return v.strip().upper()
    return v
```

Added to:
- `PatientV2Base`
- `PatientV2Update`

## Schema Structure

### PatientV2Base
Base schema with all clinical fields - used as foundation for other schemas.

### PatientV2Create
Inherits all fields from `PatientV2Base`. Required fields:
- `name`
- `phone`
- `doctor_id`

All clinical fields are optional.

### PatientV2Update
All fields are optional, including clinical fields. Allows partial updates.

### PatientV2Response
Inherits from `PatientV2Base` with additional response fields:
- `id`
- `doctor_id`
- `created_at`
- `updated_at`
- `current_day`
- `flow_state`
- `doctor` (optional relationship)
- `quiz_sessions` (optional relationship)

## Examples Updated

Updated schema examples in all classes to demonstrate the new clinical fields:

### PatientV2Create Example
```json
{
  "name": "João Silva",
  "email": "joao@example.com",
  "phone": "(11) 98765-4321",
  "birth_date": "1980-05-15T00:00:00-03:00",
  "cpf": "123.456.789-00",
  "treatment_type": "Reposição Hormonal",
  "treatment_start_date": "2025-01-10",
  "doctor_notes": "Paciente apresentou boa resposta ao tratamento.",
  "doctor_id": "123e4567-e89b-12d3-a456-426614174000",
  "allergies": "Penicilina, Dipirona",
  "medications": "Levotiroxina 100mcg",
  "blood_type": "A+",
  "emergency_contact": "Maria Silva - (11) 99999-9999",
  "patient_data": {"insurance": "Unimed", "preferred_contact": "whatsapp"}
}
```

## Testing

Created comprehensive test suite: `tests/schemas/test_patient_v2_clinical_fields.py`

### Test Coverage (11 tests, all passing ✅)

1. ✅ **test_patient_v2_base_with_clinical_fields** - Validates all clinical fields accepted
2. ✅ **test_blood_type_validation_valid_types** - Tests all valid blood types
3. ✅ **test_blood_type_validation_lowercase_normalization** - Tests uppercase conversion
4. ✅ **test_blood_type_validation_invalid_type** - Tests rejection of invalid patterns
5. ✅ **test_patient_v2_create_with_clinical_fields** - Tests creation with clinical fields
6. ✅ **test_patient_v2_update_with_clinical_fields** - Tests update with clinical fields
7. ✅ **test_clinical_fields_optional** - Validates all fields are optional
8. ✅ **test_empty_string_allergies** - Tests empty string handling
9. ✅ **test_patient_data_jsonb_accepts_complex_structure** - Tests complex JSON structures
10. ✅ **test_emergency_contact_max_length** - Tests max_length validation
11. ✅ **test_patient_v2_response_includes_clinical_fields** - Tests response schema

### Running Tests
```bash
cd backend-hormonia
python3 -m pytest tests/schemas/test_patient_v2_clinical_fields.py -v
```

## Database Compatibility

These schema fields map to the existing database model (`app/models/patient.py`):

- **allergies**, **medications**, **emergency_contact**: Can be stored in `patient_data` JSONB column
- **blood_type**: Can be stored in `patient_data` JSONB column
- **patient_data**: Direct mapping to `metadata` column in database (attribute name: `patient_data`)

Note: The v1 schema stores some fields differently (e.g., `emergency_contact_name` and `emergency_contact_phone` as separate fields). The v2 schema consolidates these into a single `emergency_contact` field for simplicity.

## Migration Considerations

No database migration is required for these changes because:

1. All new fields are optional
2. Fields can be stored in existing `metadata` JSONB column
3. Backward compatible with existing data

## API Impact

These fields are now available in the following v2 API endpoints:

- `POST /api/v2/patients` - Create patient with clinical fields
- `GET /api/v2/patients/{id}` - Retrieve patient with clinical fields
- `PATCH /api/v2/patients/{id}` - Update patient clinical fields
- `GET /api/v2/patients` - List patients with clinical fields

## Field Mapping: V1 vs V2

| V1 Schema | V2 Schema | Notes |
|-----------|-----------|-------|
| `allergies: list[str]` | `allergies: str` | Changed from list to string for simplicity |
| `current_medications: list[str]` | `medications: str` | Renamed and changed from list to string |
| `blood_type: str` | `blood_type: str` | Same pattern validation |
| `emergency_contact_name: str` + `emergency_contact_phone: str` | `emergency_contact: str` | Consolidated into single field |
| `metadata: Dict[str, Any]` | `patient_data: Dict[str, Any]` | Same functionality, clearer name |

## Validation Rules

| Field | Required | Max Length | Pattern | Normalization |
|-------|----------|------------|---------|---------------|
| allergies | No | - | - | - |
| medications | No | - | - | - |
| blood_type | No | - | `^(A\|B\|AB\|O)[+-]$` | Uppercase |
| emergency_contact | No | 200 | - | - |
| patient_data | No | - | Valid JSON | - |

## Files Modified

1. `/backend-hormonia/app/schemas/v2/patient.py`
   - Added import: `Dict, Any` from typing
   - Updated `PatientV2Base` with 5 new fields
   - Updated `PatientV2Create` examples
   - Updated `PatientV2Update` with 5 new fields and examples
   - Updated `PatientV2Response` examples
   - Added `blood_type` validator to `PatientV2Base` and `PatientV2Update`

2. `/backend-hormonia/tests/schemas/test_patient_v2_clinical_fields.py` (NEW)
   - Comprehensive test suite with 11 tests
   - Validates all new fields and their constraints

## Verification

All tests passing:
```
✅ 11 passed in 0.43s
```

Schema syntax validated:
```bash
python3 -m py_compile app/schemas/v2/patient.py  # ✅ No errors
```

## Next Steps (Optional)

1. Update API documentation to reflect new fields
2. Add API integration tests for clinical fields endpoints
3. Consider creating migration to add dedicated database columns for frequently-used clinical fields (if performance becomes a concern)
4. Update frontend forms to include new clinical fields

## Compatibility

- ✅ Backward compatible (all fields optional)
- ✅ No breaking changes
- ✅ Works with existing database schema
- ✅ Maintains v1 schema compatibility where possible

---

**Date**: 2025-12-23
**Developer**: Claude Code (Coder Agent)
**Test Status**: All tests passing (11/11) ✅
