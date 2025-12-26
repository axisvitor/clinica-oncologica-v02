# Integration Tests - Complete Index

## 📚 Documentation Files

### Getting Started
- **[QUICK_START.md](QUICK_START.md)** - One-page quick reference for running tests
- **[README.md](README.md)** - Complete documentation (8,000+ words)
- **[INTEGRATION_TEST_SETUP_SUMMARY.md](INTEGRATION_TEST_SETUP_SUMMARY.md)** - Setup completion summary

### Verification
- **[verify_setup.py](verify_setup.py)** - Automated setup verification script

## 🔧 Configuration Files

### Core Configuration
- **[conftest.py](conftest.py)** - Integration test fixtures and utilities (342 lines)
  - Real database connections
  - Cleanup fixtures
  - Unique identifier generators
  - Safety mechanisms

- **[__init__.py](__init__.py)** - Module initialization
- **[.gitignore](.gitignore)** - Git ignore rules for test artifacts

### Project Configuration
- **[../../pytest.ini](../../pytest.ini)** - Pytest configuration with integration marker

## 🧪 Test Files

### Patient Saga Tests
- **[test_patient_saga.py](test_patient_saga.py)** - Patient onboarding saga integration tests (385 lines)
  - `test_complete_patient_registration_saga` - Full saga flow
  - `test_saga_compensation_on_failure` - Failure handling
  - `test_multiple_concurrent_sagas` - Concurrent execution
  - `test_saga_idempotency` - Retry safety
  - `test_saga_timeout_handling` - Timeout detection

### Other Integration Tests
- **[test_saga_compensation.py](test_saga_compensation.py)** - Saga compensation patterns (421 lines)
- **[test_saga_concurrency.py](test_saga_concurrency.py)** - Concurrent saga execution (549 lines)
- **[test_circuit_breaker.py](test_circuit_breaker.py)** - Circuit breaker pattern (483 lines)
- **[test_error_handling_integration.py](test_error_handling_integration.py)** - Error handling (494 lines)
- **[test_patient_constraints.py](test_patient_constraints.py)** - Database constraints (321 lines)
- **[test_race_condition_protection.py](test_race_condition_protection.py)** - Race conditions (237 lines)
- **[test_race_condition_protection_real_db.py](test_race_condition_protection_real_db.py)** - Real DB race conditions (244 lines)
- **[test_quiz_debounce_integration.py](test_quiz_debounce_integration.py)** - Quiz debouncing (341 lines)
- **[test_security_fixes_integration.py](test_security_fixes_integration.py)** - Security tests (379 lines)
- **[test_webhook_hmac.py](test_webhook_hmac.py)** - Webhook HMAC validation (311 lines)
- **[test_phase1_integration.py](test_phase1_integration.py)** - Phase 1 integration (418 lines)
- **[test_v1_endpoints_disabled.py](test_v1_endpoints_disabled.py)** - V1 endpoint tests (28 lines)

**Total Test Code**: ~5,000 lines

## 🎯 Quick Commands Reference

### Setup
```bash
# 1. Create test database
createdb hormonia_test

# 2. Set environment
export DATABASE_URL="postgresql://user:password@localhost/hormonia_test"

# 3. Run migrations
alembic upgrade head

# 4. Verify setup
python tests/integration/verify_setup.py
```

### Running Tests
```bash
# All integration tests
pytest -m integration

# Verbose output
pytest -m integration -v

# Specific file
pytest -m integration tests/integration/test_patient_saga.py

# Specific test
pytest -m integration tests/integration/test_patient_saga.py::TestPatientOnboardingSaga::test_complete_patient_registration_saga

# Skip integration tests (default)
pytest -m "not integration"
```

### Debugging
```bash
# Show print statements
pytest -m integration -s

# Stop on first failure
pytest -m integration -x

# Show locals on failure
pytest -m integration -l

# Full traceback
pytest -m integration --tb=long
```

## 🛡️ Safety Features

### Database Protection
1. **URL validation**: Must contain "test"
2. **Automatic skip**: If DATABASE_URL not set
3. **NullPool**: No connection reuse
4. **Isolated tests**: Each test gets fresh session

### Cleanup System
1. **Automatic tracking**: `cleanup_patients.track(patient.id)`
2. **Cascade deletion**: Deletes related records first
3. **Transaction safety**: Rollback on errors
4. **Emergency cleanup**: `cleanup_all_test_data()`

### Test Isolation
1. **Unique identifiers**: Timestamp-based IDs
2. **No shared state**: Independent sessions
3. **Real commits**: No transaction rollback
4. **Idempotent tests**: Can run multiple times

## 📊 Available Fixtures

### Database Fixtures
```python
real_database_url        # Get DATABASE_URL with safety checks
real_engine             # SQLAlchemy engine (NullPool)
real_db_session         # Real session (commits changes)
real_saga_orchestrator  # Real saga orchestrator
```

### Cleanup Fixtures
```python
cleanup_patients  # Track and delete patients
cleanup_sagas     # Track and delete sagas
cleanup_flows     # Track and delete flows
```

### Data Generation
```python
unique_phone_number  # Timestamp-based unique phone
unique_email         # Timestamp-based unique email
sample_patient_data  # Complete patient data dict
```

### Utilities
```python
event_loop              # Async event loop
integration_test_marker # Integration marker flag
```

## 🔍 Test Markers

```python
@pytest.mark.integration  # Integration test (real DB)
@pytest.mark.unit         # Unit test
@pytest.mark.slow         # Slow running test
@pytest.mark.api          # API endpoint test
@pytest.mark.database     # Requires database
@pytest.mark.saga         # Saga pattern test
@pytest.mark.firebase     # Firebase required
@pytest.mark.e2e          # End-to-end test
```

## 📝 Test Template

```python
import pytest
from sqlalchemy.orm import Session

@pytest.mark.integration
class TestMyFeature:
    """Integration tests for My Feature."""

    def test_complete_workflow(
        self,
        real_db_session: Session,
        cleanup_patients,
        unique_phone_number,
    ):
        """
        Test complete workflow.

        Verifies:
        1. Data creation
        2. Workflow execution
        3. Final state
        """
        # Create test data
        patient = create_patient(phone=unique_phone_number)
        cleanup_patients.track(patient.id)

        # Execute workflow
        result = execute_workflow(patient)

        # Verify
        assert result.success == True
        real_db_session.refresh(patient)
        assert patient.workflow_complete == True
```

## 🆘 Troubleshooting Guide

### Common Issues

| Problem | Solution |
|---------|----------|
| "DATABASE_URL not set" | `export DATABASE_URL="postgresql://user:password@localhost/hormonia_test"` |
| "refusing to run on production" | URL must contain "test" |
| Unique constraint violations | Use `unique_phone_number` and `unique_email` fixtures |
| Foreign key errors during cleanup | Cleanup deletes in correct order automatically |
| Orphaned test data | Run `cleanup_all_test_data(session)` |
| Tests skip automatically | Use `-m integration` to run them |

### Debug Commands

```bash
# Check DATABASE_URL
echo $DATABASE_URL

# List all test markers
pytest --markers

# Collect tests without running
pytest -m integration --collect-only

# Show fixture details
pytest --fixtures

# Verify setup
python tests/integration/verify_setup.py
```

## 📈 Statistics

- **Total Test Files**: 14
- **Total Test Lines**: ~5,000
- **Documentation Lines**: ~1,000
- **Configuration Lines**: ~500
- **Total Lines**: ~6,500

### Test Coverage
- Patient saga flows: ✅
- Saga compensation: ✅
- Concurrent execution: ✅
- Circuit breakers: ✅
- Error handling: ✅
- Security: ✅
- Race conditions: ✅
- Database constraints: ✅

## 🎓 Learning Resources

### Internal Documentation
- [README.md](README.md) - Complete guide
- [QUICK_START.md](QUICK_START.md) - Quick reference
- [conftest.py](conftest.py) - Fixture documentation

### External Resources
- [Pytest Documentation](https://docs.pytest.org/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/14/core/connections.html#testing)
- [Saga Pattern](https://microservices.io/patterns/data/saga.html)
- [Integration Testing Best Practices](https://martinfowler.com/bliki/IntegrationTest.html)

## ✅ Checklist for New Tests

- [ ] Mark with `@pytest.mark.integration`
- [ ] Use `real_db_session` fixture
- [ ] Use cleanup fixtures (`cleanup_patients`, etc.)
- [ ] Use unique identifier fixtures
- [ ] Track all created records for cleanup
- [ ] Test complete workflows (not isolated functions)
- [ ] Document test purpose in docstring
- [ ] Verify database state after operations
- [ ] Handle async properly if needed
- [ ] Add meaningful assertions

## 🚀 Next Steps

1. **Run verification**: `python tests/integration/verify_setup.py`
2. **Run tests**: `pytest -m integration`
3. **Add more tests**: Follow the template
4. **Update documentation**: Keep README.md current
5. **Monitor cleanup**: Check for orphaned data

---

**Last Updated**: 2024-12-23
**Status**: ✅ Ready for use
**Total Files**: 20 (test files + documentation)
