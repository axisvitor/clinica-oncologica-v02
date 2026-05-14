"""Focused contract proof for canonical session-cache identity helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.dependencies import auth_session_cache

pytestmark = [pytest.mark.unit, pytest.mark.auth]


def _fallback_user_model(
    *,
    user_id: str,
    firebase_uid: str | None = None,
    email: str = "fallback.cache@example.com",
    role: str = "doctor",
    is_active: bool = True,
):
    return SimpleNamespace(
        id=user_id,
        firebase_uid=firebase_uid,
        email=email,
        full_name="Dra. Fallback Cache",
        role=SimpleNamespace(value=role),
        is_active=is_active,
        created_at=None,
        updated_at=None,
        firebase_last_sign_in=None,
        firebase_photo_url=None,
    )


def _redis_cache_with_session(session_payload: dict | None):
    return SimpleNamespace(
        get_session=AsyncMock(return_value=session_payload),
        update_session_activity=AsyncMock(return_value=True),
        get_user_by_id=AsyncMock(
            side_effect=AssertionError(
                "DB-authoritative session cache hits should not require user-id cache lookup"
            )
        ),
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError(
                "Canonical session resolution must not consult firebase_uid cache entries"
            )
        ),
        cache_user_data_by_user_id=AsyncMock(return_value=True),
        cache_user_data=AsyncMock(return_value=True),
        create_session=AsyncMock(return_value=True),
    )


async def _resolve_with_db_session(
    *,
    session_id: str,
    redis_cache,
    db_user,
):
    load_user_from_db_by_session = AsyncMock(return_value=db_user)
    load_user_from_db_by_user_id = AsyncMock(
        side_effect=AssertionError(
            "DB-authoritative session resolution should not perform a second user-id DB lookup"
        )
    )

    user_data, resolution_mode = await auth_session_cache.resolve_session_user_data(
        session_id=session_id,
        redis_cache=redis_cache,
        redis_operation_timeout=0.1,
        session_ttl=86400,
        load_user_from_db_by_user_id=load_user_from_db_by_user_id,
        load_user_from_db_by_session=load_user_from_db_by_session,
        serialize_user=lambda user: auth_session_cache.serialize_user_data(user),
    )
    return user_data, resolution_mode, load_user_from_db_by_session, load_user_from_db_by_user_id


@pytest.mark.asyncio
async def test_resolve_session_user_data_validates_embedded_canonical_user_through_db_session():
    canonical_user_id = str(uuid4())
    session_payload = {
        "session_id": "canonical-embedded-session",
        "user_id": canonical_user_id,
        "email": "embedded.cache@example.com",
        "full_name": "Dra. Embedded Cache",
        "role": "doctor",
        "is_active": True,
        "created_at": "2026-03-14T09:00:00-03:00",
        "updated_at": "2026-03-14T09:30:00-03:00",
        "last_login": None,
    }
    redis_cache = _redis_cache_with_session(session_payload)
    db_user = _fallback_user_model(
        user_id=canonical_user_id,
        email="db.cache@example.com",
    )

    user_data, resolution_mode, load_by_session, load_by_user_id = await _resolve_with_db_session(
        session_id="canonical-embedded-session",
        redis_cache=redis_cache,
        db_user=db_user,
    )

    assert resolution_mode == "redis", (
        "canonical_identity surface=cache_embedded resolution_mode=unexpected"
    )
    assert user_data["id"] == canonical_user_id, (
        "canonical_identity surface=cache_embedded canonical_user_id_missing=true"
    )
    assert user_data["email"] == db_user.email
    assert user_data["role"] == db_user.role.value
    assert "firebase_uid" not in user_data, (
        "canonical_identity surface=cache_embedded firebase_uid_present=true"
    )
    load_by_session.assert_awaited_once_with("canonical-embedded-session")
    load_by_user_id.assert_not_called()
    redis_cache.get_user_by_id.assert_not_called()
    redis_cache.get_user_by_uid.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_session_user_data_accepts_embedded_canonical_id_alias_after_db_validation():
    canonical_user_id = str(uuid4())
    session_payload = {
        "session_id": "canonical-id-alias-session",
        "id": canonical_user_id,
        "email": "embedded.id.alias@example.com",
        "full_name": "Dra. Embedded Alias",
        "role": "doctor",
        "is_active": True,
        "created_at": "2026-03-14T09:00:00-03:00",
        "updated_at": "2026-03-14T09:30:00-03:00",
        "last_login": None,
    }
    redis_cache = _redis_cache_with_session(session_payload)
    db_user = _fallback_user_model(
        user_id=canonical_user_id,
        email="db.id.alias@example.com",
    )

    user_data, resolution_mode, load_by_session, load_by_user_id = await _resolve_with_db_session(
        session_id="canonical-id-alias-session",
        redis_cache=redis_cache,
        db_user=db_user,
    )

    assert resolution_mode == "redis", (
        "canonical_identity surface=cache_id_alias resolution_mode=unexpected"
    )
    assert user_data["id"] == canonical_user_id, (
        "canonical_identity surface=cache_id_alias canonical_user_id_missing=true"
    )
    assert user_data["email"] == db_user.email
    assert "firebase_uid" not in user_data, (
        "canonical_identity surface=cache_id_alias firebase_uid_present=true"
    )
    load_by_session.assert_awaited_once_with("canonical-id-alias-session")
    load_by_user_id.assert_not_called()
    redis_cache.get_user_by_id.assert_not_called()
    redis_cache.get_user_by_uid.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_session_user_data_uses_session_db_lookup_without_uid_cache_fallback():
    canonical_user_id = str(uuid4())
    firebase_uid = "c" * 28
    canonical_user = _fallback_user_model(
        user_id=canonical_user_id,
        firebase_uid=firebase_uid,
    )

    redis_cache = _redis_cache_with_session(
        {
            "user_id": canonical_user_id,
            "firebase_uid": firebase_uid,
        }
    )

    user_data, resolution_mode, load_by_session, load_by_user_id = await _resolve_with_db_session(
        session_id="dual-identity-session",
        redis_cache=redis_cache,
        db_user=canonical_user,
    )

    assert resolution_mode == "redis", (
        "canonical_identity surface=user_id_priority resolution_mode=unexpected"
    )
    assert user_data["id"] == canonical_user_id, (
        "canonical_identity surface=user_id_priority canonical_user_id_missing=true"
    )
    assert user_data["email"] == canonical_user.email
    assert "firebase_uid" not in user_data, (
        "canonical_identity surface=user_id_priority firebase_uid_present=true"
    )
    assert redis_cache.get_user_by_uid.await_count == 0, (
        "canonical_identity surface=user_id_priority firebase_uid_cache_fallback_used=true"
    )
    load_by_session.assert_awaited_once_with("dual-identity-session")
    load_by_user_id.assert_not_called()


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
        load_user_from_db_by_user_id=AsyncMock(
            side_effect=AssertionError(
                "Fallback path should resolve from session -> DB, not direct user_id lookup"
            )
        ),
        load_user_from_db_by_session=AsyncMock(return_value=canonical_user),
        serialize_user=lambda user: auth_session_cache.serialize_user_data(user),
    )

    assert resolution_mode == "fallback", (
        "canonical_identity surface=fallback_rehydrate resolution_mode=unexpected"
    )
    assert user_data["id"] == str(canonical_user.id), (
        "canonical_identity surface=fallback_rehydrate canonical_user_id_missing=true"
    )
    assert "firebase_uid" not in user_data, (
        "canonical_identity surface=fallback_rehydrate firebase_uid_present=true"
    )
    redis_cache.cache_user_data_by_user_id.assert_awaited_once_with(
        user_data["id"], user_data, ttl=900
    )
    redis_cache.cache_user_data.assert_not_called()
    redis_cache.create_session.assert_awaited_once()
    create_session_call = redis_cache.create_session.await_args
    assert create_session_call.kwargs["session_id"] == "fallback-session-contract"
    assert create_session_call.kwargs["user_id"] == user_data["id"]
    assert create_session_call.kwargs["firebase_uid"] is None, (
        "canonical_identity surface=fallback_rehydrate session_rehydrated_with_firebase_uid=true"
    )
    assert "firebase_uid" not in create_session_call.kwargs["metadata"], (
        "canonical_identity surface=fallback_rehydrate metadata_firebase_uid_present=true"
    )
    assert create_session_call.kwargs["metadata"]["session_id"] == "fallback-session-contract"
    assert create_session_call.kwargs["metadata"]["email"] == canonical_user.email
    assert create_session_call.kwargs["metadata"]["max_age_seconds"] == 43200


@pytest.mark.asyncio
async def test_resolve_session_user_data_ignores_firebase_uid_only_redis_payload_and_uses_db_session_user():
    canonical_user_id = str(uuid4())
    redis_cache = _redis_cache_with_session({"firebase_uid": "f" * 28})

    user_data, resolution_mode, load_by_session, load_by_user_id = await _resolve_with_db_session(
        session_id="compat-only-session",
        redis_cache=redis_cache,
        db_user=_fallback_user_model(user_id=canonical_user_id),
    )

    assert resolution_mode == "redis", (
        "canonical_identity surface=compat_redis_ignored resolution_mode=unexpected"
    )
    assert user_data["id"] == canonical_user_id, (
        "canonical_identity surface=compat_redis_ignored canonical_user_id_missing=true"
    )
    assert "firebase_uid" not in user_data, (
        "canonical_identity surface=compat_redis_ignored firebase_uid_present=true"
    )
    load_by_session.assert_awaited_once_with("compat-only-session")
    load_by_user_id.assert_not_called()
    redis_cache.get_user_by_id.assert_not_called()
    redis_cache.get_user_by_uid.assert_not_called()
