"""Operational proofs for the no-Firebase session-first staff-auth hard cut."""

from __future__ import annotations

import json

import pytest
from fastapi import Request

from app.config import settings
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.main import app
from app.middleware.csrf import get_csrf_token
from app.schemas.v2.system import ComponentHealth

pytestmark = [pytest.mark.api, pytest.mark.auth]


class HealthyAsyncRedis:
    async def ping(self):
        return True

    async def get(self, _key):
        return None

    async def setex(self, _key, _ttl, _value):
        return True

    async def info(self):
        return {
            "used_memory": 1024,
            "used_memory_peak": 2048,
            "connected_clients": 1,
            "keyspace_hits": 1,
            "keyspace_misses": 0,
        }


@pytest.fixture
def without_firebase_auth_config(monkeypatch):
    for attr in (
        "FIREBASE_ADMIN_PROJECT_ID",
        "FIREBASE_ADMIN_PRIVATE_KEY",
        "FIREBASE_ADMIN_CLIENT_EMAIL",
        "FIREBASE_PROJECT_ID",
    ):
        if hasattr(settings, attr):
            monkeypatch.setattr(settings, attr, None)

    for key in (
        "FIREBASE_WEB_API_KEY",
        "FIREBASE_WEB_PROJECT_ID",
        "FIREBASE_WEB_APP_ID",
        "FIREBASE_AUTH_DOMAIN",
        "VITE_FIREBASE_API_KEY",
        "VITE_FIREBASE_PROJECT_ID",
        "VITE_FIREBASE_APP_ID",
        "VITE_FIREBASE_AUTH_DOMAIN",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def admin_session_auth():
    csrf_token = get_csrf_token()
    session_id = "admin-hard-cut-session"
    admin_user = {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "admin@example.com",
        "full_name": "Admin Hard Cut",
        "role": "admin",
        "is_active": True,
        "firebase_uid": None,
    }

    async def _override_current_user_from_session(request: Request):
        request.state.user_id = admin_user["id"]
        request.state.user_role = admin_user["role"]
        request.state.session_id = session_id
        return admin_user

    app.dependency_overrides[get_current_user_from_session] = _override_current_user_from_session
    try:
        yield {
            "headers": {
                "X-Session-ID": session_id,
                "X-CSRF-Token": csrf_token,
            },
            "cookies": {
                settings.SESSION_COOKIE_NAME: session_id,
                "csrf_token": csrf_token,
            },
        }
    finally:
        app.dependency_overrides.pop(get_current_user_from_session, None)


@pytest.fixture
def healthy_operational_dependencies(monkeypatch):
    redis = HealthyAsyncRedis()

    async def _healthy_redis():
        return redis

    async def _no_config_cache():
        return None

    monkeypatch.setattr(
        ComponentHealth,
        "dict",
        lambda self, *args, **kwargs: self.model_dump(mode="json"),
    )
    monkeypatch.setattr("app.routers.health.get_async_redis", _healthy_redis)
    monkeypatch.setattr(
        "app.api.v2.routers.system.helpers.health_checker._get_redis_client",
        _healthy_redis,
    )
    monkeypatch.setattr(
        "app.api.v2.routers.system.initialization._get_redis_client",
        _healthy_redis,
    )
    monkeypatch.setattr(
        "app.api.v2.routers.system.config.get_redis_client",
        _no_config_cache,
    )


def test_top_level_readiness_stays_ready_without_firebase_admin_credentials(
    client,
    without_firebase_auth_config,
    healthy_operational_dependencies,
):
    response = client.get("/health/ready")

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "ready"
    assert "firebase" not in data["dependencies"]


def test_system_health_does_not_report_firebase_as_staff_auth_component(
    client,
    without_firebase_auth_config,
    healthy_operational_dependencies,
    admin_session_auth,
):
    response = client.get(
        "/api/v2/system/health",
        headers=admin_session_auth["headers"],
        cookies=admin_session_auth["cookies"],
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert "firebase" not in data["components"]
    assert "firebase" not in data["degraded_components"]
    assert "firebase" not in data["unhealthy_components"]


def test_system_validation_stops_warning_about_missing_firebase_auth_config(
    client,
    without_firebase_auth_config,
    admin_session_auth,
):
    response = client.post(
        "/api/v2/system/validate",
        headers=admin_session_auth["headers"],
        cookies=admin_session_auth["cookies"],
        json={},
    )

    assert response.status_code == 200, response.text
    data = response.json()

    warning_text = " ".join(data["warnings"] + data["recommendations"]).lower()
    assert "firebase" not in warning_text


def test_initialization_omits_firebase_component_when_staff_auth_is_session_first(
    client,
    without_firebase_auth_config,
    healthy_operational_dependencies,
    admin_session_auth,
):
    response = client.post(
        "/api/v2/system/initialize",
        headers=admin_session_auth["headers"],
        cookies=admin_session_auth["cookies"],
        json={},
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert "firebase" not in data["components"]
    assert all("firebase" not in warning.lower() for warning in data["warnings"])


def test_public_config_does_not_publish_firebase_auth_env_guidance(
    client,
    without_firebase_auth_config,
    healthy_operational_dependencies,
):
    response = client.get("/api/v2/system/config")

    assert response.status_code == 200, response.text
    data = response.json()

    assert all(not key.startswith("VITE_FIREBASE_") for key in data.keys())
    assert "firebase" not in json.dumps(data).lower()
