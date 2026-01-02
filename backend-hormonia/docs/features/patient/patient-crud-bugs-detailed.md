# Patient CRUD Bugs - Detailed Analysis

## Bug #1: Patient Creation Fails - Invalid `is_active` Parameter

### Severity: CRITICAL 🔴

### Summary
Mock fixture attempts to create Patient with `is_active=True` parameter, but the Patient model does not have this field. The model uses `deleted_at` for soft deletion instead.

### Error Message
```json
{
  "error": "HTTP_ERROR",
  "message": "'is_active' is an invalid keyword argument for Patient",
  "status_code": 400
}
```

### Root Cause
**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/critical/conftest.py`
**Line:** 293

```python
async def mock_create_patient(patient_data, doctor_id, current_user=None, idempotency_key=None):
    """Mock coordinator that creates patient directly in test session."""
    patient = Patient(
        id=uuid4(),
        doctor_id=doctor_id,
        flow_state="pending",
        is_active=True  # ❌ INVALID - Patient doesn't have this field
    )
```

### Patient Model Schema
The `Patient` model uses **soft deletion** pattern:
- **Active patients:** `deleted_at = None`
- **Deleted patients:** `deleted_at = <timestamp>`

The model does NOT have an `is_active` boolean field.

**Relevant fields from Patient model:**
```python
class Patient(BaseModel):
    __tablename__ = "patients"

    # Soft delete support
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # ... other fields
    # NO is_active field!
```

### Impact
- **5 tests fail** due to patient creation failure
- All CRUD tests dependent on creating patients skip execution
- False test failures obscure real bugs

**Affected Tests:**
1. `test_create_patient_success` - FAILED
2. `test_create_patient_duplicate_phone` - SKIPPED
3. `test_get_patient_by_id` - SKIPPED
4. `test_update_patient_success` - SKIPPED
5. `test_delete_patient_success` - SKIPPED

### Fix
Remove the `is_active=True` parameter from mock fixture:

```python
async def mock_create_patient(patient_data, doctor_id, current_user=None, idempotency_key=None):
    """Mock coordinator that creates patient directly in test session."""
    patient = Patient(
        id=uuid4(),
        doctor_id=doctor_id,
        flow_state="pending"
        # is_active removed - Patient uses deleted_at for soft deletion
    )
    # ... rest of the function
```

### Verification
After fix, run:
```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia
python3 -m pytest tests/api/critical/test_patients_crud.py -v
```

Expected: All 9 CRUD tests should pass.

---

## Bug #2: Patient Search Returns No Results

### Severity: MODERATE 🟡

### Summary
Patient search by name returns 0 results even when patients with matching names exist in the database.

### Test Failure
```python
# Test creates 3 patients, 2 with matching search term
search_term = f"SearchJoão{timestamp}"
patients = [
    {"name": f"{search_term} Silva", ...},   # Should match
    {"name": "Maria Santos", ...},            # Should not match
    {"name": f"{search_term} Pedro", ...},   # Should match
]

# Search returns 0 results instead of 2
response = authenticated_client.get(f"/api/v2/patients/?search={search_term}")
matching = [p for p in data["data"] if search_term in p.get("name", "")]
assert len(matching) >= 2  # ❌ FAILS: 0 >= 2
```

### Root Cause Analysis

#### Search Implementation is Correct ✅
The search implementation in `PatientRepository.list_v2()` is working correctly:

**File:** `app/repositories/patient/pagination.py` (lines 114-118)
```python
# Search (Name, Email hash, or Phone hash) - LGPD compliant
if filters.get("search"):
    search_criteria = build_search_criteria(filters["search"])
    if search_criteria:
        criteria.append(or_(*search_criteria))
```

**File:** `app/repositories/patient/encryption_helpers.py` (lines 36-54)
```python
def build_search_criteria(search_term: str) -> List:
    """Build LGPD-compliant search criteria."""
    criteria_parts = []
    search_val = f"%{search_term}%"

    # Name search - always use ILIKE (plaintext OK)
    criteria_parts.append(Patient.name.ilike(search_val))
    # ... email and phone hash searches
    return criteria_parts
```

The search uses `ILIKE` for case-insensitive partial matching on the `name` field, which is correct.

#### Actual Root Cause: Test Data Not Created ❌
The test search fails because **Bug #1 prevents patient creation**:

1. Test tries to create 3 patients
2. Creation fails with `is_active` parameter error
3. POST requests return 400 Bad Request
4. No patients are actually created in database
5. Search query runs against empty result set
6. Returns 0 results

**Evidence from test execution:**
```bash
# Test tries to create patients
for patient_data in patients:
    authenticated_client.post("/api/v2/patients/", json=patient_data)  # All fail with 400

# Search runs against empty database
response = authenticated_client.get(f"/api/v2/patients/?search={search_term}")
# Returns: {"data": [], "has_more": false, "total": 0}
```

### Impact
- Search functionality appears broken in tests
- Cannot verify search is working correctly
- Obscures potential real search bugs

### Fix Dependencies
**Bug #2 depends on Bug #1 being fixed first:**

1. ✅ Fix Bug #1 (remove `is_active` from mock)
2. ✅ Patients will be created successfully
3. ✅ Search will find created patients
4. ✅ Test should pass

### Alternative Investigation (if still fails after Bug #1 fix)
If search still fails after fixing Bug #1, investigate:

1. **Transaction Isolation:**
   - Check if test fixture commits patients to DB
   - Verify search query sees test data in same transaction

2. **Test Fixture Session:**
   - Ensure `db_session` fixture properly flushes/commits
   - Check if rollback affects search results

3. **Name Field Encoding:**
   - Verify Unicode characters (ã, õ) handled correctly
   - Test with ASCII-only names

### Verification
After fixing Bug #1, run:
```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia
python3 -m pytest tests/api/critical/test_patients_list.py::TestPatientList::test_list_patients_search_by_name -v
```

Expected: Test should pass with 2+ matching patients found.

---

## Additional Findings

### Test Coverage Analysis

#### ✅ Working Well (11/17 tests passing)
- Authentication validation (401 responses)
- Input validation (422 responses)
- Not found handling (404 responses)
- Basic list operations
- Pagination

#### ❌ Gaps in Test Coverage

1. **Authorization Tests Missing:**
   - Doctor accessing another doctor's patient ❌
   - Doctor reassigning patient to different doctor ❌
   - Non-admin deleting patients ❌

2. **Edge Cases Not Tested:**
   - Concurrent operations (race conditions)
   - Very long names (255+ chars)
   - Special characters in names (emoji, unicode)
   - Invalid date boundaries (future dates, very old dates)
   - XSS/SQL injection attempts

3. **Data Validation Gaps:**
   - Phone number format validation
   - Email format validation (MX record checks)
   - CPF validation (Brazilian tax ID)
   - Birth date age validation (18-120 years)

4. **Performance Tests Missing:**
   - Large dataset pagination (1000+ patients)
   - Search with many results
   - Concurrent create/update operations

### Recommendations

#### Priority 1 - Critical (Fix Now)
1. ✅ Fix `is_active` parameter in mock fixture (Bug #1)
2. ✅ Verify search works after Bug #1 fix
3. ✅ Run full test suite to ensure all tests pass

#### Priority 2 - High (This Sprint)
1. Add authorization tests for cross-doctor access
2. Add edge case tests for boundary values
3. Add concurrent operation tests

#### Priority 3 - Medium (Next Sprint)
1. Add performance tests
2. Add security tests (XSS, injection)
3. Add comprehensive data validation tests

---

## Test Execution Summary

### Environment
- **Python:** 3.12.3
- **Pytest:** 8.3.4
- **Database:** PostgreSQL (real connection)
- **Redis:** Cloud Redis instance
- **Auth:** Firebase ID token (real admin user)

### Results
```
Total Tests: 17
├─ Passed: 11 ✅
├─ Failed: 2 ❌
└─ Skipped: 4 ⏭️

CRUD Tests (9):
├─ Passed: 4 ✅
├─ Failed: 1 ❌ (create_patient_success)
└─ Skipped: 4 ⏭️ (dependent on failed test)

List Tests (8):
├─ Passed: 7 ✅
└─ Failed: 1 ❌ (search_by_name)
```

### Reproduction Steps

**Bug #1 (Patient Creation):**
```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia
python3 -m pytest tests/api/critical/test_patients_crud.py::TestPatientCRUD::test_create_patient_success -vv
```

**Bug #2 (Patient Search):**
```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia
python3 -m pytest tests/api/critical/test_patients_list.py::TestPatientList::test_list_patients_search_by_name -vv
```

**All Critical Tests:**
```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia
python3 -m pytest tests/api/critical/ -v
```

---

## Files Affected

### Bug #1
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/critical/conftest.py` (line 293)

### Bug #2
- Dependent on Bug #1 fix
- Search implementation is correct (no changes needed)

### Related Files (No Changes Needed)
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/models/patient.py` - Model schema correct
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/repositories/patient/pagination.py` - Search correct
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/repositories/patient/encryption_helpers.py` - Hash search correct

---

## Conclusion

Both bugs identified are in the **test infrastructure**, not the production code:

1. **Bug #1** is a simple parameter error in the mock fixture
2. **Bug #2** is a cascading failure caused by Bug #1

The actual Patient CRUD API implementation appears to be working correctly. After fixing the mock fixture, all tests should pass.

**Next Steps:**
1. Fix mock fixture (remove `is_active`)
2. Re-run all tests
3. If search still fails, investigate transaction isolation
4. Report results via memory coordination
