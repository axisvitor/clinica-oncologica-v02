# Patient CRUD Test Results - Debug Report

**Test Execution Date:** 2025-12-23
**Test Suite:** tests/api/critical/test_patients_crud.py, test_patients_list.py
**Total Tests:** 17
**Passed:** 11
**Failed:** 2
**Skipped:** 4 (dependent on failed tests)

## Executive Summary

Two critical bugs identified in patient CRUD operations:

1. **BUG #1 (CRITICAL):** Patient creation fails with invalid keyword argument `is_active`
2. **BUG #2 (MODERATE):** Patient search by name returns no results (search not working)

## Detailed Test Results

### ✅ PASSING TESTS (11/17)

#### CRUD Operations
- `test_create_patient_missing_required_fields` ✅ - Correctly rejects incomplete data (422)
- `test_get_patient_not_found` ✅ - Correctly returns 404 for non-existent patient
- `test_delete_patient_not_found` ✅ - Correctly returns 404 when deleting non-existent patient
- `test_crud_requires_authentication` ✅ - All endpoints correctly require auth (401)

#### List Operations
- `test_list_patients_empty_or_existing` ✅ - Successfully lists patients
- `test_list_patients_with_data` ✅ - Successfully returns patient list
- `test_list_patients_pagination` ✅ - Cursor pagination works correctly
- `test_list_patients_filter_by_treatment` ✅ - Filter endpoints don't error
- `test_list_patients_sort_by_name` ✅ - Sort endpoints don't error
- `test_list_patients_invalid_pagination_params` ✅ - Correctly rejects invalid params (400/422)
- `test_list_patients_requires_authentication` ✅ - Correctly requires auth (401)

### ❌ FAILING TESTS (2/17)

#### BUG #1: Patient Creation Failure

**Test:** `test_create_patient_success`
**Status:** FAILED ❌
**Expected:** 201 Created
**Actual:** 400 Bad Request

**Error Message:**
```
{"error":"HTTP_ERROR","message":"'is_active' is an invalid keyword argument for Patient","status_code":400}
```

**Root Cause:**
The mock fixture in `conftest.py` (line 293) attempts to create a Patient with `is_active=True`:

```python
patient = Patient(
    id=uuid4(),
    doctor_id=doctor_id,
    flow_state="pending",
    is_active=True  # ❌ INVALID - Patient model doesn't have is_active column
)
```

**Patient Model Schema:**
- The `Patient` model does NOT have an `is_active` field
- It uses `deleted_at` for soft deletion (nullable DateTime)
- Active patients have `deleted_at=None`, deleted have a timestamp

**Impact:**
- **CRITICAL** - All patient creation tests fail
- Blocks 4 dependent tests (duplicate check, get by ID, update, delete)
- Production patient creation likely working (uses real coordinator, not mock)

**Fix Required:**
```python
# Remove is_active parameter from mock_create_patient in conftest.py
patient = Patient(
    id=uuid4(),
    doctor_id=doctor_id,
    flow_state="pending"
    # is_active removed
)
```

**Files Affected:**
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/critical/conftest.py` (line 293)

---

#### BUG #2: Patient Search Not Working

**Test:** `test_list_patients_search_by_name`
**Status:** FAILED ❌
**Expected:** At least 2 patients matching search term
**Actual:** 0 patients found

**Error Message:**
```python
assert 0 >= 2  # Expected 2+ matching patients, got 0
```

**Test Scenario:**
1. Creates 3 patients with names containing unique search term `SearchJoão{timestamp}`
2. Searches for patients using `/api/v2/patients/?search={term}`
3. Expected to find 2 patients with matching names
4. Found 0 patients

**Possible Root Causes:**

1. **Search not implemented:** Repository `list_v2()` may not handle `search` parameter
2. **Name field encryption:** If `name` is encrypted, search might not work without decryption
3. **Test data not persisted:** Mock fixture may not properly persist patients
4. **Transaction isolation:** Test transaction rollback may affect search

**Impact:**
- **MODERATE** - Search functionality broken
- Users cannot find patients by name
- Affects UX and productivity

**Investigation Needed:**
1. Check `PatientRepository.list_v2()` implementation for search handling
2. Verify if `name` field is encrypted (schema shows it's plaintext)
3. Check if test patients are actually persisted to DB
4. Review transaction isolation in test fixtures

**Files to Review:**
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/repositories/patient/base.py` (search implementation)
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/critical/test_patients_list.py` (line 74-95)

### ⏭️ SKIPPED TESTS (4/17)

**Reason:** Dependent on `test_create_patient_success` which fails

1. `test_create_patient_duplicate_phone` - Skipped (needs patient creation)
2. `test_get_patient_by_id` - Skipped (needs patient creation)
3. `test_update_patient_success` - Skipped (needs patient creation)
4. `test_delete_patient_success` - Skipped (needs patient creation)

## Test Coverage Analysis

### Coverage Gaps Identified

1. **Edge Cases Not Tested:**
   - Concurrent patient creation with same phone/email
   - Very long names (255+ chars)
   - Special characters in name (emoji, unicode)
   - Invalid UUID formats in path parameters
   - Boundary dates (very old/future birth dates)
   - XSS attempts in text fields

2. **Missing Authorization Tests:**
   - Doctor trying to access another doctor's patient
   - Doctor trying to update patient's doctor_id to another doctor
   - Doctor trying to delete another doctor's patient

3. **Missing Data Validation Tests:**
   - Invalid phone number formats
   - Invalid email formats
   - CPF validation (Brazilian tax ID)
   - Date validation (birth_date, treatment_start_date)

4. **Missing Performance Tests:**
   - Large dataset pagination (1000+ patients)
   - Search performance with many results
   - Concurrent read/write operations

## Recommendations

### Priority 1 (Critical - Fix Immediately)
1. ✅ Fix `is_active` parameter in mock fixture
2. 🔍 Investigate and fix patient search functionality
3. ✅ Verify all tests pass after fixes

### Priority 2 (High - Fix This Sprint)
1. Add authorization tests for cross-doctor access
2. Add data validation tests for phone/email/CPF
3. Add edge case tests for boundary values

### Priority 3 (Medium - Next Sprint)
1. Add performance tests for pagination
2. Add concurrency tests
3. Add XSS/injection security tests

## Reproduction Steps

### Bug #1: Patient Creation
```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia
python3 -m pytest tests/api/critical/test_patients_crud.py::TestPatientCRUD::test_create_patient_success -vv
```

### Bug #2: Patient Search
```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia
python3 -m pytest tests/api/critical/test_patients_list.py::TestPatientList::test_list_patients_search_by_name -vv
```

## Test Environment

- **Python:** 3.12.3
- **Pytest:** 8.3.4
- **Database:** PostgreSQL (real DB connection)
- **Redis:** Cloud Redis instance
- **Authentication:** Firebase ID token (real admin user)

## Next Steps

1. Fix mock fixture `is_active` parameter ✅
2. Debug patient search implementation 🔍
3. Re-run all tests to verify fixes ✅
4. Add missing test coverage 📋
5. Document findings in memory for coordination 💾
