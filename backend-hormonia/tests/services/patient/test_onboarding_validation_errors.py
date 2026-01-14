"""
Unit tests for OnboardingCoordinator - Validation and Error Scenarios.

This test suite covers patient onboarding failures including:
- Data validation errors
- Saga orchestrator failures
- Error wrapping semantics
"""

import pytest
from datetime import date
from uuid import uuid4
from unittest.mock import Mock, AsyncMock

from app.domain.patient.onboarding.coordinator import OnboardingCoordinator
from app.exceptions import ValidationError
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
    )


@pytest.fixture
def doctor_id():
    return uuid4()


def _enable_saga(monkeypatch):
    from app.domain.patient.onboarding import coordinator as coordinator_module
    from types import SimpleNamespace

    monkeypatch.setattr(
        coordinator_module,
        "settings",
        SimpleNamespace(ENABLE_SAGA_PATTERN=True),
    )


@pytest.mark.asyncio
async def test_integrity_validation_error_propagated(
    coordinator,
    mock_dependencies,
    valid_patient_data,
    doctor_id,
    monkeypatch,
):
    _enable_saga(monkeypatch)
    mock_dependencies["integrity_service"].validate_patient_data.side_effect = ValidationError(
        "Invalid email format"
    )

    with pytest.raises(ValidationError, match="Invalid email format"):
        await coordinator.create_patient(
            patient_data=valid_patient_data,
            doctor_id=doctor_id,
        )

    mock_dependencies["saga_orchestrator"].execute_patient_onboarding_saga.assert_not_called()


@pytest.mark.asyncio
async def test_saga_validation_error_passthrough(
    coordinator,
    mock_dependencies,
    valid_patient_data,
    doctor_id,
    monkeypatch,
):
    _enable_saga(monkeypatch)
    mock_dependencies["saga_orchestrator"].execute_patient_onboarding_saga.side_effect = ValidationError(
        "Saga validation failure"
    )

    with pytest.raises(ValidationError, match="Saga validation failure"):
        await coordinator.create_patient(
            patient_data=valid_patient_data,
            doctor_id=doctor_id,
        )


@pytest.mark.asyncio
async def test_saga_generic_error_wrapped(
    coordinator,
    mock_dependencies,
    valid_patient_data,
    doctor_id,
    monkeypatch,
):
    _enable_saga(monkeypatch)
    mock_dependencies["saga_orchestrator"].execute_patient_onboarding_saga.side_effect = Exception(
        "Saga orchestrator error"
    )

    with pytest.raises(ValidationError, match="Falha ao executar Saga Pattern"):
        await coordinator.create_patient(
            patient_data=valid_patient_data,
            doctor_id=doctor_id,
        )
