"""Integrated proof for the session-first hard cut without Firebase staff-auth config."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import status

from app.config import settings
from app.core.security import create_password_reset_token
from app.dependencies.auth_dependencies import get_redis_cache
from app.main import app
from app.middleware.csrf import get_csrf_token
from app.models.session import Session as SessionModel
from app.models.user import AuthProvider
from app.services import notification_service as notification_service_module
from app.utils.security import verify_password
from app.utils.timezone import now_sao_paulo
from tests.conftest import create_test_user

pytestmark = [pytest.mark.integration, pytest.mark.auth]


class RecordingIntegratedRedisCache:
    """Redis double that preserves canonical session-first auth behavior."""

    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self.invalidated_sessions: list[str] = []
        self.invalidated_identities: list[str] = []

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

    async def get_user_by_uid(self, firebase_uid: str):
        raise AssertionError(
            f"Integrated session-first auth should not need firebase_uid cache lookup (got {firebase_uid!r})"
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


class EmailCapture:
    def __init__(self):
        self.calls: list[dict] = []

    async def send(self, _service, subject, message, recipients, template_data):
        self.calls.append(
            {
                "subject": subject,
                "message": message,
                "recipients": list(recipients or []),
                "template_data": template_data,
            }
        )
        return f"message-{len(self.calls)}"


@pytest.fixture
def integrated_user(db_session):
    password = "StartPass123!"
    email = f"hard-cut-e2e-{uuid4().hex[:8]}@example.com"
    user = create_test_user(
        db_session,
        email=email,
        password=password,
        full_name="Dra. Integrated Proof",
        firebase_uid=None,
        is_active=True,
    )
    user.auth_provider = AuthProvider.LOCAL
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, password


@pytest.fixture
def integrated_redis_cache():
    return RecordingIntegratedRedisCache()


@pytest.fixture
def override_integrated_redis_cache(integrated_redis_cache):
    async def _override_redis_cache():
        return integrated_redis_cache

    app.dependency_overrides[get_redis_cache] = _override_redis_cache
    try:
        yield integrated_redis_cache
    finally:
        app.dependency_overrides.pop(get_redis_cache, None)


@pytest.fixture
def email_capture(monkeypatch):
    capture = EmailCapture()
    monkeypatch.setattr(
        notification_service_module.NotificationService,
        "_send_email",
        capture.send,
    )
    return capture


def _session_request_parts(session_id: str):
    csrf_token = get_csrf_token()
    return {
        "headers": {
            "X-CSRF-Token": csrf_token,
        },
        "cookies": {
            settings.SESSION_COOKIE_NAME: session_id,
            "csrf_token": csrf_token,
        },
    }


def test_login_verify_reset_password_rotate_and_logout_without_firebase_staff_auth(
    client,
    db_session,
    integrated_user,
    override_integrated_redis_cache,
    email_capture,
):
    user, initial_password = integrated_user
    reset_password = "ResetPass123!"
    rotated_password = "RotatedPass123!"

    login_response = client.post(
        "/api/v2/auth/login",
        json={
            "email": user.email,
            "password": initial_password,
            "remember_me": True,
        },
    )

    assert login_response.status_code == status.HTTP_200_OK, login_response.text
    login_data = login_response.json()
    session_id = login_data["session_id"]
    session_request = _session_request_parts(session_id)
    client.cookies.clear()

    legacy_header_verify_response = client.get(
        "/api/v2/auth/verify-session",
        headers={"X-Session-ID": session_id},
    )
    assert (
        legacy_header_verify_response.status_code == status.HTTP_401_UNAUTHORIZED
    ), legacy_header_verify_response.text
    legacy_header_verify_data = legacy_header_verify_response.json()
    assert legacy_header_verify_data["detail"] == "Session cookie required"
    assert legacy_header_verify_data["message"] == "Session cookie required"
    assert legacy_header_verify_data["error"] == "HTTP_ERROR"

    legacy_bearer_verify_response = client.get(
        "/api/v2/auth/verify-session",
        headers={"Authorization": f"Bearer {session_id}"},
    )
    assert (
        legacy_bearer_verify_response.status_code == status.HTTP_401_UNAUTHORIZED
    ), legacy_bearer_verify_response.text
    legacy_bearer_verify_data = legacy_bearer_verify_response.json()
    assert legacy_bearer_verify_data["detail"] == "Session cookie required"
    assert legacy_bearer_verify_data["message"] == "Session cookie required"
    assert legacy_bearer_verify_data["error"] == "HTTP_ERROR"

    assert login_data["valid"] is True
    assert login_data["user"]["id"] == str(user.id)
    assert login_data["user"]["email"] == user.email
    assert session_id in override_integrated_redis_cache.sessions

    verify_session_response = client.get(
        "/api/v2/auth/verify-session",
        headers=session_request["headers"],
        cookies=session_request["cookies"],
    )

    assert verify_session_response.status_code == status.HTTP_200_OK, verify_session_response.text
    verify_data = verify_session_response.json()
    assert verify_data["user_id"] == str(user.id)
    assert verify_data["user"]["email"] == user.email

    protected_response = client.get(
        "/api/v2/users/me",
        headers=session_request["headers"],
        cookies=session_request["cookies"],
    )

    assert protected_response.status_code == status.HTTP_200_OK, protected_response.text
    assert protected_response.json()["email"] == user.email

    reset_request_response = client.post(
        "/api/v2/auth/password/reset-request",
        headers={"X-CSRF-Token": session_request["headers"]["X-CSRF-Token"]},
        cookies={"csrf_token": session_request["cookies"]["csrf_token"]},
        json={"email": user.email},
    )

    assert reset_request_response.status_code == status.HTTP_202_ACCEPTED, reset_request_response.text
    assert reset_request_response.json() == {
        "success": True,
        "message": "If the account exists, a recovery email has been sent.",
    }
    assert len(email_capture.calls) == 1
    assert email_capture.calls[0]["recipients"] == [user.email]

    reset_confirm_response = client.post(
        "/api/v2/auth/password/reset-confirm",
        json={
            "token": create_password_reset_token(user.email),
            "new_password": reset_password,
        },
    )

    assert reset_confirm_response.status_code == status.HTTP_200_OK, reset_confirm_response.text
    assert reset_confirm_response.json() == {
        "success": True,
        "message": "Password reset successful",
    }
    assert override_integrated_redis_cache.invalidated_identities == [str(user.id)]

    stale_session_response = client.get(
        "/api/v2/auth/verify-session",
        headers=session_request["headers"],
        cookies=session_request["cookies"],
    )
    assert stale_session_response.status_code == status.HTTP_401_UNAUTHORIZED, stale_session_response.text

    relogin_response = client.post(
        "/api/v2/auth/login",
        json={
            "email": user.email,
            "password": reset_password,
            "remember_me": False,
        },
    )

    assert relogin_response.status_code == status.HTTP_200_OK, relogin_response.text
    relogin_data = relogin_response.json()
    rotated_session_id = relogin_data["session_id"]
    rotated_request = _session_request_parts(rotated_session_id)

    password_change_response = client.put(
        "/api/v2/auth/password",
        headers=rotated_request["headers"],
        cookies=rotated_request["cookies"],
        json={
            "current_password": reset_password,
            "new_password": rotated_password,
        },
    )

    assert password_change_response.status_code == status.HTTP_200_OK, password_change_response.text
    assert password_change_response.json() == {
        "message": "Password changed successfully",
        "success": True,
    }

    rotated_verify_after_password_change = client.get(
        "/api/v2/auth/verify-session",
        headers=rotated_request["headers"],
        cookies=rotated_request["cookies"],
    )
    assert (
        rotated_verify_after_password_change.status_code == status.HTTP_401_UNAUTHORIZED
    ), rotated_verify_after_password_change.text

    logout_all_login_response = client.post(
        "/api/v2/auth/login",
        json={
            "email": user.email,
            "password": rotated_password,
            "remember_me": False,
        },
    )

    assert logout_all_login_response.status_code == status.HTTP_200_OK, logout_all_login_response.text
    logout_all_session_id = logout_all_login_response.json()["session_id"]
    logout_all_request = _session_request_parts(logout_all_session_id)

    logout_all_response = client.delete(
        "/api/v2/auth/logout-all",
        headers=logout_all_request["headers"],
        cookies=logout_all_request["cookies"],
    )

    assert logout_all_response.status_code == status.HTTP_200_OK, logout_all_response.text
    logout_all_data = logout_all_response.json()
    assert logout_all_data["success"] is True
    assert logout_all_data["message"] == "Logged out from all devices"
    assert logout_all_data["sessions_deleted"] >= 1

    revoked_verify_response = client.get(
        "/api/v2/auth/verify-session",
        headers=logout_all_request["headers"],
        cookies=logout_all_request["cookies"],
    )
    assert revoked_verify_response.status_code == status.HTTP_401_UNAUTHORIZED, revoked_verify_response.text

    final_login_response = client.post(
        "/api/v2/auth/login",
        json={
            "email": user.email,
            "password": rotated_password,
            "remember_me": False,
        },
    )

    assert final_login_response.status_code == status.HTTP_200_OK, final_login_response.text
    final_session_id = final_login_response.json()["session_id"]
    final_request = _session_request_parts(final_session_id)

    final_logout_response = client.delete(
        "/api/v2/auth/logout",
        headers=final_request["headers"],
        cookies=final_request["cookies"],
    )

    assert final_logout_response.status_code == status.HTTP_200_OK, final_logout_response.text
    assert final_logout_response.json() == {
        "message": "Logged out successfully",
        "success": True,
    }

    db_session.expire_all()
    updated_user = db_session.query(type(user)).filter(type(user).id == user.id).first()
    assert updated_user is not None
    assert updated_user.auth_provider == AuthProvider.LOCAL
    assert verify_password(rotated_password, updated_user.hashed_password)

    db_sessions = (
        db_session.query(SessionModel)
        .filter(SessionModel.user_id == user.id)
        .order_by(SessionModel.created_at.asc())
        .all()
    )
    assert len(db_sessions) >= 3
    assert all(session.is_active is False for session in db_sessions)
    assert all(session.revoked_at is not None for session in db_sessions)

    initial_session = (
        db_session.query(SessionModel)
        .filter(SessionModel.id == UUID(session_id))
        .first()
    )
    assert initial_session is not None
    assert initial_session.revocation_reason == "password_reset"
