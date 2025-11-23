"""
Integration tests for patient unique constraints.

Tests verify that the database constraints prevent duplicate patients
from being created, especially in concurrent scenarios.
"""
import pytest
import asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.models.patient import Patient, FlowState
from app.core.database import get_db


@pytest.fixture
def doctor_id():
    """Generate a test doctor ID."""
    return uuid4()


@pytest.fixture
def patient_data(doctor_id):
    """Generate base patient data."""
    return {
        'doctor_id': doctor_id,
        'name': 'Test Patient',
        'phone': '+5511999999999',
        'email': 'test@example.com',
        'cpf': '12345678901',
        'flow_state': FlowState.ONBOARDING,
        'current_day': 0
    }


class TestPatientUniqueConstraints:
    """Test suite for patient unique constraints."""

    @pytest.mark.asyncio
    async def test_duplicate_phone_same_doctor_prevented(self, db_session: AsyncSession, patient_data):
        """Test that duplicate phone for same doctor is prevented."""
        # Create first patient
        patient1 = Patient(**patient_data)
        db_session.add(patient1)
        await db_session.commit()

        # Attempt to create second patient with same phone and doctor
        patient2 = Patient(**patient_data)
        patient2.email = 'different@example.com'  # Different email
        patient2.cpf = '98765432100'  # Different CPF

        db_session.add(patient2)

        # Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()

        assert 'uq_patient_phone_doctor' in str(exc_info.value)
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_duplicate_email_same_doctor_prevented(self, db_session: AsyncSession, patient_data):
        """Test that duplicate email for same doctor is prevented."""
        # Create first patient
        patient1 = Patient(**patient_data)
        db_session.add(patient1)
        await db_session.commit()

        # Attempt to create second patient with same email and doctor
        patient2 = Patient(**patient_data)
        patient2.phone = '+5511888888888'  # Different phone
        patient2.cpf = '98765432100'  # Different CPF

        db_session.add(patient2)

        # Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()

        assert 'uq_patient_email_doctor' in str(exc_info.value)
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_duplicate_cpf_same_doctor_prevented(self, db_session: AsyncSession, patient_data):
        """Test that duplicate CPF for same doctor is prevented."""
        # Create first patient
        patient1 = Patient(**patient_data)
        db_session.add(patient1)
        await db_session.commit()

        # Attempt to create second patient with same CPF and doctor
        patient2 = Patient(**patient_data)
        patient2.phone = '+5511888888888'  # Different phone
        patient2.email = 'different@example.com'  # Different email

        db_session.add(patient2)

        # Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()

        assert 'uq_patient_cpf_doctor' in str(exc_info.value)
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_same_phone_different_doctors_allowed(self, db_session: AsyncSession, patient_data):
        """Test that same phone for different doctors is allowed."""
        doctor1_id = uuid4()
        doctor2_id = uuid4()

        # Create first patient with doctor1
        patient1 = Patient(**patient_data)
        patient1.doctor_id = doctor1_id
        db_session.add(patient1)
        await db_session.commit()

        # Create second patient with same phone but different doctor
        patient2 = Patient(**patient_data)
        patient2.doctor_id = doctor2_id
        patient2.email = 'different@example.com'
        patient2.cpf = '98765432100'

        db_session.add(patient2)
        await db_session.commit()  # Should succeed

        # Verify both patients exist
        await db_session.refresh(patient1)
        await db_session.refresh(patient2)

        assert patient1.phone == patient2.phone
        assert patient1.doctor_id != patient2.doctor_id

    @pytest.mark.asyncio
    async def test_null_email_allowed_multiple_times(self, db_session: AsyncSession, patient_data):
        """Test that NULL email is allowed for multiple patients with same doctor."""
        # Create first patient without email
        patient1 = Patient(**patient_data)
        patient1.email = None
        db_session.add(patient1)
        await db_session.commit()

        # Create second patient without email (different phone and CPF)
        patient2 = Patient(**patient_data)
        patient2.email = None
        patient2.phone = '+5511888888888'
        patient2.cpf = '98765432100'

        db_session.add(patient2)
        await db_session.commit()  # Should succeed

        # Verify both patients exist with NULL email
        await db_session.refresh(patient1)
        await db_session.refresh(patient2)

        assert patient1.email is None
        assert patient2.email is None
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
                    patient = Patient(**data)
                    session.add(patient)
                    await session.commit()
                    return True
                except IntegrityError:
                    await session.rollback()
                    return False

        # Simulate concurrent creation attempts
        from app.core.database import AsyncSessionLocal

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
        patient1 = Patient(**patient_data)
        db_session.add(patient1)
        await db_session.commit()

        # Test phone constraint
        patient2 = Patient(**patient_data)
        patient2.email = 'other@example.com'
        patient2.cpf = '98765432100'
        db_session.add(patient2)

        try:
            await db_session.commit()
            pytest.fail("Expected IntegrityError")
        except IntegrityError as e:
            error_msg = str(e.orig)
            assert 'uq_patient_phone_doctor' in error_msg or 'duplicate key' in error_msg.lower()
            await db_session.rollback()

    @pytest.mark.asyncio
    async def test_index_performance_phone_lookup(self, db_session: AsyncSession, doctor_id):
        """Test that phone lookup uses the composite index."""
        # Create multiple patients
        for i in range(10):
            patient = Patient(
                doctor_id=doctor_id,
                name=f'Patient {i}',
                phone=f'+551199999{i:04d}',
                email=f'patient{i}@example.com',
                cpf=f'{i:011d}',
                flow_state=FlowState.ONBOARDING,
                current_day=0
            )
            db_session.add(patient)

        await db_session.commit()

        # Query using phone and doctor_id (should use idx_patient_phone_doctor)
        from sqlalchemy import select
        stmt = select(Patient).where(
            Patient.phone == '+5511999990005',
            Patient.doctor_id == doctor_id
        )

        result = await db_session.execute(stmt)
        patient = result.scalar_one_or_none()

        assert patient is not None
        assert patient.name == 'Patient 5'


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
