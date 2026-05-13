"""Security regressions for M014/S01 password reset token replay handling."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import status

from app.config import settings
from app.core.security import (
    PASSWORD_RESET_TOKEN_AUDIENCE,
    PASSWORD_RESET_TOKEN_ISSUER,
    PASSWORD_RESET_TOKEN_TYPE,
    create_password_reset_token,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.main import app
from app.models.session import Session as SessionModel
from app.models.user import AuthProvider
from app.services.password_reset_service import PasswordResetFailure, PasswordResetService
from app.utils.security import verify_password
from app.utils.timezone import now_sao_paulo
from tests.conftest import create_test_user

pytestmark = [pytest.mark.security, pytest.mark.auth]

RESET_CONFIRM_SUCCESS_MESSAGE = "Password reset successful"
RESET_REPLAY_ERROR = "AUTH_RESET_TOKEN_REPLAYED"
RESET_TOKEN_ERROR = "AUTH_RESET_TOKEN_INVALID_OR_EXPIRED"
RESET_SERVICE_ERROR = "AUTH_PASSWORD_RESET_SERVICE_UNAVAILABLE"
RESET_WEAK_PASSWORD_ERROR = "AUTH_PASSWORD_WEAK"


class RecordingPasswordResetRedisCache:
    """Redis double with SET NX EX semantics and session-revocation recording."""

    def __init__(self, *, fail_set: bool = False) -> None:
        self.fail_set = fail_set
        self.values: dict[str, str] = {}
        self.set_calls: list[dict[str, object]] = []
        self.invalidated_identities: list[str] = []
        self.invalidated_sessions: list[str] = []
        self.sessions: dict[str, dict[str, object]] = {}

    async def set(self, key: str, value: str, *args, **kwargs) -> bool:
        _ = args
        ttl = kwargs.get("ex") or kwargs.get("ttl")
        nx = bool(kwargs.get("nx", False))
        self.set_calls.append({"key": key, "value": value, "ttl": ttl, "nx": nx})
        if self.fail_set:
            raise RuntimeError("redis unavailable")
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def invalidate_all_user_sessions(self, identity: str) -> int:
        self.invalidated_identities.append(str(identity))
        matching_session_ids = [
            session_id
            for session_id, payload in list(self.sessions.items())
            if str(payload.get("user_id")) == str(identity)
        ]
        for session_id in matching_session_ids:
            self.invalidated_sessions.append(session_id)
            self.sessions.pop(session_id, None)
        return len(matching_session_ids)


def _csrf_headers(client) -> dict[str, str]:
    response = client.get("/api/v2/auth/csrf-token")
    assert response.status_code == status.HTTP_200_OK, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}


@pytest.fixture
def replay_redis_cache() -> RecordingPasswordResetRedisCache:
    return RecordingPasswordResetRedisCache()


@pytest.fixture
def override_replay_redis_cache(client, replay_redis_cache):
    async def _override_redis_cache():
        return replay_redis_cache

    app.dependency_overrides[get_redis_cache] = _override_redis_cache
    yield replay_redis_cache
    app.dependency_overrides.pop(get_redis_cache, None)


@pytest.fixture
def reset_user(db_session):
    old_password = "OldReplay123!"
    user = create_test_user(
        db_session,
        email=f"reset-replay-{uuid4().hex[:8]}@example.com",
        password=old_password,
        full_name="Dra. Replay Safety",
        firebase_uid=None,
        is_active=True,
    )
    user.auth_provider = AuthProvider.LOCAL
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _seed_active_session(
    db_session,
    redis_cache: RecordingPasswordResetRedisCache,
    user,
) -> SessionModel:
    session = SessionModel(
        user_id=user.id,
        session_token=f"reset-replay-{uuid4().hex}",
        ip_address="127.0.0.1",
        user_agent="pytest-password-reset-replay",
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
    }
    return session


def _token_without_jti(email: str) -> str:
    issued_at = now_sao_paulo()
    payload = {
        "sub": email,
        "exp": issued_at + timedelta(hours=1),
        "iat": issued_at,
        "nbf": issued_at,
        "type": PASSWORD_RESET_TOKEN_TYPE,
        "iss": PASSWORD_RESET_TOKEN_ISSUER,
        "aud": PASSWORD_RESET_TOKEN_AUDIENCE,
    }
    return jwt.encode(payload, settings.SECURITY_SECRET_KEY, algorithm="HS256")


def _decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.SECURITY_SECRET_KEY,
        algorithms=["HS256"],
        audience=PASSWORD_RESET_TOKEN_AUDIENCE,
        issuer=PASSWORD_RESET_TOKEN_ISSUER,
    )


def _assert_stable_auth_error(payload: dict, error_code: str) -> None:
    assert payload["error"] == error_code
    assert "request_id" in payload
    assert "timestamp" in payload
    forbidden = {"temporary_password", "reset_token", "raw_token", "token", "password"}
    assert forbidden.isdisjoint(_collect_keys(payload))


def _collect_keys(payload) -> set[str]:
    if isinstance(payload, dict):
        keys = set(payload.keys())
        for value in payload.values():
            keys.update(_collect_keys(value))
        return keys
    if isinstance(payload, list):
        keys: set[str] = set()
        for value in payload:
            keys.update(_collect_keys(value))
        return keys
    return set()


def _assert_response_redacts_sensitive_values(response, *sensitive_values: str) -> None:
    response_text = response.text
    for sensitive_value in sensitive_values:
        assert sensitive_value not in response_text


def test_password_reset_token_is_single_use_and_replay_has_no_second_side_effects(
    client,
    db_session,
    override_replay_redis_cache,
    reset_user,
):
    active_session = _seed_active_session(db_session, override_replay_redis_cache, reset_user)
    user_model = type(reset_user)
    user_id = reset_user.id
    user_email = reset_user.email
    active_session_id = active_session.id
    token = create_password_reset_token(user_email)
    token_payload = _decode_token(token)

    first_response = client.post(
        "/api/v2/auth/password/reset-confirm",
        headers=_csrf_headers(client),
        json={"token": token, "new_password": "FirstReplay123!"},
    )

    assert first_response.status_code == status.HTTP_200_OK, first_response.text
    assert first_response.json() == {"success": True, "message": RESET_CONFIRM_SUCCESS_MESSAGE}

    db_session.expire_all()
    migrated_user = db_session.query(user_model).filter(user_model.id == user_id).first()
    assert migrated_user is not None
    first_hash = migrated_user.hashed_password
    assert verify_password("FirstReplay123!", first_hash)

    revoked_session = (
        db_session.query(SessionModel)
        .filter(SessionModel.id == UUID(str(active_session_id)))
        .first()
    )
    assert revoked_session is not None
    assert revoked_session.is_active is False

    assert len(override_replay_redis_cache.set_calls) == 1
    first_set = override_replay_redis_cache.set_calls[0]
    assert first_set["nx"] is True
    assert isinstance(first_set["ttl"], int) and first_set["ttl"] > 0
    assert token not in str(first_set)
    assert user_email not in str(first_set)
    assert token_payload["jti"] not in str(first_set)
    assert override_replay_redis_cache.invalidated_identities == [str(user_id)]
    assert str(active_session_id) in override_replay_redis_cache.invalidated_sessions

    second_response = client.post(
        "/api/v2/auth/password/reset-confirm",
        headers=_csrf_headers(client),
        json={"token": token, "new_password": "SecondReplay456!"},
    )

    assert second_response.status_code == status.HTTP_409_CONFLICT, second_response.text
    second_payload = second_response.json()
    _assert_stable_auth_error(second_payload, RESET_REPLAY_ERROR)
    _assert_response_redacts_sensitive_values(
        second_response,
        token,
        user_email,
        "FirstReplay123!",
        "SecondReplay456!",
    )

    assert override_replay_redis_cache.invalidated_identities == [str(user_id)]
    assert len(override_replay_redis_cache.set_calls) == 2
    assert override_replay_redis_cache.set_calls[1]["key"] == first_set["key"]


class RecordingDb:
    """Minimal DB double that records mutation entry points."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.flushed = False
        self.committed = False
        self.refreshed: list[object] = []
        self.rolled_back = False

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def refresh(self, value: object) -> None:
        self.refreshed.append(value)

    def rollback(self) -> None:
        self.rolled_back = True


class StaticUserRepository:
    def __init__(self, user) -> None:
        self.user = user
        self.lookups: list[str] = []

    def get_by_email(self, email: str):
        self.lookups.append(email)
        if email == self.user.email.lower():
            return self.user
        return None


class RecordingSessionRepository:
    def __init__(self) -> None:
        self.revocations: list[tuple[object, str | None, bool]] = []

    def revoke_all_user_sessions(self, user_id, reason=None, *, commit=True) -> int:
        self.revocations.append((user_id, reason, commit))
        return 1


@pytest.mark.asyncio
async def test_service_replay_denial_happens_before_user_or_session_mutation(reset_user):
    redis_cache = RecordingPasswordResetRedisCache()
    token = create_password_reset_token(reset_user.email)
    token_payload = _decode_token(token)
    replay_key = PasswordResetService._token_consumption_key(token_payload["jti"])
    await redis_cache.set(replay_key, "1", ex=3600, nx=True)

    db = RecordingDb()
    session_repository = RecordingSessionRepository()
    service = PasswordResetService(
        db,
        redis_cache=redis_cache,
        user_repository=StaticUserRepository(reset_user),
        session_repository=session_repository,
        notification_service=object(),
    )
    original_hash = reset_user.hashed_password
    original_last_password_change = reset_user.last_password_change

    with pytest.raises(PasswordResetFailure) as exc_info:
        await service.confirm_password_reset(token, "DirectReplay123!")

    assert exc_info.value.error_code == RESET_REPLAY_ERROR
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.reason == "jti_already_consumed"
    assert reset_user.hashed_password == original_hash
    assert reset_user.last_password_change == original_last_password_change
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert session_repository.revocations == []


@pytest.mark.asyncio
async def test_service_cache_failure_happens_before_user_or_session_mutation(reset_user):
    redis_cache = RecordingPasswordResetRedisCache(fail_set=True)
    token = create_password_reset_token(reset_user.email)
    db = RecordingDb()
    session_repository = RecordingSessionRepository()
    service = PasswordResetService(
        db,
        redis_cache=redis_cache,
        user_repository=StaticUserRepository(reset_user),
        session_repository=session_repository,
        notification_service=object(),
    )
    original_hash = reset_user.hashed_password
    original_last_password_change = reset_user.last_password_change

    with pytest.raises(PasswordResetFailure) as exc_info:
        await service.confirm_password_reset(token, "CacheUnavailable123!")

    assert exc_info.value.error_code == RESET_SERVICE_ERROR
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc_info.value.reason == "cache_set_exception"
    assert len(redis_cache.set_calls) == 1
    assert reset_user.hashed_password == original_hash
    assert reset_user.last_password_change == original_last_password_change
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False
    assert session_repository.revocations == []


@pytest.mark.parametrize(
    ("token_factory", "expected_status"),
    [
        (lambda user: "not-a-valid-reset-token", status.HTTP_400_BAD_REQUEST),
        (
            lambda user: create_password_reset_token(
                user.email,
                expires_delta=timedelta(seconds=-1),
            ),
            status.HTTP_400_BAD_REQUEST,
        ),
        (lambda user: _token_without_jti(user.email), status.HTTP_400_BAD_REQUEST),
    ],
)
def test_invalid_expired_or_missing_jti_tokens_do_not_consume_or_mutate(
    client,
    override_replay_redis_cache,
    reset_user,
    token_factory,
    expected_status,
):
    user_email = reset_user.email
    token = token_factory(reset_user)

    response = client.post(
        "/api/v2/auth/password/reset-confirm",
        headers=_csrf_headers(client),
        json={"token": token, "new_password": "ValidReplay789!"},
    )

    assert response.status_code == expected_status, response.text
    _assert_stable_auth_error(response.json(), RESET_TOKEN_ERROR)
    _assert_response_redacts_sensitive_values(response, token, user_email, "ValidReplay789!")
    assert override_replay_redis_cache.set_calls == []
    assert override_replay_redis_cache.invalidated_identities == []


def test_cache_set_failure_fails_closed_before_password_or_session_mutation(
    client,
    db_session,
    replay_redis_cache,
    reset_user,
):
    replay_redis_cache.fail_set = True

    async def _override_redis_cache():
        return replay_redis_cache

    app.dependency_overrides[get_redis_cache] = _override_redis_cache
    _seed_active_session(db_session, replay_redis_cache, reset_user)
    user_email = reset_user.email
    token = create_password_reset_token(user_email)

    response = client.post(
        "/api/v2/auth/password/reset-confirm",
        headers=_csrf_headers(client),
        json={"token": token, "new_password": "CacheFailure123!"},
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, response.text
    _assert_stable_auth_error(response.json(), RESET_SERVICE_ERROR)
    _assert_response_redacts_sensitive_values(response, token, user_email, "CacheFailure123!")
    assert len(replay_redis_cache.set_calls) == 1
    assert replay_redis_cache.invalidated_identities == []


def test_weak_password_does_not_consume_valid_token(
    client,
    override_replay_redis_cache,
    reset_user,
):
    user_email = reset_user.email
    token = create_password_reset_token(user_email)

    response = client.post(
        "/api/v2/auth/password/reset-confirm",
        headers=_csrf_headers(client),
        json={"token": token, "new_password": "weakpass"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    _assert_stable_auth_error(response.json(), RESET_WEAK_PASSWORD_ERROR)
    _assert_response_redacts_sensitive_values(response, token, user_email, "weakpass")
    assert override_replay_redis_cache.set_calls == []
    assert override_replay_redis_cache.invalidated_identities == []
