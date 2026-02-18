import pytest
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.exceptions import FlowStateConflictError
from app.services.flow_core import (
    FlowCore,
    FLOW_ADVANCE_BLOCKED_MESSAGE as CORE_BLOCKED_MESSAGE,
    FLOW_ADVANCE_BLOCKED_CODE as CORE_BLOCKED_CODE,
    FLOW_ADVANCE_BLOCKED_REASON as CORE_BLOCKED_REASON,
)
from app.services.flow_management import (
    FlowManagementService,
    FLOW_ADVANCE_BLOCKED_MESSAGE as MGMT_BLOCKED_MESSAGE,
    FLOW_ADVANCE_BLOCKED_CODE as MGMT_BLOCKED_CODE,
    FLOW_ADVANCE_BLOCKED_REASON as MGMT_BLOCKED_REASON,
)


class _PlatformSyncStub:
    async def sync_patient_record_update(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_flow_core_blocks_advance_while_awaiting_response() -> None:
    db = MagicMock()
    db.rollback = MagicMock()

    service = FlowCore(
        db=db,
        platform_sync=_PlatformSyncStub(),
        template_loader=MagicMock(),
        template_cache=MagicMock(),
    )

    flow_state = SimpleNamespace(
        step_data={"awaiting_response": True},
        current_step=7,
    )
    service.flow_state_repo = MagicMock()
    service.flow_state_repo.get_active_flow.return_value = flow_state
    service.calculate_patient_day = AsyncMock(return_value=8)

    patient_id = uuid4()

    with pytest.raises(FlowStateConflictError) as exc_info:
        await service.advance_patient_flow(patient_id)

    error = exc_info.value
    assert str(error) == CORE_BLOCKED_MESSAGE
    assert error.code == CORE_BLOCKED_CODE
    assert error.details["blocked"] is True
    assert error.details["block_reason"] == CORE_BLOCKED_REASON
    assert error.details["patient_id"] == str(patient_id)
    service.calculate_patient_day.assert_not_awaited()
    db.rollback.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("awaiting_value", [True, "true", "YES", "1"])
async def test_flow_management_blocks_advance_while_awaiting_response(
    awaiting_value,
) -> None:
    flow_repo = MagicMock()
    flow_repo.db = MagicMock()

    flow_state = SimpleNamespace(
        id=uuid4(),
        status="active",
        step_data={"awaiting_response": awaiting_value},
        current_step=3,
        version=1,
        flow_template_version_id=uuid4(),
        completed_at=None,
    )
    flow_repo.get_active_flow.return_value = flow_state

    with patch("app.services.flow_management.EnhancedFlowEngine") as engine_cls:
        engine = MagicMock()
        engine_cls.return_value = engine
        service = FlowManagementService(flow_repo=flow_repo, db=MagicMock())

        patient_id = uuid4()
        with pytest.raises(FlowStateConflictError) as exc_info:
            await service.advance_patient_flow(patient_id)

    error = exc_info.value
    assert str(error) == MGMT_BLOCKED_MESSAGE
    assert error.code == MGMT_BLOCKED_CODE
    assert error.details["blocked"] is True
    assert error.details["block_reason"] == MGMT_BLOCKED_REASON
    assert error.details["patient_id"] == str(patient_id)
    engine._commit_flow_state_with_lock.assert_not_called()
    flow_repo.db.query.assert_not_called()
