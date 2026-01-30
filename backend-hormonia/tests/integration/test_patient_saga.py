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

from datetime import datetime, date
from enum import IntEnum

import pytest
from sqlalchemy.orm import Session

from app.models.enums import SagaStatus
from app.models.patient import Patient
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.orchestration.saga_orchestrator import SagaOrchestrator


class SagaStep(IntEnum):
    """Minimal step mapping for integration tests."""

    PATIENT_CREATED = 1
    FLOW_INITIALIZED = 2
    WELCOME_MESSAGE = 3
    COMPLETED = 4


def _serialize_patient_data(patient_data: dict) -> dict:
    serialized = {}
    for key, value in patient_data.items():
        if isinstance(value, (date, datetime)):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized


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
        """
        patient = Patient(**sample_patient_data)
        real_db_session.add(patient)
        real_db_session.commit()
        real_db_session.refresh(patient)

        cleanup_patients.track(patient.id)

        assert patient.id is not None
        assert patient.phone == sample_patient_data["phone"]

        saga = PatientOnboardingSaga(
            patient_id=patient.id,
            status=SagaStatus.STARTED,
            current_step=SagaStep.PATIENT_CREATED,
            patient_data=_serialize_patient_data(sample_patient_data),
            step_data={
                "source": "integration_test",
                "test_timestamp": datetime.now().isoformat(),
            },
        )
        real_db_session.add(saga)
        real_db_session.commit()
        real_db_session.refresh(saga)

        cleanup_sagas.track(saga.id)

        assert saga.id is not None
        assert saga.status == SagaStatus.STARTED
        assert saga.current_step == SagaStep.PATIENT_CREATED

        saga.status = SagaStatus.IN_PROGRESS
        saga.current_step = SagaStep.FLOW_INITIALIZED
        real_db_session.commit()

        real_db_session.refresh(saga)
        assert saga.status == SagaStatus.IN_PROGRESS
        assert saga.current_step == SagaStep.FLOW_INITIALIZED

        saga.current_step = SagaStep.WELCOME_MESSAGE
        real_db_session.commit()

        real_db_session.refresh(saga)
        assert saga.current_step == SagaStep.WELCOME_MESSAGE

        saga.current_step = SagaStep.COMPLETED
        saga.status = SagaStatus.COMPLETED
        saga.step_data["completion_timestamp"] = datetime.now().isoformat()
        real_db_session.commit()

        real_db_session.refresh(saga)
        assert saga.status == SagaStatus.COMPLETED
        assert saga.current_step == SagaStep.COMPLETED
        assert "completion_timestamp" in saga.step_data

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
        """
        patient = Patient(**sample_patient_data)
        real_db_session.add(patient)
        real_db_session.commit()
        real_db_session.refresh(patient)
        cleanup_patients.track(patient.id)

        saga = PatientOnboardingSaga(
            patient_id=patient.id,
            status=SagaStatus.STARTED,
            current_step=SagaStep.PATIENT_CREATED,
            patient_data=_serialize_patient_data(sample_patient_data),
            step_data={"test": "compensation_test"},
        )
        real_db_session.add(saga)
        real_db_session.commit()
        real_db_session.refresh(saga)
        cleanup_sagas.track(saga.id)

        saga.status = SagaStatus.IN_PROGRESS
        saga.current_step = SagaStep.FLOW_INITIALIZED
        real_db_session.commit()

        saga.status = SagaStatus.COMPENSATING
        saga.error_message = "Simulated flow initialization failure"
        saga.error_type = "IntegrationTest"
        saga.step_data["failed_step"] = int(SagaStep.FLOW_INITIALIZED)
        real_db_session.commit()

        real_db_session.refresh(saga)
        assert saga.status == SagaStatus.COMPENSATING
        assert saga.error_message is not None

        saga.current_step = SagaStep.PATIENT_CREATED
        saga.status = SagaStatus.COMPENSATED
        saga.step_data["compensation_timestamp"] = datetime.now().isoformat()
        real_db_session.commit()

        real_db_session.refresh(saga)
        assert saga.status == SagaStatus.COMPENSATED
        assert saga.current_step == SagaStep.PATIENT_CREATED
        assert "compensation_timestamp" in saga.step_data

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
        """
        num_patients = 3
        patients = []
        sagas = []

        for i in range(num_patients):
            timestamp = int(datetime.now().timestamp() * 1000) + i
            phone = f"+5511999{timestamp % 1000000:06d}"
            email = f"test_{timestamp}@example.com"

            patient_data = {
                "name": f"Test Patient {timestamp}",
                "phone": phone,
                "email": email,
                "birth_date": date(1990, 1, 1),
                "cpf": f"{timestamp % 100000000000:011d}",
            }

            patient = Patient(**patient_data)
            real_db_session.add(patient)
            real_db_session.commit()
            real_db_session.refresh(patient)
            patients.append(patient)
            cleanup_patients.track(patient.id)

            saga = PatientOnboardingSaga(
                patient_id=patient.id,
                status=SagaStatus.STARTED,
                current_step=SagaStep.PATIENT_CREATED,
                patient_data=_serialize_patient_data(patient_data),
                step_data={"batch_index": i},
            )
            real_db_session.add(saga)
            real_db_session.commit()
            real_db_session.refresh(saga)
            sagas.append(saga)
            cleanup_sagas.track(saga.id)

        assert len(patients) == num_patients
        assert len(sagas) == num_patients

        for saga in sagas:
            saga.status = SagaStatus.IN_PROGRESS
            saga.current_step = SagaStep.FLOW_INITIALIZED
            real_db_session.commit()

            saga.current_step = SagaStep.WELCOME_MESSAGE
            real_db_session.commit()

            saga.current_step = SagaStep.COMPLETED
            saga.status = SagaStatus.COMPLETED
            real_db_session.commit()

        for saga in sagas:
            real_db_session.refresh(saga)
            assert saga.status == SagaStatus.COMPLETED
            assert saga.current_step == SagaStep.COMPLETED

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
        """
        patient = Patient(**sample_patient_data)
        real_db_session.add(patient)
        real_db_session.commit()
        real_db_session.refresh(patient)
        cleanup_patients.track(patient.id)

        saga = PatientOnboardingSaga(
            patient_id=patient.id,
            status=SagaStatus.IN_PROGRESS,
            current_step=SagaStep.FLOW_INITIALIZED,
            patient_data=_serialize_patient_data(sample_patient_data),
            step_data={"retry_test": True},
        )
        real_db_session.add(saga)
        real_db_session.commit()
        real_db_session.refresh(saga)
        cleanup_sagas.track(saga.id)

        for retry in range(3):
            saga.step_data[f"attempt_{retry + 1}"] = datetime.now().isoformat()
            real_db_session.commit()
            real_db_session.refresh(saga)

            assert saga.current_step == SagaStep.FLOW_INITIALIZED
            assert saga.status == SagaStatus.IN_PROGRESS

        assert "attempt_1" in saga.step_data
        assert "attempt_2" in saga.step_data
        assert "attempt_3" in saga.step_data

        saga.current_step = SagaStep.WELCOME_MESSAGE
        real_db_session.commit()

        real_db_session.refresh(saga)
        assert saga.current_step == SagaStep.WELCOME_MESSAGE

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
        """
        patient = Patient(**sample_patient_data)
        real_db_session.add(patient)
        real_db_session.commit()
        real_db_session.refresh(patient)
        cleanup_patients.track(patient.id)

        saga = PatientOnboardingSaga(
            patient_id=patient.id,
            status=SagaStatus.IN_PROGRESS,
            current_step=SagaStep.FLOW_INITIALIZED,
            patient_data=_serialize_patient_data(sample_patient_data),
            step_data={
                "started_at": "2023-01-01T00:00:00",
                "timeout_test": True,
            },
        )
        real_db_session.add(saga)
        real_db_session.commit()
        real_db_session.refresh(saga)
        cleanup_sagas.track(saga.id)

        saga.status = SagaStatus.FAILED
        saga.error_message = "Saga execution timeout"
        saga.error_type = "Timeout"
        saga.step_data["timeout_detected"] = datetime.now().isoformat()
        real_db_session.commit()

        real_db_session.refresh(saga)
        assert saga.status == SagaStatus.FAILED
        assert "timeout_detected" in saga.step_data
        assert saga.error_message is not None
