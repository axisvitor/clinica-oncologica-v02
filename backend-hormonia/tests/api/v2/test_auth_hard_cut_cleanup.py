"""Hard-cut cleanup proofs for remaining Firebase staff-auth seams."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Request, status

from app.api.v2.routers.admin import dependencies as admin_dependencies
from app.config import settings
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.main import app
from app.middleware.csrf import get_csrf_token
from app.models.session import Session as SessionModel
from app.models.user import AuthProvider, UserRole
from app.utils.security import verify_password
from app.utils.timezone import now_sao_paulo
from tests.conftest import create_test_user

pytestmark = [pytest.mark.api, pytest.mark.auth]


class RecordingHardCutRedisCache:
    """Redis double that records canonical user-id session invalidation."""

    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self.invalidated_sessions: list[str] = []
        self.invalidated_identities: list[str] = []

    async def get_session(self, session_id: str):
        payload = self.sessions.get(str(session_id))
        return dict(payload) if payload else None

    async def update_session_activity(self, session_id: str, extend_ttl: bool = True, custom_ttl=None):
        _ = session_id, extend_ttl, custom_ttl
        return True

    async def get_user_by_uid(self, firebase_uid: str):
        raise AssertionError(
            f"Session-first staff auth should not need firebase_uid cache lookup (got {firebase_uid!r})"
        )

    async def invalidate_session(self, session_id: str):
        self.invalidated_sessions.append(str(session_id))
        self.sessions.pop(str(session_id), None)
        return True

    async def delete_session(self, session_id: str):
        self.invalidated_sessions.append(str(session_id))
        self.sessions.pop(str(session_id), None)
        return True

    async def invalidate_all_user_sessions(self, identity: str):
        self.invalidated_identities.append(str(identity))
        matching_session_ids = [
            session_id
            for session_id, payload in list(self.sessions.items())
            if str(payload.get("user_id")) == str(identity)
            or str(payload.get("firebase_uid")) == str(identity)
        ]
        for session_id in matching_session_ids:
            self.invalidated_sessions.append(session_id)
            self.sessions.pop(session_id, None)
        return len(matching_session_ids)

    async def delete_pattern(self, pattern: str):
        _ = pattern
        return 0


@pytest.fixture
def local_password_user(db_session):
    password = "LocalPass123!"
    email = f"hard-cut-{uuid4().hex[:8]}@example.com"
    user = create_test_user(
        db_session,
        email=email,
        password=password,
        full_name="Dra. Hard Cut Cleanup",
        firebase_uid=None,
        is_active=True,
        role=UserRole.DOCTOR,
    )
    user.auth_provider = AuthProvider.LOCAL
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, password


@pytest.fixture
def hard_cut_redis_cache():
    return RecordingHardCutRedisCache()


@pytest.fixture
def override_hard_cut_redis_cache(hard_cut_redis_cache):
    async def _override_redis_cache():
        return hard_cut_redis_cache

    app.dependency_overrides[get_redis_cache] = _override_redis_cache
    try:
        yield hard_cut_redis_cache
    finally:
        app.dependency_overrides.pop(get_redis_cache, None)


@pytest.fixture
def local_session_auth(local_password_user):
    user, _password = local_password_user
    session_id = f"session-hard-cut-{user.id}"
    csrf_token = get_csrf_token()
    session_user = {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "firebase_uid": None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login": user.firebase_last_sign_in.isoformat() if user.firebase_last_sign_in else None,
    }

    async def _override_current_user_from_session(request: Request):
        request.state.user_id = str(user.id)
        request.state.user_role = user.role.value
        request.state.session_id = session_id
        return session_user

    app.dependency_overrides[get_current_user_from_session] = _override_current_user_from_session
    try:
        yield {
            "headers": {
                "X-CSRF-Token": csrf_token,
            },
            "cookies": {
                settings.SESSION_COOKIE_NAME: session_id,
                "csrf_token": csrf_token,
            },
            "session_user": session_user,
            "session_id": session_id,
        }
    finally:
        app.dependency_overrides.pop(get_current_user_from_session, None)


def _seed_active_session(db_session, redis_cache: RecordingHardCutRedisCache, user, *, label: str) -> SessionModel:
    session = SessionModel(
        user_id=user.id,
        session_token=f"{label}-{uuid4().hex}",
        ip_address="127.0.0.1",
        user_agent=f"pytest-{label}",
        last_activity=now_sao_paulo(),
        expires_at=now_sao_paulo() + timedelta(days=5),
        is_active=True,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    redis_cache.sessions[str(session.id)] = {
        "session_id": str(session.id),
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
    }
    return session


def test_firebase_verify_route_is_tombstoned_for_staff_auth(client):
    csrf_token = get_csrf_token()

    response = client.post(
        "/api/v2/auth/firebase/verify",
        headers={"X-CSRF-Token": csrf_token},
        cookies={"csrf_token": csrf_token},
        json={"id_token": "header.payload.signature"},
    )

    assert response.status_code in {
        status.HTTP_404_NOT_FOUND,
        status.HTTP_410_GONE,
    }, response.text


def test_debug_token_inspection_no_longer_depends_on_firebase_verification():
    debug_auth_source = Path("app/api/v2/routers/debug/auth.py").read_text(encoding="utf-8")

    assert "verify_firebase_token" not in debug_auth_source
    assert "Firebase ID token" not in debug_auth_source


def test_password_change_rejects_legacy_header_transport_without_cookie(client):
    csrf_token = get_csrf_token()

    response = client.put(
        "/api/v2/auth/password",
        headers={
            "X-Session-ID": "legacy-session",
            "X-CSRF-Token": csrf_token,
        },
        cookies={"csrf_token": csrf_token},
        json={
            "current_password": "WrongPass123!",
            "new_password": "NewHardCut123!",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
    data = response.json()
    assert data["detail"] == "Session cookie required"
    assert data["message"] == "Session cookie required"
    assert data["error"] == "HTTP_ERROR"


def test_password_change_rejects_legacy_bearer_transport_without_cookie(client):
    csrf_token = get_csrf_token()

    response = client.put(
        "/api/v2/auth/password",
        headers={
            "Authorization": "Bearer legacy-session",
            "X-CSRF-Token": csrf_token,
        },
        cookies={"csrf_token": csrf_token},
        json={
            "current_password": "WrongPass123!",
            "new_password": "NewHardCut123!",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
    data = response.json()
    assert data["detail"] == "Session cookie required"
    assert data["message"] == "Session cookie required"
    assert data["error"] == "HTTP_ERROR"


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Session-ID": "legacy-session"},
        {"Authorization": "Bearer legacy-session"},
    ],
)
def test_verify_session_rejects_legacy_transport_without_cookie(client, headers):
    response = client.get("/api/v2/auth/verify-session", headers=headers)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
    data = response.json()
    assert data["detail"] == "Session cookie required"
    assert data["message"] == "Session cookie required"
    assert data["error"] == "HTTP_ERROR"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "expected_x_session_id", "expected_authorization"),
    [
        ({"X-Session-ID": "legacy-admin-session"}, "legacy-admin-session", None),
        (
            {"Authorization": "Bearer legacy-admin-session"},
            None,
            "Bearer legacy-admin-session",
        ),
    ],
)
async def test_admin_dependency_rejects_legacy_transport_without_cookie_even_in_test_mode(
    monkeypatch,
    headers,
    expected_x_session_id,
    expected_authorization,
):
    request = MagicMock(spec=Request)
    request.headers = headers
    request.cookies = {}
    request.state = SimpleNamespace()
    request.app = SimpleNamespace(dependency_overrides={})
    db = AsyncMock()
    redis_cache = object()

    async def _session_override(
        *,
        request: Request,
        session_cookie_id=None,
        x_session_id=None,
        authorization=None,
        redis_cache=None,
    ):
        assert session_cookie_id is None
        assert x_session_id == expected_x_session_id
        assert authorization == expected_authorization
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session cookie required",
            headers={"WWW-Authenticate": "Session"},
        )

    request.app.dependency_overrides = {
        admin_dependencies.get_current_user_from_session: _session_override,
    }
    monkeypatch.setenv("TESTING", "1")

    with pytest.raises(HTTPException) as exc_info:
        await admin_dependencies.get_admin_user(
            request=request,
            db=db,
            redis_cache=redis_cache,
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Session cookie required"
    db.execute.assert_not_awaited()


def test_password_change_rejects_wrong_current_password_with_stable_diagnostics(
    client,
    db_session,
    local_password_user,
    local_session_auth,
):
    user, original_password = local_password_user

    response = client.put(
        "/api/v2/auth/password",
        headers=local_session_auth["headers"],
        cookies=local_session_auth["cookies"],
        json={
            "current_password": "WrongPass123!",
            "new_password": "NewHardCut123!",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    data = response.json()

    assert data["error"] == "AUTH_PASSWORD_CURRENT_PASSWORD_INVALID"
    assert data["message"] == "Current password is incorrect."
    assert data["request_id"]

    db_session.refresh(user)
    assert verify_password(original_password, user.hashed_password)


def test_password_change_updates_local_hash_and_revokes_sessions_by_user_id(
    client,
    db_session,
    local_password_user,
    local_session_auth,
    override_hard_cut_redis_cache,
):
    user, original_password = local_password_user
    existing_sessions = [
        _seed_active_session(db_session, override_hard_cut_redis_cache, user, label="password-change-a"),
        _seed_active_session(db_session, override_hard_cut_redis_cache, user, label="password-change-b"),
    ]

    response = client.put(
        "/api/v2/auth/password",
        headers=local_session_auth["headers"],
        cookies=local_session_auth["cookies"],
        json={
            "current_password": original_password,
            "new_password": "PasswordRotated123!",
        },
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json() == {
        "message": "Password changed successfully",
        "success": True,
    }

    db_session.expire_all()
    updated_user = db_session.query(type(user)).filter(type(user).id == user.id).first()
    assert updated_user is not None
    assert verify_password("PasswordRotated123!", updated_user.hashed_password)
    assert updated_user.auth_provider == AuthProvider.LOCAL
    assert updated_user.last_password_change is not None

    revoked_sessions = (
        db_session.query(SessionModel)
        .filter(SessionModel.user_id == user.id)
        .order_by(SessionModel.created_at.asc())
        .all()
    )
    assert len(revoked_sessions) >= len(existing_sessions)
    assert all(session.is_active is False for session in revoked_sessions)
    assert all(session.revoked_at is not None for session in revoked_sessions)

    assert override_hard_cut_redis_cache.invalidated_identities == [str(user.id)]
    assert {
        str(existing_sessions[0].id),
        str(existing_sessions[1].id),
    }.issubset(set(override_hard_cut_redis_cache.invalidated_sessions))


def test_logout_all_revokes_sessions_using_canonical_user_id_when_firebase_uid_missing(
    client,
    db_session,
    local_password_user,
    local_session_auth,
    override_hard_cut_redis_cache,
):
    user, _password = local_password_user
    seeded_sessions = [
        _seed_active_session(db_session, override_hard_cut_redis_cache, user, label="logout-all-a"),
        _seed_active_session(db_session, override_hard_cut_redis_cache, user, label="logout-all-b"),
    ]

    response = client.delete(
        "/api/v2/auth/logout-all",
        headers=local_session_auth["headers"],
        cookies=local_session_auth["cookies"],
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    assert data == {
        "message": "Logged out from all devices",
        "success": True,
        "sessions_deleted": len(seeded_sessions),
    }
    assert override_hard_cut_redis_cache.invalidated_identities == [str(user.id)]
    assert {
        str(seeded_sessions[0].id),
        str(seeded_sessions[1].id),
    }.issubset(set(override_hard_cut_redis_cache.invalidated_sessions))

    db_session.expire_all()
    revoked_sessions = (
        db_session.query(SessionModel)
        .filter(SessionModel.user_id == user.id)
        .order_by(SessionModel.created_at.asc())
        .all()
    )
    assert all(session.is_active is False for session in revoked_sessions)
    assert all(session.revoked_at is not None for session in revoked_sessions)
