# Patient API V2 Evolution - Test Suite

## Quick Start

```bash
# Run all v2 evolution tests
pytest tests/api/v2/test_patient_clinical_fields.py tests/api/v2/test_patient_advanced_filters.py -v

# Run with coverage
pytest tests/api/v2/ --cov=app.api.v2.patients_crud --cov-report=html --cov-report=term
```

## Test Files

1. **`test_patient_clinical_fields.py`** - Clinical fields validation (20+ tests)
2. **`test_patient_advanced_filters.py`** - Advanced filtering & sorting (30+ tests)
3. **`TEST_SUITE_SUMMARY.md`** - Complete test documentation

## Coverage Targets

- Clinical fields: **95%+**
- Advanced filters: **90%+**
- Backward compatibility: **100%**
- Overall: **90%+**

## Key Features Tested

### Clinical Fields
- allergies, current_medications, comorbidities
- blood_type (A+, A-, B+, B-, AB+, AB-, O+, O-)
- emergency_contact_name, emergency_contact_phone

### Advanced Filters
- treatment_phase (initial, maintenance, followup)
- has_active_flow (true/false)
- created_after, created_before (ISO datetime)
- sort_by (name, email, created_at)
- sort_order (asc, desc)

## Critical Tests

✅ **Backward Compatibility** - Old clients work without new fields
✅ **Validation** - All invalid data rejected
✅ **RBAC** - Doctors can't access other doctors' patients
✅ **Data Integrity** - Emergency contact requires both name and phone

## See Also

- [TEST_SUITE_SUMMARY.md](./TEST_SUITE_SUMMARY.md) - Full test documentation
- [/backend-hormonia/docs/api/v2/](../../../docs/api/v2/) - API documentation
