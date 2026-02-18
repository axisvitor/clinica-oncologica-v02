# Integration Tests - Quick Start Guide

## 🚀 One-Command Setup

```bash
# 1. Create test database
createdb hormonia_test

# 2. Set environment variable
export DATABASE_URL="postgresql://user:password@localhost/hormonia_test"

# 3. Run migrations
alembic upgrade head

# 4. Run integration tests
pytest -m integration
```

## 📋 Essential Commands

### Run Tests

```bash
# Run all integration tests
pytest -m integration

# Run with verbose output
pytest -m integration -v

# Run specific test file
pytest -m integration tests/integration/test_patient_saga.py

# Run specific test method
pytest -m integration tests/integration/test_patient_saga.py::TestPatientOnboardingSaga::test_complete_patient_registration_saga
```

### Skip Integration Tests

```bash
# Default (integration tests skipped)
pytest

# Explicit skip
pytest -m "not integration"
```

## 🛡️ Safety Checklist

- [ ] DATABASE_URL contains "test" (or CONFIRM_REAL_DB=1) ✅
- [ ] Using separate test database (recommended) ✅
- [ ] Migrations applied ✅
- [ ] Cleanup fixtures used ✅
- [ ] Unique identifiers used ✅

## 📝 Test Template

```python
import pytest
from sqlalchemy.orm import Session

@pytest.mark.integration
def test_my_feature(
    real_db_session: Session,
    cleanup_patients,
    unique_phone_number,
):
    """Test description."""
    # Create
    patient = create_patient(phone=unique_phone_number)
    cleanup_patients.track(patient.id)  # REQUIRED!

    # Execute
    result = do_something(patient)

    # Verify
    assert result.success == True
```

## 🔧 Available Fixtures

### Database
- `real_db_session` - Real database session
- `real_saga_orchestrator` - Real saga orchestrator

### Cleanup
- `cleanup_patients` - Auto-delete patients
- `cleanup_sagas` - Auto-delete sagas
- `cleanup_flows` - Auto-delete flows

### Data Generation
- `unique_phone_number` - Unique phone
- `unique_email` - Unique email
- `sample_patient_data` - Complete patient data

## ⚠️ Common Mistakes

### ❌ Wrong
```python
def test_something(real_db_session):
    patient = Patient(phone="+5511999999999")  # Fixed phone!
    # No cleanup tracking!
```

### ✅ Correct
```python
def test_something(real_db_session, cleanup_patients, unique_phone_number):
    patient = Patient(phone=unique_phone_number)
    cleanup_patients.track(patient.id)  # Tracked!
```

## 🆘 Troubleshooting

### Problem: "DATABASE_URL not set"
```bash
export DATABASE_URL="postgresql://user:password@localhost/hormonia_test"
```

### Problem: "refusing to run on production"
```bash
# URL must contain "test" unless explicitly overridden
export DATABASE_URL="postgresql://user:password@localhost/hormonia_test"

# Explicitly allow running on a real database (use with caution)
# export CONFIRM_REAL_DB=1
```

### Problem: Orphaned test data
```python
from tests.integration.conftest import cleanup_all_test_data
cleanup_all_test_data(session)
```

## 📚 Full Documentation

See `/tests/integration/README.md` for complete documentation.

## ✅ Success Criteria

After setup, this should work:

```bash
pytest -m integration -v
# All tests pass
# No orphaned data
# All cleanup successful
```
