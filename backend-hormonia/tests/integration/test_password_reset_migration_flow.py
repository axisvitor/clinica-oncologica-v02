"""Integration contract for password reset migration and session revocation."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import status

from app.core.security import create_password_reset_token
from app.dependencies.auth_dependencies import get_redis_cache
from app.main import app
from app.models.session import Session as SessionModel
from app.models.user import AuthProvider, User, UserRole
from app.services import notification_service as notification_service_module
from app.utils.security import verify_password
from app.utils.timezone import now_sao_paulo

pytestmark = [pytest.mark.integration, pytest.mark.auth]

RESET_REQUEST_SUCCESS_MESSAGE = "If the account exists, a recovery email has been sent."
RESET_CONFIRM_SUCCESS_MESSAGE = "Password reset successful"


class RecordingRecoveryRedisCache:
    """Redis double that records bulk session revocation by canonical identity."""

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
        _ = session_id, extend_ttl, custom_ttl
        return True

    async def get_user_by_uid(self, firebase_uid: str):
        _ = firebase_uid
        return None

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
    """Small notification double that records attempted reset emails."""

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
def recovery_redis_cache():
    return RecordingRecoveryRedisCache()


@pytest.fixture
def override_recovery_redis_cache(recovery_redis_cache):
    async def _override_redis_cache():
        return recovery_redis_cache

    app.dependency_overrides[get_redis_cache] = _override_redis_cache
    try:
        yield recovery_redis_cache
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


@pytest.fixture
def firebase_era_user(db_session):
    user = User(
        email=f"firebase-era-{uuid4().hex[:8]}@example.com",
        hashed_password=None,
        full_name="Dr. Firebase Era",
        role=UserRole.DOCTOR,
        is_active=True,
        firebase_uid=f"firebase-{uuid4().hex}",
        auth_provider=AuthProvider.FIREBASE,
        failed_login_attempts=4,
        is_locked=True,
        locked_until=now_sao_paulo() + timedelta(hours=2),
        force_change_password=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_created_user(db_session):
    user = User(
        email=f"admin-created-{uuid4().hex[:8]}@example.com",
        hashed_password=None,
        full_name="Dr. Admin Created",
        role=UserRole.DOCTOR,
        is_active=True,
        firebase_uid=None,
        auth_provider=AuthProvider.LOCAL,
        failed_login_attempts=2,
        is_locked=True,
        locked_until=now_sao_paulo() + timedelta(hours=1),
        force_change_password=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _seed_active_session(db_session, redis_cache: RecordingRecoveryRedisCache, user: User) -> SessionModel:
    session = SessionModel(
        user_id=user.id,
        session_token=f"reset-migration-{uuid4().hex}",
        ip_address="127.0.0.1",
        user_agent="pytest-password-reset-migration",
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
        "firebase_uid": user.firebase_uid,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
    }
    return session


def _csrf_headers(client) -> dict[str, str]:
    response = client.get("/api/v2/auth/csrf-token")
    assert response.status_code == status.HTTP_200_OK, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}


@pytest.mark.parametrize(
    "seeded_user_fixture,new_password",
    [
        ("firebase_era_user", "MigratedFirebase123!"),
        ("admin_created_user", "MigratedAdmin123!"),
    ],
)
def test_password_reset_migrates_user_state_revokes_sessions_and_restores_local_login(
    client,
    db_session,
    request,
    override_recovery_redis_cache,
    email_capture,
    seeded_user_fixture,
    new_password,
):
    user = request.getfixturevalue(seeded_user_fixture)
    existing_session = _seed_active_session(db_session, override_recovery_redis_cache, user)

    reset_request_response = client.post(
        "/api/v2/auth/password/reset-request",
        headers=_csrf_headers(client),
        json={"email": user.email},
    )

    assert reset_request_response.status_code == status.HTTP_202_ACCEPTED, reset_request_response.text
    assert reset_request_response.json() == {
        "success": True,
        "message": RESET_REQUEST_SUCCESS_MESSAGE,
    }
    assert len(email_capture.calls) == 1
    assert email_capture.calls[0]["recipients"] == [user.email]

    reset_confirm_response = client.post(
        "/api/v2/auth/password/reset-confirm",
        headers=_csrf_headers(client),
        json={
            "token": create_password_reset_token(user.email),
            "new_password": new_password,
        },
    )

    assert reset_confirm_response.status_code == status.HTTP_200_OK, reset_confirm_response.text
    assert reset_confirm_response.json() == {
        "success": True,
        "message": RESET_CONFIRM_SUCCESS_MESSAGE,
    }

    db_session.expire_all()
    migrated_user = db_session.query(User).filter(User.id == user.id).first()
    assert migrated_user is not None
    assert migrated_user.auth_provider == AuthProvider.LOCAL
    assert migrated_user.hashed_password is not None
    assert verify_password(new_password, migrated_user.hashed_password)
    assert migrated_user.force_change_password is False
    assert migrated_user.failed_login_attempts == 0
    assert migrated_user.is_locked is False
    assert migrated_user.locked_until is None
    assert migrated_user.last_password_change is not None

    revoked_session = (
        db_session.query(SessionModel)
        .filter(SessionModel.id == UUID(str(existing_session.id)))
        .first()
    )
    assert revoked_session is not None
    assert revoked_session.is_active is False
    assert revoked_session.revoked_at is not None

    assert override_recovery_redis_cache.invalidated_identities == [str(user.id)]
    assert str(existing_session.id) in override_recovery_redis_cache.invalidated_sessions
    assert str(existing_session.id) not in override_recovery_redis_cache.sessions

    login_response = client.post(
        "/api/v2/auth/login",
        headers=_csrf_headers(client),
        json={
            "email": user.email,
            "password": new_password,
            "remember_me": False,
        },
    )

    assert login_response.status_code == status.HTTP_200_OK, login_response.text
    login_data = login_response.json()
    assert login_data["valid"] is True
    assert login_data["user"]["id"] == str(user.id)
    assert login_data["user"]["email"] == user.email
