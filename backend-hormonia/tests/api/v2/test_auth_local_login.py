"""Contract tests for first-party local auth endpoints."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import Request, Response

from app.api.v2.routers import auth as auth_router_module
from app.config import settings
from app.dependencies.auth_dependencies import get_redis_cache
from app.main import app
from app.models.session import Session as SessionModel
from app.models.user import AuthProvider
from app.utils.timezone import now_sao_paulo
from tests.conftest import create_test_user

pytestmark = [pytest.mark.api, pytest.mark.auth]


class LocalSessionRedisCache:
    """Small Redis double for session-backed auth contract tests."""

    def __init__(self, session_id: str, session_payload: dict):
        self.session_id = session_id
        self.session_payload = session_payload
        self.invalidated_sessions: list[str] = []

    async def get_session(self, session_id: str):
        if session_id == self.session_id:
            return dict(self.session_payload)
        return None

    async def update_session_activity(self, session_id: str, extend_ttl: bool = True, custom_ttl=None):
        _ = session_id, extend_ttl, custom_ttl
        return True

    async def get_user_by_uid(self, firebase_uid: str):
        raise AssertionError(
            f"Local session auth should not need firebase_uid cache lookup (got {firebase_uid!r})"
        )

    async def invalidate_session(self, session_id: str):
        self.invalidated_sessions.append(session_id)
        return True

    async def delete_session(self, session_id: str):
        self.invalidated_sessions.append(session_id)
        return True


class CapturingLoginRedisCache:
    """Redis double that records login session writes for contract assertions."""

    def __init__(self):
        self.create_session_calls: list[dict[str, object]] = []

    async def create_session(self, *args, **kwargs):
        self.create_session_calls.append({"args": args, "kwargs": kwargs})
        return True


@pytest.fixture
def local_user(db_session):
    password = "LocalPass123!"
    email = f"local-auth-{uuid4().hex[:8]}@example.com"
    user = create_test_user(
        db_session,
        email=email,
        password=password,
        full_name="Dra. Local Contract",
        firebase_uid=None,
        is_active=True,
    )
    user.auth_provider = AuthProvider.LOCAL
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, password


@pytest.fixture
def inactive_local_user(db_session):
    password = "InactivePass123!"
    email = f"inactive-local-{uuid4().hex[:8]}@example.com"
    user = create_test_user(
        db_session,
        email=email,
        password=password,
        full_name="Conta Inativa",
        firebase_uid=None,
        is_active=False,
    )
    user.auth_provider = AuthProvider.LOCAL
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, password


@pytest.fixture
def local_session(db_session, local_user):
    user, _password = local_user
    session = SessionModel(
        user_id=user.id,
        session_token=f"local-session-token-{uuid4().hex}",
        ip_address="127.0.0.1",
        user_agent="pytest-local-auth",
        last_activity=now_sao_paulo(),
        expires_at=now_sao_paulo() + timedelta(days=5),
        is_active=True,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture
def local_session_cache(local_user, local_session):
    user, _password = local_user
    session_payload = {
        "session_id": str(local_session.id),
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": True,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login": None,
        # Intentionally no firebase_uid: this is the canonical local-auth contract.
    }
    return LocalSessionRedisCache(str(local_session.id), session_payload)


@pytest.fixture
def override_local_session_cache(local_session_cache):
    async def _override_redis_cache():
        return local_session_cache

    app.dependency_overrides[get_redis_cache] = _override_redis_cache
    try:
        yield local_session_cache
    finally:
        app.dependency_overrides.pop(get_redis_cache, None)


@pytest.fixture
def capture_login_session_cache():
    cache = CapturingLoginRedisCache()

    async def _override_redis_cache():
        return cache

    app.dependency_overrides[get_redis_cache] = _override_redis_cache
    try:
        yield cache
    finally:
        app.dependency_overrides.pop(get_redis_cache, None)


def test_post_login_with_email_password_returns_canonical_response_and_cookie_contract(
    client,
    local_user,
    capture_login_session_cache,
):
    user, password = local_user

    response = client.post(
        "/api/v2/auth/login",
        json={
            "email": user.email,
            "password": password,
            "remember_me": True,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["valid"] is True
    assert data["message"] == "Login successful"
    assert data["session_id"]
    assert data["user"]["id"] == str(user.id)
    assert data["user"]["email"] == user.email
    assert data["user"]["full_name"] == user.full_name
    assert data["user"]["role"] == user.role.value
    assert data["user"]["is_active"] is True
    assert "firebase_uid" not in data["user"]
    assert response.headers.get("X-Session-ID") is None

    response_dump = str(data).lower()
    assert "password" not in response_dump
    assert "hashed_password" not in response_dump

    assert len(capture_login_session_cache.create_session_calls) == 1
    create_session_call = capture_login_session_cache.create_session_calls[0]
    assert create_session_call["args"] == ()
    assert create_session_call["kwargs"]["user_id"] == str(user.id)
    assert "firebase_uid" not in create_session_call["kwargs"]
    assert "firebase_uid" not in create_session_call["kwargs"]["metadata"]
    assert create_session_call["kwargs"]["metadata"]["email"] == user.email
    assert create_session_call["kwargs"]["metadata"]["role"] == user.role.value

    cookie_header = response.headers.get("set-cookie", "")
    cookie_header_lower = cookie_header.lower()
    assert f"{settings.SESSION_COOKIE_NAME}=" in cookie_header
    assert "httponly" in cookie_header_lower
    assert "path=/" in cookie_header_lower
    assert f"samesite={settings.SESSION_COOKIE_SAMESITE}".lower() in cookie_header_lower
    if settings.SESSION_ENABLE_COOKIE_SECURE:
        assert "secure" in cookie_header_lower


def test_post_login_rejects_invalid_credentials_with_stable_error_payload(client, local_user):
    user, _password = local_user

    response = client.post(
        "/api/v2/auth/login",
        json={
            "email": user.email,
            "password": "WrongPass123!",
        },
    )

    assert response.status_code == 401, response.text
    data = response.json()

    assert data["error"] == "AUTH_INVALID_CREDENTIALS"
    assert "request_id" in data
    assert "password" not in str(data).lower()


def test_post_login_rejects_inactive_account_with_stable_error_payload(client, inactive_local_user):
    user, password = inactive_local_user

    response = client.post(
        "/api/v2/auth/login",
        json={
            "email": user.email,
            "password": password,
        },
    )

    assert response.status_code == 403, response.text
    data = response.json()

    assert data["error"] == "AUTH_ACCOUNT_INACTIVE"
    assert "request_id" in data
    assert "password" not in str(data).lower()


def test_verify_session_accepts_local_session_identity_without_firebase_uid(
    client,
    local_user,
    local_session,
    override_local_session_cache,
):
    user, _password = local_user

    response = client.get(
        "/api/v2/auth/verify-session",
        cookies={settings.SESSION_COOKIE_NAME: str(local_session.id)},
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["valid"] is True
    assert data["session_id"] == str(local_session.id)
    assert data["user_id"] == str(user.id)
    assert data["user"]["id"] == str(user.id)
    assert data["user"]["email"] == user.email
    assert data["user"]["role"] == user.role.value
    assert "firebase_uid" not in data["user"]


def test_verify_session_rejects_x_session_id_header_without_cookie(
    client,
    local_session,
    override_local_session_cache,
):
    response = client.get(
        "/api/v2/auth/verify-session",
        headers={"X-Session-ID": str(local_session.id)},
    )

    assert response.status_code == 401, response.text
    data = response.json()
    assert data["detail"] == "Session cookie required"
    assert data["message"] == "Session cookie required"
    assert data["error"] == "HTTP_ERROR"


def test_verify_session_rejects_bearer_session_transport_without_cookie(
    client,
    local_session,
    override_local_session_cache,
):
    response = client.get(
        "/api/v2/auth/verify-session",
        headers={"Authorization": f"Bearer {local_session.id}"},
    )

    assert response.status_code == 401, response.text
    data = response.json()
    assert data["detail"] == "Session cookie required"
    assert data["message"] == "Session cookie required"
    assert data["error"] == "HTTP_ERROR"


@pytest.mark.asyncio
async def test_logout_returns_canonical_success_shape_and_clears_local_session_cookie(
    db_session,
    local_user,
    local_session,
    override_local_session_cache,
):
    user, _password = local_user
    request = MagicMock(spec=Request)
    request.cookies = {settings.SESSION_COOKIE_NAME: str(local_session.id)}
    response = Response()

    current_user = {
        **override_local_session_cache.session_payload,
        "id": override_local_session_cache.session_payload["user_id"],
    }

    payload = await auth_router_module.logout(
        request=request,
        response=response,
        current_user=current_user,
        redis_cache=override_local_session_cache,
        db=db_session,
    )

    assert payload == {
        "message": "Logged out successfully",
        "success": True,
    }

    db_session.refresh(local_session)
    assert local_session.user_id == user.id
    assert local_session.is_active is False
    assert local_session.revoked_at is not None
    assert override_local_session_cache.invalidated_sessions == [str(local_session.id)]

    cookie_header = response.headers.get("set-cookie", "")
    cookie_header_lower = cookie_header.lower()
    assert f"{settings.SESSION_COOKIE_NAME}=" in cookie_header
    assert "expires=" in cookie_header_lower or "max-age=0" in cookie_header_lower


def test_logout_rejects_bearer_session_transport_without_cookie(
    client,
    db_session,
    local_session,
    override_local_session_cache,
):
    response = client.delete(
        "/api/v2/auth/logout",
        headers={"Authorization": f"Bearer {local_session.id}"},
    )

    assert response.status_code == 401, response.text
    data = response.json()
    assert data["detail"] == "Session cookie required"
    assert data["message"] == "Session cookie required"
    assert data["error"] == "HTTP_ERROR"

    db_session.refresh(local_session)
    assert local_session.is_active is True
    assert local_session.revoked_at is None
    assert override_local_session_cache.invalidated_sessions == []
