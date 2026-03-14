"""Focused contract proof for the shared V2 session/auth helper family."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v2 import auth_session_shared, user_cache_shared
from app.api.v2.messages import helpers as message_helpers
from app.api.v2.routers.tasks import dependencies as tasks_dependencies

pytestmark = [pytest.mark.api, pytest.mark.auth]


def _canonical_user_data(
    *,
    user_id: str | None = None,
    firebase_uid: str | None = None,
    email: str = "shared.helper@example.com",
    role: str = "doctor",
) -> dict:
    resolved_user_id = user_id or str(uuid4())
    return {
        "id": resolved_user_id,
        "firebase_uid": firebase_uid,
        "email": email,
        "full_name": "Dra. Shared Helper",
        "role": role,
        "is_active": True,
        "created_at": "2026-03-14T10:00:00-03:00",
        "updated_at": "2026-03-14T10:30:00-03:00",
        "last_login": None,
        "photo_url": None,
    }


def _shared_user_model(*, user_id: str, firebase_uid: str | None = None, role: str = "doctor"):
    return SimpleNamespace(
        id=user_id,
        firebase_uid=firebase_uid,
        email="shared.db@example.com",
        full_name="Dra. Shared DB",
        role=SimpleNamespace(value=role),
        is_active=True,
        created_at=None,
        updated_at=None,
        firebase_last_sign_in=None,
        firebase_photo_url=None,
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
    )


@pytest.mark.asyncio
async def test_messages_helper_accepts_embedded_canonical_session_without_firebase_uid():
    session_payload = {
        "session_id": "messages-session",
        "user_id": str(uuid4()),
        "email": "messages.shared@example.com",
        "full_name": "Dra. Messages Shared",
        "role": "doctor",
        "is_active": True,
    }
    redis_cache = SimpleNamespace(
        get_session=AsyncMock(return_value=session_payload),
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError("Embedded canonical message session should not require firebase_uid cache lookup")
        ),
        get_user_by_id=AsyncMock(
            side_effect=AssertionError("Embedded canonical message session should not require user cache lookup")
        ),
    )

    user_data = await message_helpers._get_current_user_simple(
        session_cookie_id="messages-session",
        db=object(),
        redis_cache=redis_cache,
    )

    assert user_data["id"] == session_payload["user_id"]
    assert user_data["email"] == session_payload["email"]
    assert user_data["role"] == session_payload["role"]
    assert user_data["firebase_uid"] is None
    redis_cache.get_user_by_uid.assert_not_called()
    redis_cache.get_user_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_shared_helper_accepts_embedded_canonical_id_alias_without_user_id():
    session_payload = {
        "session_id": "shared-id-alias-session",
        "id": str(uuid4()),
        "email": "shared.alias@example.com",
        "full_name": "Dra. Shared Alias",
        "role": "doctor",
        "is_active": True,
    }
    redis_cache = SimpleNamespace(
        get_session=AsyncMock(return_value=session_payload),
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError("Embedded canonical shared id alias should not require firebase_uid cache lookup")
        ),
        get_user_by_id=AsyncMock(
            side_effect=AssertionError("Embedded canonical shared id alias should not require user cache lookup")
        ),
    )

    user_data = await auth_session_shared.get_user_data_from_session(
        session_id="shared-id-alias-session",
        db=object(),
        redis_cache=redis_cache,
    )

    assert user_data["id"] == session_payload["id"]
    assert user_data["email"] == session_payload["email"]
    assert user_data["firebase_uid"] is None
    redis_cache.get_user_by_uid.assert_not_called()
    redis_cache.get_user_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_tasks_dependency_uses_cookie_only_canonical_session():
    session_payload = {
        "session_id": "cookie-session",
        "user_id": str(uuid4()),
        "email": "tasks.shared@example.com",
        "full_name": "Dra. Tasks Shared",
        "role": "admin",
        "is_active": True,
    }
    redis_cache = SimpleNamespace(
        get_session=AsyncMock(
            side_effect=lambda session_id: session_payload if session_id == "cookie-session" else None
        ),
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError("Canonical cookie session should not require firebase_uid cache lookup")
        ),
        get_user_by_id=AsyncMock(
            side_effect=AssertionError("Embedded canonical cookie session should not require user cache lookup")
        ),
    )

    user_data = await tasks_dependencies._get_current_user_simple(
        session_cookie_id="cookie-session",
        db=object(),
        redis_cache=redis_cache,
    )

    assert user_data["id"] == session_payload["user_id"]
    assert user_data["role"] == session_payload["role"]
    redis_cache.get_session.assert_awaited_once_with("cookie-session")


@pytest.mark.asyncio
async def test_user_cache_shared_prefers_db_lookup_by_user_id_before_firebase_uid_cache_when_canonical_id_present():
    canonical_user_id = str(uuid4())
    firebase_uid = "s" * 28
    stale_uid_cache_user = _canonical_user_data(
        user_id=str(uuid4()),
        firebase_uid=firebase_uid,
        email="stale.shared.uid@example.com",
    )
    canonical_user = _shared_user_model(user_id=canonical_user_id, firebase_uid=firebase_uid)

    redis_cache = SimpleNamespace(
        get_user_by_id=AsyncMock(return_value=None),
        get_user_by_uid=AsyncMock(return_value=stale_uid_cache_user),
        cache_user_data_by_user_id=AsyncMock(return_value=True),
        cache_user_data=AsyncMock(return_value=True),
    )
    fetch_user_by_id = AsyncMock(return_value=canonical_user)

    user_data = await user_cache_shared.get_or_cache_user_data(
        redis_cache=redis_cache,
        user_id=canonical_user_id,
        firebase_uid=firebase_uid,
        fetch_user_by_id=fetch_user_by_id,
        fetch_user_by_uid=AsyncMock(
            side_effect=AssertionError("firebase_uid DB fallback should stay quarantined when user_id exists")
        ),
    )

    assert user_data["id"] == canonical_user_id
    assert user_data["email"] == canonical_user.email
    redis_cache.get_user_by_uid.assert_not_called()
    fetch_user_by_id.assert_awaited_once_with(canonical_user_id)


@pytest.mark.asyncio
async def test_user_cache_shared_falls_back_to_firebase_uid_only_when_canonical_identity_is_absent():
    firebase_uid = "u" * 28
    cached_user = _canonical_user_data(firebase_uid=firebase_uid, email="compat.shared.uid@example.com")
    redis_cache = SimpleNamespace(
        get_user_by_uid=AsyncMock(return_value=cached_user),
        cache_user_data_by_user_id=AsyncMock(return_value=True),
        cache_user_data=AsyncMock(return_value=True),
    )

    user_data = await user_cache_shared.get_or_cache_user_data(
        redis_cache=redis_cache,
        user_id=None,
        firebase_uid=firebase_uid,
        fetch_user_by_id=AsyncMock(
            side_effect=AssertionError("Canonical DB lookup should not run without a canonical user_id")
        ),
        fetch_user_by_uid=AsyncMock(
            side_effect=AssertionError("firebase_uid cache hit should not require DB lookup")
        ),
    )

    assert user_data["firebase_uid"] == firebase_uid
    assert user_data["email"] == cached_user["email"]
    redis_cache.get_user_by_uid.assert_awaited_once_with(firebase_uid)
