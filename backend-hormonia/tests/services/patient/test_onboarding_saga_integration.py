"""
Unit tests for OnboardingCoordinator - Saga Integration Scenarios.

This test suite validates coordinator behavior around saga requirements:
- Saga orchestrator is required
- Saga feature flag gating
- Saga returns a valid patient
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
def base_dependencies():
    db = Mock()
    integrity_service = Mock()
    validation_service = Mock()
    notification_service = Mock()
    completion_service = Mock()
    creation_service = Mock()

    return {
        "db": db,
        "integrity_service": integrity_service,
        "validation_service": validation_service,
        "notification_service": notification_service,
        "completion_service": completion_service,
        "creation_service": creation_service,
    }


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


def _set_saga_enabled(monkeypatch, enabled: bool):
    from app.domain.patient.onboarding import coordinator as coordinator_module
    from types import SimpleNamespace

    monkeypatch.setattr(
        coordinator_module,
        "settings",
        SimpleNamespace(ENABLE_SAGA_PATTERN=enabled),
    )


@pytest.mark.asyncio
async def test_create_patient_requires_saga_orchestrator(
    base_dependencies,
    valid_patient_data,
    doctor_id,
    monkeypatch,
):
    _set_saga_enabled(monkeypatch, True)

    coordinator = OnboardingCoordinator(
        **base_dependencies,
        saga_orchestrator=None,
    )

    with pytest.raises(ValidationError, match="Saga Pattern desabilitado"):
        await coordinator.create_patient(
            patient_data=valid_patient_data,
            doctor_id=doctor_id,
        )

    base_dependencies["integrity_service"].validate_patient_data.assert_called_once_with(
        patient_data=valid_patient_data,
        doctor_id=doctor_id,
        is_update=False,
    )


@pytest.mark.asyncio
async def test_create_patient_fails_when_saga_disabled(
    base_dependencies,
    valid_patient_data,
    doctor_id,
    monkeypatch,
):
    _set_saga_enabled(monkeypatch, False)

    saga_orchestrator = Mock()
    saga_orchestrator.execute_patient_onboarding_saga = AsyncMock()
    coordinator = OnboardingCoordinator(
        **base_dependencies,
        saga_orchestrator=saga_orchestrator,
    )

    with pytest.raises(ValidationError, match="Saga Pattern desabilitado"):
        await coordinator.create_patient(
            patient_data=valid_patient_data,
            doctor_id=doctor_id,
        )

    base_dependencies["integrity_service"].validate_patient_data.assert_called_once_with(
        patient_data=valid_patient_data,
        doctor_id=doctor_id,
        is_update=False,
    )
    saga_orchestrator.execute_patient_onboarding_saga.assert_not_called()


@pytest.mark.asyncio
async def test_create_patient_raises_when_saga_returns_none(
    base_dependencies,
    valid_patient_data,
    doctor_id,
    monkeypatch,
):
    _set_saga_enabled(monkeypatch, True)

    saga_orchestrator = Mock()
    saga_orchestrator.execute_patient_onboarding_saga = AsyncMock(return_value=None)
    coordinator = OnboardingCoordinator(
        **base_dependencies,
        saga_orchestrator=saga_orchestrator,
    )

    with pytest.raises(ValidationError, match="não retornou paciente"):
        await coordinator.create_patient(
            patient_data=valid_patient_data,
            doctor_id=doctor_id,
        )

    saga_orchestrator.execute_patient_onboarding_saga.assert_awaited_once()
