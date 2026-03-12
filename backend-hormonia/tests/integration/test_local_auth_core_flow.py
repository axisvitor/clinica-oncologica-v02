"""Integration contract for local login -> protected route -> logout."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.config import settings
from app.dependencies.auth_dependencies import get_redis_cache
from app.main import app
from app.models.session import Session as SessionModel
from app.models.user import AuthProvider
from app.utils.timezone import now_sao_paulo
from tests.conftest import create_test_user

pytestmark = [pytest.mark.integration, pytest.mark.auth]


class RecordingLocalAuthRedisCache:
    """Redis double that records the local-auth session lifecycle."""

    def __init__(self, user):
        self.user = user
        self.sessions: dict[str, dict] = {}
        self.users_by_uid: dict[str, dict] = {}
        self.invalidated_sessions: list[str] = []

    async def create_session(self, *args, **kwargs):
        session_id = kwargs.get("session_id") or args[0]
        user_id = kwargs.get("user_id") or args[1]
        firebase_uid = kwargs.get("firebase_uid")
        if firebase_uid is None and len(args) >= 3:
            firebase_uid = args[2]
        metadata = kwargs.get("metadata") or {}

        self.sessions[str(session_id)] = {
            "session_id": str(session_id),
            "user_id": str(user_id),
            "firebase_uid": firebase_uid,
            "email": self.user.email,
            "full_name": self.user.full_name,
            "role": self.user.role.value,
            "is_active": self.user.is_active,
            "created_at": now_sao_paulo().isoformat(),
            "updated_at": now_sao_paulo().isoformat(),
            "last_login": None,
            **metadata,
        }
        return True

    async def get_session(self, session_id: str):
        payload = self.sessions.get(str(session_id))
        return dict(payload) if payload else None

    async def update_session_activity(self, session_id: str, extend_ttl: bool = True, custom_ttl=None):
        _ = extend_ttl, custom_ttl
        payload = self.sessions.get(str(session_id))
        if payload:
            payload["last_activity"] = now_sao_paulo().isoformat()
        return True

    async def cache_user_data(self, cache_key: str | None, user_data: dict, ttl: int = 900):
        _ = ttl
        if cache_key:
            self.users_by_uid[str(cache_key)] = dict(user_data)
        return True

    async def get_user_by_uid(self, firebase_uid: str):
        if firebase_uid is None:
            return None
        payload = self.users_by_uid.get(str(firebase_uid))
        return dict(payload) if payload else None

    async def invalidate_session(self, session_id: str):
        self.invalidated_sessions.append(str(session_id))
        self.sessions.pop(str(session_id), None)
        return True

    async def delete_session(self, session_id: str):
        self.invalidated_sessions.append(str(session_id))
        self.sessions.pop(str(session_id), None)
        return True

    async def delete_pattern(self, pattern: str):
        _ = pattern
        return 0


@pytest.fixture
def local_auth_user(db_session):
    password = "FlowPass123!"
    email = f"local-flow-{uuid4().hex[:8]}@example.com"
    user = create_test_user(
        db_session,
        email=email,
        password=password,
        full_name="Dr. Local Flow",
        firebase_uid=None,
        is_active=True,
    )
    user.auth_provider = AuthProvider.LOCAL
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, password


@pytest.fixture
def local_auth_redis_cache(local_auth_user):
    user, _password = local_auth_user
    return RecordingLocalAuthRedisCache(user)


@pytest.fixture
def override_local_auth_redis_cache(local_auth_redis_cache):
    async def _override_redis_cache():
        return local_auth_redis_cache

    app.dependency_overrides[get_redis_cache] = _override_redis_cache
    try:
        yield local_auth_redis_cache
    finally:
        app.dependency_overrides.pop(get_redis_cache, None)


def test_local_auth_core_flow_invalidates_db_and_redis(
    client,
    db_session,
    local_auth_user,
    override_local_auth_redis_cache,
):
    user, password = local_auth_user

    login_response = client.post(
        "/api/v2/auth/login",
        json={
            "email": user.email,
            "password": password,
            "remember_me": True,
        },
    )

    assert login_response.status_code == 200, login_response.text
    login_data = login_response.json()
    session_id = login_data["session_id"]

    assert login_data["user"]["id"] == str(user.id)
    assert login_data["user"]["email"] == user.email
    assert client.cookies.get(settings.SESSION_COOKIE_NAME) == session_id
    assert session_id in override_local_auth_redis_cache.sessions

    db_session.expire_all()
    persisted_session = (
        db_session.query(SessionModel)
        .filter(SessionModel.id == UUID(session_id))
        .first()
    )
    assert persisted_session is not None
    assert persisted_session.user_id == user.id
    assert persisted_session.is_active is True
    assert persisted_session.expires_at >= now_sao_paulo() + timedelta(days=4)

    me_response = client.get("/api/v2/users/me")

    assert me_response.status_code == 200, me_response.text
    me_data = me_response.json()
    assert me_data["id"] == str(user.id)
    assert me_data["email"] == user.email
    assert me_data["role"] == user.role.value
    assert me_data["is_active"] is True

    logout_response = client.delete("/api/v2/auth/logout")

    assert logout_response.status_code == 200, logout_response.text
    assert logout_response.json() == {
        "message": "Logged out successfully",
        "success": True,
    }

    db_session.expire_all()
    revoked_session = (
        db_session.query(SessionModel)
        .filter(SessionModel.id == UUID(session_id))
        .first()
    )
    assert revoked_session is not None
    assert revoked_session.is_active is False
    assert revoked_session.revoked_at is not None

    assert session_id in override_local_auth_redis_cache.invalidated_sessions
    assert session_id not in override_local_auth_redis_cache.sessions
