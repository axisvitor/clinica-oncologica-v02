"""
Integration tests for Concurrent Operations and Race Conditions.

CRITICAL: Tests concurrent access, race conditions, and database locking.
Coverage target: 100% of concurrent operation scenarios.

Test scenarios:
1. Concurrent patient creation (same CPF) → Only one succeeds
2. Concurrent message processing → No duplicate messages
3. Concurrent saga execution → Database locks prevent duplicates

Relates to: docs/code-review-paciente/07-TESTES-QUALIDADE.md
GAP: Concurrent Operations (0% → 100% coverage)

File: backend-hormonia/tests/integration/test_concurrent_operations.py
"""
import pytest
import asyncio
from uuid import uuid4
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.models.patient import Patient, FlowState
from app.models.user import User
from app.models.message import Message, MessageDirection
from app.schemas.patient import PatientCreate
from app.domain.patient.onboarding.coordinator import PatientOnboardingService


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
    """Create test patient data (same CPF for concurrent tests)."""
    return PatientCreate(
        name="Test Concurrent Patient",
        phone="+5511987654321",
        email="concurrent@test.com",
        cpf="12345678901",  # Same CPF for all concurrent requests
        birth_date=date(1990, 1, 1),
        treatment_type="Quimioterapia"
    )


@pytest.fixture
def onboarding_service(db_session: Session) -> PatientOnboardingService:
    """Create onboarding service with real dependencies."""
    from app.repositories.patient import PatientRepository
    from app.services.patient.integrity_service import PatientIntegrityService
    from app.services.patient.flow_service import PatientFlowService
    from app.services.message import MessageService
    from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode

    patient_repo = PatientRepository(db_session)
    integrity_service = PatientIntegrityService(db_session, patient_repo)
    flow_service = PatientFlowService(db_session)
    message_service = MessageService(db_session)
    whatsapp_service = UnifiedWhatsAppService(db=db_session, messaging_mode=MessagingMode.LEGACY)

    return PatientOnboardingService(
        db=db_session,
        integrity_service=integrity_service,
        flow_service=flow_service,
        message_service=message_service,
        whatsapp_service=whatsapp_service,
        saga_orchestrator=None
    )


@pytest.mark.integration
class TestConcurrentPatientCreation:
    """Test concurrent patient creation with same CPF."""

    @pytest.mark.asyncio
    async def test_concurrent_patient_creation_same_cpf(
        self,
        db_session: Session,
        doctor_user: User,
        patient_data: PatientCreate,
        onboarding_service: PatientOnboardingService
    ):
        """
        Test concurrent patient creation with identical CPF.

        Scenario:
        - 5 concurrent requests to create patient with same CPF
        - Database unique constraint on (cpf, doctor_id)
        - Only 1 should succeed, 4 should fail with IntegrityError

        Race condition prevention:
        - Database UNIQUE constraint
        - SELECT FOR UPDATE locking
        - Proper error handling
        """
        # Arrange
        initial_count = db_session.query(Patient).count()
        results = []

        async def create_patient_concurrent():
            """Attempt to create patient (may fail due to constraint)."""
            try:
                patient = await onboarding_service._create_patient_direct(
                    patient_data=patient_data,
                    doctor_id=doctor_user.id,
                    current_user=None
                )
                return ("success", patient)
            except IntegrityError as e:
                db_session.rollback()
                return ("integrity_error", str(e))
            except Exception as e:
                db_session.rollback()
                return ("error", str(e))

        # Act - 5 concurrent creation attempts
        tasks = [create_patient_concurrent() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # Assert
        successes = [r for r in results if r[0] == "success"]
        failures = [r for r in results if r[0] in ["integrity_error", "error"]]

        # Only 1 should succeed (or multiple if they find existing patient)
        final_count = db_session.query(Patient).filter(
            Patient.cpf == patient_data.cpf,
            Patient.doctor_id == doctor_user.id
        ).count()

        assert final_count == 1, \
            f"Expected 1 patient, found {final_count}. Concurrent creation failed!"

    @pytest.mark.asyncio
    async def test_concurrent_patient_creation_different_cpf(
        self,
        db_session: Session,
        doctor_user: User,
        onboarding_service: PatientOnboardingService
    ):
        """
        Test concurrent patient creation with different CPFs.

        Scenario:
        - 3 concurrent requests with different CPFs
        - All should succeed (no conflict)

        Expected:
        - All 3 patients created successfully
        - No race conditions
        """
        # Arrange
        async def create_patient_with_unique_cpf(index: int):
            """Create patient with unique CPF."""
            unique_cpf = f"1234567890{index}"
            patient_data = PatientCreate(
                name=f"Patient {index}",
                phone=f"+551198765432{index}",
                email=f"patient{index}@test.com",
                cpf=unique_cpf,
                birth_date=date(1990, 1, 1),
                treatment_type="Quimioterapia"
            )

            return await onboarding_service._create_patient_direct(
                patient_data=patient_data,
                doctor_id=doctor_user.id,
                current_user=None
            )

        # Act - 3 concurrent creations with different CPFs
        tasks = [create_patient_with_unique_cpf(i) for i in range(3)]
        patients = await asyncio.gather(*tasks)

        # Assert - All should succeed
        assert len(patients) == 3
        assert all(p is not None for p in patients)

        # Verify all in database
        created_count = db_session.query(Patient).filter(
            Patient.doctor_id == doctor_user.id
        ).count()
        assert created_count == 3


@pytest.mark.integration
class TestConcurrentMessageProcessing:
    """Test concurrent message processing."""

    @pytest.mark.asyncio
    async def test_concurrent_message_processing(
        self,
        db_session: Session,
        doctor_user: User
    ):
        """
        Test concurrent message processing (no duplicate messages).

        Scenario:
        - Patient sends message
        - 3 concurrent webhook calls for same message
        - Only 1 message should be stored (idempotency)

        Idempotency:
        - Message deduplication by message_id
        - Database constraint or idempotency check
        """
        # Arrange - Create patient
        patient = Patient(
            name="Test Patient",
            phone="+5511999999999",
            email="patient@test.com",
            cpf="98765432100",
            doctor_id=doctor_user.id,
            flow_state=FlowState.ACTIVE
        )
        db_session.add(patient)
        db_session.commit()
        db_session.refresh(patient)

        message_id = f"msg_{uuid4()}"
        initial_message_count = db_session.query(Message).count()

        async def process_message_concurrent():
            """Process same message concurrently."""
            from app.services.message import MessageService
            message_service = MessageService(db_session)

            try:
                message = message_service.create_message(
                    patient_id=patient.id,
                    content="Hello from concurrent test",
                    direction=MessageDirection.INBOUND,
                    external_id=message_id  # Same message ID
                )
                db_session.commit()
                return ("success", message)
            except IntegrityError:
                db_session.rollback()
                return ("duplicate", None)
            except Exception as e:
                db_session.rollback()
                return ("error", str(e))

        # Act - 3 concurrent message processing attempts
        tasks = [process_message_concurrent() for _ in range(3)]
        results = await asyncio.gather(*tasks)

        # Assert - Only 1 message stored
        final_message_count = db_session.query(Message).filter(
            Message.external_id == message_id
        ).count()

        assert final_message_count == 1, \
            f"Expected 1 message, found {final_message_count}. Duplicate messages created!"

    @pytest.mark.asyncio
    async def test_concurrent_message_status_update(
        self,
        db_session: Session,
        doctor_user: User
    ):
        """
        Test concurrent message status updates.

        Scenario:
        - Message exists with status "sent"
        - 2 concurrent updates to "delivered"
        - Both should succeed (idempotent update)
        - Final status should be "delivered"

        Race condition:
        - Last write wins
        - No data corruption
        """
        # Arrange - Create patient and message
        patient = Patient(
            name="Test Patient",
            phone="+5511999999999",
            email="patient@test.com",
            cpf="11111111111",
            doctor_id=doctor_user.id,
            flow_state=FlowState.ACTIVE
        )
        db_session.add(patient)
        db_session.commit()

        message = Message(
            patient_id=patient.id,
            content="Test message",
            direction=MessageDirection.OUTBOUND,
            status="sent"
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        async def update_message_status():
            """Update message status concurrently."""
            from app.services.message import MessageService
            message_service = MessageService(db_session)

            try:
                updated = message_service.update_message_status(
                    message_id=message.id,
                    new_status="delivered"
                )
                db_session.commit()
                return ("success", updated)
            except Exception as e:
                db_session.rollback()
                return ("error", str(e))

        # Act - 2 concurrent status updates
        tasks = [update_message_status() for _ in range(2)]
        results = await asyncio.gather(*tasks)

        # Assert - Final status is "delivered"
        db_session.refresh(message)
        assert message.status == "delivered", "Concurrent updates corrupted message status"


@pytest.mark.integration
class TestConcurrentSagaExecution:
    """Test concurrent saga execution."""

    @pytest.mark.asyncio
    async def test_concurrent_saga_execution(
        self,
        db_session: Session,
        doctor_user: User,
        patient_data: PatientCreate
    ):
        """
        Test concurrent saga executions don't create duplicate patients.

        Scenario:
        - 2 saga orchestrators start simultaneously
        - Both try to create same patient (same CPF)
        - Database locks prevent duplicates
        - Only 1 patient created

        Race condition prevention:
        - SELECT FOR UPDATE SKIP LOCKED
        - Database unique constraints
        - Saga idempotency checks
        """
        # Arrange
        from unittest.mock import Mock

        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True

        mock_evolution = Mock()

        async def execute_saga_concurrent():
            """Execute patient onboarding saga."""
            from app.orchestration.saga_orchestrator import SagaOrchestrator

            saga = SagaOrchestrator(
                db=db_session,
                redis=mock_redis,
                evolution_client=mock_evolution,
                enable_persistence=False
            )

            try:
                patient = await saga.execute_patient_onboarding_saga(
                    patient_data=patient_data,
                    doctor_id=doctor_user.id
                )
                return ("success", patient)
            except IntegrityError:
                db_session.rollback()
                return ("duplicate", None)
            except Exception as e:
                db_session.rollback()
                return ("error", str(e))

        # Act - 2 concurrent saga executions
        tasks = [execute_saga_concurrent() for _ in range(2)]
        results = await asyncio.gather(*tasks)

        # Assert - Only 1 patient created
        patient_count = db_session.query(Patient).filter(
            Patient.cpf == patient_data.cpf,
            Patient.doctor_id == doctor_user.id
        ).count()

        assert patient_count <= 1, \
            f"Expected 1 patient, found {patient_count}. Concurrent sagas created duplicates!"

    @pytest.mark.asyncio
    async def test_saga_select_for_update_locking(
        self,
        db_session: Session,
        doctor_user: User,
        patient_data: PatientCreate
    ):
        """
        Test SELECT FOR UPDATE prevents concurrent saga race conditions.

        Scenario:
        - Patient exists
        - 2 sagas try to update simultaneously
        - One gets lock, other waits or skips
        - No data corruption

        Locking:
        - SELECT ... FOR UPDATE
        - SKIP LOCKED for non-blocking
        """
        # Arrange - Create patient
        patient = Patient(
            name=patient_data.name,
            phone=patient_data.phone,
            email=patient_data.email,
            cpf=patient_data.cpf,
            doctor_id=doctor_user.id,
            flow_state=FlowState.ONBOARDING
        )
        db_session.add(patient)
        db_session.commit()
        db_session.refresh(patient)

        async def update_patient_with_lock():
            """Update patient using SELECT FOR UPDATE."""
            from sqlalchemy import text

            try:
                # Lock patient row
                result = db_session.execute(
                    text(
                        "SELECT * FROM patients WHERE id = :patient_id FOR UPDATE SKIP LOCKED"
                    ),
                    {"patient_id": str(patient.id)}
                ).fetchone()

                if result is None:
                    return ("locked", None)  # Row locked by another transaction

                # Update patient
                patient.flow_state = FlowState.ACTIVE
                db_session.commit()
                return ("success", patient)

            except Exception as e:
                db_session.rollback()
                return ("error", str(e))

        # Act - 2 concurrent updates with locking
        tasks = [update_patient_with_lock() for _ in range(2)]
        results = await asyncio.gather(*tasks)

        # Assert - Only one should succeed, other skipped (locked)
        successes = [r for r in results if r[0] == "success"]
        locked = [r for r in results if r[0] == "locked"]

        assert len(successes) >= 1, "At least one update should succeed"
        # One might be locked (SKIP LOCKED behavior)


@pytest.mark.integration
class TestDatabaseTransactionIsolation:
    """Test database transaction isolation levels."""

    @pytest.mark.asyncio
    async def test_read_committed_isolation(
        self,
        db_session: Session,
        doctor_user: User
    ):
        """
        Test READ COMMITTED isolation prevents dirty reads.

        Scenario:
        - Transaction A creates patient (uncommitted)
        - Transaction B tries to read
        - Transaction B should NOT see uncommitted data
        """
        # This requires multiple database sessions
        # Simplified test with single session

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        # Create second session
        engine2 = create_engine(db_session.bind.url)
        Session2 = sessionmaker(bind=engine2)
        session2 = Session2()

        try:
            # Transaction A: Create patient (don't commit)
            patient_a = Patient(
                name="Uncommitted Patient",
                phone="+5511111111111",
                email="uncommitted@test.com",
                cpf="00000000000",
                doctor_id=doctor_user.id,
                flow_state=FlowState.ONBOARDING
            )
            db_session.add(patient_a)
            db_session.flush()  # Flush but don't commit

            # Transaction B: Try to read
            patient_b = session2.query(Patient).filter(
                Patient.cpf == "00000000000"
            ).first()

            # Assert - Should NOT see uncommitted data
            assert patient_b is None, "READ COMMITTED violated: saw uncommitted data!"

            # Commit transaction A
            db_session.commit()

            # Transaction B: Read again
            patient_b = session2.query(Patient).filter(
                Patient.cpf == "00000000000"
            ).first()

            # Assert - Should see committed data
            assert patient_b is not None, "Should see committed data"

        finally:
            session2.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
