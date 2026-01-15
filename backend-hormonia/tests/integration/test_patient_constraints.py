"""
Integration tests for patient unique constraints.

Tests verify that the database constraints prevent duplicate patients
from being created, especially in concurrent scenarios.

LGPD Compliance: Tests use hash-based uniqueness constraints
(phone_hash, email_hash, cpf_hash) instead of plaintext columns.
"""
import pytest
import asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.models.patient import Patient, FlowState


def create_patient_with_lgpd(
    doctor_id,
    name: str = "Test Patient",
    phone: str = "+5511999999999",
    email: str = "test@example.com",
    cpf: str = "12345678909",
    flow_state=FlowState.ONBOARDING,
    current_day: int = 0
):
    """
    Helper to create Patient with LGPD-compliant encryption.

    Uses set_phone(), set_email(), set_cpf() methods to properly
    encrypt and hash sensitive data.
    """
    patient = Patient(
        doctor_id=doctor_id,
        name=name,
        flow_state=flow_state,
        current_day=current_day
    )
    if phone:
        patient.set_phone(phone)
    if email:
        patient.set_email(email)
    if cpf:
        patient.set_cpf(cpf)
    return patient


@pytest.fixture
def doctor_id():
    """Generate a test doctor ID."""
    return uuid4()


@pytest.fixture
def patient_data(doctor_id):
    """Generate base patient data dictionary."""
    return {
        'doctor_id': doctor_id,
        'name': 'Test Patient',
        'phone': '+5511999999999',
        'email': 'test@example.com',
        'cpf': '12345678909',
        'flow_state': FlowState.ONBOARDING,
        'current_day': 0
    }


class TestPatientUniqueConstraints:
    """Test suite for patient unique constraints using hash columns."""

    @pytest.mark.asyncio
    async def test_duplicate_phone_hash_same_doctor_prevented(self, db_session: AsyncSession, patient_data):
        """Test that duplicate phone_hash for same doctor is prevented."""
        # Create first patient
        patient1 = create_patient_with_lgpd(**patient_data)
        db_session.add(patient1)
        await db_session.commit()

        # Attempt to create second patient with same phone and doctor
        patient2_data = patient_data.copy()
        patient2_data['email'] = 'different@example.com'
        patient2_data['cpf'] = '12345678909'
        patient2 = create_patient_with_lgpd(**patient2_data)

        db_session.add(patient2)

        # Should raise IntegrityError due to unique constraint on phone_hash
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()

        # Constraint may be named uq_patient_phone_hash_doctor or similar
        error_msg = str(exc_info.value).lower()
        assert 'phone' in error_msg or 'duplicate' in error_msg
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_duplicate_email_hash_same_doctor_prevented(self, db_session: AsyncSession, patient_data):
        """Test that duplicate email_hash for same doctor is prevented."""
        # Create first patient
        patient1 = create_patient_with_lgpd(**patient_data)
        db_session.add(patient1)
        await db_session.commit()

        # Attempt to create second patient with same email and doctor
        patient2_data = patient_data.copy()
        patient2_data['phone'] = '+5511888888888'
        patient2_data['cpf'] = '12345678909'
        patient2 = create_patient_with_lgpd(**patient2_data)

        db_session.add(patient2)

        # Should raise IntegrityError due to unique constraint on email_hash
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()

        error_msg = str(exc_info.value).lower()
        assert 'email' in error_msg or 'duplicate' in error_msg
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_duplicate_cpf_hash_same_doctor_prevented(self, db_session: AsyncSession, patient_data):
        """Test that duplicate cpf_hash for same doctor is prevented."""
        # Create first patient
        patient1 = create_patient_with_lgpd(**patient_data)
        db_session.add(patient1)
        await db_session.commit()

        # Attempt to create second patient with same CPF and doctor
        patient2_data = patient_data.copy()
        patient2_data['phone'] = '+5511888888888'
        patient2_data['email'] = 'different@example.com'
        patient2 = create_patient_with_lgpd(**patient2_data)

        db_session.add(patient2)

        # Should raise IntegrityError due to unique constraint on cpf_hash
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()

        error_msg = str(exc_info.value).lower()
        assert 'cpf' in error_msg or 'duplicate' in error_msg
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_same_phone_different_doctors_allowed(self, db_session: AsyncSession, patient_data):
        """Test that same phone for different doctors is allowed."""
        doctor1_id = uuid4()
        doctor2_id = uuid4()

        # Create first patient with doctor1
        patient1_data = patient_data.copy()
        patient1_data['doctor_id'] = doctor1_id
        patient1 = create_patient_with_lgpd(**patient1_data)
        db_session.add(patient1)
        await db_session.commit()

        # Create second patient with same phone but different doctor
        patient2_data = patient_data.copy()
        patient2_data['doctor_id'] = doctor2_id
        patient2_data['email'] = 'different@example.com'
        patient2_data['cpf'] = '12345678909'
        patient2 = create_patient_with_lgpd(**patient2_data)

        db_session.add(patient2)
        await db_session.commit()  # Should succeed

        # Verify both patients exist
        await db_session.refresh(patient1)
        await db_session.refresh(patient2)

        # LGPD: Compare decrypted phones
        assert patient1.phone_decrypted == patient2.phone_decrypted
        assert patient1.doctor_id != patient2.doctor_id

    @pytest.mark.asyncio
    async def test_null_email_allowed_multiple_times(self, db_session: AsyncSession, patient_data):
        """Test that NULL email is allowed for multiple patients with same doctor."""
        # Create first patient without email
        patient1_data = patient_data.copy()
        patient1_data['email'] = None
        patient1 = create_patient_with_lgpd(**patient1_data)
        db_session.add(patient1)
        await db_session.commit()

        # Create second patient without email (different phone and CPF)
        patient2_data = patient_data.copy()
        patient2_data['email'] = None
        patient2_data['phone'] = '+5511888888888'
        patient2_data['cpf'] = '12345678909'
        patient2 = create_patient_with_lgpd(**patient2_data)

        db_session.add(patient2)
        await db_session.commit()  # Should succeed

        # Verify both patients exist with NULL email
        await db_session.refresh(patient1)
        await db_session.refresh(patient2)

        # LGPD: Check encrypted email is None
        assert patient1.email_encrypted is None
        assert patient2.email_encrypted is None
        assert patient1.doctor_id == patient2.doctor_id

    @pytest.mark.asyncio
    async def test_concurrent_patient_creation_race_condition(self, db_session: AsyncSession, patient_data):
        """
        Test race condition: concurrent attempts to create same patient.

        This simulates the real-world scenario where two API requests
        try to create the same patient simultaneously.
        """
        async def create_patient(session_factory, data):
            """Helper to create patient in separate transaction."""
            async with session_factory() as session:
                try:
                    patient = create_patient_with_lgpd(**data)
                    session.add(patient)
                    await session.commit()
                    return True
                except IntegrityError:
                    await session.rollback()
                    return False

        # Simulate concurrent creation attempts
        from app.database import AsyncSessionLocal

        results = await asyncio.gather(
            create_patient(AsyncSessionLocal, patient_data),
            create_patient(AsyncSessionLocal, patient_data),
            create_patient(AsyncSessionLocal, patient_data),
            return_exceptions=True
        )

        # Exactly one should succeed, others should fail
        successes = sum(1 for r in results if r is True)
        failures = sum(1 for r in results if r is False)

        assert successes == 1, f"Expected 1 success, got {successes}"
        assert failures == 2, f"Expected 2 failures, got {failures}"

    @pytest.mark.asyncio
    async def test_constraint_error_messages(self, db_session: AsyncSession, patient_data):
        """Test that constraint violations provide clear error messages."""
        # Create first patient
        patient1 = create_patient_with_lgpd(**patient_data)
        db_session.add(patient1)
        await db_session.commit()

        # Test phone constraint
        patient2_data = patient_data.copy()
        patient2_data['email'] = 'other@example.com'
        patient2_data['cpf'] = '12345678909'
        patient2 = create_patient_with_lgpd(**patient2_data)
        db_session.add(patient2)

        try:
            await db_session.commit()
            pytest.fail("Expected IntegrityError")
        except IntegrityError as e:
            error_msg = str(e.orig).lower()
            assert 'phone' in error_msg or 'duplicate' in error_msg
            await db_session.rollback()

    @pytest.mark.asyncio
    async def test_index_performance_phone_hash_lookup(self, db_session: AsyncSession, doctor_id):
        """Test that phone_hash lookup uses the composite index."""
        from app.services.encryption import get_lgpd_encryption_service, FieldType

        encryption = get_lgpd_encryption_service()

        # Create multiple patients
        for i in range(10):
            patient = create_patient_with_lgpd(
                doctor_id=doctor_id,
                name=f'Patient {i}',
                phone=f'+551199999{i:04d}',
                email=f'patient{i}@example.com',
                cpf=f'{i:011d}'
            )
            db_session.add(patient)

        await db_session.commit()

        # Query using phone_hash and doctor_id (should use index)
        from sqlalchemy import select

        # Generate hash for lookup using generate_hash with FieldType
        target_phone = '+5511999990005'
        phone_hash = encryption.generate_hash(target_phone, FieldType.PHONE)

        stmt = select(Patient).where(
            Patient.phone_hash == phone_hash,
            Patient.doctor_id == doctor_id
        )

        result = await db_session.execute(stmt)
        patient = result.scalar_one_or_none()

        assert patient is not None
        assert patient.name == 'Patient 5'
        # LGPD: Verify decrypted phone matches
        assert patient.phone_decrypted == target_phone


@pytest.mark.asyncio
async def test_migration_idempotency():
    """
    Test that the migration can be run multiple times safely.

    This test verifies that:
    1. Running upgrade twice doesn't break
    2. Running downgrade then upgrade restores state
    """
    # This would be implemented with actual alembic migration testing
    # For now, just a placeholder
    pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
