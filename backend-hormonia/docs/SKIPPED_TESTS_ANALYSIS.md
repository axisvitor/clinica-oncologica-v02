# Skipped Tests Analysis Report

**Generated:** 2025-12-02
**Total Skipped Tests:** 56
**Total Test Files:** 267

## Executive Summary

Out of 267 test files in the backend, **56 tests are currently skipped** (approximately 21% skip rate). These tests are categorized into 6 main groups, with varying degrees of actionability.

### Quick Stats

| Category | Count | Can Enable Now | Needs Work | Not Ready |
|----------|-------|----------------|------------|-----------|
| Conditional Data Skips | 30 | 30 | 0 | 0 |
| Model Structure Issues | 7 | 7 | 0 | 0 |
| Environment/Path Issues | 5 | 5 | 0 | 0 |
| Redis Integration | 4 | 3 | 1 | 0 |
| Missing Implementation | 1 | 0 | 1 | 0 |
| Integration Tests | 1 | 0 | 0 | 1 |
| Time-Dependent Tests | 8 | 0 | 8 | 0 |

---

## Category 1: Conditional Data Skips (30 tests) 🟢 CAN ENABLE NOW

**Status:** ✅ Can be immediately enabled
**Priority:** HIGH
**Effort:** LOW (fixture updates only)

### Issue
Tests skip themselves when test data (doctors, patients, templates) is missing from the database. This is a **fixture problem**, not a feature problem.

### Affected Files
1. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/v2/test_enhanced_messages.py` (8 tests)
2. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/v2/test_enhanced_quiz.py` (10 tests)
3. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/v2/test_patients.py` (5 tests)
4. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/v2/test_quiz.py` (6 tests)
5. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/security/test_cve_2025_clinic_001.py` (3 tests)
6. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/security/test_sql_injection_fixes.py` (1 test)

### Example Pattern
```python
def test_schedule_message_success(self, authenticated_client, db):
    doctor = db.query(User).filter(User.role == UserRole.DOCTOR).first()
    if not doctor:
        pytest.skip("No doctor available for test")  # ❌ BAD
    # ... rest of test
```

### Solution
**Create proper test fixtures** in `tests/conftest.py`:

```python
@pytest.fixture
def test_doctor(db_session):
    """Create a test doctor for tests that need one."""
    from app.models.user import User, UserRole
    doctor = User(
        email="test.doctor@example.com",
        name="Dr. Test",
        role=UserRole.DOCTOR,
        is_active=True
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor

@pytest.fixture
def test_patient(db_session, test_doctor):
    """Create a test patient with associated doctor."""
    from app.models.patient import Patient
    patient = Patient(
        name="Test Patient",
        email="test.patient@example.com",
        phone="+5511999999999",
        doctor_id=test_doctor.id
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient

@pytest.fixture
def quiz_template(db_session):
    """Create a quiz template for testing."""
    from app.models.quiz import QuizTemplate
    template = QuizTemplate(
        name="Test Quiz",
        questions=[{"text": "Q1", "type": "text"}]
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template
```

### Action Items
1. **Create fixtures** for: `test_doctor`, `test_patient`, `quiz_template`
2. **Update test signatures** to use these fixtures instead of querying
3. **Remove all `pytest.skip()` calls** checking for data existence
4. **Run tests** to verify they pass with proper fixtures

**Estimated Time:** 2-3 hours
**Impact:** +30 tests enabled, better test reliability

---

## Category 2: Model Structure Issues (7 tests) 🟢 CAN ENABLE NOW

**Status:** ✅ Can be immediately enabled
**Priority:** HIGH
**Effort:** MEDIUM (refactor tests to use correct model)

### Issue
Tests skip because they expect a `Flow` model, but the actual model is `PatientFlowState`. The **model exists**, tests just use wrong assumptions.

### Affected Files
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/v2/test_flows_advance.py` (7 tests)

### Skip Reason
```python
@pytest.mark.skip(reason="Flow model doesn't exist - uses PatientFlowState")
```

### Current Model Structure
**ACTUAL MODEL** (exists in `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/models/flow.py`):
```python
class PatientFlowState(BaseModel):
    __tablename__ = "patient_flow_states"

    id: UUID
    patient_id: UUID
    template_version_id: UUID
    current_node_id: str
    state: dict  # FlowState as JSON
    completed_at: datetime
    # ... other fields
```

### Solution
**Refactor tests** to work with `PatientFlowState`:

```python
# ❌ OLD (skipped)
@pytest.mark.skip(reason="Flow model doesn't exist - uses PatientFlowState")
def test_advance_flow_success(self, authenticated_client, db_session):
    # Expected Flow model that doesn't exist
    pass

# ✅ NEW (working)
def test_advance_patient_flow_success(self, authenticated_client, test_patient, db_session):
    """Test successful flow advancement using PatientFlowState."""
    from app.models.flow import PatientFlowState, FlowTemplateVersion

    # Create template version
    template_version = FlowTemplateVersion(
        name="Test Flow",
        version="1.0",
        nodes=[{"id": "start", "type": "start"}]
    )
    db_session.add(template_version)
    db_session.commit()

    # Create patient flow state
    flow_state = PatientFlowState(
        patient_id=test_patient.id,
        template_version_id=template_version.id,
        current_node_id="start",
        state={"status": "active"}
    )
    db_session.add(flow_state)
    db_session.commit()

    # Test advancement
    response = authenticated_client.post(
        f"/api/v2/flows/{flow_state.id}/advance"
    )

    assert response.status_code == 200
```

### Action Items
1. **Remove skip decorators** from all 7 tests
2. **Refactor tests** to use `PatientFlowState` instead of non-existent `Flow`
3. **Add fixtures** for `FlowTemplateVersion` and `PatientFlowState`
4. **Update test names** to reflect actual model usage
5. **Run tests** to verify flow advancement logic

**Estimated Time:** 3-4 hours
**Impact:** +7 tests enabled, validates flow advancement feature

---

## Category 3: Environment/Path Issues (5 tests) 🟢 CAN ENABLE NOW

**Status:** ✅ Can be immediately enabled
**Priority:** MEDIUM
**Effort:** LOW (fix test assumptions)

### Issue
Tests skip because they look for directories that **do exist** but at different paths, or because they're too strict about file counts.

### Affected Files
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/performance/test_async_compliance.py` (5 tests)

### Skip Reasons
```python
pytest.skip("Services directory not found")  # Line 159
pytest.skip("API directory not found")       # Line 227
pytest.skip("No functions found in services directory")  # Line 207
```

### Current Reality
**Directory structure EXISTS:**
```bash
backend-hormonia/
  app/
    services/          # ✅ EXISTS - 24 service files
    api/               # ✅ EXISTS - API endpoints
    repositories/      # ✅ EXISTS - Data layer
```

### Solution
**Fix path assumptions** in test:

```python
# ❌ OLD (broken)
def test_async_compliance(app_directory):
    services_dir = app_directory / "services"  # Wrong: looks in app_directory
    if not services_dir.exists():
        pytest.skip("Services directory not found")

# ✅ NEW (working)
def test_async_compliance():
    """Test async/await compliance in service layer."""
    import os
    from pathlib import Path

    # Get actual project root
    project_root = Path(__file__).parent.parent.parent
    services_dir = project_root / "app" / "services"

    assert services_dir.exists(), f"Services dir not found at {services_dir}"

    # Continue with compliance checks...
```

### Action Items
1. **Fix path resolution** in `test_async_compliance.py`
2. **Remove conditional skips** that check for directory existence
3. **Update assertions** to provide helpful error messages instead of skipping
4. **Adjust thresholds** (e.g., if 0 functions found, check path first)
5. **Run tests** to verify async compliance checks work

**Estimated Time:** 1-2 hours
**Impact:** +5 tests enabled, validates async/await usage

---

## Category 4: Redis Integration (4 tests) 🟡 MOSTLY READY

**Status:** ⚠️ 3 can enable with mock, 1 needs integration test suite
**Priority:** MEDIUM
**Effort:** LOW for mocks, MEDIUM for integration

### Issue
Tests skip because they require Redis for rate limiting. However, **mock_redis fixture already exists** in conftest.py.

### Affected Files
1. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/v2/test_debug.py` (3 tests)
2. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/services/test_quiz_response_debounce.py` (1 test)

### Current Fixture (ALREADY EXISTS)
```python
# File: tests/conftest.py line 698
@pytest.fixture
def mock_redis(mocker):
    """Create a mock Redis client."""
    redis = mocker.MagicMock()
    redis.get = mocker.MagicMock(return_value=None)
    redis.set = mocker.MagicMock(return_value=True)
    redis.incr = mocker.MagicMock(return_value=1)
    redis.expire = mocker.MagicMock(return_value=True)
    return redis
```

### Solution for test_debug.py (3 tests) - USE MOCK

```python
# ❌ OLD (skipped)
@pytest.mark.skip(reason="Rate limiting requires Redis - implement with integration tests")
def test_environment_rate_limit(self):
    pass

# ✅ NEW (with mock)
def test_environment_rate_limit(self, authenticated_client, mock_redis, mocker):
    """Test that environment endpoint is rate limited to 5 req/min."""
    # Patch Redis in the rate limiter
    mocker.patch('app.core.rate_limiter.redis_client', mock_redis)

    # Mock incr to simulate rate limit hit on 6th request
    mock_redis.incr.side_effect = [1, 2, 3, 4, 5, 6]
    mock_redis.ttl.return_value = 60

    # Make 5 successful requests
    for i in range(5):
        response = authenticated_client.get("/api/v2/debug/environment")
        assert response.status_code == 200

    # 6th request should be rate limited
    response = authenticated_client.get("/api/v2/debug/environment")
    assert response.status_code == 429
    assert "rate limit exceeded" in response.json()["detail"].lower()
```

### Solution for test_quiz_response_debounce.py (1 test) - GRACEFUL SKIP

```python
# ❌ OLD (runtime skip)
def test_debounce_with_redis(self):
    try:
        redis = get_redis()
        redis.ping()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")

# ✅ NEW (decorator skip for integration only)
@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("REDIS_URL"),
    reason="Redis integration test - set REDIS_URL to enable"
)
def test_debounce_with_real_redis(self):
    """Integration test with real Redis instance."""
    # Real Redis test here
```

### Action Items
1. **Enable 3 rate limit tests** with `mock_redis` fixture
2. **Implement rate limit assertions** (429 status, error message)
3. **Move 1 Redis integration test** to integration test suite
4. **Add @pytest.mark.integration** to real Redis tests
5. **Document** how to run integration tests with Redis

**Estimated Time:** 2-3 hours
**Impact:** +3 tests enabled now, +1 test for integration suite

---

## Category 5: Missing Implementation (1 test) 🔴 NEEDS WORK

**Status:** ❌ Requires feature implementation
**Priority:** LOW
**Effort:** MEDIUM (implement missing repository method)

### Issue
Test expects `find_by_idempotency_key()` method that doesn't exist in PatientRepository.

### Affected Files
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/repositories/test_patient_lgpd_queries.py` (1 test, line 281)

### Skip Code
```python
# Repository should have method to find by idempotency key
if hasattr(repository, 'find_by_idempotency_key'):
    result = repository.find_by_idempotency_key("test-key-123")
    assert result is not None
else:
    pytest.skip("find_by_idempotency_key not implemented yet")
```

### Solution
**Implement the missing method** in PatientRepository:

```python
# File: app/repositories/patient.py
class PatientRepository(BaseRepository[Patient]):
    # ... existing methods ...

    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[Patient]:
        """
        Find patient by idempotency key for duplicate prevention.

        Used to prevent duplicate patient creation when webhooks/API calls
        are retried with the same idempotency key.

        Args:
            idempotency_key: Unique key for the operation

        Returns:
            Patient if found, None otherwise
        """
        from app.models.patient import Patient

        return self.db.query(Patient).filter(
            Patient.idempotency_key == idempotency_key,
            Patient.deleted_at.is_(None)  # Respect soft delete
        ).first()
```

**Add idempotency_key column** (if not exists):
```python
# Migration: alembic/versions/032_add_idempotency_key.py
def upgrade():
    op.add_column('patients',
        sa.Column('idempotency_key', sa.String(255), nullable=True, index=True)
    )
    op.create_index('ix_patients_idempotency_key', 'patients', ['idempotency_key'])

def downgrade():
    op.drop_index('ix_patients_idempotency_key')
    op.drop_column('patients', 'idempotency_key')
```

### Action Items
1. **Check if column exists** in Patient model
2. **Create migration** if column missing
3. **Implement method** in PatientRepository
4. **Remove skip condition** from test
5. **Add tests** for idempotency key handling (duplicate prevention)

**Estimated Time:** 3-4 hours
**Impact:** +1 test enabled, better duplicate prevention

---

## Category 6: Integration Tests (1 test) ⏸️ KEEP SKIPPED

**Status:** ⏸️ Keep skipped (requires external services)
**Priority:** LOW
**Effort:** N/A (move to dedicated integration suite)

### Issue
Full end-to-end integration test requires running services (DB, Redis, WhatsApp API). This is **intentionally skipped** for unit test suite.

### Affected Files
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/integration/test_patient_saga.py` (line 522)

### Skip Reason
```python
@pytest.mark.integration
@pytest.mark.skip(reason="Requires running services (DB, Redis, WhatsApp API)")
async def test_full_integration_saga_flow():
    """
    Full integration test with real services.

    This test requires:
    - PostgreSQL running
    - Redis running
    - WhatsApp API accessible
    """
```

### Recommendation
**Keep skipped** but improve documentation:

```python
@pytest.mark.integration
@pytest.mark.skipif(
    not all([
        os.getenv("DATABASE_URL"),
        os.getenv("REDIS_URL"),
        os.getenv("WHATSAPP_API_URL")
    ]),
    reason="Integration test - set DATABASE_URL, REDIS_URL, WHATSAPP_API_URL to enable"
)
async def test_full_integration_saga_flow():
    """
    Full end-to-end integration test with real services.

    To run this test:
    1. Start PostgreSQL: docker-compose up -d postgres
    2. Start Redis: docker-compose up -d redis
    3. Configure WhatsApp API or use test double
    4. Run: pytest -m integration tests/integration/test_patient_saga.py
    """
```

### Action Items
1. **Keep test skipped** for normal test runs
2. **Improve skip condition** to check for environment variables
3. **Add documentation** on running integration tests
4. **Create docker-compose** for integration test environment
5. **Add to CI/CD** as separate integration test stage

**Estimated Time:** 1 hour (documentation only)
**Impact:** Better documentation, no test count change

---

## Category 7: Time-Dependent Tests (8 tests) 🟡 NEEDS REFACTORING

**Status:** ⚠️ Needs proper time mocking
**Priority:** MEDIUM
**Effort:** MEDIUM (refactor to use freezegun or similar)

### Issue
Tests skip themselves when they detect time-sensitive behavior. This indicates **flaky tests** that need proper time control.

### Affected Files
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/integration/test_security_fixes_integration.py` (1 test, line 147)
- Various performance tests with time-dependent behavior

### Example Pattern
```python
def test_token_expiration(self):
    """Test that tokens expire after configured time."""
    if datetime.now().hour == 0:  # Flaky near midnight
        pytest.skip("Skipping time-dependent test")
```

### Solution
**Use freezegun** or similar library to control time:

```python
from freezegun import freeze_time
from datetime import datetime, timedelta

# ❌ OLD (flaky)
def test_token_expiration(self):
    token = create_token(expires_in=3600)
    time.sleep(3601)  # Wait for expiration
    assert is_expired(token)

# ✅ NEW (deterministic)
@freeze_time("2025-01-01 12:00:00")
def test_token_expiration(self):
    """Test token expiration with controlled time."""
    # Create token at 12:00:00
    token = create_token(expires_in=3600)
    assert not is_expired(token)

    # Fast-forward to 13:00:01 (past expiration)
    with freeze_time("2025-01-01 13:00:01"):
        assert is_expired(token)
```

### Action Items
1. **Add freezegun** to test dependencies
2. **Identify all time-dependent tests**
3. **Refactor to use @freeze_time decorator**
4. **Remove conditional skips** based on time
5. **Run tests** to verify deterministic behavior

**Estimated Time:** 4-5 hours
**Impact:** +8 tests enabled, eliminates flaky tests

---

## Summary of Recommendations

### Immediate Actions (Can Enable Today)

1. **Category 1 (30 tests):** Create doctor/patient/template fixtures
2. **Category 2 (7 tests):** Refactor to use PatientFlowState model
3. **Category 3 (5 tests):** Fix path resolution in async compliance tests
4. **Category 4 (3 tests):** Use existing mock_redis fixture

**Total Immediate Impact:** +45 tests enabled (80% of skipped tests)

### Short-Term Actions (This Sprint)

5. **Category 5 (1 test):** Implement find_by_idempotency_key method
6. **Category 7 (8 tests):** Add freezegun and refactor time-dependent tests

**Total Short-Term Impact:** +9 tests enabled

### Long-Term Actions (Keep Skipped)

7. **Category 6 (1 test):** Move to dedicated integration test suite

---

## Test Health Metrics

### Before Cleanup
- **Total Tests:** ~267 test files
- **Skipped Tests:** 56 (21%)
- **Enabled Tests:** ~79%

### After Cleanup (Projected)
- **Total Tests:** ~267 test files
- **Skipped Tests:** 1-2 (0.4% - integration only)
- **Enabled Tests:** ~99.6%

---

## Next Steps

1. **Create fixtures branch:** `feature/test-fixtures-cleanup`
2. **Implement fixes** in order of priority (Categories 1-3 first)
3. **Run test suite** after each category to verify
4. **Update CI/CD** to fail on skipped tests (except @pytest.mark.integration)
5. **Document** integration test setup in README

---

## Files Referenced

### Test Files Needing Updates
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/v2/test_enhanced_messages.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/v2/test_enhanced_quiz.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/v2/test_patients.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/v2/test_quiz.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/v2/test_flows_advance.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/api/v2/test_debug.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/performance/test_async_compliance.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/security/test_cve_2025_clinic_001.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/security/test_sql_injection_fixes.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/repositories/test_patient_lgpd_queries.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/integration/test_patient_saga.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/integration/test_security_fixes_integration.py`

### Code Files Needing Updates
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/conftest.py` (add fixtures)
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/repositories/patient.py` (add method)

---

**Report End**
