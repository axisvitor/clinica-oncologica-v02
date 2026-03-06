from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from app.api.v2.routers.admin_extensions.dependencies import get_admin_user
from app.core.database.async_engine import get_async_db
from app.utils.request_context import RequestContext, get_request_context


@pytest.fixture
def mock_db():
    db = AsyncMock()
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


@pytest.fixture
def client_without_admin(mock_db):
    from app.api.v2.routers.admin_extensions import router

    app = FastAPI()
    app.include_router(router, prefix="/admin-ext")

    async def _override_db():
        yield mock_db

    async def _override_context():
        return RequestContext(ip_address="127.0.0.1", user_agent="pytest")

    async def _override_admin_user():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authentication required",
        )

    app.dependency_overrides[get_async_db] = _override_db
    app.dependency_overrides[get_request_context] = _override_context
    app.dependency_overrides[get_admin_user] = _override_admin_user

    with TestClient(app) as test_client:
        yield test_client


def test_get_flow_health_returns_summary_counts(client):
    service = MagicMock()
    service.get_health_summary = AsyncMock(
        return_value={"active": 5, "stalled": 2, "failed": 1, "completed": 8}
    )

    with patch(
        "app.api.v2.routers.admin_extensions.flow_health.FlowHealthService",
        return_value=service,
    ):
        response = client.get("/admin-ext/flow-health/")

    assert response.status_code == 200
    assert response.json() == {
        "active": 5,
        "stalled": 2,
        "failed": 1,
        "completed": 8,
    }
    service.get_health_summary.assert_awaited_once()


def test_post_check_stalls_returns_results_and_audits_action(client):
    stalled_flows = [
        {
            "patient_id": str(uuid4()),
            "flow_state_id": str(uuid4()),
            "hours_stuck": 9.0,
            "last_interaction_at": "2026-03-06T12:00:00+00:00",
        }
    ]
    service = MagicMock()
    service.check_and_fire_stall_alerts = AsyncMock(return_value=stalled_flows)

    with (
        patch(
            "app.api.v2.routers.admin_extensions.flow_health.FlowHealthService",
            return_value=service,
        ),
        patch(
            "app.api.v2.routers.admin_extensions.flow_health.log_admin_extension_action",
            new=AsyncMock(),
        ) as audit_log,
    ):
        response = client.post("/admin-ext/flow-health/check-stalls")

    assert response.status_code == 200
    assert response.json() == {
        "stalled_count": 1,
        "alerts_fired": True,
        "stalled_flows": stalled_flows,
    }
    service.check_and_fire_stall_alerts.assert_awaited_once()
    audit_log.assert_awaited_once()


def test_flow_health_endpoints_require_admin_auth(client_without_admin):
    response = client_without_admin.get("/admin-ext/flow-health/")

    assert response.status_code in {401, 403}
