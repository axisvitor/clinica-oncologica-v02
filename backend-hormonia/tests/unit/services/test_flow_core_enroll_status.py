from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.services.flow.types import FlowType
from app.services.flow_core import FlowCore
from app.utils.timezone import now_sao_paulo


class _QueryResult:
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class _AsyncLikeSession:
    def __init__(self, execute_results):
        self._execute_results = list(execute_results)
        self.execute = AsyncMock(side_effect=self._pop_execute_result)
        self.add = Mock()
        self.commit = AsyncMock()
        self.flush = AsyncMock()
        self.refresh = AsyncMock()
        self.rollback = AsyncMock()
        self.query = Mock()

    async def _pop_execute_result(self, _statement):
        if not self._execute_results:
            raise AssertionError("Unexpected execute() call in test")
        return _QueryResult(self._execute_results.pop(0))


@pytest.mark.asyncio
async def test_enroll_patient_initializes_active_flow_state():
    patient = SimpleNamespace(id=uuid4(), created_at=now_sao_paulo())
    flow_kind = SimpleNamespace(id=uuid4(), kind_key=FlowType.ONBOARDING.value)
    active_version = SimpleNamespace(id=uuid4())
    db = _AsyncLikeSession([patient, None, flow_kind, active_version])

    service = FlowCore(
        db,
        platform_sync=Mock(),
        template_loader=Mock(),
        template_cache=Mock(),
    )

    flow_state = await service.enroll_patient(
        patient_id=patient.id,
        flow_type=FlowType.ONBOARDING,
        auto_commit=False,
    )

    assert flow_state.patient_id == patient.id
    assert flow_state.current_step == 1
    assert flow_state.status == "active"
    assert flow_state.step_data["enrollment_date"]
    db.add.assert_called_once_with(flow_state)
    db.flush.assert_awaited_once()
    db.commit.assert_not_awaited()
    db.refresh.assert_awaited_once_with(flow_state)
