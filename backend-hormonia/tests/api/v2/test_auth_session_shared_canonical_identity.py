"""Focused contract proof for the shared V2 session/auth helper family."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v2 import auth_session_shared, user_cache_shared
from app.api.v2.messages import helpers as message_helpers
from app.api.v2.routers.tasks import dependencies as tasks_dependencies

pytestmark = [pytest.mark.api, pytest.mark.auth]


def _canonical_user_data(
    *,
    user_id: str | None = None,
    email: str = "shared.helper@example.com",
    role: str = "doctor",
) -> dict:
    resolved_user_id = user_id or str(uuid4())
    return {
        "id": resolved_user_id,
        "email": email,
        "full_name": "Dra. Shared Helper",
        "role": role,
        "is_active": True,
        "created_at": "2026-03-14T10:00:00-03:00",
        "updated_at": "2026-03-14T10:30:00-03:00",
        "last_login": None,
        "photo_url": None,
    }


def _shared_user_model(
    *,
    user_id: str,
    firebase_uid: str | None = None,
    role: str = "doctor",
    email: str = "shared.db@example.com",
):
    return SimpleNamespace(
        id=user_id,
        firebase_uid=firebase_uid,
        email=email,
        full_name="Dra. Shared DB",
        role=SimpleNamespace(value=role),
        is_active=True,
        created_at=None,
        updated_at=None,
        firebase_last_sign_in=None,
        firebase_photo_url=None,
    )


def _shared_db(user):
    async def _execute(_stmt):
        return SimpleNamespace(scalar_one_or_none=lambda: user)

    return SimpleNamespace(execute=AsyncMock(side_effect=_execute))


def _session_redis_cache(session_payload: dict | None):
    return SimpleNamespace(
        get_session=AsyncMock(return_value=session_payload),
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError("Shared session auth must not read firebase_uid cache")
        ),
        get_user_by_id=AsyncMock(
            side_effect=AssertionError("DB-authoritative shared auth must not read user cache")
        ),
        cache_user_data_by_user_id=AsyncMock(return_value=True),
        cache_user_data=AsyncMock(return_value=True),
        create_session=AsyncMock(return_value=True),
    )


@pytest.mark.parametrize(
    ("authorization", "x_session_id", "session_cookie_id", "query_session_id", "expected"),
    [
        ("Bearer bearer-session", "header-session", "cookie-session", "query-session", "cookie-session"),
        (None, "header-session", "cookie-session", "query-session", "cookie-session"),
        (None, None, "cookie-session", "query-session", "cookie-session"),
        (None, None, None, "query-session", None),
    ],
)
def test_shared_resolve_session_id_uses_cookie_only_contract(
    authorization: str | None,
    x_session_id: str | None,
    session_cookie_id: str | None,
    query_session_id: str | None,
    expected: str,
):
    assert (
        auth_session_shared.resolve_session_id(
            authorization=authorization,
            x_session_id=x_session_id,
            session_cookie_id=session_cookie_id,
            query_session_id=query_session_id,
        )
        == expected
    ), (
        "canonical_identity surface=session_id_resolution cookie_only_contract_broken=true"
    )


@pytest.mark.asyncio
async def test_messages_helper_accepts_canonical_session_after_db_validation_without_firebase_uid():
    canonical_user_id = str(uuid4())
    session_payload = {
        "session_id": "messages-session",
        "user_id": canonical_user_id,
        "email": "messages.shared@example.com",
        "full_name": "Dra. Messages Shared",
        "role": "doctor",
        "is_active": True,
    }
    redis_cache = _session_redis_cache(session_payload)
    db = _shared_db(
        _shared_user_model(
            user_id=canonical_user_id,
            email="messages.db@example.com",
        )
    )

    user_data = await message_helpers._get_current_user_simple(
        session_cookie_id="messages-session",
        db=db,
        redis_cache=redis_cache,
    )

    assert user_data["id"] == canonical_user_id, (
        "canonical_identity surface=messages_embedded canonical_user_id_missing=true"
    )
    assert user_data["email"] == "messages.db@example.com"
    assert user_data["role"] == "doctor"
    assert "firebase_uid" not in user_data, (
        "canonical_identity surface=messages_embedded firebase_uid_present=true"
    )
    db.execute.assert_awaited_once()
    redis_cache.get_user_by_uid.assert_not_called()
    redis_cache.get_user_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_shared_helper_accepts_embedded_canonical_id_alias_after_db_validation():
    canonical_user_id = str(uuid4())
    session_payload = {
        "session_id": "shared-id-alias-session",
        "id": canonical_user_id,
        "email": "shared.alias@example.com",
        "full_name": "Dra. Shared Alias",
        "role": "doctor",
        "is_active": True,
    }
    redis_cache = _session_redis_cache(session_payload)
    db = _shared_db(
        _shared_user_model(
            user_id=canonical_user_id,
            email="shared.alias.db@example.com",
        )
    )

    user_data = await auth_session_shared.get_user_data_from_session(
        session_id="shared-id-alias-session",
        db=db,
        redis_cache=redis_cache,
    )

    assert user_data["id"] == canonical_user_id, (
        "canonical_identity surface=shared_id_alias canonical_user_id_missing=true"
    )
    assert user_data["email"] == "shared.alias.db@example.com"
    assert "firebase_uid" not in user_data, (
        "canonical_identity surface=shared_id_alias firebase_uid_present=true"
    )
    db.execute.assert_awaited_once()
    redis_cache.get_user_by_uid.assert_not_called()
    redis_cache.get_user_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_shared_helper_ignores_firebase_uid_only_redis_payload_and_uses_db_session_user():
    canonical_user_id = str(uuid4())
    redis_cache = _session_redis_cache(
        {
            "session_id": "legacy-firebase-only-session",
            "firebase_uid": "u" * 28,
        }
    )
    db = _shared_db(_shared_user_model(user_id=canonical_user_id))

    user_data = await auth_session_shared.get_user_data_from_session(
        session_id="legacy-firebase-only-session",
        db=db,
        redis_cache=redis_cache,
    )

    assert user_data["id"] == canonical_user_id, (
        "canonical_identity surface=shared_redis_ignored canonical_user_id_missing=true"
    )
    assert "firebase_uid" not in user_data, (
        "canonical_identity surface=shared_redis_ignored firebase_uid_present=true"
    )
    db.execute.assert_awaited_once()
    redis_cache.get_user_by_uid.assert_not_called()
    redis_cache.get_user_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_tasks_dependency_uses_cookie_only_canonical_session():
    canonical_user_id = str(uuid4())
    session_payload = {
        "session_id": "cookie-session",
        "user_id": canonical_user_id,
        "email": "tasks.shared@example.com",
        "full_name": "Dra. Tasks Shared",
        "role": "admin",
        "is_active": True,
    }
    redis_cache = _session_redis_cache(session_payload)
    db = _shared_db(
        _shared_user_model(
            user_id=canonical_user_id,
            role="admin",
            email="tasks.db@example.com",
        )
    )

    user_data = await tasks_dependencies._get_current_user_simple(
        session_cookie_id="cookie-session",
        db=db,
        redis_cache=redis_cache,
    )

    assert user_data["id"] == canonical_user_id, (
        "canonical_identity surface=tasks_cookie_session canonical_user_id_missing=true"
    )
    assert user_data["role"] == "admin"
    assert "firebase_uid" not in user_data, (
        "canonical_identity surface=tasks_cookie_session firebase_uid_present=true"
    )
    redis_cache.get_session.assert_awaited_once_with("cookie-session")
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_cache_shared_returns_canonical_runtime_payload_without_firebase_uid():
    canonical_user_id = str(uuid4())
    redis_cache = SimpleNamespace(
        get_user_by_id=AsyncMock(return_value=None),
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError(
                "Canonical runtime payload writes should not touch firebase_uid cache adapters"
            )
        ),
        cache_user_data_by_user_id=AsyncMock(return_value=True),
        cache_user_data=AsyncMock(
            side_effect=AssertionError(
                "Canonical runtime payload writes should not repopulate firebase_uid cache entries"
            )
        ),
    )
    fetch_user_by_id = AsyncMock(
        return_value=_shared_user_model(
            user_id=canonical_user_id,
            firebase_uid="s" * 28,
        )
    )

    user_data = await user_cache_shared.get_or_cache_user_data(
        redis_cache=redis_cache,
        user_id=canonical_user_id,
        fetch_user_by_id=fetch_user_by_id,
    )

    assert user_data["id"] == canonical_user_id, (
        "canonical_identity surface=user_cache_runtime canonical_user_id_missing=true"
    )
    assert user_data["email"] == "shared.db@example.com"
    assert "firebase_uid" not in user_data, (
        "canonical_identity surface=user_cache_runtime firebase_uid_present=true"
    )
    assert redis_cache.get_user_by_uid.await_count == 0, (
        "canonical_identity surface=user_cache_runtime firebase_uid_cache_lookup_used=true"
    )
    redis_cache.cache_user_data.assert_not_called()
    fetch_user_by_id.assert_awaited_once_with(canonical_user_id)
    redis_cache.cache_user_data_by_user_id.assert_awaited_once_with(
        canonical_user_id,
        user_data,
        ttl=900,
    )


@pytest.mark.asyncio
async def test_user_cache_shared_strips_legacy_firebase_uid_from_cached_user_payloads():
    canonical_user_id = str(uuid4())
    redis_cache = SimpleNamespace(
        get_user_by_id=AsyncMock(
            return_value={
                **_canonical_user_data(user_id=canonical_user_id, email="cached.shared@example.com"),
                "firebase_uid": "legacy-shared-uid",
            }
        ),
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError(
                "Canonical cache hits should not fall back to firebase_uid lookups"
            )
        ),
    )

    user_data = await user_cache_shared.get_or_cache_user_data(
        redis_cache=redis_cache,
        user_id=canonical_user_id,
        fetch_user_by_id=AsyncMock(
            side_effect=AssertionError("Canonical cache hits should not require DB lookup")
        ),
    )

    assert user_data["id"] == canonical_user_id, (
        "canonical_identity surface=user_cache_cached canonical_user_id_missing=true"
    )
    assert user_data["email"] == "cached.shared@example.com"
    assert "firebase_uid" not in user_data, (
        "canonical_identity surface=user_cache_cached firebase_uid_present=true"
    )
    assert redis_cache.get_user_by_uid.await_count == 0, (
        "canonical_identity surface=user_cache_cached firebase_uid_cache_lookup_used=true"
    )


@pytest.mark.asyncio
async def test_user_cache_shared_rejects_missing_canonical_user_id_without_firebase_uid_lookup():
    redis_cache = SimpleNamespace(
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError(
                "Missing canonical user_id should fail before firebase_uid cache lookup"
            )
        ),
        cache_user_data_by_user_id=AsyncMock(return_value=True),
        cache_user_data=AsyncMock(
            side_effect=AssertionError(
                "Missing canonical user_id should fail before firebase_uid cache writes"
            )
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await user_cache_shared.get_or_cache_user_data(
            redis_cache=redis_cache,
            user_id=None,
            fetch_user_by_id=AsyncMock(
                side_effect=AssertionError(
                    "Missing canonical user_id should fail before DB lookup"
                )
            ),
        )

    assert exc_info.value.status_code == 401, (
        "canonical_identity surface=user_cache_missing_user_id unexpected_status=true"
    )
    assert exc_info.value.detail == "Invalid session data", (
        "canonical_identity surface=user_cache_missing_user_id unexpected_detail=true"
    )
    redis_cache.get_user_by_uid.assert_not_called()
    redis_cache.cache_user_data.assert_not_called()
