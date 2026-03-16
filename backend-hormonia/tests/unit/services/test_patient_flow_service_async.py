from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.models.patient import FlowState
from app.services.flow.types import FlowType
from app.services.patient.flow_service import PatientFlowService
from app.utils.timezone import now_sao_paulo


class _ScalarResult:
    def __init__(self, item):
        self._item = item

    def first(self):
        return self._item

    def all(self):
        if self._item is None:
            return []
        if isinstance(self._item, list):
            return list(self._item)
        return [self._item]


class _QueryResult:
    def __init__(self, item):
        self._item = item

    def scalars(self):
        return _ScalarResult(self._item)


class _AsyncLikeSession:
    def __init__(self, *, execute_results=None, patient=None):
        self._execute_results = list(execute_results or [])
        self._patient = patient
        self.add = Mock()
        self.execute = AsyncMock(side_effect=self._pop_execute_result)
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.refresh = AsyncMock()
        self.rollback = AsyncMock()
        self.delete = AsyncMock()

    async def _pop_execute_result(self, _statement):
        if not self._execute_results:
            raise AssertionError("Unexpected execute() call in test")
        return _QueryResult(self._execute_results.pop(0))

    async def get(self, _model, _patient_id):
        return self._patient


@pytest.mark.asyncio
async def test_initialize_default_flow_supports_async_session_selection_and_flush():
    flow_kind = SimpleNamespace(kind_key=FlowType.ONBOARDING.value)
    db = _AsyncLikeSession(execute_results=[flow_kind])
    started_at = now_sao_paulo()
    flow_state = SimpleNamespace(started_at=started_at)
    flow_engine = SimpleNamespace(enroll_patient=AsyncMock(return_value=flow_state))
    patient = SimpleNamespace(
        id=uuid4(),
        current_flow_type=None,
        treatment_type=FlowType.ONBOARDING.value,
        patient_data={},
    )
    current_user_id = uuid4()

    service = PatientFlowService(db=db, flow_engine=flow_engine)

    result = await service.initialize_default_flow(
        patient,
        current_user_id=current_user_id,
        auto_commit=False,
    )

    assert result is flow_state
    flow_engine.enroll_patient.assert_awaited_once_with(
        patient_id=patient.id,
        flow_type=FlowType.ONBOARDING,
        auto_commit=False,
    )
    db.execute.assert_awaited_once()
    db.flush.assert_awaited_once()
    db.commit.assert_not_awaited()
    assert patient.patient_data["actual_flow_type"] == FlowType.ONBOARDING.value
    assert patient.patient_data["initialized_by"] == str(current_user_id)
    assert patient.patient_data["flow_start_time"] == started_at.isoformat()


@pytest.mark.asyncio
async def test_activate_patient_updates_async_session_patient_without_sync_repository():
    started_at = now_sao_paulo() - timedelta(days=2)
    patient = SimpleNamespace(
        id=uuid4(),
        name="Paciente Async",
        doctor_id=uuid4(),
        patient_data={"flow_start_time": started_at.isoformat()},
        current_day=0,
        created_at=started_at,
        flow_state=FlowState.ONBOARDING,
    )
    db = _AsyncLikeSession(execute_results=[patient], patient=patient)

    service = PatientFlowService(db=db, flow_engine=SimpleNamespace())

    updated = await service.activate_patient(patient.id, auto_commit=False)

    assert updated is patient
    assert patient.flow_state == FlowState.ACTIVE
    assert patient.current_day >= 1
    db.add.assert_called_once_with(patient)
    db.flush.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_activate_patient_sets_flow_start_time_when_missing_with_async_session():
    patient = SimpleNamespace(
        id=uuid4(),
        name="Paciente Async",
        doctor_id=uuid4(),
        patient_data={},
        current_day=0,
        created_at=now_sao_paulo(),
        flow_state=FlowState.ONBOARDING,
    )
    db = _AsyncLikeSession(execute_results=[patient], patient=patient)

    service = PatientFlowService(db=db, flow_engine=SimpleNamespace())

    await service.activate_patient(patient.id, auto_commit=False)

    assert "flow_start_time" in patient.patient_data
    assert patient.flow_state == FlowState.ACTIVE
