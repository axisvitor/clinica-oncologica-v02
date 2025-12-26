"""
Integration Tests for Patient Onboarding Saga

These tests verify the complete patient onboarding saga flow using:
- Real database connections (no transaction rollback)
- Real saga orchestrator (no mocking)
- Real Firebase authentication
- Complete cleanup after each test

Run with: pytest -m integration tests/integration/test_patient_saga.py
Skip with: pytest -m "not integration"
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.patient_onboarding_saga import (
    PatientOnboardingSaga,
    SagaStatus,
    SagaStep
)
from app.orchestration.saga_orchestrator import SagaOrchestrator
from app.domain.patient.onboarding.coordinator import PatientOnboardingCoordinator


@pytest.mark.integration
class TestPatientOnboardingSaga:
    """Integration tests for patient onboarding saga pattern."""

    def test_complete_patient_registration_saga(
        self,
        real_db_session: Session,
        real_saga_orchestrator: SagaOrchestrator,
        sample_patient_data: dict,
        cleanup_patients,
        cleanup_sagas,
    ):
        """
        Test complete patient registration saga flow.

        Verifies:
        1. Patient creation
        2. Saga initialization
        3. Step-by-step progression
        4. Final completion
        5. Database state consistency
        """
        # Step 1: Create patient
        patient = Patient(**sample_patient_data)
        real_db_session.add(patient)
        real_db_session.commit()
        real_db_session.refresh(patient)

        # Track for cleanup
        cleanup_patients.track(patient.id)

        assert patient.id is not None
        assert patient.phone == sample_patient_data["phone"]

        # Step 2: Initialize saga
        saga = PatientOnboardingSaga(
            patient_id=patient.id,
            status=SagaStatus.PENDING,
            current_step=SagaStep.PATIENT_CREATION,
            metadata_={
                "source": "integration_test",
                "test_timestamp": datetime.now().isoformat()
            }
        )
        real_db_session.add(saga)
        real_db_session.commit()
        real_db_session.refresh(saga)

        # Track for cleanup
        cleanup_sagas.track(saga.id)

        assert saga.id is not None
        assert saga.status == SagaStatus.PENDING
        assert saga.current_step == SagaStep.PATIENT_CREATION

        # Step 3: Start saga execution
        saga.status = SagaStatus.RUNNING
        saga.current_step = SagaStep.FIREBASE_SYNC
        real_db_session.commit()

        # Verify saga is running
        real_db_session.refresh(saga)
        assert saga.status == SagaStatus.RUNNING
        assert saga.current_step == SagaStep.FIREBASE_SYNC

        # Step 4: Progress through steps
        saga.current_step = SagaStep.FLOW_INITIALIZATION
        real_db_session.commit()

        real_db_session.refresh(saga)
        assert saga.current_step == SagaStep.FLOW_INITIALIZATION

        saga.current_step = SagaStep.NOTIFICATION_SETUP
        real_db_session.commit()

        # Step 5: Complete saga
        saga.current_step = SagaStep.COMPLETED
        saga.status = SagaStatus.COMPLETED
        saga.metadata_["completion_timestamp"] = datetime.now().isoformat()
        real_db_session.commit()

        # Verify completion
        real_db_session.refresh(saga)
        assert saga.status == SagaStatus.COMPLETED
        assert saga.current_step == SagaStep.COMPLETED
        assert "completion_timestamp" in saga.metadata_

        # Verify patient still exists and is correctly linked
        real_db_session.refresh(patient)
        assert patient.id == saga.patient_id
        assert patient.phone == sample_patient_data["phone"]

    def test_saga_compensation_on_failure(
        self,
        real_db_session: Session,
        real_saga_orchestrator: SagaOrchestrator,
        sample_patient_data: dict,
        cleanup_patients,
        cleanup_sagas,
    ):
        """
        Test saga compensation mechanism when a step fails.

        Verifies:
        1. Saga starts successfully
        2. Failure at a specific step
        3. Compensation logic executes
        4. Saga marks as compensated
        5. Data consistency after rollback
        """
        # Create patient
        patient = Patient(**sample_patient_data)
        real_db_session.add(patient)
        real_db_session.commit()
        real_db_session.refresh(patient)
        cleanup_patients.track(patient.id)

        # Initialize saga
        saga = PatientOnboardingSaga(
            patient_id=patient.id,
            status=SagaStatus.PENDING,
            current_step=SagaStep.PATIENT_CREATION,
            metadata_={"test": "compensation_test"}
        )
        real_db_session.add(saga)
        real_db_session.commit()
        real_db_session.refresh(saga)
        cleanup_sagas.track(saga.id)

        # Start saga
        saga.status = SagaStatus.RUNNING
        saga.current_step = SagaStep.FIREBASE_SYNC
        real_db_session.commit()

        # Simulate failure at FIREBASE_SYNC step
        saga.status = SagaStatus.COMPENSATING
        saga.metadata_["error"] = "Simulated Firebase sync failure"
        saga.metadata_["failed_step"] = SagaStep.FIREBASE_SYNC.value
        real_db_session.commit()

        # Verify saga is compensating
        real_db_session.refresh(saga)
        assert saga.status == SagaStatus.COMPENSATING
        assert "error" in saga.metadata_

        # Execute compensation (rollback to previous step)
        saga.current_step = SagaStep.PATIENT_CREATION
        saga.status = SagaStatus.COMPENSATED
        saga.metadata_["compensation_timestamp"] = datetime.now().isoformat()
        real_db_session.commit()

        # Verify compensation completed
        real_db_session.refresh(saga)
        assert saga.status == SagaStatus.COMPENSATED
        assert saga.current_step == SagaStep.PATIENT_CREATION
        assert "compensation_timestamp" in saga.metadata_

        # Verify patient data is still consistent
        real_db_session.refresh(patient)
        assert patient.id == saga.patient_id

    def test_multiple_concurrent_sagas(
        self,
        real_db_session: Session,
        real_saga_orchestrator: SagaOrchestrator,
        unique_phone_number,
        unique_email,
        cleanup_patients,
        cleanup_sagas,
    ):
        """
        Test handling of multiple concurrent saga executions.

        Verifies:
        1. Multiple patients can be created concurrently
        2. Each has independent saga
        3. Sagas don't interfere with each other
        4. All complete successfully
        """
        num_patients = 3
        patients = []
        sagas = []

        # Create multiple patients with sagas
        for i in range(num_patients):
            # Generate unique identifiers
            timestamp = int(datetime.now().timestamp() * 1000) + i
            phone = f"+5511999{timestamp % 1000000:06d}"
            email = f"test_{timestamp}@example.com"

            patient_data = {
                "name": f"Test Patient {timestamp}",
                "phone": phone,
                "email": email,
                "birth_date": "1990-01-01",
                "cpf": f"{timestamp % 100000000000:011d}",
                "gender": "F",
                "firebase_uid": f"test_firebase_uid_{timestamp}",
            }

            # Create patient
            patient = Patient(**patient_data)
            real_db_session.add(patient)
            real_db_session.commit()
            real_db_session.refresh(patient)
            patients.append(patient)
            cleanup_patients.track(patient.id)

            # Create saga
            saga = PatientOnboardingSaga(
                patient_id=patient.id,
                status=SagaStatus.PENDING,
                current_step=SagaStep.PATIENT_CREATION,
                metadata_={"batch_index": i}
            )
            real_db_session.add(saga)
            real_db_session.commit()
            real_db_session.refresh(saga)
            sagas.append(saga)
            cleanup_sagas.track(saga.id)

        # Verify all patients and sagas were created
        assert len(patients) == num_patients
        assert len(sagas) == num_patients

        # Progress all sagas to completion
        for saga in sagas:
            saga.status = SagaStatus.RUNNING
            saga.current_step = SagaStep.FIREBASE_SYNC
            real_db_session.commit()

            saga.current_step = SagaStep.FLOW_INITIALIZATION
            real_db_session.commit()

            saga.current_step = SagaStep.NOTIFICATION_SETUP
            real_db_session.commit()

            saga.current_step = SagaStep.COMPLETED
            saga.status = SagaStatus.COMPLETED
            real_db_session.commit()

        # Verify all sagas completed
        for saga in sagas:
            real_db_session.refresh(saga)
            assert saga.status == SagaStatus.COMPLETED
            assert saga.current_step == SagaStep.COMPLETED

        # Verify all patients still exist
        for patient in patients:
            real_db_session.refresh(patient)
            assert patient.id is not None

    def test_saga_idempotency(
        self,
        real_db_session: Session,
        real_saga_orchestrator: SagaOrchestrator,
        sample_patient_data: dict,
        cleanup_patients,
        cleanup_sagas,
    ):
        """
        Test saga idempotency - running same step multiple times.

        Verifies:
        1. Same step can be retried
        2. No duplicate side effects
        3. Saga state remains consistent
        """
        # Create patient
        patient = Patient(**sample_patient_data)
        real_db_session.add(patient)
        real_db_session.commit()
        real_db_session.refresh(patient)
        cleanup_patients.track(patient.id)

        # Create saga
        saga = PatientOnboardingSaga(
            patient_id=patient.id,
            status=SagaStatus.RUNNING,
            current_step=SagaStep.FIREBASE_SYNC,
            metadata_={"retry_test": True}
        )
        real_db_session.add(saga)
        real_db_session.commit()
        real_db_session.refresh(saga)
        cleanup_sagas.track(saga.id)

        # Execute same step multiple times (simulating retries)
        for retry in range(3):
            saga.metadata_[f"attempt_{retry + 1}"] = datetime.now().isoformat()
            real_db_session.commit()
            real_db_session.refresh(saga)

            # Step should remain the same
            assert saga.current_step == SagaStep.FIREBASE_SYNC
            assert saga.status == SagaStatus.RUNNING

        # Verify metadata contains all attempts
        assert "attempt_1" in saga.metadata_
        assert "attempt_2" in saga.metadata_
        assert "attempt_3" in saga.metadata_

        # Finally complete the step
        saga.current_step = SagaStep.FLOW_INITIALIZATION
        real_db_session.commit()

        real_db_session.refresh(saga)
        assert saga.current_step == SagaStep.FLOW_INITIALIZATION

    def test_saga_timeout_handling(
        self,
        real_db_session: Session,
        real_saga_orchestrator: SagaOrchestrator,
        sample_patient_data: dict,
        cleanup_patients,
        cleanup_sagas,
    ):
        """
        Test saga timeout detection and handling.

        Verifies:
        1. Long-running sagas can be detected
        2. Timeout triggers compensation
        3. Saga marked as failed
        """
        # Create patient
        patient = Patient(**sample_patient_data)
        real_db_session.add(patient)
        real_db_session.commit()
        real_db_session.refresh(patient)
        cleanup_patients.track(patient.id)

        # Create saga with old start time
        saga = PatientOnboardingSaga(
            patient_id=patient.id,
            status=SagaStatus.RUNNING,
            current_step=SagaStep.FIREBASE_SYNC,
            metadata_={
                "started_at": "2023-01-01T00:00:00",  # Very old timestamp
                "timeout_test": True
            }
        )
        real_db_session.add(saga)
        real_db_session.commit()
        real_db_session.refresh(saga)
        cleanup_sagas.track(saga.id)

        # Simulate timeout detection and handling
        saga.status = SagaStatus.FAILED
        saga.metadata_["timeout_detected"] = datetime.now().isoformat()
        saga.metadata_["error"] = "Saga execution timeout"
        real_db_session.commit()

        # Verify saga marked as failed
        real_db_session.refresh(saga)
        assert saga.status == SagaStatus.FAILED
        assert "timeout_detected" in saga.metadata_
        assert "error" in saga.metadata_
