# Clinical Fields Enhancement - Patient Schema v2

**Status**: ✅ COMPLETED
**Date**: 2025-11-16
**Priority**: Medium
**Backward Compatibility**: 100%

## Overview

Enhanced Patient schema (v2) with optional clinical fields to improve patient data management while maintaining 100% backward compatibility with existing data.

## Changes Summary

### New Clinical Fields in PatientBase

All fields are **optional** (backward compatible):

1. **allergies** (`Optional[list[str]]`)
   - Known allergies (medications, foods, etc.)
   - Example: `["Penicillin", "Peanuts"]`

2. **current_medications** (`Optional[list[str]]`)
   - Current medications patient is taking
   - Example: `["Aspirin 100mg", "Metformin 500mg"]`

3. **comorbidities** (`Optional[list[str]]`)
   - Existing health conditions
   - Example: `["Diabetes Type 2", "Hypertension"]`

4. **blood_type** (`Optional[str]`)
   - Pattern: `^(A|B|AB|O)[+-]$`
   - Valid values: A+, A-, B+, B-, AB+, AB-, O+, O-

5. **emergency_contact_name** (`Optional[str]`)
   - Max length: 200 characters
   - Emergency contact person name

6. **emergency_contact_phone** (`Optional[str]`)
   - Must start with country code (+)
   - Validated by `validate_emergency_phone` validator

### New Validators

1. **validate_email_format**
   - Validates email format using regex
   - Pattern: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
   - Only validates if email is provided

2. **validate_emergency_phone**
   - Ensures emergency contact phone starts with country code (+)
   - Only validates if phone is provided

## Files Modified

- `/backend-hormonia/app/schemas/patient.py`

## Schema Classes Updated

### PatientBase
- Added 6 clinical fields
- Added 2 new validators (email, emergency_phone)

### PatientCreate
- Inherits all new fields from PatientBase

### PatientUpdate
- Added all 6 clinical fields as optional
- Added email and emergency_phone validators

### PatientResponse
- Inherits all new fields from PatientBase
- Will return new fields in API responses

## Backward Compatibility

✅ **100% Backward Compatible**

- All new fields are `Optional`
- Existing API calls work without changes
- Existing data remains valid
- No migration required for existing records
- New fields return `null` if not set

## API Impact

### Request Examples

**Before (still works):**
```json
{
  "phone": "+5511999999999",
  "name": "Maria Silva",
  "email": "maria@example.com",
  "birth_date": "1980-05-15"
}
```

**After (enhanced):**
```json
{
  "phone": "+5511999999999",
  "name": "Maria Silva",
  "email": "maria@example.com",
  "birth_date": "1980-05-15",
  "allergies": ["Penicilina", "Latex"],
  "current_medications": ["Metformina 500mg", "Aspirina 100mg"],
  "comorbidities": ["Diabetes Tipo 2", "Hipertensão"],
  "blood_type": "A+",
  "emergency_contact_name": "João Silva",
  "emergency_contact_phone": "+5511888888888"
}
```

## Validation Rules

| Field | Validation | Error Message |
|-------|------------|---------------|
| email | Email format regex | "Invalid email format" |
| blood_type | Pattern: (A\|B\|AB\|O)[+-] | Pydantic validation error |
| emergency_contact_phone | Starts with + | "Emergency contact phone must start with country code (+)" |
| emergency_contact_name | Max 200 chars | Pydantic validation error |

## Testing Recommendations

### Unit Tests
1. Test all new fields with valid data
2. Test validators with invalid data
3. Test backward compatibility (requests without new fields)
4. Test blood_type pattern validation
5. Test emergency_phone validation
6. Test email validation

### Integration Tests
1. Create patient with all new fields
2. Create patient without new fields (backward compat)
3. Update patient with new fields
4. Retrieve patient and verify new fields in response
5. Test partial updates

## Database Considerations

**Note**: This schema update does NOT include database migration.

To persist these fields in the database, you will need to:

1. Create Alembic migration to add columns to `patients` table
2. Update SQLAlchemy model (`app/models/patient.py`)
3. Consider using JSONB field for list fields (allergies, medications, comorbidities)

## Next Steps

- [ ] Create database migration for new fields
- [ ] Update Patient model (`app/models/patient.py`)
- [ ] Write unit tests for validators
- [ ] Write integration tests for API endpoints
- [ ] Update API documentation (OpenAPI/Swagger)
- [ ] Update frontend to support new fields

## References

- Patient Schema: `/backend-hormonia/app/schemas/patient.py`
- Patient Model: `/backend-hormonia/app/models/patient.py`
- Patient API: `/backend-hormonia/app/api/v2/patients_crud.py`
