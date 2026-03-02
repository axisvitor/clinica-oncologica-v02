"""
Fixtures for Saga Compensation Testing.

Provides comprehensive test fixtures for testing saga orchestration,
compensation logic, and rollback scenarios.
"""

import uuid
from datetime import datetime
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock

import pytest
from sqlalchemy.orm import Session

from app.models.patient import Patient, FlowState
from app.models.flow import PatientFlowState
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus
from app.orchestration.saga_orchestrator import SagaOrchestrator


from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
@pytest.fixture
def test_patient_data() -> Dict[str, Any]:
    """
    Provide valid patient data for saga testing.

    Returns:
        Dict with patient creation data
    """
    return {
        "name": "João Silva",
        "phone": "5548999887766",
        "email": "joao.silva@example.com",
        "cpf": "12345678909",
        "birth_date": "1985-05-15",
        "doctor_id": uuid.uuid4(),
    }


@pytest.fixture
def test_saga_id() -> uuid.UUID:
    """Generate unique saga ID for testing."""
    return uuid.uuid4()


@pytest.fixture
def mock_redis():
    """
    Mock Redis client for saga state persistence.

    Returns:
        Mock Redis with setex, get, delete methods
    """
    redis_mock = Mock()
    redis_mock.setex = Mock(return_value=True)
    redis_mock.get = Mock(return_value=None)
    redis_mock.delete = Mock(return_value=1)
    return redis_mock


@pytest.fixture
def saga_orchestrator(
    db_session: Session,
    mock_redis,
) -> SagaOrchestrator:
    """
    Create saga orchestrator with mocked external services.

    Args:
        db_session: SQLAlchemy database session
        mock_redis: Mocked Redis client

    Returns:
        Configured SagaOrchestrator instance
    """
    return SagaOrchestrator(
        db=db_session,
        redis=mock_redis,
        enable_persistence=True,
        max_retries=3,
        retry_initial_delay=0.1,  # Fast retries for tests
        retry_max_delay=1,
        global_timeout=30,
    )


@pytest.fixture
def failed_saga_record(
    db_session: Session,
    test_patient_data: Dict[str, Any],
    test_saga_id: uuid.UUID,
) -> PatientOnboardingSaga:
    """
    Create a failed saga record for compensation testing.

    Args:
        db_session: Database session
        test_patient_data: Patient data
        test_saga_id: Saga ID

    Returns:
        PatientOnboardingSaga in FAILED status
    """
    saga = PatientOnboardingSaga(
        id=test_saga_id,
        patient_id=None,  # Failed before patient creation
        doctor_id=test_patient_data["doctor_id"],
        status=SagaStatus.FAILED,
        current_step=0,
        retry_count=3,
        max_retries=3,
        patient_data=test_patient_data,
        execution_log=[],
        error_message="Simulated failure for testing",
        error_type="TestError",
        started_at=now_sao_paulo_naive(),
    )
    db_session.add(saga)
    db_session.commit()
    return saga


@pytest.fixture
def completed_patient_record(
    db_session: Session,
    test_patient_data: Dict[str, Any],
) -> Patient:
    """
    Create a completed patient record for compensation testing.

    Args:
        db_session: Database session
        test_patient_data: Patient data

    Returns:
        Patient record in database
    """
    patient = Patient(
        name=test_patient_data["name"],
        phone=test_patient_data["phone"],
        email=test_patient_data["email"],
        cpf=test_patient_data["cpf"],
        birth_date=test_patient_data["birth_date"],
        doctor_id=test_patient_data["doctor_id"],
        flow_state=FlowState.ONBOARDING_START,
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


@pytest.fixture
def completed_flow_state(
    db_session: Session,
    completed_patient_record: Patient,
) -> PatientFlowState:
    """
    Create a flow state for compensation testing.

    Args:
        db_session: Database session
        completed_patient_record: Patient with flow state

    Returns:
        PatientFlowState record
    """
    # Get or create flow template
    from app.models.flow import FlowKind, FlowTemplateVersion

    flow_kind = db_session.query(FlowKind).filter(
        FlowKind.flow_type == "onboarding"
    ).first()

    if not flow_kind:
        flow_kind = FlowKind(
            flow_type="onboarding",
            display_name="Onboarding - First 15 Days",
            description="Initial patient onboarding flow",
        )
        db_session.add(flow_kind)
        db_session.flush()

    template_version = db_session.query(FlowTemplateVersion).filter(
        FlowTemplateVersion.kind_id == flow_kind.id,
        FlowTemplateVersion.is_active == True,
    ).first()

    if not template_version:
        template_version = FlowTemplateVersion(
            kind_id=flow_kind.id,
            version=1,
            template_data={"steps": []},
            is_active=True,
        )
        db_session.add(template_version)
        db_session.flush()

    flow_state = PatientFlowState(
        patient_id=completed_patient_record.id,
        template_version_id=template_version.id,
        current_step=0,
        state_data={},
    )
    db_session.add(flow_state)
    db_session.commit()
    db_session.refresh(flow_state)
    return flow_state


@pytest.fixture
def saga_with_partial_completion(
    db_session: Session,
    completed_patient_record: Patient,
    test_saga_id: uuid.UUID,
) -> PatientOnboardingSaga:
    """
    Create saga that completed step 1 (patient creation) but failed on step 2.

    Args:
        db_session: Database session
        completed_patient_record: Created patient
        test_saga_id: Saga ID

    Returns:
        PatientOnboardingSaga in FAILED status with patient_id set
    """
    saga = PatientOnboardingSaga(
        id=test_saga_id,
        patient_id=completed_patient_record.id,
        doctor_id=completed_patient_record.doctor_id,
        status=SagaStatus.FAILED,
        current_step=1,  # Failed after step 1
        retry_count=3,
        max_retries=3,
        patient_data={
            "name": completed_patient_record.name,
            "phone": completed_patient_record.phone,
            "email": completed_patient_record.email,
        },
        execution_log=[
            {
                "step": 1,
                "action": "create_patient",
                "status": "success",
                "timestamp": now_sao_paulo_naive().isoformat(),
            },
            {
                "step": 2,
                "action": "create_flow_state",
                "status": "failed",
                "timestamp": now_sao_paulo_naive().isoformat(),
                "message": "Simulated flow state creation failure",
            },
        ],
        error_message="Flow state creation failed",
        error_type="FlowStateError",
        started_at=now_sao_paulo_naive(),
    )
    db_session.add(saga)
    db_session.commit()
    return saga


@pytest.fixture
def mock_failing_action():
    """
    Mock action that always fails for testing compensation.

    Returns:
        AsyncMock that raises exception
    """
    async def failing_action(*args, **kwargs):
        raise Exception("Simulated step failure")

    return AsyncMock(side_effect=failing_action)


@pytest.fixture
def mock_successful_compensation():
    """
    Mock compensation that always succeeds.

    Returns:
        AsyncMock that returns True
    """
    async def successful_compensation(*args, **kwargs):
        return True

    return AsyncMock(return_value=True)


@pytest.fixture
def mock_failing_compensation():
    """
    Mock compensation that fails for testing error handling.

    Returns:
        AsyncMock that raises exception
    """
    async def failing_compensation(*args, **kwargs):
        raise Exception("Compensation failed")

    return AsyncMock(side_effect=failing_compensation)


__all__ = [
    "test_patient_data",
    "test_saga_id",
    "mock_redis",
    "saga_orchestrator",
    "failed_saga_record",
    "completed_patient_record",
    "completed_flow_state",
    "saga_with_partial_completion",
    "mock_failing_action",
    "mock_successful_compensation",
    "mock_failing_compensation",
]
