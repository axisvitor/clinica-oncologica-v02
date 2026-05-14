"""M015/S02 runtime contract tests for DB-authoritative staff sessions."""

from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request

from app.api.v2 import auth_session_shared
from app.api.v2.routers import users as users_router
from app.dependencies import auth_session_cache
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.dependencies.auth_session_invalidation import invalidate_session_cache

pytestmark = [pytest.mark.security, pytest.mark.auth]


def _user_model(
    *,
    user_id: str | None = None,
    email: str = "db.session@example.com",
    role: str = "doctor",
    is_active: bool = True,
):
    return SimpleNamespace(
        id=user_id or str(uuid4()),
        email=email,
        full_name="Dra. DB Session",
        role=SimpleNamespace(value=role),
        is_active=is_active,
        created_at=None,
        updated_at=None,
        last_login=None,
        photo_url=None,
        firebase_last_sign_in=None,
        firebase_photo_url=None,
    )


def _stale_session_payload(*, user_id: str, email: str = "stale.redis@example.com") -> dict:
    return {
        "session_id": "cache-hit-session",
        "user_id": user_id,
        "email": email,
        "full_name": "Stale Redis User",
        "role": "admin",
        "is_active": True,
        "created_at": "2026-05-13T00:00:00-03:00",
        "updated_at": "2026-05-13T00:00:00-03:00",
        "last_login": None,
    }


def _redis_cache(*, session_result=None, session_exc: BaseException | None = None):
    async def _get_session(_session_id: str):
        if session_exc is not None:
            raise session_exc
        return session_result

    return SimpleNamespace(
        get_session=AsyncMock(side_effect=_get_session),
        update_session_activity=AsyncMock(return_value=True),
        get_user_by_id=AsyncMock(
            side_effect=AssertionError(
                "DB-authoritative session resolution must not trust user-id cache hits"
            )
        ),
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError("Legacy firebase_uid cache must not be consulted")
        ),
        cache_user_data_by_user_id=AsyncMock(return_value=True),
        cache_user_data=AsyncMock(return_value=True),
        create_session=AsyncMock(return_value=True),
        session_ttl=43200,
    )


def _db_execute_result(user):
    return SimpleNamespace(scalar_one_or_none=lambda: user)


def _shared_db(user=None, *, exc: BaseException | None = None):
    async def _execute(_stmt):
        if exc is not None:
            raise exc
        return _db_execute_result(user)

    return SimpleNamespace(execute=AsyncMock(side_effect=_execute))


async def _resolve_session_cache(redis_cache, *, db_user=None, db_exc=None, session_id="cache-hit-session"):
    async def _load_by_session(_session_id: str):
        if db_exc is not None:
            raise db_exc
        return db_user

    load_by_session = AsyncMock(side_effect=_load_by_session)
    user_data, resolution_mode = await auth_session_cache.resolve_session_user_data(
        session_id=session_id,
        redis_cache=redis_cache,
        redis_operation_timeout=0.1,
        session_ttl=43200,
        load_user_from_db_by_user_id=AsyncMock(
            side_effect=AssertionError(
                "DB-authoritative session resolution should not perform a second user-id DB lookup"
            )
        ),
        load_user_from_db_by_session=load_by_session,
        serialize_user=lambda user: auth_session_cache.serialize_user_data(user),
    )
    return user_data, resolution_mode, load_by_session


@pytest.mark.asyncio
async def test_cache_hit_requires_db_session_validation_before_trusting_redis_payload():
    user_id = str(uuid4())
    db_user = _user_model(user_id=user_id, email="db-authoritative@example.com")
    redis_cache = _redis_cache(session_result=_stale_session_payload(user_id=user_id))

    user_data, resolution_mode, load_by_session = await _resolve_session_cache(
        redis_cache,
        db_user=db_user,
    )

    assert resolution_mode == "redis"
    assert user_data["id"] == user_id
    assert user_data["email"] == "db-authoritative@example.com"
    assert user_data["role"] == "doctor"
    load_by_session.assert_awaited_once_with("cache-hit-session")
    redis_cache.get_user_by_id.assert_not_called()
    redis_cache.get_user_by_uid.assert_not_called()


@pytest.mark.asyncio
async def test_cache_miss_falls_back_to_db_session_and_rehydrates_redis():
    user_id = str(uuid4())
    db_user = _user_model(user_id=user_id)
    redis_cache = _redis_cache(session_result=None)

    user_data, resolution_mode, load_by_session = await _resolve_session_cache(
        redis_cache,
        db_user=db_user,
        session_id="cache-miss-session",
    )

    assert resolution_mode == "fallback"
    assert user_data["id"] == user_id
    load_by_session.assert_awaited_once_with("cache-miss-session")
    redis_cache.cache_user_data_by_user_id.assert_awaited_once()
    redis_cache.create_session.assert_awaited_once()
    assert redis_cache.create_session.await_args.kwargs["session_id"] == "cache-miss-session"


@pytest.mark.asyncio
async def test_redis_manager_session_rehydration_preserves_fallback_metadata():
    from app.core.redis_manager.manager import RedisManager

    stored: dict[str, object] = {}

    class _FakeRedis:
        def setex(self, key, ttl, value):
            stored["key"] = key
            stored["ttl"] = ttl
            stored["value"] = value
            return True

    manager = RedisManager()
    manager._sync_client = _FakeRedis()
    user_id = str(uuid4())

    created = await manager.create_session(
        session_id="manager-cache-miss-session",
        user_id=user_id,
        firebase_uid=None,
        metadata={
            "email": "manager-fallback@example.com",
            "role": "doctor",
            "is_active": True,
            "max_age_seconds": 43200,
        },
        ttl=43200,
    )

    assert created is True
    assert stored["key"] == "session:manager-cache-miss-session"
    assert stored["ttl"] == 43200
    payload = json.loads(stored["value"])
    assert payload["user_id"] == user_id
    assert payload["email"] == "manager-fallback@example.com"
    assert payload["role"] == "doctor"
    assert payload["is_active"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("db_state", ["revoked", "expired"])
async def test_stale_redis_cache_is_denied_when_db_session_is_not_active(db_state: str):
    del db_state
    redis_cache = _redis_cache(session_result=_stale_session_payload(user_id=str(uuid4())))

    with pytest.raises(HTTPException) as exc_info:
        await _resolve_session_cache(redis_cache, db_user=None)

    assert exc_info.value.status_code == 401
    assert "Invalid or expired session" in exc_info.value.detail
    redis_cache.get_user_by_id.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "redis_exc",
    [asyncio.TimeoutError(), RuntimeError("redis unavailable")],
)
async def test_redis_timeout_or_error_falls_back_to_db_session(redis_exc: BaseException):
    user_id = str(uuid4())
    redis_cache = _redis_cache(session_exc=redis_exc)

    user_data, resolution_mode, load_by_session = await _resolve_session_cache(
        redis_cache,
        db_user=_user_model(user_id=user_id),
        session_id="redis-fallback-session",
    )

    assert resolution_mode == "fallback"
    assert user_data["id"] == user_id
    load_by_session.assert_awaited_once_with("redis-fallback-session")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "db_exc",
    [asyncio.TimeoutError(), RuntimeError("database unavailable")],
)
async def test_db_timeout_or_error_fails_closed_even_when_redis_has_stale_session(db_exc: BaseException):
    redis_cache = _redis_cache(session_result=_stale_session_payload(user_id=str(uuid4())))

    with pytest.raises(HTTPException) as exc_info:
        await _resolve_session_cache(redis_cache, db_exc=db_exc)

    assert exc_info.value.status_code == 503
    assert "Database temporarily unavailable" in exc_info.value.detail


@pytest.mark.asyncio
async def test_inactive_db_user_denied_before_stale_redis_active_payload_is_trusted():
    user_id = str(uuid4())
    redis_cache = _redis_cache(session_result=_stale_session_payload(user_id=user_id))

    with pytest.raises(HTTPException) as exc_info:
        await _resolve_session_cache(
            redis_cache,
            db_user=_user_model(user_id=user_id, is_active=False),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "User account is inactive"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("x_session_id", "authorization"),
    [("legacy-header-session", None), (None, "Bearer legacy-bearer-session")],
)
async def test_staff_session_auth_rejects_legacy_transports_without_cookie(
    x_session_id: str | None,
    authorization: str | None,
):
    request = MagicMock(spec=Request)
    request.state = SimpleNamespace()
    redis_cache = _redis_cache(session_result=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_from_session(
            request=request,
            session_cookie_id=None,
            x_session_id=x_session_id,
            authorization=authorization,
            redis_cache=redis_cache,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Session cookie required"
    redis_cache.get_session.assert_not_called()
    assert not hasattr(request.state, "session_id")


@pytest.mark.asyncio
async def test_shared_helper_cache_hit_validates_db_session_before_embedded_payload():
    user_id = str(uuid4())
    redis_cache = _redis_cache(session_result=_stale_session_payload(user_id=user_id))

    user_data = await auth_session_shared.get_user_data_from_session(
        session_id="shared-cache-hit-session",
        db=_shared_db(_user_model(user_id=user_id, email="shared-db@example.com")),
        redis_cache=redis_cache,
    )

    assert user_data["id"] == user_id
    assert user_data["email"] == "shared-db@example.com"
    assert user_data["role"] == "doctor"
    redis_cache.get_user_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_shared_helper_cache_miss_uses_db_session_fallback():
    user_id = str(uuid4())
    redis_cache = _redis_cache(session_result=None)

    user_data = await auth_session_shared.get_user_data_from_session(
        session_id="shared-cache-miss-session",
        db=_shared_db(_user_model(user_id=user_id)),
        redis_cache=redis_cache,
    )

    assert user_data["id"] == user_id
    redis_cache.cache_user_data_by_user_id.assert_awaited_once()
    redis_cache.create_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_shared_helper_rejects_stale_cache_when_db_session_missing():
    redis_cache = _redis_cache(session_result=_stale_session_payload(user_id=str(uuid4())))

    with pytest.raises(HTTPException) as exc_info:
        await auth_session_shared.get_user_data_from_session(
            session_id="shared-revoked-session",
            db=_shared_db(None),
            redis_cache=redis_cache,
        )

    assert exc_info.value.status_code == 401
    assert "Invalid or expired session" in exc_info.value.detail


@pytest.mark.asyncio
async def test_session_cache_invalidation_uses_wrapper_session_contract_first():
    session_id = str(uuid4())
    redis_cache = SimpleNamespace(
        invalidate_session=AsyncMock(return_value=True),
        delete_session=AsyncMock(return_value=True),
        delete=AsyncMock(return_value=1),
    )

    invalidated = await invalidate_session_cache(redis_cache, session_id)

    assert invalidated is True
    redis_cache.invalidate_session.assert_awaited_once_with(session_id)
    redis_cache.delete_session.assert_not_called()
    redis_cache.delete.assert_not_called()


@pytest.mark.asyncio
async def test_session_cache_invalidation_falls_back_on_helper_signature_mismatch():
    session_id = str(uuid4())
    redis_cache = SimpleNamespace(
        invalidate_session=AsyncMock(side_effect=TypeError("unexpected signature")),
        delete_session=AsyncMock(return_value=True),
        delete=AsyncMock(return_value=1),
    )

    invalidated = await invalidate_session_cache(redis_cache, session_id)

    assert invalidated is True
    redis_cache.invalidate_session.assert_awaited_once_with(session_id)
    redis_cache.delete_session.assert_awaited_once_with(session_id)
    redis_cache.delete.assert_not_called()


@pytest.mark.asyncio
async def test_session_cache_invalidation_raw_redis_deletes_canonical_session_key_and_compat_key():
    session_id = str(uuid4())
    redis_cache = SimpleNamespace(delete=AsyncMock(return_value=2))

    invalidated = await invalidate_session_cache(redis_cache, session_id)

    assert invalidated is True
    redis_cache.delete.assert_awaited_once_with(f"session:{session_id}", session_id)


@pytest.mark.asyncio
async def test_session_cache_invalidation_failure_logs_sanitized_warning(caplog):
    session_id = str(uuid4())
    redis_cache = SimpleNamespace(
        invalidate_session=AsyncMock(side_effect=RuntimeError("redis password=secret unavailable"))
    )

    with caplog.at_level(logging.WARNING):
        invalidated = await invalidate_session_cache(redis_cache, session_id)

    assert invalidated is False
    assert "session_cache_invalidation_failed" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "password=secret" not in caplog.text


class _FakeSessionRevocationQuery:
    def __init__(self, session):
        self._session = session

    def filter(self, *args):
        del args
        return self

    def first(self):
        return self._session


class _FakeSessionRevocationDb:
    def __init__(self, session, events: list[str], *, commit_exc: BaseException | None = None):
        self._session = session
        self._events = events
        self._commit_exc = commit_exc
        self.rollback_called = False

    def query(self, _model):
        return _FakeSessionRevocationQuery(self._session)

    def commit(self):
        self._events.append("commit")
        if self._commit_exc is not None:
            raise self._commit_exc

    def rollback(self):
        self.rollback_called = True


@pytest.mark.asyncio
async def test_user_revoke_session_commits_db_before_invalidating_redis_cache():
    user_id = uuid4()
    session_id = uuid4()
    events: list[str] = []
    session = SimpleNamespace(
        id=session_id,
        user_id=user_id,
        is_active=True,
        revoked_at=None,
        revocation_reason=None,
    )

    async def _invalidate(_session_id: str):
        events.append("cache")
        return True

    response = await users_router.revoke_session(
        str(session_id),
        current_user={"id": str(user_id), "role": "doctor"},
        db=_FakeSessionRevocationDb(session, events),
        redis_cache=SimpleNamespace(invalidate_session=_invalidate),
    )

    assert events == ["commit", "cache"]
    assert response == {"session_id": str(session_id), "revoked": True, "message": "Revoked"}
    assert session.is_active is False
    assert session.revoked_at is not None
    assert session.revocation_reason == "User requested revocation"


@pytest.mark.asyncio
async def test_user_revoke_session_missing_or_foreign_row_has_no_cache_side_effect():
    user_id = uuid4()
    session_id = uuid4()
    events: list[str] = []
    redis_cache = SimpleNamespace(invalidate_session=AsyncMock(return_value=True))

    with pytest.raises(HTTPException) as exc_info:
        await users_router.revoke_session(
            str(session_id),
            current_user={"id": str(user_id), "role": "doctor"},
            db=_FakeSessionRevocationDb(None, events),
            redis_cache=redis_cache,
        )

    assert exc_info.value.status_code == 404
    assert events == []
    redis_cache.invalidate_session.assert_not_called()


@pytest.mark.asyncio
async def test_user_revoke_session_cache_failure_after_commit_still_relies_on_db_revocation(caplog):
    user_id = uuid4()
    session_id = uuid4()
    events: list[str] = []
    session = SimpleNamespace(
        id=session_id,
        user_id=user_id,
        is_active=True,
        revoked_at=None,
        revocation_reason=None,
    )
    redis_cache = SimpleNamespace(
        invalidate_session=AsyncMock(side_effect=RuntimeError("redis password=secret unavailable"))
    )

    with caplog.at_level(logging.WARNING):
        response = await users_router.revoke_session(
            str(session_id),
            current_user={"id": str(user_id), "role": "doctor"},
            db=_FakeSessionRevocationDb(session, events),
            redis_cache=redis_cache,
        )

    assert events == ["commit"]
    assert response["revoked"] is True
    assert session.is_active is False
    assert session.revoked_at is not None
    assert "session_cache_invalidation_failed" in caplog.text
    assert "password=secret" not in caplog.text
