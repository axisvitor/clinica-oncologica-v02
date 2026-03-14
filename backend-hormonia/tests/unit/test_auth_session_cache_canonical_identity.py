"""Focused contract proof for canonical session-cache identity helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.dependencies import auth_session_cache

pytestmark = [pytest.mark.unit, pytest.mark.auth]


def _canonical_user_data(
    *,
    user_id: str | None = None,
    firebase_uid: str | None = None,
    email: str = "canonical.cache@example.com",
    role: str = "doctor",
) -> dict:
    resolved_user_id = user_id or str(uuid4())
    return {
        "id": resolved_user_id,
        "firebase_uid": firebase_uid,
        "email": email,
        "full_name": "Dra. Canonical Cache",
        "role": role,
        "is_active": True,
        "created_at": "2026-03-14T09:00:00-03:00",
        "updated_at": "2026-03-14T09:30:00-03:00",
        "last_login": None,
        "photo_url": None,
    }


def _fallback_user_model(*, user_id: str, firebase_uid: str | None = None):
    return SimpleNamespace(
        id=user_id,
        firebase_uid=firebase_uid,
        email="fallback.cache@example.com",
        full_name="Dra. Fallback Cache",
        role=SimpleNamespace(value="doctor"),
        is_active=True,
        created_at=None,
        updated_at=None,
        firebase_last_sign_in=None,
        firebase_photo_url=None,
    )


@pytest.mark.asyncio
async def test_resolve_session_user_data_uses_embedded_canonical_user_without_firebase_uid():
    session_payload = {
        "session_id": "canonical-embedded-session",
        "user_id": str(uuid4()),
        "email": "embedded.cache@example.com",
        "full_name": "Dra. Embedded Cache",
        "role": "doctor",
        "is_active": True,
        "created_at": "2026-03-14T09:00:00-03:00",
        "updated_at": "2026-03-14T09:30:00-03:00",
        "last_login": None,
    }
    redis_cache = SimpleNamespace(
        get_session=AsyncMock(return_value=session_payload),
        update_session_activity=AsyncMock(return_value=True),
        get_user_by_id=AsyncMock(
            side_effect=AssertionError("Embedded canonical session payload should not require user-id cache lookup")
        ),
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError("Embedded canonical session payload should not require firebase_uid cache lookup")
        ),
    )

    user_data, resolution_mode = await auth_session_cache.resolve_session_user_data(
        session_id="canonical-embedded-session",
        redis_cache=redis_cache,
        redis_operation_timeout=0.1,
        session_ttl=86400,
        validate_firebase_uid=MagicMock(side_effect=AssertionError("firebase_uid fallback should not run")),
        load_user_from_db_by_user_id=AsyncMock(
            side_effect=AssertionError("Embedded canonical session payload should not require DB lookup")
        ),
        load_user_from_db_by_firebase_uid=AsyncMock(
            side_effect=AssertionError("Embedded canonical session payload should not require firebase DB lookup")
        ),
        load_user_from_db_by_session=AsyncMock(
            side_effect=AssertionError("Embedded canonical session payload should not require session fallback lookup")
        ),
    )

    assert resolution_mode == "redis"
    assert user_data["id"] == session_payload["user_id"]
    assert user_data["email"] == session_payload["email"]
    assert user_data["role"] == session_payload["role"]
    assert user_data["firebase_uid"] is None
    redis_cache.get_user_by_id.assert_not_called()
    redis_cache.get_user_by_uid.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_session_user_data_accepts_embedded_canonical_id_alias_without_user_id():
    session_payload = {
        "session_id": "canonical-id-alias-session",
        "id": str(uuid4()),
        "email": "embedded.id.alias@example.com",
        "full_name": "Dra. Embedded Alias",
        "role": "doctor",
        "is_active": True,
        "created_at": "2026-03-14T09:00:00-03:00",
        "updated_at": "2026-03-14T09:30:00-03:00",
        "last_login": None,
    }
    redis_cache = SimpleNamespace(
        get_session=AsyncMock(return_value=session_payload),
        update_session_activity=AsyncMock(return_value=True),
        get_user_by_id=AsyncMock(
            side_effect=AssertionError("Embedded canonical id alias should not require user-id cache lookup")
        ),
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError("Embedded canonical id alias should not require firebase_uid cache lookup")
        ),
    )

    user_data, resolution_mode = await auth_session_cache.resolve_session_user_data(
        session_id="canonical-id-alias-session",
        redis_cache=redis_cache,
        redis_operation_timeout=0.1,
        session_ttl=86400,
        validate_firebase_uid=MagicMock(side_effect=AssertionError("firebase_uid fallback should not run")),
        load_user_from_db_by_user_id=AsyncMock(
            side_effect=AssertionError("Embedded canonical id alias should not require DB lookup")
        ),
        load_user_from_db_by_firebase_uid=AsyncMock(
            side_effect=AssertionError("Embedded canonical id alias should not require firebase DB lookup")
        ),
        load_user_from_db_by_session=AsyncMock(
            side_effect=AssertionError("Embedded canonical id alias should not require session fallback lookup")
        ),
    )

    assert resolution_mode == "redis"
    assert user_data["id"] == session_payload["id"]
    assert user_data["email"] == session_payload["email"]
    assert user_data["firebase_uid"] is None
    redis_cache.get_user_by_id.assert_not_called()
    redis_cache.get_user_by_uid.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_session_user_data_prefers_db_lookup_by_user_id_before_firebase_uid_cache_fallback():
    canonical_user_id = str(uuid4())
    firebase_uid = "c" * 28
    stale_uid_cache_user = _canonical_user_data(
        user_id=str(uuid4()),
        firebase_uid=firebase_uid,
        email="stale.uid.cache@example.com",
    )
    canonical_user = _fallback_user_model(user_id=canonical_user_id, firebase_uid=firebase_uid)

    redis_cache = SimpleNamespace(
        get_session=AsyncMock(
            return_value={
                "user_id": canonical_user_id,
                "firebase_uid": firebase_uid,
            }
        ),
        update_session_activity=AsyncMock(return_value=True),
        get_user_by_id=AsyncMock(return_value=None),
        get_user_by_uid=AsyncMock(return_value=stale_uid_cache_user),
    )
    load_user_from_db_by_user_id = AsyncMock(return_value=canonical_user)

    user_data, resolution_mode = await auth_session_cache.resolve_session_user_data(
        session_id="dual-identity-session",
        redis_cache=redis_cache,
        redis_operation_timeout=0.1,
        session_ttl=86400,
        validate_firebase_uid=MagicMock(),
        load_user_from_db_by_user_id=load_user_from_db_by_user_id,
        load_user_from_db_by_firebase_uid=AsyncMock(
            side_effect=AssertionError("firebase_uid DB fallback should stay quarantined when user_id exists")
        ),
        load_user_from_db_by_session=AsyncMock(
            side_effect=AssertionError("Session lookup should stay on the canonical user_id path")
        ),
        serialize_user=lambda user: auth_session_cache.serialize_user_data(user),
    )

    assert resolution_mode == "redis"
    assert user_data["id"] == canonical_user_id
    assert user_data["email"] == canonical_user.email
    redis_cache.get_user_by_uid.assert_not_called()
    load_user_from_db_by_user_id.assert_awaited_once_with(canonical_user_id)


@pytest.mark.asyncio
async def test_resolve_session_user_data_rehydrates_fallback_session_with_canonical_user_id():
    canonical_user = _fallback_user_model(user_id=str(uuid4()))
    redis_cache = SimpleNamespace(
        get_session=AsyncMock(side_effect=RuntimeError("redis unavailable")),
        update_session_activity=AsyncMock(return_value=True),
        cache_user_data_by_user_id=AsyncMock(return_value=True),
        cache_user_data=AsyncMock(return_value=True),
        create_session=AsyncMock(return_value=True),
    )

    user_data, resolution_mode = await auth_session_cache.resolve_session_user_data(
        session_id="fallback-session-contract",
        redis_cache=redis_cache,
        redis_operation_timeout=0.1,
        session_ttl=43200,
        validate_firebase_uid=MagicMock(side_effect=AssertionError("fallback session should not need firebase_uid validation")),
        load_user_from_db_by_user_id=AsyncMock(
            side_effect=AssertionError("Fallback path should resolve from session -> DB, not direct user_id lookup")
        ),
        load_user_from_db_by_firebase_uid=AsyncMock(
            side_effect=AssertionError("Fallback path should not reach firebase DB lookup")
        ),
        load_user_from_db_by_session=AsyncMock(return_value=canonical_user),
        serialize_user=lambda user: auth_session_cache.serialize_user_data(user),
    )

    assert resolution_mode == "fallback"
    assert user_data["id"] == str(canonical_user.id)
    redis_cache.cache_user_data_by_user_id.assert_awaited_once_with(user_data["id"], user_data, ttl=900)
    redis_cache.cache_user_data.assert_not_called()
    redis_cache.create_session.assert_awaited_once()
    create_session_call = redis_cache.create_session.await_args
    assert create_session_call.kwargs["session_id"] == "fallback-session-contract"
    assert create_session_call.kwargs["user_id"] == user_data["id"]
    assert create_session_call.kwargs["firebase_uid"] is None
    assert "firebase_uid" not in create_session_call.kwargs["metadata"]
    assert create_session_call.kwargs["metadata"]["session_id"] == "fallback-session-contract"
    assert create_session_call.kwargs["metadata"]["email"] == canonical_user.email
    assert create_session_call.kwargs["metadata"]["max_age_seconds"] == 43200


@pytest.mark.asyncio
async def test_resolve_session_user_data_falls_back_to_firebase_uid_only_when_canonical_identity_is_absent():
    firebase_uid = "f" * 28
    cached_user = _canonical_user_data(firebase_uid=firebase_uid, email="compat.uid.cache@example.com")
    validate_firebase_uid = MagicMock()
    redis_cache = SimpleNamespace(
        get_session=AsyncMock(return_value={"firebase_uid": firebase_uid}),
        update_session_activity=AsyncMock(return_value=True),
        get_user_by_uid=AsyncMock(return_value=cached_user),
    )

    user_data, resolution_mode = await auth_session_cache.resolve_session_user_data(
        session_id="compat-only-session",
        redis_cache=redis_cache,
        redis_operation_timeout=0.1,
        session_ttl=86400,
        validate_firebase_uid=validate_firebase_uid,
        load_user_from_db_by_user_id=AsyncMock(
            side_effect=AssertionError("Canonical DB lookup should not run without a canonical user_id")
        ),
        load_user_from_db_by_firebase_uid=AsyncMock(
            side_effect=AssertionError("firebase_uid cache hit should not require DB lookup")
        ),
        load_user_from_db_by_session=AsyncMock(
            side_effect=AssertionError("Session fallback should not run on compatibility cache hit")
        ),
        serialize_user=lambda user: auth_session_cache.serialize_user_data(user),
    )

    assert resolution_mode == "redis"
    assert user_data["firebase_uid"] == firebase_uid
    assert user_data["email"] == cached_user["email"]
    validate_firebase_uid.assert_called_once_with(firebase_uid)
    redis_cache.get_user_by_uid.assert_awaited_once_with(firebase_uid)
