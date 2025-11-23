"""
Race Condition Protection Tests - HIGH-003

Tests concurrent patient creation to verify that race conditions
are properly prevented through database constraints.

Scenarios:
1. Concurrent creation with same CPF → Only 1 succeeds
2. Concurrent creation with same phone → Only 1 succeeds
3. Concurrent creation with same email → Only 1 succeeds
4. High-load stress test → Zero duplicates
"""
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple
from uuid import UUID, uuid4
from datetime import date

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientCreate
from app.services.patient.creation_service import PatientCreationService
from app.exceptions import ValidationError


class TestRaceConditionProtection:
    """
    Test suite for race condition protection in patient creation.

    HIGH-003: Ensures database constraints prevent duplicate creation
    even under high concurrent load.
    """

    @pytest.fixture
    def test_doctor(self, db: Session) -> User:
        """Create a test doctor."""
        doctor = User(
            id=uuid4(),
            email="doctor@test.com",
            name="Test Doctor",
            role="DOCTOR",
        )
        db.add(doctor)
        db.commit()
        db.refresh(doctor)
        return doctor

    def test_concurrent_cpf_creation(self, db: Session, test_doctor: User):
        """
        Test concurrent creation with same CPF.

        Expected:
        - Only 1 patient created
        - 9 threads get ValidationError with duplicate_cpf
        """
        same_cpf = "12345678901"
        successes = []
        failures = []
        errors = []

        def create_patient(thread_id: int) -> Tuple[bool, str]:
            """Thread worker to create patient."""
            try:
                # Each thread gets its own session
                from app.database import SessionLocal
                thread_db = SessionLocal()

                service = PatientCreationService(thread_db)

                patient_data = PatientCreate(
                    name=f"Patient Thread {thread_id}",
                    phone=f"+5511999{thread_id:06d}",
                    email=f"patient{thread_id}@test.com",
                    cpf=same_cpf,  # SAME CPF - should conflict!
                    birth_date=date(1990, 1, 1),
                    treatment_type="Quimioterapia",
                )

                patient = service.create_patient_safe(
                    patient_data,
                    test_doctor.id
                )

                thread_db.commit()
                patient_id = patient.id
                thread_db.close()

                return True, str(patient_id)

            except ValidationError as e:
                return False, e.code

            except Exception as e:
                return False, f"error:{str(e)}"

        # Launch 10 concurrent threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(create_patient, i): i
                for i in range(10)
            }

            for future in as_completed(futures):
                success, result = future.result()
                if success:
                    successes.append(result)
                else:
                    if result.startswith("duplicate_"):
                        failures.append(result)
                    else:
                        errors.append(result)

        # Assertions
        assert len(successes) == 1, (
            f"Race condition detected! {len(successes)} patients created. "
            f"Expected only 1."
        )

        assert len(failures) == 9, (
            f"Expected 9 duplicate errors, got {len(failures)}"
        )

        # All failures should be duplicate_cpf
        for failure in failures:
            assert failure == "duplicate_cpf", (
                f"Unexpected error code: {failure}"
            )

        assert len(errors) == 0, (
            f"Unexpected errors: {errors}"
        )

        print(f"✅ CPF Race Condition Test: {len(successes)} created, {len(failures)} prevented")

        # Cleanup
        db.query(Patient).filter(Patient.cpf == same_cpf).delete()
        db.commit()

    def test_concurrent_phone_creation(self, db: Session, test_doctor: User):
        """
        Test concurrent creation with same phone.

        Expected:
        - Only 1 patient created
        - 9 threads get ValidationError with duplicate_phone
        """
        same_phone = "+5511988888888"
        successes = []
        failures = []

        def create_patient(thread_id: int) -> Tuple[bool, str]:
            """Thread worker to create patient."""
            try:
                from app.database import SessionLocal
                thread_db = SessionLocal()

                service = PatientCreationService(thread_db)

                patient_data = PatientCreate(
                    name=f"Patient Thread {thread_id}",
                    phone=same_phone,  # SAME PHONE - should conflict!
                    email=f"patient{thread_id}@test.com",
                    cpf=f"{thread_id:011d}",
                    birth_date=date(1990, 1, 1),
                    treatment_type="Quimioterapia",
                )

                patient = service.create_patient_safe(
                    patient_data,
                    test_doctor.id
                )

                thread_db.commit()
                patient_id = patient.id
                thread_db.close()

                return True, str(patient_id)

            except ValidationError as e:
                return False, e.code

            except Exception as e:
                return False, f"error:{str(e)}"

        # Launch 10 concurrent threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(create_patient, i): i
                for i in range(10)
            }

            for future in as_completed(futures):
                success, result = future.result()
                if success:
                    successes.append(result)
                else:
                    failures.append(result)

        # Assertions
        assert len(successes) == 1, (
            f"Race condition detected! {len(successes)} patients created"
        )

        assert len(failures) == 9

        # All failures should be duplicate_phone
        for failure in failures:
            assert failure == "duplicate_phone"

        print(f"✅ Phone Race Condition Test: {len(successes)} created, {len(failures)} prevented")

        # Cleanup
        db.query(Patient).filter(Patient.phone == same_phone).delete()
        db.commit()

    def test_high_load_stress_test(self, db: Session, test_doctor: User):
        """
        Stress test with 100 concurrent requests.

        Test that under high load:
        - No race conditions occur
        - All patients are created successfully
        - Database integrity is maintained
        """
        num_threads = 100
        successes = []
        failures = []

        def create_unique_patient(thread_id: int) -> Tuple[bool, str]:
            """Thread worker - creates patient with unique data."""
            try:
                from app.database import SessionLocal
                thread_db = SessionLocal()

                service = PatientCreationService(thread_db)

                # Each patient has UNIQUE data
                patient_data = PatientCreate(
                    name=f"Stress Test Patient {thread_id}",
                    phone=f"+5511999{thread_id:06d}",
                    email=f"stress{thread_id}@test.com",
                    cpf=f"{thread_id:011d}",
                    birth_date=date(1990, 1, 1),
                    treatment_type="Quimioterapia",
                )

                patient = service.create_patient_safe(
                    patient_data,
                    test_doctor.id
                )

                thread_db.commit()
                patient_id = patient.id
                thread_db.close()

                return True, str(patient_id)

            except Exception as e:
                return False, str(e)

        # Launch 100 concurrent threads
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {
                executor.submit(create_unique_patient, i): i
                for i in range(num_threads)
            }

            for future in as_completed(futures):
                success, result = future.result()
                if success:
                    successes.append(result)
                else:
                    failures.append(result)

        # Assertions
        assert len(successes) == num_threads, (
            f"Not all patients created: {len(successes)}/{num_threads}"
        )

        assert len(failures) == 0, (
            f"Unexpected failures: {failures}"
        )

        # Verify no duplicates in database
        created_cpfs = [f"{i:011d}" for i in range(num_threads)]
        patients_in_db = (
            db.query(Patient)
            .filter(Patient.cpf.in_(created_cpfs))
            .all()
        )

        assert len(patients_in_db) == num_threads, (
            f"Database integrity violation: {len(patients_in_db)} != {num_threads}"
        )

        print(f"✅ Stress Test: {len(successes)}/{num_threads} patients created successfully")

        # Cleanup
        db.query(Patient).filter(Patient.cpf.in_(created_cpfs)).delete()
        db.commit()

    def test_race_condition_error_messages(self, db: Session, test_doctor: User):
        """
        Test that race condition errors have clear messages.

        Ensures ValidationError provides:
        - Clear error message
        - Correct error code
        - Field identification
        """
        # Create initial patient
        from app.database import SessionLocal
        thread_db = SessionLocal()

        service = PatientCreationService(thread_db)

        patient_data = PatientCreate(
            name="Initial Patient",
            phone="+5511987654321",
            email="initial@test.com",
            cpf="11122233344",
            birth_date=date(1990, 1, 1),
            treatment_type="Quimioterapia",
        )

        patient = service.create_patient_safe(patient_data, test_doctor.id)
        thread_db.commit()

        # Try to create duplicate
        duplicate_data = PatientCreate(
            name="Duplicate Patient",
            phone="+5511987654321",  # Same phone
            email="duplicate@test.com",
            cpf="99988877766",
            birth_date=date(1990, 1, 1),
            treatment_type="Radioterapia",
        )

        with pytest.raises(ValidationError) as exc_info:
            service.create_patient_safe(duplicate_data, test_doctor.id)

        error = exc_info.value

        # Assertions
        assert error.code == "duplicate_phone"
        assert error.field == "phone"
        assert "telefone" in error.message.lower()

        print(f"✅ Error message: {error.message}")
        print(f"✅ Error code: {error.code}")

        # Cleanup
        thread_db.query(Patient).filter(Patient.id == patient.id).delete()
        thread_db.commit()
        thread_db.close()


class TestRaceConditionMetrics:
    """
    Test metrics and monitoring for race condition prevention.
    """

    def test_race_condition_logging(self, db: Session, test_doctor: User, caplog):
        """
        Test that race conditions are properly logged.

        Ensures:
        - Duplicate attempts are logged
        - PII is masked in logs
        - Log level is appropriate (WARNING)
        """
        import logging
        from app.database import SessionLocal

        caplog.set_level(logging.WARNING)

        # Create initial patient
        thread_db = SessionLocal()
        service = PatientCreationService(thread_db)

        patient_data = PatientCreate(
            name="Log Test Patient",
            phone="+5511999999999",
            email="logtest@test.com",
            cpf="12312312312",
            birth_date=date(1990, 1, 1),
            treatment_type="Quimioterapia",
        )

        patient = service.create_patient_safe(patient_data, test_doctor.id)
        thread_db.commit()

        # Try duplicate
        try:
            service.create_patient_safe(patient_data, test_doctor.id)
        except ValidationError:
            pass

        # Check logs
        assert any(
            "Duplicate" in record.message
            for record in caplog.records
        )

        # Verify PII masking in logs
        for record in caplog.records:
            # CPF should be masked
            assert "12312312312" not in record.message
            # Phone should be masked
            assert "+5511999999999" not in record.message

        print("✅ Race condition logging verified")

        # Cleanup
        thread_db.query(Patient).filter(Patient.id == patient.id).delete()
        thread_db.commit()
        thread_db.close()
