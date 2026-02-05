"""
Race Condition Protection Tests - HIGH-003 - Real DB Synchronous Version

Tests concurrent patient creation to verify that race conditions
are properly prevented through database constraints.
This version ensures visibility by avoiding the global test transaction.
"""
import pytest
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple
from datetime import date
from faker import Faker
from uuid import UUID

from sqlalchemy.orm import sessionmaker
from sqlalchemy import exc

from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.services.patient.onboarding_factory import get_onboarding_coordinator
from app.exceptions import ValidationError, ConflictError
from app.config import settings

# Disable side effects for these tests
settings.WHATSAPP_ENABLE_ON_REGISTRATION = False
settings.FLOW_ENABLE_AUTO_ENROLLMENT = False

fake = Faker('pt_BR')

def get_valid_cpf():
    """Generate a valid Brazilian CPF without formatting."""
    return fake.cpf().replace(".", "").replace("-", "")

@pytest.fixture
def standalone_db(test_engine):
    """Provide a session that is NOT wrapped in a transaction rollback."""
    SessionLocal = sessionmaker(bind=test_engine)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def test_doctor_standalone(test_engine) -> User:
    """Create a test doctor with a real commit to be visible across connections."""
    import uuid
    SessionLocal = sessionmaker(bind=test_engine)
    db = SessionLocal()
    
    unique_email = f"standalone_doctor_{uuid.uuid4().hex[:8]}@test.com"
    doctor = User(
        id=uuid.uuid4(),
        email=unique_email,
        full_name="Standalone Test Doctor",
        role=UserRole.DOCTOR,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    doctor_id = doctor.id
    db.close() # Close session to ensure it's in DB
    
    yield doctor
    
    # Cleanup
    db = SessionLocal()
    try:
        db.query(Patient).filter(Patient.doctor_id == doctor_id).delete()
        db.query(User).filter(User.id == doctor_id).delete()
        db.commit()
    except:
        db.rollback()
    finally:
        db.close()


class TestRaceConditionProtectionRealDBSync:
    """
    Test suite for race condition protection using real database and synchronous sessions.
    """

    def test_concurrent_cpf_creation_sync(self, test_engine, test_doctor_standalone):
        """
        Test concurrent creation with same CPF.
        """
        same_cpf = get_valid_cpf()
        num_threads = 5
        doctor_id = test_doctor_standalone.id
        
        successes = []
        failures = []
        
        def create_patient(thread_id: int) -> Tuple[bool, str]:
            # Each thread MUST have its own session and connection
            SessionLocal = sessionmaker(bind=test_engine)
            thread_db = SessionLocal()
            try:
                coordinator = get_onboarding_coordinator(thread_db)
                service = coordinator.creation_service

                patient_data = PatientCreate(
                    name=f"Sync Patient {thread_id}",
                    phone=f"+5511997{thread_id:06d}",
                    email=f"sync_cpf_{thread_id}_{UUID(int=thread_id).hex[:6]}@test.com",
                    cpf=same_cpf,
                    birth_date=date(1990, 1, 1),
                    treatment_type="Quimioterapia",
                )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    patient = loop.run_until_complete(
                        service.create_patient_direct(patient_data, doctor_id)
                    )
                    thread_db.commit()
                    return True, str(patient.id)
                finally:
                    loop.close()

            except ValidationError as e:
                return False, f"val:{e.code}"
            except (exc.IntegrityError, ConflictError, exc.DatabaseError) as e:
                return False, f"conflict:{str(e)}"
            except Exception as e:
                return False, f"error:{str(e)}"
            finally:
                thread_db.close()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_patient, i) for i in range(num_threads)]
            for future in as_completed(futures):
                success, result = future.result()
                if success: 
                    successes.append(result)
                else: 
                    failures.append(result)

        # Assertions
        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}. Failures: {failures}"
        assert len(failures) == num_threads - 1
        for f in failures:
            assert "duplicate_cpf" in f or "conflict" in f or "uq_patient_cpf_hash_doctor" in f

    def test_concurrent_phone_creation_sync(self, test_engine, test_doctor_standalone):
        """
        Test concurrent creation with same phone.
        """
        same_phone = f"+551195{fake.random_number(digits=8, fix_len=True)}"
        num_threads = 5
        doctor_id = test_doctor_standalone.id
        
        successes = []
        failures = []
        
        def create_patient(thread_id: int) -> Tuple[bool, str]:
            SessionLocal = sessionmaker(bind=test_engine)
            thread_db = SessionLocal()
            try:
                coordinator = get_onboarding_coordinator(thread_db)
                service = coordinator.creation_service

                patient_data = PatientCreate(
                    name=f"Sync Phone Patient {thread_id}",
                    phone=same_phone,
                    email=f"sync_phone_{thread_id}_{UUID(int=thread_id).hex[:6]}@test.com",
                    cpf=get_valid_cpf(),
                    birth_date=date(1990, 1, 1),
                    treatment_type="Quimioterapia",
                )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    patient = loop.run_until_complete(
                        service.create_patient_direct(patient_data, doctor_id)
                    )
                    thread_db.commit()
                    return True, str(patient.id)
                finally:
                    loop.close()

            except ValidationError as e:
                return False, f"val:{e.code}"
            except (exc.IntegrityError, ConflictError, exc.DatabaseError):
                return False, "conflict"
            finally:
                thread_db.close()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_patient, i) for i in range(num_threads)]
            for future in as_completed(futures):
                success, result = future.result()
                if success: successes.append(result)
                else: failures.append(result)

        assert len(successes) == 1
        assert len(failures) == num_threads - 1

    def test_error_reporting_real_db_sync(self, test_engine, test_doctor_standalone):
        """
        Test clear error reporting for duplicates on real DB.
        """
        common_cpf = get_valid_cpf()
        doctor_id = test_doctor_standalone.id
        
        SessionLocal = sessionmaker(bind=test_engine)
        db = SessionLocal()
        
        coordinator = get_onboarding_coordinator(db)
        service = coordinator.creation_service

        patient_data = PatientCreate(
            name="Initial Patient Real",
            phone=f"+551194{fake.random_number(digits=8, fix_len=True)}",
            email=f"initial_sync_{fake.random_number(digits=5)}@test.com",
            cpf=common_cpf,
            birth_date=date(1990, 1, 1),
            treatment_type="Quimioterapia",
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(service.create_patient_direct(patient_data, doctor_id))
            db.commit()

            duplicate_data = PatientCreate(
                name="Duplicate Patient Real",
                phone=f"+551194{fake.random_number(digits=8, fix_len=True)}",
                email=f"duplicate_sync_{fake.random_number(digits=5)}@test.com",
                cpf=common_cpf,
                birth_date=date(1990, 1, 1),
                treatment_type="Radioterapia",
            )

            with pytest.raises(ValidationError) as exc_info:
                loop.run_until_complete(service.create_patient_direct(duplicate_data, doctor_id))
            
            assert exc_info.value.code == "duplicate_cpf"
        finally:
            loop.close()
            db.close()
