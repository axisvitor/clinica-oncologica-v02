# Integration Tests

This directory contains integration tests that use **real database connections, real saga patterns, and real Firebase authentication** without mocking.

## ⚠️ CRITICAL WARNINGS

1. **These tests commit REAL data to the database**
2. **Always use a TEST database, NEVER production**
3. **Database URL MUST contain 'test' in the name**
4. **Tests are SKIPPED by default in CI** (use `-m integration` to run)
5. **Cleanup fixtures delete data after each test**

## Prerequisites

### 1. Test Database Setup

Create a dedicated test database:

```sql
CREATE DATABASE hormonia_test;
```

### 2. Environment Configuration

Set the test database URL:

```bash
export DATABASE_URL="postgresql://user:password@localhost/hormonia_test"
```

**SAFETY CHECK**: The conftest.py will refuse to run if DATABASE_URL doesn't contain "test".

### 3. Run Migrations

Apply database schema to test database:

```bash
alembic upgrade head
```

## Running Integration Tests

### Run All Integration Tests

```bash
# Run only integration tests
pytest -m integration

# Run with verbose output
pytest -m integration -v

# Run specific test file
pytest -m integration tests/integration/test_patient_saga.py

# Run specific test
pytest -m integration tests/integration/test_patient_saga.py::TestPatientOnboardingSaga::test_complete_patient_registration_saga
```

### Skip Integration Tests (Default)

```bash
# Skip integration tests (default behavior)
pytest -m "not integration"

# Run only unit tests
pytest -m unit
```

### Run All Tests (Including Integration)

```bash
# Run everything
pytest --override-ini="addopts="
```

## Test Structure

### conftest.py

Provides fixtures for integration testing:

- `real_db_session`: Real database session that commits changes
- `cleanup_patients`: Tracks and deletes test patients
- `cleanup_sagas`: Tracks and deletes test sagas
- `cleanup_flows`: Tracks and deletes test flows
- `unique_phone_number`: Generates unique phone numbers
- `unique_email`: Generates unique emails
- `real_saga_orchestrator`: Real saga orchestrator instance
- `sample_patient_data`: Sample patient data with unique IDs

### test_patient_saga.py

Tests for patient onboarding saga:

1. **test_complete_patient_registration_saga**: Full saga flow from start to completion
2. **test_saga_compensation_on_failure**: Compensation mechanism on failures
3. **test_multiple_concurrent_sagas**: Multiple concurrent saga executions
4. **test_saga_idempotency**: Retry safety and idempotency
5. **test_saga_timeout_handling**: Timeout detection and handling

## Cleanup Mechanism

### Automatic Cleanup

Every test uses cleanup fixtures:

```python
def test_example(cleanup_patients, cleanup_sagas):
    # Create patient
    patient = create_patient(...)
    cleanup_patients.track(patient.id)  # Will be deleted after test

    # Create saga
    saga = create_saga(...)
    cleanup_sagas.track(saga.id)  # Will be deleted after test

    # Test logic...
```

### Manual Emergency Cleanup

If tests fail and leave orphaned data:

```python
from tests.integration.conftest import cleanup_all_test_data

# In Python REPL or script
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("postgresql://user:password@localhost/hormonia_test")
Session = sessionmaker(bind=engine)
session = Session()

cleanup_all_test_data(session)
```

## Best Practices

### 1. Always Use Cleanup Fixtures

```python
@pytest.mark.integration
def test_something(cleanup_patients):
    patient = create_patient()
    cleanup_patients.track(patient.id)  # REQUIRED
    # Test logic...
```

### 2. Use Unique Identifiers

```python
@pytest.mark.integration
def test_something(unique_phone_number, unique_email):
    patient_data = {
        "phone": unique_phone_number,  # Guaranteed unique
        "email": unique_email,  # Guaranteed unique
        ...
    }
```

### 3. Verify Database State

```python
@pytest.mark.integration
def test_something(real_db_session):
    # Create
    patient = Patient(...)
    real_db_session.add(patient)
    real_db_session.commit()

    # Verify
    real_db_session.refresh(patient)
    assert patient.id is not None
```

### 4. Test Complete Workflows

Integration tests should verify end-to-end flows, not individual functions:

```python
@pytest.mark.integration
def test_complete_workflow(real_db_session, real_saga_orchestrator):
    # 1. Create patient
    patient = create_patient()

    # 2. Initialize saga
    saga = initialize_saga(patient.id)

    # 3. Execute saga steps
    execute_saga_steps(saga)

    # 4. Verify completion
    assert saga.status == SagaStatus.COMPLETED
    assert patient.onboarding_complete == True
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  integration-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_DB: hormonia_test
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio

      - name: Run migrations
        env:
          DATABASE_URL: postgresql://test_user:test_password@localhost/hormonia_test
        run: alembic upgrade head

      - name: Run integration tests
        env:
          DATABASE_URL: postgresql://test_user:test_password@localhost/hormonia_test
        run: pytest -m integration -v
```

## Troubleshooting

### Problem: Tests fail with "DATABASE_URL not set"

**Solution**: Set the DATABASE_URL environment variable:

```bash
export DATABASE_URL="postgresql://user:password@localhost/hormonia_test"
```

### Problem: Tests fail with "refusing to run on production database"

**Solution**: Ensure DATABASE_URL contains "test":

```bash
# Good
postgresql://user:password@localhost/hormonia_test

# Bad (will be rejected)
postgresql://user:password@localhost/hormonia_prod
```

### Problem: Tests leave orphaned data

**Solution**: Use cleanup fixtures or run manual cleanup:

```python
from tests.integration.conftest import cleanup_all_test_data
cleanup_all_test_data(session)
```

### Problem: Unique constraint violations

**Solution**: Always use `unique_phone_number` and `unique_email` fixtures:

```python
def test_something(unique_phone_number, unique_email):
    patient_data = {
        "phone": unique_phone_number,
        "email": unique_email,
        ...
    }
```

### Problem: Foreign key constraint errors during cleanup

**Solution**: Cleanup deletes related records in the correct order. If you see this error, check that you're tracking all created records:

```python
cleanup_patients.track(patient.id)  # Don't forget this!
cleanup_sagas.track(saga.id)  # Don't forget this!
```

## Adding New Integration Tests

1. **Create test file** in `tests/integration/`
2. **Mark as integration**: `@pytest.mark.integration`
3. **Use cleanup fixtures**: Track all created records
4. **Use unique identifiers**: Use fixtures for phone/email
5. **Test complete workflows**: Not just individual functions
6. **Document expected behavior**: Clear test names and docstrings

Example template:

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
        Test complete workflow for My Feature.

        Verifies:
        1. Step one
        2. Step two
        3. Final state
        """
        # Create test data
        patient = create_patient(phone=unique_phone_number)
        cleanup_patients.track(patient.id)

        # Execute workflow
        result = execute_workflow(patient)

        # Verify outcome
        assert result.success == True

        # Verify database state
        real_db_session.refresh(patient)
        assert patient.workflow_complete == True
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/14/core/connections.html#testing-with-engines-and-connections)
- [Saga Pattern](https://microservices.io/patterns/data/saga.html)
