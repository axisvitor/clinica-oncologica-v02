"""
Unit tests for OnboardingCoordinator - Happy Path Scenarios.

This test suite covers successful patient onboarding flows including:
- Saga-based creation
- Propagation of idempotency keys to the saga orchestrator

Priority: P0 - Critical Business Path
"""

import pytest
from datetime import date
from uuid import uuid4
from unittest.mock import Mock, AsyncMock

from app.domain.patient.onboarding.coordinator import OnboardingCoordinator
from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.utils.db_retry import reset_circuit_breaker


@pytest.fixture(autouse=True)
def _reset_circuit_breaker_state():
    reset_circuit_breaker()


@pytest.fixture
def mock_dependencies():
    db = Mock()
    integrity_service = Mock()
    validation_service = Mock()
    saga_orchestrator = Mock()
    saga_orchestrator.execute_patient_onboarding_saga = AsyncMock()
    notification_service = Mock()
    completion_service = Mock()
    creation_service = Mock()

    return {
        "db": db,
        "integrity_service": integrity_service,
        "validation_service": validation_service,
        "saga_orchestrator": saga_orchestrator,
        "notification_service": notification_service,
        "completion_service": completion_service,
        "creation_service": creation_service,
    }


@pytest.fixture
def coordinator(mock_dependencies):
    return OnboardingCoordinator(**mock_dependencies)


@pytest.fixture
def valid_patient_data():
    return PatientCreate(
        name="Joao Silva",
        email="joao.silva@example.com",
        phone="+5511999887766",
        birth_date=date(1980, 5, 15),
        treatment_type="Quimioterapia",
    )


@pytest.fixture
def doctor_id():
    return uuid4()


@pytest.fixture
def current_user():
    user = Mock()
    user.id = uuid4()
    user.email = "doctor@example.com"
    return user


def _enable_saga(monkeypatch):
    from app.domain.patient.onboarding import coordinator as coordinator_module
    from types import SimpleNamespace

    monkeypatch.setattr(
        coordinator_module,
        "settings",
        SimpleNamespace(ENABLE_SAGA_PATTERN=True),
    )


@pytest.mark.asyncio
async def test_create_patient_via_saga_returns_patient(
    coordinator,
    mock_dependencies,
    valid_patient_data,
    doctor_id,
    current_user,
    monkeypatch,
):
    _enable_saga(monkeypatch)

    expected_patient = Patient(
        id=uuid4(),
        name=valid_patient_data.name,
        phone=valid_patient_data.phone,
        email=valid_patient_data.email,
        doctor_id=doctor_id,
    )
    mock_dependencies["saga_orchestrator"].execute_patient_onboarding_saga.return_value = (
        expected_patient
    )

    result = await coordinator.create_patient(
        patient_data=valid_patient_data,
        doctor_id=doctor_id,
        current_user=current_user,
    )

    assert result == expected_patient
    mock_dependencies["integrity_service"].validate_patient_data.assert_called_once_with(
        patient_data=valid_patient_data,
        doctor_id=doctor_id,
        is_update=False,
    )
    mock_dependencies[
        "saga_orchestrator"
    ].execute_patient_onboarding_saga.assert_awaited_once_with(
        patient_data=valid_patient_data,
        doctor_id=doctor_id,
        current_user=current_user,
        idempotency_key=None,
    )


@pytest.mark.asyncio
async def test_create_patient_passes_idempotency_key(
    coordinator,
    mock_dependencies,
    valid_patient_data,
    doctor_id,
    current_user,
    monkeypatch,
):
    _enable_saga(monkeypatch)

    idempotency_key = "test-idempotency-key"
    expected_patient = Patient(
        id=uuid4(),
        name=valid_patient_data.name,
        phone=valid_patient_data.phone,
        email=valid_patient_data.email,
        doctor_id=doctor_id,
    )
    mock_dependencies["saga_orchestrator"].execute_patient_onboarding_saga.return_value = (
        expected_patient
    )

    result = await coordinator.create_patient(
        patient_data=valid_patient_data,
        doctor_id=doctor_id,
        current_user=current_user,
        idempotency_key=idempotency_key,
    )

    assert result == expected_patient
    mock_dependencies[
        "saga_orchestrator"
    ].execute_patient_onboarding_saga.assert_awaited_once_with(
        patient_data=valid_patient_data,
        doctor_id=doctor_id,
        current_user=current_user,
        idempotency_key=idempotency_key,
    )
