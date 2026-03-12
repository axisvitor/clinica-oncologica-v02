"""Contract tests for first-party local auth endpoints.

These tests are intentionally written before the implementation cutover.
They should stay red until `/api/v2/auth/login`, `verify-session`, and
`logout` satisfy the slice's local-auth contract.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

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
        # Intentionally no firebase_uid: this is the contract T03 must satisfy.
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


def test_post_login_with_email_password_returns_canonical_response_and_cookie_contract(client, local_user):
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

    response_dump = str(data).lower()
    assert "password" not in response_dump
    assert "hashed_password" not in response_dump

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


def test_logout_returns_canonical_success_shape_and_clears_local_session_cookie(
    client,
    db_session,
    local_user,
    local_session,
    override_local_session_cache,
):
    user, _password = local_user

    response = client.delete(
        "/api/v2/auth/logout",
        headers={"X-Session-ID": str(local_session.id)},
        cookies={settings.SESSION_COOKIE_NAME: str(local_session.id)},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
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
