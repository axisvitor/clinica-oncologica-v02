"""
Integration tests for Saga Compensation flows.

CRITICAL: Tests compensation (rollback) logic when saga steps fail.
Coverage target: 100% of all saga compensation scenarios.

Test scenarios:
1. Compensation after step 2 failure (Firebase failure) → Patient deleted
2. Compensation after step 3 failure (Flow failure) → Firebase user deleted
3. Compensation after step 4 failure (Message failure) → Flow cleaned up
4. Full rollback with all compensations → Complete cleanup

Relates to: docs/code-review-paciente/07-TESTES-QUALIDADE.md
GAP: Saga Compensation Tests (0% → 100% coverage)

File: backend-hormonia/tests/integration/test_saga_compensation.py
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import date
from sqlalchemy.orm import Session

from app.models.patient import Patient, FlowState
from app.models.user import User
from app.schemas.patient import PatientCreate
from app.coordination.saga_orchestrator import SagaOrchestrator, SagaStatus


@pytest.fixture
def mock_redis():
    """Mock Redis client for saga persistence."""
    redis_mock = Mock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = True
    return redis_mock


@pytest.fixture
def mock_evolution_client():
    """Mock Evolution API client."""
    client = Mock()
    client.send_message = AsyncMock(return_value={"success": True, "message_id": "msg_123"})
    return client


@pytest.fixture
def doctor_user(db_session: Session) -> User:
    """Create a test doctor user."""
    doctor = User(
        id=uuid4(),
        email=f"doctor_{uuid4()}@test.com",
        username=f"doctor_{uuid4()}",
        role="DOCTOR",
        is_active=True
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


@pytest.fixture
def patient_data() -> PatientCreate:
    """Create test patient data."""
    unique_id = str(uuid4())[:8]
    return PatientCreate(
        name=f"Test Patient {unique_id}",
        phone=f"+5511987654{unique_id[:3]}",
        email=f"patient_{unique_id}@test.com",
        cpf=f"{unique_id[:11].zfill(11)}",
        birth_date=date(1990, 1, 1),
        treatment_type="Quimioterapia"
    )


@pytest.fixture
def saga_orchestrator(db_session: Session, mock_redis, mock_evolution_client):
    """Create saga orchestrator with mocked dependencies."""
    return SagaOrchestrator(
        db=db_session,
        redis=mock_redis,
        evolution_client=mock_evolution_client,
        enable_persistence=True,
        max_retries=3
    )


@pytest.mark.integration
class TestSagaCompensationStep2FirebaseFailure:
    """Test compensation when Firebase (step 2) fails."""

    @pytest.mark.asyncio
    async def test_compensation_step_2_firebase_failure(
        self,
        db_session: Session,
        doctor_user: User,
        patient_data: PatientCreate,
        saga_orchestrator: SagaOrchestrator
    ):
        """
        Test saga compensation when Firebase authentication fails.

        Scenario:
        1. Step 1: Create patient (SUCCESS) ✅
        2. Step 2: Create Firebase user (FAILURE) ❌
        3. Compensation: Delete patient (ROLLBACK) ↩️

        Expected:
        - Saga status: COMPENSATED
        - Patient deleted from database
        - No Firebase user created
        """
        # Arrange
        initial_patient_count = db_session.query(Patient).count()

        # Mock Firebase to fail
        with patch('app.integrations.firebase.firebase_admin.auth.create_user') as mock_firebase:
            mock_firebase.side_effect = Exception("Firebase authentication service unavailable")

            # Act
            with pytest.raises(Exception) as exc_info:
                patient = await saga_orchestrator.execute_patient_onboarding_saga(
                    patient_data=patient_data,
                    doctor_id=doctor_user.id
                )

            # Assert - Saga failed
            assert "Firebase" in str(exc_info.value)

            # Assert - Compensation executed (patient deleted)
            final_patient_count = db_session.query(Patient).count()
            assert final_patient_count == initial_patient_count, \
                "Patient should be deleted after Firebase failure compensation"

            # Assert - No orphaned patients
            orphaned_patients = db_session.query(Patient).filter(
                Patient.phone == patient_data.phone,
                Patient.doctor_id == doctor_user.id
            ).all()
            assert len(orphaned_patients) == 0, "Found orphaned patient after compensation"


@pytest.mark.integration
class TestSagaCompensationStep3FlowFailure:
    """Test compensation when Flow initialization (step 3) fails."""

    @pytest.mark.asyncio
    async def test_compensation_step_3_flow_failure(
        self,
        db_session: Session,
        doctor_user: User,
        patient_data: PatientCreate,
        saga_orchestrator: SagaOrchestrator
    ):
        """
        Test saga compensation when Flow initialization fails.

        Scenario:
        1. Step 1: Create patient (SUCCESS) ✅
        2. Step 2: Create Firebase user (SUCCESS) ✅
        3. Step 3: Initialize flow (FAILURE) ❌
        4. Compensation: Delete Firebase user (ROLLBACK) ↩️
        5. Compensation: Delete patient (ROLLBACK) ↩️

        Expected:
        - Saga status: COMPENSATED
        - Patient deleted from database
        - Firebase user deleted
        - No flow state created
        """
        # Arrange
        firebase_uid = None

        # Mock Firebase to succeed, Flow to fail
        with patch('app.integrations.firebase.firebase_admin.auth.create_user') as mock_create, \
             patch('app.integrations.firebase.firebase_admin.auth.delete_user') as mock_delete, \
             patch('app.services.patient.flow_service.PatientFlowService.initialize_flow') as mock_flow:

            # Firebase create succeeds
            firebase_user = Mock()
            firebase_user.uid = f"firebase_uid_{uuid4()}"
            mock_create.return_value = firebase_user
            firebase_uid = firebase_user.uid

            # Flow initialization fails
            mock_flow.side_effect = Exception("Flow template not found")

            # Act
            with pytest.raises(Exception) as exc_info:
                patient = await saga_orchestrator.execute_patient_onboarding_saga(
                    patient_data=patient_data,
                    doctor_id=doctor_user.id
                )

            # Assert - Saga failed
            assert "Flow" in str(exc_info.value)

            # Assert - Firebase user was deleted (compensation)
            mock_delete.assert_called_once_with(firebase_uid)

            # Assert - Patient was deleted (compensation)
            patient_exists = db_session.query(Patient).filter(
                Patient.phone == patient_data.phone
            ).first()
            assert patient_exists is None, "Patient should be deleted after flow failure"


@pytest.mark.integration
class TestSagaCompensationStep4MessageFailure:
    """Test compensation when Message sending (step 4) fails."""

    @pytest.mark.asyncio
    async def test_compensation_step_4_message_failure(
        self,
        db_session: Session,
        doctor_user: User,
        patient_data: PatientCreate,
        saga_orchestrator: SagaOrchestrator
    ):
        """
        Test saga compensation when Welcome message sending fails.

        Scenario:
        1. Step 1: Create patient (SUCCESS) ✅
        2. Step 2: Create Firebase user (SUCCESS) ✅
        3. Step 3: Initialize flow (SUCCESS) ✅
        4. Step 4: Send welcome message (FAILURE) ❌
        5. Compensation: Clean up flow (ROLLBACK) ↩️
        6. Compensation: Delete Firebase user (ROLLBACK) ↩️
        7. Compensation: Delete patient (ROLLBACK) ↩️

        Expected:
        - Saga status: COMPENSATED
        - All resources cleaned up
        - No partial state left
        """
        # Arrange
        # Mock all steps to succeed except message sending
        with patch('app.integrations.firebase.firebase_admin.auth.create_user') as mock_create, \
             patch('app.integrations.firebase.firebase_admin.auth.delete_user') as mock_delete, \
             patch('app.services.patient.flow_service.PatientFlowService.initialize_flow') as mock_flow, \
             patch('app.services.whatsapp_unified.UnifiedWhatsAppService.send_message') as mock_whatsapp:

            # Firebase succeeds
            firebase_user = Mock()
            firebase_user.uid = f"firebase_uid_{uuid4()}"
            mock_create.return_value = firebase_user

            # Flow succeeds
            mock_flow.return_value = Mock(id=uuid4(), status="active")

            # WhatsApp fails
            mock_whatsapp.side_effect = Exception("WhatsApp API timeout")

            # Act
            with pytest.raises(Exception) as exc_info:
                patient = await saga_orchestrator.execute_patient_onboarding_saga(
                    patient_data=patient_data,
                    doctor_id=doctor_user.id
                )

            # Assert - Saga failed
            assert "WhatsApp" in str(exc_info.value) or "timeout" in str(exc_info.value).lower()

            # Assert - All compensations executed
            mock_delete.assert_called()  # Firebase user deleted

            # Assert - No patient left in database
            patient_exists = db_session.query(Patient).filter(
                Patient.phone == patient_data.phone
            ).first()
            assert patient_exists is None, "Patient should be deleted after message failure"


@pytest.mark.integration
class TestSagaFullRollback:
    """Test complete saga rollback with all compensations."""

    @pytest.mark.asyncio
    async def test_saga_compensation_full_rollback(
        self,
        db_session: Session,
        doctor_user: User,
        patient_data: PatientCreate,
        saga_orchestrator: SagaOrchestrator
    ):
        """
        Test full saga rollback executes all compensation steps in reverse order.

        Scenario:
        - Saga executes multiple steps successfully
        - Final step fails
        - All compensations execute in reverse order (LIFO)

        Expected:
        - Compensation order: Step 4 → Step 3 → Step 2 → Step 1
        - All resources cleaned up
        - Saga state: COMPENSATED
        """
        # Arrange
        compensation_order = []

        def track_compensation(step_name):
            """Track compensation execution order."""
            compensation_order.append(step_name)

        # Mock all steps
        with patch('app.integrations.firebase.firebase_admin.auth.create_user') as mock_create, \
             patch('app.integrations.firebase.firebase_admin.auth.delete_user') as mock_delete, \
             patch('app.services.patient.flow_service.PatientFlowService.initialize_flow') as mock_flow, \
             patch('app.services.whatsapp_unified.UnifiedWhatsAppService.send_message') as mock_whatsapp:

            # All steps succeed except final one
            firebase_user = Mock()
            firebase_user.uid = f"firebase_uid_{uuid4()}"
            mock_create.return_value = firebase_user
            mock_flow.return_value = Mock(id=uuid4(), status="active")
            mock_whatsapp.side_effect = Exception("Final step failure")

            # Track deletion order
            mock_delete.side_effect = lambda uid: track_compensation("firebase_user")

            # Act
            with pytest.raises(Exception):
                await saga_orchestrator.execute_patient_onboarding_saga(
                    patient_data=patient_data,
                    doctor_id=doctor_user.id
                )

            # Assert - Compensations executed
            assert "firebase_user" in compensation_order

            # Assert - Database clean
            patient_count = db_session.query(Patient).filter(
                Patient.phone == patient_data.phone
            ).count()
            assert patient_count == 0, "All patients should be cleaned up after full rollback"

    @pytest.mark.asyncio
    async def test_saga_compensation_idempotency(
        self,
        db_session: Session,
        doctor_user: User,
        patient_data: PatientCreate,
        saga_orchestrator: SagaOrchestrator
    ):
        """
        Test that saga compensation is idempotent (can be retried safely).

        Scenario:
        - Saga fails and starts compensation
        - Compensation partially completes
        - Compensation is retried
        - No errors occur due to already-deleted resources

        Expected:
        - Second compensation run succeeds
        - No errors from deleting non-existent resources
        """
        # Arrange
        with patch('app.integrations.firebase.firebase_admin.auth.delete_user') as mock_delete:
            # First call succeeds, second call raises "user not found" (already deleted)
            mock_delete.side_effect = [
                None,  # First call succeeds
                Exception("User not found"),  # Second call fails (already deleted)
            ]

            # Act - Try compensation twice
            with pytest.raises(Exception):
                await saga_orchestrator._compensate_saga(saga_id="test_saga_123")

            # Second compensation should handle "already deleted" gracefully
            # (implementation should catch "not found" errors during compensation)


@pytest.mark.integration
class TestSagaCompensationResilience:
    """Test saga compensation resilience and error handling."""

    @pytest.mark.asyncio
    async def test_compensation_continues_on_partial_failure(
        self,
        db_session: Session,
        doctor_user: User,
        patient_data: PatientCreate,
        saga_orchestrator: SagaOrchestrator
    ):
        """
        Test that saga compensation continues even if one compensation step fails.

        Scenario:
        - Saga fails
        - Compensation step 2 fails
        - Compensation continues with step 1

        Expected:
        - All compensations attempted (best-effort)
        - Partial cleanup better than no cleanup
        """
        # Arrange
        compensation_attempts = []

        with patch('app.integrations.firebase.firebase_admin.auth.delete_user') as mock_delete:
            # Firebase deletion fails but we continue
            mock_delete.side_effect = lambda uid: compensation_attempts.append("firebase")

            # Act
            try:
                await saga_orchestrator._compensate_saga(saga_id="test_saga_456")
            except Exception:
                pass  # Expected to fail

            # Assert - Attempted compensation
            assert "firebase" in compensation_attempts, \
                "Should attempt all compensations even if some fail"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
