from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v2.routers.admin_extensions.dependencies import get_admin_user
from app.core.database.async_engine import get_async_db
from app.models.flow import PatientFlowState
from app.utils.request_context import RequestContext, get_request_context


class FakeResult:
    def __init__(
        self,
        *,
        scalar_value: Any = None,
        rows: list[Any] | None = None,
    ) -> None:
        self._scalar_value = scalar_value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._scalar_value

    def scalar(self) -> Any:
        return self._scalar_value

    def all(self) -> list[Any]:
        return list(self._rows)


def build_flow_state(
    *,
    patient_id=None,
    current_step: int = 1,
    version: int = 0,
    step_data: dict[str, Any] | None = None,
    updated_at: datetime | None = None,
) -> PatientFlowState:
    return PatientFlowState(
        id=uuid4(),
        patient_id=patient_id or uuid4(),
        flow_template_version_id=uuid4(),
        current_step=current_step,
        status="active",
        version=version,
        step_data=step_data or {},
        updated_at=updated_at or datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def client(mock_db):
    from app.api.v2.routers.admin_extensions import router

    app = FastAPI()
    app.include_router(router, prefix="/admin-ext")

    async def _override_db():
        yield mock_db

    async def _override_admin_user():
        return {"id": str(uuid4()), "email": "admin@test.com", "role": "admin"}

    async def _override_context():
        return RequestContext(ip_address="127.0.0.1", user_agent="pytest")

    app.dependency_overrides[get_async_db] = _override_db
    app.dependency_overrides[get_admin_user] = _override_admin_user
    app.dependency_overrides[get_request_context] = _override_context

    with TestClient(app) as test_client:
        yield test_client


def test_reset_flow_returns_cleared_fields_for_active_flow(client, mock_db):
    patient_id = uuid4()
    flow_state = build_flow_state(
        patient_id=patient_id,
        version=5,
        step_data={
            "awaiting_response": True,
            "context_mismatch_count": 3,
            "pending_response_context": {"flow_day": 2},
            "keep": "value",
        },
    )
    mock_db.execute.return_value = FakeResult(scalar_value=flow_state)

    with patch(
        "app.api.v2.routers.admin_extensions.flow_ops.log_admin_extension_action",
        new=AsyncMock(),
    ) as audit_log:
        response = client.post(f"/admin-ext/flow-ops/{patient_id}/reset")

    assert response.status_code == 200
    assert response.json() == {
        "patient_id": str(patient_id),
        "flow_state_id": str(flow_state.id),
        "action": "reset",
        "cleared_fields": [
            "awaiting_response",
            "context_mismatch_count",
            "pending_response_context",
        ],
    }
    assert flow_state.step_data == {"keep": "value"}
    assert flow_state.version == 6
    mock_db.commit.assert_awaited_once()
    audit_log.assert_awaited_once()


def test_reset_flow_returns_404_when_no_active_flow(client, mock_db):
    patient_id = uuid4()
    mock_db.execute.return_value = FakeResult(scalar_value=None)

    response = client.post(f"/admin-ext/flow-ops/{patient_id}/reset")

    assert response.status_code == 404
    assert response.json()["detail"] == "Active flow not found"


def test_advance_flow_returns_next_day_for_active_flow(client, mock_db):
    patient_id = uuid4()
    flow_state = build_flow_state(
        patient_id=patient_id,
        current_step=3,
        version=7,
        step_data={
            "current_flow_day": 3,
            "current_day_message_index": 2,
            "flow_kind": "onboarding",
            "awaiting_response": True,
        },
    )
    mock_db.execute.return_value = FakeResult(scalar_value=flow_state)

    with (
        patch(
            "app.api.v2.routers.admin_extensions.flow_ops.advance_day_atomic",
            new=AsyncMock(return_value={"day_advance_verified": True}),
        ) as advance_day,
        patch(
            "app.api.v2.routers.admin_extensions.flow_ops.log_admin_extension_action",
            new=AsyncMock(),
        ) as audit_log,
    ):
        response = client.post(f"/admin-ext/flow-ops/{patient_id}/advance")

    assert response.status_code == 200
    assert response.json() == {
        "patient_id": str(patient_id),
        "flow_state_id": str(flow_state.id),
        "action": "advance",
        "new_day": 4,
    }
    assert flow_state.current_step == 4
    assert flow_state.step_data["current_flow_day"] == 4
    advance_day.assert_awaited_once()
    audit_log.assert_awaited_once()


def test_advance_flow_returns_404_when_no_active_flow(client, mock_db):
    patient_id = uuid4()
    mock_db.execute.return_value = FakeResult(scalar_value=None)

    response = client.post(f"/admin-ext/flow-ops/{patient_id}/advance")

    assert response.status_code == 404
    assert response.json()["detail"] == "Active flow not found"


def test_unstick_flow_returns_cleared_fields_for_active_flow(client, mock_db):
    patient_id = uuid4()
    flow_state = build_flow_state(
        patient_id=patient_id,
        version=2,
        step_data={
            "awaiting_response": True,
            "recovery_attempts": 2,
            "last_recovery_at": "2026-03-06T12:00:00+00:00",
            "context_mismatch_count": 4,
            "keep": "value",
        },
    )
    mock_db.execute.return_value = FakeResult(scalar_value=flow_state)

    with patch(
        "app.api.v2.routers.admin_extensions.flow_ops.log_admin_extension_action",
        new=AsyncMock(),
    ) as audit_log:
        response = client.post(f"/admin-ext/flow-ops/{patient_id}/unstick")

    assert response.status_code == 200
    assert response.json() == {
        "patient_id": str(patient_id),
        "flow_state_id": str(flow_state.id),
        "action": "unstick",
        "cleared_fields": [
            "awaiting_response",
            "recovery_attempts",
            "last_recovery_at",
            "context_mismatch_count",
        ],
    }
    assert flow_state.step_data == {"keep": "value"}
    assert flow_state.version == 3
    mock_db.commit.assert_awaited_once()
    audit_log.assert_awaited_once()


def test_list_failed_flow_ops_returns_delivery_failures(client, mock_db):
    updated_at = datetime(2026, 3, 6, 18, 0, tzinfo=timezone.utc)
    flow_state = build_flow_state(
        current_step=4,
        updated_at=updated_at,
        step_data={
            "delivery_failures": [
                {"message_id": "msg-1", "error": "timeout", "attempt": 3}
            ],
            "permanently_failed_at": "2026-03-06T17:59:00+00:00",
        },
    )
    mock_db.execute.side_effect = [
        FakeResult(scalar_value=1),
        FakeResult(rows=[(flow_state, "Maria Flow")]),
    ]

    response = client.get("/admin-ext/flow-ops/failed")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert len(body["items"]) == 1

    item = body["items"][0]
    assert item["flow_state_id"] == str(flow_state.id)
    assert item["patient_id"] == str(flow_state.patient_id)
    assert item["patient_name"] == "Maria Flow"
    assert item["current_step"] == 4
    assert item["failure_type"] == "delivery_failure"
    assert item["failure_details"] == {
        "delivery_failures": [
            {"message_id": "msg-1", "error": "timeout", "attempt": 3}
        ],
        "permanently_failed_at": "2026-03-06T17:59:00+00:00",
    }
    assert item["updated_at"].startswith("2026-03-06T18:00:00")


def test_list_failed_flow_ops_returns_mismatch_resets(client, mock_db):
    updated_at = datetime(2026, 3, 6, 18, 5, tzinfo=timezone.utc)
    flow_state = build_flow_state(
        current_step=2,
        updated_at=updated_at,
        step_data={
            "last_mismatch_reset_at": "2026-03-06T18:00:00+00:00",
            "context_mismatch_count": 3,
        },
    )
    mock_db.execute.side_effect = [
        FakeResult(scalar_value=1),
        FakeResult(rows=[(flow_state, "Mismatch Patient")]),
    ]

    response = client.get("/admin-ext/flow-ops/failed")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["failure_type"] == "mismatch_reset"
    assert item["failure_details"] == {
        "last_mismatch_reset_at": "2026-03-06T18:00:00+00:00",
        "context_mismatch_count": 3,
    }


def test_list_failed_flow_ops_returns_empty_list_when_no_failures(client, mock_db):
    mock_db.execute.side_effect = [
        FakeResult(scalar_value=0),
        FakeResult(rows=[]),
    ]

    response = client.get("/admin-ext/flow-ops/failed")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_failed_flow_ops_respects_limit_and_offset(client, mock_db):
    updated_at = datetime(2026, 3, 6, 18, 10, tzinfo=timezone.utc)
    flow_state = build_flow_state(
        current_step=5,
        updated_at=updated_at,
        step_data={"delivery_failures": [{"message_id": "msg-2"}]},
    )
    mock_db.execute.side_effect = [
        FakeResult(scalar_value=2),
        FakeResult(rows=[(flow_state, "Paged Patient")]),
    ]

    response = client.get("/admin-ext/flow-ops/failed", params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    assert response.json()["limit"] == 1
    assert response.json()["offset"] == 1

    list_statement = mock_db.execute.await_args_list[1].args[0]
    assert list_statement._limit_clause.value == 1
    assert list_statement._offset_clause.value == 1


def test_mutating_flow_ops_endpoints_emit_audit_logs(client, mock_db):
    patient_id = uuid4()
    flow_state = build_flow_state(
        patient_id=patient_id,
        current_step=1,
        step_data={"current_flow_day": 1, "flow_kind": "onboarding"},
    )

    with (
        patch(
            "app.api.v2.routers.admin_extensions.flow_ops.log_admin_extension_action",
            new=AsyncMock(),
        ) as audit_log,
        patch(
            "app.api.v2.routers.admin_extensions.flow_ops.advance_day_atomic",
            new=AsyncMock(return_value={"day_advance_verified": True}),
        ),
    ):
        for endpoint in ("reset", "advance", "unstick"):
            mock_db.execute.reset_mock()
            mock_db.commit.reset_mock()
            mock_db.execute.return_value = FakeResult(scalar_value=flow_state)

            response = client.post(f"/admin-ext/flow-ops/{patient_id}/{endpoint}")

            assert response.status_code == 200

    assert audit_log.await_count == 3
