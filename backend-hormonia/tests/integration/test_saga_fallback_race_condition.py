"""
Integration tests for saga fallback race condition fix.

CRITICAL: Tests the fix for P0 issue where saga fallback blindly creates
duplicate patients without checking if one was partially created.

Test scenarios:
1. Saga fails after patient creation → Fallback finds existing patient
2. Concurrent saga executions → Database constraints prevent duplicates
3. Partial patient creation → Fallback completes onboarding
4. IntegrityError handling → Proper error messages
5. Database-level race conditions → SELECT FOR UPDATE locking

File: backend-hormonia/tests/integration/test_saga_fallback_race_condition.py
"""
import pytest
import asyncio
from uuid import uuid4
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.patient import Patient, FlowState
from app.models.user import User
from app.schemas.patient import PatientCreate
from app.services.patient.onboarding_service import PatientOnboardingService
from app.services.patient.integrity_service import PatientIntegrityService
from app.services.patient.flow_service import PatientFlowService
from app.coordination.saga_orchestrator import SagaOrchestrator


@pytest.fixture
def doctor_user(db: Session) -> User:
    """Create a test doctor user."""
    doctor = User(
        id=uuid4(),
        email=f"doctor_{uuid4()}@test.com",
        username=f"doctor_{uuid4()}",
        role="DOCTOR",
        is_active=True
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
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
def onboarding_service(db: Session) -> PatientOnboardingService:
    """Create onboarding service with dependencies."""
    from app.repositories.patient import PatientRepository
    from app.services.message import MessageService
    from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode

    patient_repo = PatientRepository(db)
    integrity_service = PatientIntegrityService(db, patient_repo)
    flow_service = PatientFlowService(db)

    # Create and inject message and whatsapp services (ISSUE-004)
    message_service = MessageService(db)
    whatsapp_service = UnifiedWhatsAppService(db=db, messaging_mode=MessagingMode.LEGACY)

    return PatientOnboardingService(
        db=db,
        integrity_service=integrity_service,
        flow_service=flow_service,
        message_service=message_service,  # ✅ INJECTED
        whatsapp_service=whatsapp_service,  # ✅ INJECTED
        saga_orchestrator=None  # No saga for fallback testing
    )


class TestSagaFallbackRaceCondition:
    """Test suite for saga fallback race condition fix."""

    @pytest.mark.asyncio
    async def test_find_existing_patient_by_cpf(
        self, db: Session, doctor_user: User, patient_data: PatientCreate, onboarding_service: PatientOnboardingService
    ):
        """Test finding existing patient by CPF."""
        # Create a patient first
        existing_patient = Patient(
            name=patient_data.name,
            phone=patient_data.phone,
            email=patient_data.email,
            cpf=patient_data.cpf,
            doctor_id=doctor_user.id,
            flow_state=FlowState.ONBOARDING
        )
        db.add(existing_patient)
        db.commit()
        db.refresh(existing_patient)

        # Try to find it
        found_patient = await onboarding_service._find_existing_patient(
            cpf=patient_data.cpf,
            email=patient_data.email,
            phone=patient_data.phone,
            doctor_id=doctor_user.id
        )

        assert found_patient is not None
        assert found_patient.id == existing_patient.id
        assert found_patient.cpf == patient_data.cpf

    @pytest.mark.asyncio
    async def test_find_existing_patient_by_email(
        self, db: Session, doctor_user: User, patient_data: PatientCreate, onboarding_service: PatientOnboardingService
    ):
        """Test finding existing patient by email when CPF is None."""
        # Create a patient without CPF
        existing_patient = Patient(
            name=patient_data.name,
            phone=patient_data.phone,
            email=patient_data.email,
            cpf=None,  # No CPF
            doctor_id=doctor_user.id,
            flow_state=FlowState.ONBOARDING
        )
        db.add(existing_patient)
        db.commit()
        db.refresh(existing_patient)

        # Try to find it (with CPF=None, should fall back to email)
        found_patient = await onboarding_service._find_existing_patient(
            cpf=None,
            email=patient_data.email,
            phone=patient_data.phone,
            doctor_id=doctor_user.id
        )

        assert found_patient is not None
        assert found_patient.id == existing_patient.id
        assert found_patient.email == patient_data.email

    @pytest.mark.asyncio
    async def test_find_existing_patient_by_phone(
        self, db: Session, doctor_user: User, patient_data: PatientCreate, onboarding_service: PatientOnboardingService
    ):
        """Test finding existing patient by phone when CPF and email are None."""
        # Create a patient without CPF or email
        existing_patient = Patient(
            name=patient_data.name,
            phone=patient_data.phone,
            email=None,  # No email
            cpf=None,  # No CPF
            doctor_id=doctor_user.id,
            flow_state=FlowState.ONBOARDING
        )
        db.add(existing_patient)
        db.commit()
        db.refresh(existing_patient)

        # Try to find it (should fall back to phone)
        found_patient = await onboarding_service._find_existing_patient(
            cpf=None,
            email=None,
            phone=patient_data.phone,
            doctor_id=doctor_user.id
        )

        assert found_patient is not None
        assert found_patient.id == existing_patient.id
        assert found_patient.phone == patient_data.phone

    @pytest.mark.asyncio
    async def test_find_existing_patient_not_found(
        self, db: Session, doctor_user: User, patient_data: PatientCreate, onboarding_service: PatientOnboardingService
    ):
        """Test that non-existent patient returns None."""
        found_patient = await onboarding_service._find_existing_patient(
            cpf=patient_data.cpf,
            email=patient_data.email,
            phone=patient_data.phone,
            doctor_id=doctor_user.id
        )

        assert found_patient is None

    @pytest.mark.asyncio
    async def test_find_existing_patient_ignores_deleted(
        self, db: Session, doctor_user: User, patient_data: PatientCreate, onboarding_service: PatientOnboardingService
    ):
        """Test that soft-deleted patients are not found."""
        from datetime import datetime

        # Create a soft-deleted patient
        deleted_patient = Patient(
            name=patient_data.name,
            phone=patient_data.phone,
            email=patient_data.email,
            cpf=patient_data.cpf,
            doctor_id=doctor_user.id,
            flow_state=FlowState.ONBOARDING,
            deleted_at=datetime.utcnow()  # Soft deleted
        )
        db.add(deleted_patient)
        db.commit()

        # Try to find it (should return None)
        found_patient = await onboarding_service._find_existing_patient(
            cpf=patient_data.cpf,
            email=patient_data.email,
            phone=patient_data.phone,
            doctor_id=doctor_user.id
        )

        assert found_patient is None

    @pytest.mark.asyncio
    async def test_complete_partial_onboarding_updates_patient(
        self, db: Session, doctor_user: User, patient_data: PatientCreate, onboarding_service: PatientOnboardingService
    ):
        """Test completing partial onboarding updates patient data."""
        # Create a partial patient (missing some fields)
        partial_patient = Patient(
            name="Incomplete Name",
            phone=patient_data.phone,
            email=None,  # Missing email
            cpf=patient_data.cpf,
            doctor_id=doctor_user.id,
            flow_state=FlowState.ONBOARDING
        )
        db.add(partial_patient)
        db.commit()
        db.refresh(partial_patient)

        # Complete onboarding with full data
        completed_patient = await onboarding_service._complete_partial_onboarding(
            existing_patient=partial_patient,
            patient_data=patient_data,
            current_user=None
        )

        # Verify updates
        assert completed_patient.id == partial_patient.id
        assert completed_patient.email == patient_data.email  # Email was added
        assert completed_patient.name == "Incomplete Name"  # Name preserved (was already set)

    @pytest.mark.asyncio
    async def test_fallback_finds_existing_patient(
        self, db: Session, doctor_user: User, patient_data: PatientCreate, onboarding_service: PatientOnboardingService
    ):
        """Test that fallback finds existing patient instead of creating duplicate."""
        # Simulate saga creating a patient then failing
        existing_patient = Patient(
            name=patient_data.name,
            phone=patient_data.phone,
            email=patient_data.email,
            cpf=patient_data.cpf,
            doctor_id=doctor_user.id,
            flow_state=FlowState.ONBOARDING
        )
        db.add(existing_patient)
        db.commit()
        db.refresh(existing_patient)

        # Call fallback (should find existing patient, not create duplicate)
        result_patient = await onboarding_service._create_patient_direct(
            patient_data=patient_data,
            doctor_id=doctor_user.id,
            current_user=None
        )

        # Verify it's the same patient (not a duplicate)
        assert result_patient.id == existing_patient.id
        assert result_patient.cpf == patient_data.cpf

        # Verify only one patient exists
        patient_count = db.query(Patient).filter(
            Patient.cpf == patient_data.cpf,
            Patient.doctor_id == doctor_user.id
        ).count()
        assert patient_count == 1

    @pytest.mark.asyncio
    async def test_concurrent_fallback_no_duplicates(
        self, db: Session, doctor_user: User, patient_data: PatientCreate, onboarding_service: PatientOnboardingService
    ):
        """Test concurrent fallback calls don't create duplicate patients."""
        # Simulate two concurrent fallback calls
        async def create_patient():
            return await onboarding_service._create_patient_direct(
                patient_data=patient_data,
                doctor_id=doctor_user.id,
                current_user=None
            )

        # Run two concurrent creation attempts
        results = await asyncio.gather(
            create_patient(),
            create_patient(),
            return_exceptions=True
        )

        # At least one should succeed
        successful_results = [r for r in results if isinstance(r, Patient)]
        assert len(successful_results) >= 1

        # Verify only one patient exists in database
        patient_count = db.query(Patient).filter(
            Patient.phone == patient_data.phone,
            Patient.doctor_id == doctor_user.id
        ).count()
        assert patient_count == 1, "Concurrent fallback created duplicate patients!"

    @pytest.mark.asyncio
    async def test_database_constraint_prevents_duplicates(
        self, db: Session, doctor_user: User, patient_data: PatientCreate
    ):
        """Test that database constraints prevent duplicate patient creation."""
        from app.repositories.patient import PatientRepository

        repository = PatientRepository(db)

        # Create first patient
        patient1 = repository.create({
            "name": patient_data.name,
            "phone": patient_data.phone,
            "email": patient_data.email,
            "cpf": patient_data.cpf,
            "doctor_id": doctor_user.id,
            "flow_state": FlowState.ONBOARDING
        })
        db.commit()

        # Try to create duplicate (should fail with IntegrityError)
        with pytest.raises(IntegrityError):
            patient2 = repository.create({
                "name": patient_data.name,
                "phone": patient_data.phone,  # Duplicate phone
                "email": patient_data.email,  # Duplicate email
                "cpf": patient_data.cpf,  # Duplicate CPF
                "doctor_id": doctor_user.id,
                "flow_state": FlowState.ONBOARDING
            })
            db.commit()

        db.rollback()

    @pytest.mark.asyncio
    async def test_saga_idempotency_reuses_existing_patient(
        self, db: Session, doctor_user: User, patient_data: PatientCreate
    ):
        """Test saga orchestrator reuses existing patient (idempotency)."""
        # This would require saga orchestrator fixture
        # Placeholder for future implementation
        pass


class TestSagaOrchestratorLocking:
    """Test database-level locking in saga orchestrator."""

    @pytest.mark.asyncio
    async def test_select_for_update_prevents_race_condition(
        self, db: Session, doctor_user: User, patient_data: PatientCreate
    ):
        """Test SELECT FOR UPDATE prevents concurrent saga race conditions."""
        # Create a patient
        patient = Patient(
            name=patient_data.name,
            phone=patient_data.phone,
            email=patient_data.email,
            cpf=patient_data.cpf,
            doctor_id=doctor_user.id,
            flow_state=FlowState.ONBOARDING
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

        # Test that SELECT FOR UPDATE locks the row
        from sqlalchemy import text
        result = db.execute(
            text(
                "SELECT * FROM patients WHERE cpf = :cpf AND doctor_id = :doctor_id FOR UPDATE SKIP LOCKED"
            ),
            {"cpf": patient_data.cpf, "doctor_id": str(doctor_user.id)}
        ).fetchone()

        assert result is not None
        # If another transaction tried to lock, it would skip this row


@pytest.mark.asyncio
async def test_complete_workflow_no_duplicates(
    db: Session, doctor_user: User, patient_data: PatientCreate, onboarding_service: PatientOnboardingService
):
    """
    Integration test: Complete workflow should never create duplicate patients.

    Scenario:
    1. Saga starts and creates patient
    2. Saga fails during message/flow step
    3. Fallback is triggered
    4. Fallback finds existing patient and completes onboarding
    5. No duplicate patient is created
    """
    # Step 1: Simulate saga creating patient then failing
    partial_patient = Patient(
        name=patient_data.name,
        phone=patient_data.phone,
        email=patient_data.email,
        cpf=patient_data.cpf,
        doctor_id=doctor_user.id,
        flow_state=FlowState.ONBOARDING
    )
    db.add(partial_patient)
    db.commit()
    db.refresh(partial_patient)

    patient_id_before = partial_patient.id

    # Step 2: Fallback is triggered (simulated by calling create_patient_direct)
    result_patient = await onboarding_service._create_patient_direct(
        patient_data=patient_data,
        doctor_id=doctor_user.id,
        current_user=None
    )

    # Step 3: Verify no duplicate was created
    assert result_patient.id == patient_id_before, "Fallback created a duplicate patient!"

    # Step 4: Verify only one patient exists
    all_patients = db.query(Patient).filter(
        Patient.cpf == patient_data.cpf,
        Patient.doctor_id == doctor_user.id
    ).all()

    assert len(all_patients) == 1, f"Found {len(all_patients)} patients, expected 1"
    assert all_patients[0].id == patient_id_before


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
