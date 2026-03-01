# Quick Fix Checklist - Immediate Actions
**Priority**: P0 Critical Issues
**Estimated Time**: 50 minutes
**Goal**: Get all critical tests passing

---

## ✅ Fix 1: Patient Creation Tests (15 minutes)

### Issue
- **Test File**: `tests/api/critical/test_patients_crud.py`
- **Error**: 422 Unprocessable Entity
- **Root Cause**: Missing `email` and `birth_date` in payload

### Fix Steps

1. **Locate test file**:
```bash
cd backend-hormonia
code tests/api/critical/test_patients_crud.py
```

2. **Find test payloads** (search for `test_create_patient`):
```python
# BEFORE (broken)
payload = {
    "name": "Test Patient",
    "cpf": "12345678901",
    "phone": "11999999999"
}
```

3. **Update payload** with required fields:
```python
# AFTER (fixed)
payload = {
    "name": "Test Patient",
    "cpf": "12345678901",
    "email": "test@example.com",      # ADD THIS
    "birth_date": "1990-01-01",        # ADD THIS
    "phone": "11999999999"
}
```

4. **Find ALL occurrences** - Update every test payload in the file

5. **Verify fix**:
```bash
python3 -m pytest tests/api/critical/test_patients_crud.py -v
```

### Expected Result
```
tests/api/critical/test_patients_crud.py::test_create_patient PASSED
tests/api/critical/test_patients_crud.py::test_list_patients PASSED
tests/api/critical/test_patients_crud.py::test_update_patient PASSED
tests/api/critical/test_patients_crud.py::test_delete_patient PASSED
```

---

## ✅ Fix 2: Quiz Endpoint Tests (30 minutes)

### Issue
- **Test File**: `tests/api/critical/test_quiz_session.py`
- **Error**: 405 Method Not Allowed
- **Root Cause**: Missing POST handler or incorrect endpoint

### Investigation Steps

1. **Check current router**:
```bash
cd backend-hormonia
grep -r "quiz.*session" app/api/v2/routers/ -A 5
```

2. **Verify endpoint registration** in `app/api/v2/routers/quiz_sessions.py`:
```python
# Should have POST endpoint
@router.post("/", response_model=QuizSessionResponse)
async def create_quiz_session(
    quiz_data: QuizSessionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Implementation
```

3. **Check router registration** in `app/core/router_registry.py`:
```python
# Should include quiz_sessions router
app.include_router(
    quiz_sessions_router,
    prefix="/api/v2/quiz-sessions",  # Verify this path
    tags=["quiz-sessions"]
)
```

### Fix Options

**Option A**: Add missing POST handler (if not found)
```python
# In app/api/v2/routers/quiz_sessions.py
from app.schemas.v2.quiz import QuizSessionCreate, QuizSessionResponse

@router.post("/", response_model=QuizSessionResponse)
async def create_quiz_session(
    quiz_data: QuizSessionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new quiz session"""
    session = await quiz_service.create_session(
        db=db,
        patient_id=current_user.id,
        quiz_data=quiz_data
    )
    return session
```

**Option B**: Fix test endpoint path (if POST exists but path is wrong)
```python
# In tests/api/critical/test_quiz_session.py
# Update endpoint path to match router
response = client.post(
    "/api/v2/quiz-sessions",  # Verify correct path
    json=payload,
    headers=headers
)
```

### Verify Fix
```bash
python3 -m pytest tests/api/critical/test_quiz_session.py -v
```

### Expected Result
```
tests/api/critical/test_quiz_session.py::test_create_session PASSED
tests/api/critical/test_quiz_session.py::test_submit_answer PASSED
tests/api/critical/test_quiz_session.py::test_complete_session PASSED
```

---

## ✅ Fix 3: Integration Test Imports (5 minutes)

### Issue
- **File**: `tests/integration/conftest.py`
- **Error**: `ImportError: cannot import name 'get_db' from 'app.core.database_config'`
- **Root Cause**: Database refactoring moved `get_db` function

### Fix Steps

1. **Open file**:
```bash
cd backend-hormonia
code tests/integration/conftest.py
```

2. **Find broken import** (line ~10-15):
```python
# BEFORE (broken)
from app.core.database_config import get_db
```

3. **Update to correct path**:
```python
# AFTER (fixed)
from app.database import get_db
```

4. **Check for other occurrences**:
```bash
grep -r "from app.core.database_config import get_db" tests/
```

5. **Update ALL files** with the broken import

### Verify Fix
```bash
python3 -m pytest tests/integration/ --collect-only
# Should collect ~50+ tests without errors
```

---

## 🧪 Final Verification

### Run Full Critical Test Suite
```bash
cd backend-hormonia
python3 -m pytest tests/api/critical/ -v
```

### Expected Output
```
tests/api/critical/test_patients_crud.py::test_create_patient PASSED
tests/api/critical/test_patients_crud.py::test_list_patients PASSED
tests/api/critical/test_patients_crud.py::test_update_patient PASSED
tests/api/critical/test_patients_crud.py::test_delete_patient PASSED
tests/api/critical/test_patients_crud.py::test_patient_validation PASSED

tests/api/critical/test_patients_list.py::test_list_with_filters PASSED
tests/api/critical/test_patients_list.py::test_pagination PASSED
tests/api/critical/test_patients_list.py::test_search PASSED

tests/api/critical/test_quiz_session.py::test_create_session PASSED
tests/api/critical/test_quiz_session.py::test_submit_answer PASSED
tests/api/critical/test_quiz_session.py::test_complete_session PASSED

tests/api/critical/test_quiz_submit.py::test_submit_validation PASSED
tests/api/critical/test_quiz_submit.py::test_submit_scoring PASSED

========================= 31 passed in 15.23s =========================
```

---

## ✅ Completion Checklist

- [ ] Fix 1: Patient creation tests updated and passing
- [ ] Fix 2: Quiz endpoint tests verified and passing
- [ ] Fix 3: Integration test imports corrected
- [ ] Full critical test suite runs without errors (31/31 passing)
- [ ] Changes committed to git

### Commit Changes
```bash
git add tests/api/critical/test_patients_crud.py
git add tests/api/critical/test_quiz_session.py  # If modified
git add tests/integration/conftest.py
git add app/api/v2/routers/quiz_sessions.py  # If modified

git commit -m "fix(tests): resolve critical test failures

- Add required email and birth_date fields to patient test payloads
- Fix quiz session endpoint routing and POST handler
- Update integration test imports after database refactoring

Fixes 5 failing critical tests, all 31 tests now passing."
```

---

## 🎯 Success Criteria

After completing these fixes:
- ✅ All 31 critical tests passing
- ✅ Integration tests can be collected and run
- ✅ No import errors in test suite
- ✅ Ready to proceed with P0 performance fixes

**Next Steps**: Proceed to `PERFORMANCE_QUICK_FIXES.md` for startup optimization
