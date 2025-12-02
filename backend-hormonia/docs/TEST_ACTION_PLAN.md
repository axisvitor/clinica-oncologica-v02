# Test Coverage Action Plan - Priority Implementation

**Created**: 2025-12-02
**Target Completion**: 10 weeks
**Goal**: Achieve 85% test coverage

---

## Week 1: Critical Fixes (Days 1-7)

### Day 1-2: Fix Skipped Tests (18 tests)

#### Location 1: `tests/repositories/test_patient_n1_optimization.py:404`
```python
# CURRENT:
pytest.skip("Integration test - requires staging database")

# FIX:
@pytest.fixture
def staging_patient_data(db_session):
    """Create realistic patient data for N+1 testing."""
    patients = []
    for i in range(100):
        patient = Patient(
            name=f"Patient {i}",
            email=f"patient{i}@test.com",
            cpf_hash=f"hash_{i}"
        )
        db_session.add(patient)
    db_session.commit()
    return patients

def test_find_all_with_relationships_no_n1(db_session, staging_patient_data):
    """Verify query optimization prevents N+1."""
    with assert_query_count(db_session, expected=1):
        patients = patient_repo.find_all_with_relationships()
        # Access relationships to trigger lazy loading
        for p in patients:
            _ = p.messages
            _ = p.appointments
```

#### Location 2: `tests/repositories/test_patient_lgpd_queries.py:281`
```python
# CURRENT:
pytest.skip("find_by_idempotency_key not implemented yet")

# FIX:
# 1. Implement method in repository:
# app/repositories/patient.py
def find_by_idempotency_key(self, key: str) -> Optional[Patient]:
    """Find patient by idempotency key for duplicate prevention."""
    return self.db.query(Patient).filter(
        Patient.idempotency_key == key
    ).first()

# 2. Add test:
def test_find_by_idempotency_key(db_session, patient_factory):
    """Verify idempotency key lookup."""
    key = str(uuid4())
    patient = patient_factory(idempotency_key=key)

    found = patient_repo.find_by_idempotency_key(key)
    assert found.id == patient.id

    # Test not found
    assert patient_repo.find_by_idempotency_key("nonexistent") is None
```

#### Location 3: `tests/api/v2/test_enhanced_quiz.py` (8 skips)
```python
# CURRENT:
pytest.skip("No patient or template available")

# FIX:
@pytest.fixture(autouse=True)
def setup_quiz_environment(db_session):
    """Auto-setup patients and templates for all tests."""
    # Create doctor
    doctor = User(
        email="doctor@test.com",
        role=UserRole.DOCTOR,
        is_active=True
    )
    db_session.add(doctor)

    # Create patients
    patients = []
    for i in range(5):
        patient = Patient(
            name=f"Patient {i}",
            email=f"patient{i}@test.com",
            cpf_hash=f"hash_{i}",
            doctor_id=doctor.id
        )
        patients.append(patient)
        db_session.add(patient)

    # Create template
    template = QuizTemplate(
        name="Test Template",
        questions=[
            {"id": "q1", "text": "How are you?", "type": "text"}
        ]
    )
    db_session.add(template)
    db_session.commit()

    return {
        "doctor": doctor,
        "patients": patients,
        "template": template
    }

# Remove all pytest.skip() calls
def test_create_quiz_session(client, setup_quiz_environment):
    """Test quiz session creation."""
    patient = setup_quiz_environment["patients"][0]
    template = setup_quiz_environment["template"]

    response = client.post(
        f"/api/v2/quiz/sessions",
        json={
            "patient_id": str(patient.id),
            "template_id": str(template.id)
        }
    )
    assert response.status_code == 201
```

**Estimated Time**: 2 days
**Files Modified**: 3
**Tests Fixed**: 18

---

### Day 3: Key Rotation Tests (CRITICAL SECURITY)

#### Create: `tests/services/test_encryption_key_rotation.py`

```python
"""
Tests for encryption key rotation strategy.

SECURITY CRITICAL: Ensures data remains accessible after key rotation.
LGPD COMPLIANCE: Required for key lifecycle management.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from app.services.encryption.key_manager import KeyManager
from app.services.encryption.unified_encryption_service import UnifiedEncryptionService


class TestKeyRotation:
    """Test key rotation scenarios."""

    @pytest.fixture
    def key_manager(self):
        """Create key manager with mock storage."""
        manager = KeyManager()
        manager.storage = Mock()
        return manager

    def test_generate_new_key_version(self, key_manager):
        """Verify new key version generation."""
        old_key = key_manager.get_current_key()

        new_key = key_manager.rotate_key()

        assert new_key != old_key
        assert len(new_key) == 32  # 256 bits
        assert key_manager.get_key_version() == 2

    def test_decrypt_data_encrypted_with_old_key(self, key_manager):
        """Verify old data remains decryptable after rotation."""
        # Encrypt with key v1
        service = UnifiedEncryptionService(key_manager)
        cpf = "123.456.789-00"
        encrypted_v1 = service.encrypt_cpf(cpf)

        # Rotate key to v2
        key_manager.rotate_key()

        # Should still decrypt with old key
        decrypted = service.decrypt_cpf(encrypted_v1)
        assert decrypted == cpf

    def test_new_encryptions_use_new_key(self, key_manager):
        """Verify new encryptions use latest key version."""
        service = UnifiedEncryptionService(key_manager)

        # Rotate to v2
        key_manager.rotate_key()

        # New encryption
        cpf = "987.654.321-00"
        encrypted = service.encrypt_cpf(cpf)

        # Check version in ciphertext
        assert encrypted.startswith("v2:")

    def test_re_encrypt_data_with_new_key(self, key_manager):
        """Test re-encryption strategy for old data."""
        service = UnifiedEncryptionService(key_manager)

        # Encrypt with v1
        cpf = "111.222.333-44"
        encrypted_v1 = service.encrypt_cpf(cpf)

        # Rotate key
        key_manager.rotate_key()

        # Re-encrypt
        encrypted_v2 = service.re_encrypt(encrypted_v1)

        assert encrypted_v2.startswith("v2:")
        assert service.decrypt_cpf(encrypted_v2) == cpf

    def test_batch_re_encryption(self, db_session, key_manager):
        """Test batch re-encryption of patient data."""
        service = UnifiedEncryptionService(key_manager)

        # Create patients with v1 encryption
        patients = []
        for i in range(100):
            patient = Patient(
                name=f"Patient {i}",
                cpf_encrypted=service.encrypt_cpf(f"{i:011d}")
            )
            patients.append(patient)
            db_session.add(patient)
        db_session.commit()

        # Rotate key
        key_manager.rotate_key()

        # Batch re-encrypt
        re_encrypted_count = service.batch_re_encrypt_patients(db_session)

        assert re_encrypted_count == 100

        # Verify all use v2
        for patient in patients:
            db_session.refresh(patient)
            assert patient.cpf_encrypted.startswith("v2:")

    def test_key_rotation_audit_log(self, key_manager):
        """Verify key rotation is logged for audit."""
        with patch('app.services.audit_service.log_security_event') as mock_log:
            key_manager.rotate_key()

            mock_log.assert_called_once_with(
                event_type="KEY_ROTATION",
                old_version=1,
                new_version=2,
                timestamp=pytest.approx(datetime.utcnow(), abs=timedelta(seconds=1))
            )

    def test_automatic_key_rotation_schedule(self, key_manager):
        """Test automatic rotation after configured period."""
        # Set rotation policy: 90 days
        key_manager.set_rotation_policy(days=90)

        # Mock key age
        key_manager.current_key_created_at = datetime.utcnow() - timedelta(days=91)

        # Should trigger rotation
        assert key_manager.should_rotate() is True

        # Recent key should not rotate
        key_manager.current_key_created_at = datetime.utcnow() - timedelta(days=30)
        assert key_manager.should_rotate() is False

    def test_old_key_retention_policy(self, key_manager):
        """Verify old keys are retained for decryption."""
        # Rotate multiple times
        key_v1 = key_manager.get_current_key()
        key_manager.rotate_key()
        key_v2 = key_manager.get_current_key()
        key_manager.rotate_key()
        key_v3 = key_manager.get_current_key()

        # All keys should be accessible
        assert key_manager.get_key(version=1) == key_v1
        assert key_manager.get_key(version=2) == key_v2
        assert key_manager.get_key(version=3) == key_v3

    def test_key_deletion_after_re_encryption_complete(self, key_manager):
        """Test old key deletion after data migration."""
        service = UnifiedEncryptionService(key_manager)

        # Rotate and re-encrypt all data
        key_manager.rotate_key()
        service.batch_re_encrypt_all_models(db_session)

        # Mark v1 for deletion
        key_manager.mark_key_for_deletion(version=1)

        # Verify key is in pending deletion state
        assert key_manager.get_key_status(version=1) == "PENDING_DELETION"

        # After grace period (30 days), key should be deleted
        with freeze_time(datetime.utcnow() + timedelta(days=31)):
            key_manager.cleanup_old_keys()
            assert key_manager.get_key(version=1) is None
```

**Estimated Time**: 1 day
**Files Created**: 1
**Security Risk**: Eliminated

---

### Day 4-7: Repository Tests (Priority 1 - Top 5)

#### File 1: `tests/repositories/test_user.py`

```python
"""
Tests for User repository - CRITICAL PATH.

Covers:
- User CRUD operations
- Role management
- Authentication queries
- Active/inactive users
- Email uniqueness
"""
import pytest
from uuid import uuid4

from app.models.user import User, UserRole
from app.repositories.user import UserRepository


class TestUserRepository:
    """Test User repository operations."""

    @pytest.fixture
    def user_repo(self, db_session):
        """Create user repository."""
        return UserRepository(db_session)

    @pytest.fixture
    def sample_user(self):
        """Sample user data."""
        return {
            "email": "test@example.com",
            "name": "Test User",
            "password_hash": "hashed_password",
            "role": UserRole.DOCTOR,
            "is_active": True
        }

    def test_create_user(self, user_repo, sample_user):
        """Test user creation."""
        user = user_repo.create(**sample_user)

        assert user.id is not None
        assert user.email == sample_user["email"]
        assert user.role == UserRole.DOCTOR
        assert user.is_active is True
        assert user.created_at is not None

    def test_create_duplicate_email_raises_error(self, user_repo, sample_user):
        """Test duplicate email constraint."""
        user_repo.create(**sample_user)

        with pytest.raises(IntegrityError):
            user_repo.create(**sample_user)

    def test_find_by_id(self, user_repo, sample_user):
        """Test user lookup by ID."""
        user = user_repo.create(**sample_user)

        found = user_repo.find_by_id(user.id)
        assert found.id == user.id

    def test_find_by_email(self, user_repo, sample_user):
        """Test user lookup by email."""
        user = user_repo.create(**sample_user)

        found = user_repo.find_by_email(sample_user["email"])
        assert found.id == user.id

    def test_find_by_email_case_insensitive(self, user_repo, sample_user):
        """Test email lookup is case-insensitive."""
        user = user_repo.create(**sample_user)

        found = user_repo.find_by_email("TEST@EXAMPLE.COM")
        assert found.id == user.id

    def test_find_active_users(self, user_repo, sample_user):
        """Test filtering active users."""
        active_user = user_repo.create(**sample_user)
        inactive_user = user_repo.create(
            email="inactive@example.com",
            name="Inactive User",
            password_hash="hash",
            role=UserRole.DOCTOR,
            is_active=False
        )

        active_users = user_repo.find_active_users()
        assert len(active_users) == 1
        assert active_users[0].id == active_user.id

    def test_find_by_role(self, user_repo):
        """Test finding users by role."""
        doctor = user_repo.create(
            email="doctor@example.com",
            name="Doctor",
            password_hash="hash",
            role=UserRole.DOCTOR,
            is_active=True
        )
        admin = user_repo.create(
            email="admin@example.com",
            name="Admin",
            password_hash="hash",
            role=UserRole.ADMIN,
            is_active=True
        )

        doctors = user_repo.find_by_role(UserRole.DOCTOR)
        assert len(doctors) == 1
        assert doctors[0].id == doctor.id

    def test_update_user(self, user_repo, sample_user):
        """Test user update."""
        user = user_repo.create(**sample_user)

        updated = user_repo.update(user.id, name="Updated Name")
        assert updated.name == "Updated Name"
        assert updated.email == sample_user["email"]  # Unchanged

    def test_deactivate_user(self, user_repo, sample_user):
        """Test user deactivation."""
        user = user_repo.create(**sample_user)

        deactivated = user_repo.deactivate(user.id)
        assert deactivated.is_active is False

    def test_delete_user(self, user_repo, sample_user):
        """Test user soft delete."""
        user = user_repo.create(**sample_user)

        user_repo.delete(user.id)

        # Verify soft delete (marked as deleted, not actually removed)
        deleted_user = user_repo.find_by_id(user.id)
        assert deleted_user.deleted_at is not None

    def test_count_users_by_role(self, user_repo):
        """Test user count aggregation by role."""
        for i in range(3):
            user_repo.create(
                email=f"doctor{i}@example.com",
                name=f"Doctor {i}",
                password_hash="hash",
                role=UserRole.DOCTOR,
                is_active=True
            )

        for i in range(2):
            user_repo.create(
                email=f"admin{i}@example.com",
                name=f"Admin {i}",
                password_hash="hash",
                role=UserRole.ADMIN,
                is_active=True
            )

        counts = user_repo.count_by_role()
        assert counts[UserRole.DOCTOR] == 3
        assert counts[UserRole.ADMIN] == 2
```

**Continue with similar comprehensive tests for:**
- `test_message.py`
- `test_quiz.py`
- `test_appointment.py`
- `test_medication.py`

**Estimated Time**: 4 days (0.8 days per repository)
**Files Created**: 5
**Coverage Impact**: +40% for repository layer

---

## Week 2: Complete Repository Tests (Days 8-14)

### Remaining Repository Tests (14 files)

Create tests for:
1. `test_treatment.py`
2. `test_consent.py`
3. `test_notification.py`
4. `test_alert.py`
5. `test_flow.py`
6. `test_flow_template.py`
7. `test_flow_template_version.py`
8. `test_flow_analytics.py`
9. `test_session.py`
10. `test_report.py`
11. `test_template.py`
12. `test_base.py`
13. `test_base_v2.py`
14. `test_connection_state.py`

**Template for Each Test File**:

```python
"""
Tests for [Model] repository.

Coverage:
- CRUD operations (create, read, update, delete)
- Query methods (filters, sorting, pagination)
- Relationship loading (eager vs lazy)
- Constraint validation (unique, foreign key)
- Transaction handling
- Concurrent access
- Performance (N+1 query prevention)
"""
import pytest
from uuid import uuid4
from datetime import datetime

from app.models.[model] import [Model]
from app.repositories.[repository] import [Repository]


class Test[Model]Repository:
    """Test [Model] repository operations."""

    # Standard test methods:
    # 1. test_create_[model]
    # 2. test_create_duplicate_raises_error
    # 3. test_find_by_id
    # 4. test_find_by_[unique_field]
    # 5. test_find_all_with_filters
    # 6. test_find_with_pagination
    # 7. test_update_[model]
    # 8. test_delete_[model]
    # 9. test_count_[model]
    # 10. test_bulk_operations
    # 11. test_relationship_loading
    # 12. test_query_performance
    # 13. test_concurrent_updates
    # 14. test_constraint_violations
```

**Estimated Time**: 7 days (0.5 days per repository)
**Files Created**: 14
**Coverage Impact**: Repository layer reaches 90%+

---

## Week 3-4: Critical Service Tests (Days 15-28)

### Top 10 Critical Services

#### Service 1: `tests/services/ai/test_ai_service.py`

```python
"""
Tests for AI Service - CRITICAL PATH.

Covers:
- Patient summary generation
- Risk assessment
- AI response quality
- Token usage optimization
- Error handling (API failures)
- Rate limiting
- Caching strategy
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from app.services.ai.ai_service import AIService


class TestAIService:
    """Test AI service operations."""

    @pytest.fixture
    def ai_service(self):
        """Create AI service with mock client."""
        service = AIService()
        service.client = Mock()
        return service

    @pytest.mark.asyncio
    async def test_generate_patient_summary(self, ai_service):
        """Test patient summary generation."""
        patient_data = {
            "name": "John Doe",
            "age": 45,
            "diagnosis": "Stage II Breast Cancer",
            "treatments": ["Chemotherapy", "Radiation"]
        }

        with patch.object(ai_service, '_call_ai_api', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "Patient summary text..."

            summary = await ai_service.generate_summary(patient_data)

            assert "John Doe" in summary
            assert "Stage II" in summary
            mock_api.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_risk_assessment(self, ai_service):
        """Test risk assessment calculation."""
        patient_data = {
            "symptoms": ["fever", "fatigue"],
            "vitals": {"temperature": 38.5},
            "medications": ["chemotherapy"]
        }

        risk = await ai_service.assess_risk(patient_data)

        assert risk["level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert 0 <= risk["score"] <= 100
        assert "reasons" in risk

    @pytest.mark.asyncio
    async def test_ai_api_failure_handling(self, ai_service):
        """Test graceful handling of AI API failures."""
        with patch.object(ai_service, '_call_ai_api', new_callable=AsyncMock) as mock_api:
            mock_api.side_effect = TimeoutError("API timeout")

            with pytest.raises(AIServiceError) as exc:
                await ai_service.generate_summary({})

            assert "timeout" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_token_usage_tracking(self, ai_service):
        """Test token usage is tracked and limited."""
        patient_data = {"name": "Test"}

        with patch.object(ai_service, '_call_ai_api', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "Summary"

            await ai_service.generate_summary(patient_data)

            # Check token usage was logged
            assert ai_service.total_tokens_used > 0

    @pytest.mark.asyncio
    async def test_summary_caching(self, ai_service, redis_mock):
        """Test summaries are cached to reduce API calls."""
        patient_id = str(uuid4())
        patient_data = {"id": patient_id, "name": "Test"}

        # First call - cache miss
        with patch.object(ai_service, '_call_ai_api', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "Cached summary"

            summary1 = await ai_service.generate_summary(patient_data)
            assert mock_api.await_count == 1

        # Second call - cache hit (no API call)
        with patch.object(ai_service, '_call_ai_api', new_callable=AsyncMock) as mock_api:
            summary2 = await ai_service.generate_summary(patient_data)
            assert mock_api.await_count == 0

        assert summary1 == summary2

    @pytest.mark.asyncio
    async def test_rate_limiting(self, ai_service):
        """Test rate limiting prevents API abuse."""
        # Make many requests rapidly
        tasks = [ai_service.generate_summary({"name": "Test"}) for _ in range(100)]

        # Should throttle after rate limit
        with pytest.raises(RateLimitExceeded):
            await asyncio.gather(*tasks)

    def test_prompt_template_validation(self, ai_service):
        """Test AI prompt templates are valid."""
        template = ai_service.get_prompt_template("patient_summary")

        assert "{patient_name}" in template
        assert "{diagnosis}" in template
        assert len(template) < 4000  # Token limit
```

**Continue with:**
- `test_patient_summary_service.py`
- `test_quiz_service.py`
- `test_firebase_auth_service.py`
- `test_firebase_user_sync_service.py`
- `test_patient_creation_service.py`
- `test_patient_crud_service.py`
- `test_patient_flow_service.py`
- `test_medico_stats_service.py`
- `test_admin_stats_service.py`

**Estimated Time**: 14 days (1.4 days per service)
**Files Created**: 10
**Coverage Impact**: +30% for service layer

---

## Week 5-6: API Router Tests (Days 29-42)

### Top 10 Missing API Tests

Template structure:

```python
"""
Tests for [Router] API endpoints.

Coverage:
- Success scenarios (200, 201, 204)
- Error handling (400, 401, 403, 404, 500)
- Input validation
- Authentication/authorization
- Rate limiting
- Response format
- Edge cases
"""
import pytest
from fastapi.testclient import TestClient


class Test[Router]API:
    """Test [Router] API endpoints."""

    def test_endpoint_requires_authentication(self, client):
        """Test endpoint rejects unauthenticated requests."""
        response = client.get("/api/v2/[endpoint]")
        assert response.status_code == 401

    def test_endpoint_success(self, client, auth_headers):
        """Test successful request."""
        response = client.get(
            "/api/v2/[endpoint]",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "data" in response.json()

    def test_endpoint_validation_error(self, client, auth_headers):
        """Test input validation."""
        response = client.post(
            "/api/v2/[endpoint]",
            headers=auth_headers,
            json={"invalid": "data"}
        )
        assert response.status_code == 422

    def test_endpoint_not_found(self, client, auth_headers):
        """Test 404 for non-existent resource."""
        response = client.get(
            f"/api/v2/[endpoint]/{uuid4()}",
            headers=auth_headers
        )
        assert response.status_code == 404

    def test_endpoint_pagination(self, client, auth_headers):
        """Test pagination works correctly."""
        response = client.get(
            "/api/v2/[endpoint]?page=1&page_size=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) <= 10
```

Create for:
1. `test_monthly_quiz_operations.py`
2. `test_health_endpoints.py`
3. `test_medications.py`
4. `test_treatments.py`
5. `test_appointments.py`
6. `test_notifications.py`
7. `test_csp_report.py`
8. `test_flow_templates.py`
9. `test_debug_endpoints.py`
10. `test_enhanced_messages_endpoints.py`

**Estimated Time**: 14 days (1.4 days per router)
**Files Created**: 10
**Coverage Impact**: API layer reaches 80%+

---

## Week 7-8: Edge Cases & Security (Days 43-56)

### Edge Case Tests

```python
# tests/edge_cases/test_network_failures.py
class TestNetworkFailures:
    def test_database_connection_timeout(self):
        """Test handling of database timeouts."""
        pass

    def test_redis_connection_failure(self):
        """Test fallback when Redis unavailable."""
        pass

    def test_external_api_timeout(self):
        """Test retry logic for API timeouts."""
        pass

# tests/edge_cases/test_data_corruption.py
class TestDataCorruption:
    def test_invalid_utf8_handling(self):
        """Test handling of invalid UTF-8 sequences."""
        pass

    def test_malformed_json_parsing(self):
        """Test graceful handling of malformed JSON."""
        pass

# tests/edge_cases/test_resource_exhaustion.py
class TestResourceExhaustion:
    def test_connection_pool_exhaustion(self):
        """Test behavior when connection pool is full."""
        pass

    def test_memory_pressure(self):
        """Test memory cleanup under pressure."""
        pass
```

### Security Tests

```python
# tests/security/test_sql_injection.py
class TestSQLInjection:
    def test_sql_injection_in_search(self):
        """Test SQL injection prevention in search."""
        malicious_input = "'; DROP TABLE users; --"
        response = client.get(f"/api/v2/patients?search={malicious_input}")
        assert response.status_code in [200, 400]
        # Verify tables still exist

# tests/security/test_xss_prevention.py
class TestXSSPrevention:
    def test_xss_script_sanitization(self):
        """Test XSS script tags are sanitized."""
        xss_payload = '<script>alert("XSS")</script>'
        response = client.post("/api/v2/patients", json={"name": xss_payload})
        # Verify response doesn't contain script tags

# tests/security/test_rate_limiting.py
class TestRateLimiting:
    def test_api_rate_limit_enforcement(self):
        """Test rate limiting prevents abuse."""
        for _ in range(100):
            response = client.get("/api/v2/patients")
        # Should eventually return 429
```

**Estimated Time**: 14 days
**Files Created**: 15-20
**Coverage Impact**: Security and edge case coverage

---

## Week 9-10: Infrastructure & Documentation (Days 57-70)

### Tasks

1. **Standardize Test Organization**
   - Create test templates
   - Document naming conventions
   - Standardize markers

2. **Add Coverage Tracking**
   ```bash
   pip install pytest-cov coverage
   pytest --cov=app --cov-report=html --cov-report=term
   ```

3. **CI/CD Integration**
   - Add coverage reports to CI
   - Set minimum coverage thresholds
   - Fail builds below 80%

4. **Documentation**
   - Update README with test instructions
   - Create TESTING.md guide
   - Document test fixtures

5. **Test Automation**
   - Set up pre-commit hooks for tests
   - Add test database automation
   - Configure parallel test execution

**Estimated Time**: 14 days

---

## Success Metrics

### Week 1
- ✅ 18 skipped tests fixed
- ✅ Key rotation tests implemented
- ✅ 5 repository tests created

### Week 2
- ✅ All 19 repository tests completed
- ✅ Repository coverage: 90%+

### Week 3-4
- ✅ 10 critical service tests created
- ✅ Service coverage: 55%+

### Week 5-6
- ✅ 10 API router tests created
- ✅ API coverage: 80%+

### Week 7-8
- ✅ Edge case coverage: 70%+
- ✅ Security test suite created

### Week 9-10
- ✅ Test infrastructure complete
- ✅ Documentation complete
- ✅ CI/CD integration complete

### Final Target
- **Overall Coverage**: 85%+
- **Repository Coverage**: 90%+
- **Service Coverage**: 80%+
- **API Coverage**: 85%+
- **Skipped Tests**: 0
- **TODO Comments**: <10
- **Empty Tests**: 0

---

## Resource Requirements

### Team
- 2 developers (full-time for 10 weeks)
- 1 QA engineer (part-time for reviews)
- 1 tech lead (for architecture decisions)

### Tools
- pytest, pytest-cov, pytest-asyncio
- coverage.py
- pytest-xdist (parallel execution)
- faker (test data generation)
- factory_boy (model factories)

### Infrastructure
- CI/CD pipeline updates
- Test database automation
- Coverage tracking dashboard

---

**Total Estimated Effort**: 70 days (2 developers × 5 weeks)
**Expected Outcome**: 85% overall test coverage, production-ready test suite
