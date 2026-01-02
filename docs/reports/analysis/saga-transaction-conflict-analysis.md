# Saga Pattern Transaction Conflict Analysis

## Executive Summary

**Problem**: Patient creation tests fail with "Saga Pattern não retornou paciente após execução" (400 error) due to transaction isolation conflict between test fixtures and saga's internal session management.

**Root Cause**: Test fixtures wrap all operations in a rolled-back transaction (`db_session` fixture), while the saga orchestrator commits intermediate steps internally, causing session state conflicts.

**Impact**: All patient creation tests using the saga pattern fail, preventing proper validation of the critical patient onboarding flow.

---

## Technical Analysis

### 1. Transaction Flow Conflict

#### Test Fixture Setup (`tests/api/critical/conftest.py:177-186`)
```python
@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """Create a database session for each test."""
    connection = test_engine.connect()
    transaction = connection.begin()  # ← Outer transaction
    TestingSessionLocal = sessionmaker(bind=connection)
    session = TestingSessionLocal()
    yield session
    session.close()
    transaction.rollback()  # ← ALWAYS ROLLBACK - nothing persists
    connection.close()
```

**Issue**: The outer transaction is rolled back after the test, meaning any `commit()` inside the saga is isolated and won't persist.

#### Saga Orchestrator Internal Commits (`app/orchestration/saga_orchestrator.py`)

The saga makes **4 explicit commits** during execution:

**Commit #1** - Initialize Saga Record (line 131):
```python
saga = PatientOnboardingSaga(...)
self.db.add(saga)
self.db.commit()  # ← Commit 1: Save saga record
```

**Commit #2** - Create Patient (line 308):
```python
patient = self.patient_repo.create(patient_dict)
saga.patient_id = patient.id
saga.current_step = 1
self.db.commit()  # ← Commit 2: Save patient + update saga
```

**Commit #3** - Initialize Flow (line 338):
```python
await self.flow_service.initialize_default_flow(patient, current_user_id)
saga.current_step = 3
self.db.commit()  # ← Commit 3: Update saga with flow step
```

**Commit #4** - Complete Saga (line 155):
```python
saga.status = SagaStatus.COMPLETED
saga.completed_at = datetime.now(timezone.utc)
self.db.commit()  # ← Commit 4: Mark saga as completed
```

### 2. Why the Saga Returns `None`

**Flow Breakdown**:

1. **Test fixture** creates outer transaction
2. **Saga starts** with same `db` session (bound to outer transaction)
3. **Saga calls** `self.db.commit()` 4 times
4. **Commits appear to succeed** (no exception) but data is NOT actually committed to DB
5. **Saga queries** for patient using `self.patient_repo.get_by_id(saga.patient_id)`
6. **Query returns `None`** because:
   - Test transaction isolation prevents seeing uncommitted data
   - OR session state is corrupted after mixed commit/rollback operations
7. **Saga returns `None`** from `execute_patient_onboarding_saga()`
8. **Coordinator raises error**: "Saga Pattern não retornou paciente após execução" (line 179)

---

## Evidence from Code

### Patient Repository Query (saga_orchestrator.py:219)
```python
if saga.patient_id:
    patient = self.patient_repo.get_by_id(saga.patient_id)
```

### Coordinator Check (coordinator.py:177-180)
```python
patient = await self.saga_orchestrator.execute_patient_onboarding_saga(...)

if not patient:
    raise ValidationError(
        "Saga Pattern não retornou paciente após execução"
    )
```

### Patient Repository Implementation Pattern
The `PatientRepository.create()` method likely does:
```python
def create(self, patient_dict):
    patient = Patient(**patient_dict)
    self.db.add(patient)
    # May or may not commit internally - saga commits externally
    return patient
```

After `self.db.commit()` in a rolled-back transaction context, subsequent queries fail to find the "committed" data.

---

## Solution Options

### ✅ Option 1: Mock Saga Orchestrator (RECOMMENDED)

**Pros**:
- Fastest execution
- No database transaction conflicts
- Tests API contract, not saga internals
- Allows testing error scenarios easily

**Cons**:
- Doesn't test actual saga logic (should have separate integration tests)

**Implementation**:

```python
# File: tests/api/v2/conftest.py

@pytest.fixture
def mock_saga_orchestrator(monkeypatch):
    """Mock saga orchestrator for unit tests."""
    from unittest.mock import AsyncMock, MagicMock
    from app.models.patient import Patient
    from uuid import uuid4

    async def mock_execute_saga(patient_data, doctor_id, current_user=None, idempotency_key=None):
        """Mock saga execution that returns a fake patient."""
        patient = Patient(
            id=uuid4(),
            name=patient_data.name,
            doctor_id=doctor_id,
            # Set other required fields
        )
        # Handle encrypted fields
        if patient_data.email:
            patient.set_email(patient_data.email)
        if patient_data.phone:
            patient.set_phone(patient_data.phone)
        if patient_data.cpf:
            patient.set_cpf(patient_data.cpf)

        return patient

    mock = AsyncMock()
    mock.execute_patient_onboarding_saga = mock_execute_saga

    # Patch the SagaOrchestrator import in the router
    monkeypatch.setattr(
        "app.api.v2.routers.patients.crud.SagaOrchestrator",
        lambda *args, **kwargs: mock
    )

    return mock


# Update test to use mock
class TestPatientCreate:
    def test_create_patient_success(
        self,
        authenticated_client,
        valid_patient_payload,
        mock_saga_orchestrator  # ← Inject mock
    ):
        response = authenticated_client.post(
            "/api/v2/patients",
            json=valid_patient_payload
        )

        assert response.status_code == 201
        # Verify mock was called
        mock_saga_orchestrator.execute_patient_onboarding_saga.assert_called_once()
```

### ⚠️ Option 2: Disable Transaction Rollback for Saga Tests

**Pros**:
- Tests actual saga implementation
- Catches real transaction issues

**Cons**:
- Slower (real DB commits)
- Requires manual cleanup
- Data pollution between tests
- Complex fixture management

**Implementation**:

```python
# File: tests/api/v2/conftest.py

@pytest.fixture
def db_session_no_rollback(test_engine):
    """
    Database session WITHOUT transaction rollback for saga tests.

    WARNING: Data is NOT rolled back. Requires manual cleanup.
    """
    TestingSessionLocal = sessionmaker(bind=test_engine)
    session = TestingSessionLocal()

    yield session

    # Manual cleanup (risky - may leave orphaned data)
    try:
        # Clean up test data
        from app.models.patient import Patient
        from app.models.patient_onboarding_saga import PatientOnboardingSaga
        session.query(Patient).filter(Patient.phone.like('%test%')).delete()
        session.query(PatientOnboardingSaga).delete()
        session.commit()
    except Exception as e:
        session.rollback()
        logger.warning(f"Cleanup failed: {e}")
    finally:
        session.close()


@pytest.fixture
def authenticated_client_saga(app, db_session_no_rollback):
    """Client using non-rollback session for saga tests."""
    def get_db_override():
        yield db_session_no_rollback

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)
    # ... setup authentication
    return client
```

### ⚠️ Option 3: Use Nested Transactions (SAVEPOINT)

**Pros**:
- Allows saga commits within test transaction
- Automatic rollback after test

**Cons**:
- Complex SQLAlchemy session management
- May not work with all databases
- Saga code must be aware of nested transactions

**Implementation**:

```python
@pytest.fixture
def db_session_nested(test_engine):
    """Database session using nested transactions (SAVEPOINT)."""
    connection = test_engine.connect()
    transaction = connection.begin()

    TestingSessionLocal = sessionmaker(bind=connection)
    session = TestingSessionLocal()

    # Enable SAVEPOINT for nested transactions
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
```

**Saga code changes required**:
```python
# Would need to change all commits to:
self.db.flush()  # Instead of commit in nested context
```

### ⚠️ Option 4: Create Separate Saga Integration Tests

**Pros**:
- Unit tests stay fast with mocks
- Integration tests validate real saga behavior
- Clear separation of concerns

**Cons**:
- Requires maintaining two test suites
- More test code to write

**Structure**:
```
tests/
├── unit/
│   └── api/
│       └── v2/
│           └── test_patients_create.py  # Mock saga
└── integration/
    └── saga/
        └── test_patient_onboarding_saga.py  # Real saga + DB
```

---

## Recommended Solution

**Use Option 1 (Mock Saga) for API tests** + **Option 4 (Separate Integration Tests)**

### Rationale:

1. **API Tests (Unit Level)**:
   - Mock saga orchestrator
   - Fast execution
   - Test API contract, validation, authorization
   - No transaction conflicts

2. **Saga Tests (Integration Level)**:
   - Real database (no rollback fixture)
   - Test saga orchestration logic
   - Test compensation/rollback flows
   - Manual cleanup per test

### Implementation Priority:

**Phase 1 - Quick Fix (1-2 hours)**:
- Add `mock_saga_orchestrator` fixture
- Update failing tests to use mock
- Get CI green immediately

**Phase 2 - Proper Testing (4-6 hours)**:
- Create `tests/integration/saga/test_patient_onboarding_saga.py`
- Test saga steps: create → flow → message
- Test compensation scenarios
- Test concurrent saga execution (distributed locks)
- Test saga resume functionality

---

## Example Mock Implementation

```python
# File: tests/api/v2/test_patients_create.py

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

@pytest.fixture
def mock_saga_success():
    """Mock successful saga execution."""
    async def mock_execute(patient_data, doctor_id, current_user=None, idempotency_key=None):
        from app.models.patient import Patient

        patient = Patient(
            id=uuid4(),
            name=patient_data.name,
            doctor_id=doctor_id,
            birth_date=patient_data.birth_date,
            treatment_type=patient_data.treatment_type,
            treatment_start_date=patient_data.treatment_start_date,
            flow_state="pending"
        )

        if patient_data.email:
            patient.set_email(patient_data.email)
        if patient_data.phone:
            patient.set_phone(patient_data.phone)
        if patient_data.cpf:
            patient.set_cpf(patient_data.cpf)

        return patient

    return mock_execute


class TestPatientCreate:
    def test_create_patient_success(
        self,
        authenticated_client,
        valid_patient_payload,
        mock_saga_success
    ):
        """Test successful patient creation with mocked saga."""

        # Mock the saga orchestrator
        with patch('app.api.v2.routers.patients.crud.SagaOrchestrator') as MockSaga:
            mock_instance = MockSaga.return_value
            mock_instance.execute_patient_onboarding_saga = mock_saga_success

            # Act
            response = authenticated_client.post(
                "/api/v2/patients",
                json=valid_patient_payload
            )

            # Assert
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == valid_patient_payload["name"]

            # Verify saga was called
            mock_instance.execute_patient_onboarding_saga.assert_called_once()


    def test_create_patient_saga_failure(
        self,
        authenticated_client,
        valid_patient_payload
    ):
        """Test patient creation when saga fails."""

        # Mock saga to return None (failure scenario)
        async def mock_saga_failure(*args, **kwargs):
            return None

        with patch('app.api.v2.routers.patients.crud.SagaOrchestrator') as MockSaga:
            mock_instance = MockSaga.return_value
            mock_instance.execute_patient_onboarding_saga = mock_saga_failure

            # Act
            response = authenticated_client.post(
                "/api/v2/patients",
                json=valid_patient_payload
            )

            # Assert
            assert response.status_code == 400
            assert "Saga Pattern" in response.json()["detail"]
```

---

## Integration Test Example

```python
# File: tests/integration/saga/test_patient_onboarding_saga.py

import pytest
from sqlalchemy.orm import Session
from app.orchestration.saga_orchestrator import SagaOrchestrator
from app.schemas.patient import PatientCreate
from uuid import uuid4

@pytest.fixture
def real_db_session():
    """Real database session for integration tests (no rollback)."""
    from app.core.database import SessionLocal

    session = SessionLocal()
    yield session

    # Cleanup test data
    from app.models.patient_onboarding_saga import PatientOnboardingSaga
    from app.models.patient import Patient

    try:
        # Delete test patients and sagas
        session.query(Patient).filter(
            Patient.phone.like('%99999999%')
        ).delete()
        session.query(PatientOnboardingSaga).delete()
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


class TestPatientOnboardingSaga:
    @pytest.mark.asyncio
    async def test_saga_creates_patient_successfully(self, real_db_session):
        """Test complete saga execution with real database."""

        # Arrange
        saga = SagaOrchestrator(db=real_db_session)
        doctor_id = uuid4()

        patient_data = PatientCreate(
            name="Integration Test Patient",
            phone="+5511999999999",
            email="integration@test.com",
            birth_date="1990-01-01",
            treatment_type="chemotherapy"
        )

        # Act
        patient = await saga.execute_patient_onboarding_saga(
            patient_data=patient_data,
            doctor_id=doctor_id
        )

        # Assert
        assert patient is not None
        assert patient.id is not None
        assert patient.name == "Integration Test Patient"

        # Verify patient exists in database
        from app.repositories.patient import PatientRepository
        repo = PatientRepository(real_db_session)
        found = repo.get_by_id(patient.id)
        assert found is not None


    @pytest.mark.asyncio
    async def test_saga_compensation_on_failure(self, real_db_session):
        """Test saga compensation when a step fails."""

        # Arrange - Mock flow service to fail
        from unittest.mock import patch

        saga = SagaOrchestrator(db=real_db_session)
        doctor_id = uuid4()

        patient_data = PatientCreate(
            name="Compensation Test",
            phone="+5511988888888",
            email="compensation@test.com"
        )

        # Mock flow initialization to fail
        with patch.object(
            saga.flow_service,
            'initialize_default_flow',
            side_effect=Exception("Flow init failed")
        ):
            # Act
            patient = await saga.execute_patient_onboarding_saga(
                patient_data=patient_data,
                doctor_id=doctor_id
            )

            # Assert - saga should return None after compensation
            assert patient is None

            # Verify patient was deleted by compensation
            from app.repositories.patient import PatientRepository
            repo = PatientRepository(real_db_session)
            patients = repo.get_by_phone("+5511988888888")
            assert len(patients) == 0  # Compensated
```

---

## Action Items

### Immediate (P0 - Today)
- [ ] Create `mock_saga_orchestrator` fixture
- [ ] Update `test_create_patient_success` to use mock
- [ ] Run tests to verify fix
- [ ] Update other failing patient creation tests

### Short-term (P1 - This Week)
- [ ] Create `tests/integration/saga/` directory
- [ ] Write `test_patient_onboarding_saga.py` with real DB tests
- [ ] Document saga testing strategy in `docs/testing/`
- [ ] Add saga compensation tests

### Long-term (P2 - Next Sprint)
- [ ] Review all saga usage across codebase
- [ ] Standardize saga testing approach
- [ ] Add saga monitoring/observability
- [ ] Consider saga circuit breaker for resilience

---

## References

- **Saga Orchestrator**: `/backend-hormonia/app/orchestration/saga_orchestrator.py`
- **Onboarding Coordinator**: `/backend-hormonia/app/domain/patient/onboarding/coordinator.py`
- **Patient CRUD Router**: `/backend-hormonia/app/api/v2/routers/patients/crud.py`
- **Test Fixtures**: `/backend-hormonia/tests/api/v2/conftest.py`
- **Failing Test**: `/backend-hormonia/tests/api/v2/test_patients_create.py`

---

## Conclusion

The transaction conflict between test fixtures and saga's internal commits causes the saga to return `None`, triggering the "Saga Pattern não retornou paciente" error.

**Recommended Fix**: Mock the saga orchestrator in API unit tests, and create separate integration tests for saga logic validation. This provides fast, reliable unit tests while maintaining comprehensive coverage of saga behavior.
