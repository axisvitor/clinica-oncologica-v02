"""
Session Role Enforcement Tests

Validates that session-based authentication respects stored user roles.
"""

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from unittest.mock import AsyncMock
from uuid import uuid4

from app.dependencies.auth_dependencies import (
    get_admin_user,
    get_current_user_from_session,
    get_permissions_for_role,
)
from app.models.user import User, UserRole


def _make_request() -> Request:
    return Request({"type": "http", "headers": []})


def _make_user_data(firebase_uid: str, role: str) -> dict:
    return {
        "id": str(uuid4()),
        "firebase_uid": firebase_uid,
        "email": f"{role}@example.com",
        "full_name": f"{role.title()} User",
        "role": role,
        "is_active": True,
    }


@pytest.mark.asyncio
async def test_session_admin_permissions():
    firebase_uid = "firebaseuid12345678901234567"
    request = _make_request()
    redis_cache = AsyncMock()
    redis_cache.get_session.return_value = {"firebase_uid": firebase_uid}
    redis_cache.update_session_activity.return_value = None
    redis_cache.get_user_by_uid.return_value = _make_user_data(firebase_uid, "admin")

    user_data = await get_current_user_from_session(
        request,
        session_cookie_id=None,
        authorization=None,
        x_session_id="session_admin",
        redis_cache=redis_cache,
    )

    assert user_data["role"] == "admin"
    assert "admin.read" in user_data["permissions"]
    assert user_data["permissions"] == get_permissions_for_role("admin")


@pytest.mark.asyncio
async def test_session_doctor_permissions():
    firebase_uid = "firebaseuid12345678901234568"
    request = _make_request()
    redis_cache = AsyncMock()
    redis_cache.get_session.return_value = {"firebase_uid": firebase_uid}
    redis_cache.update_session_activity.return_value = None
    redis_cache.get_user_by_uid.return_value = _make_user_data(firebase_uid, "doctor")

    user_data = await get_current_user_from_session(
        request,
        session_cookie_id=None,
        authorization=None,
        x_session_id="session_doctor",
        redis_cache=redis_cache,
    )

    assert user_data["role"] == "doctor"
    assert "admin.read" not in user_data["permissions"]
    assert user_data["permissions"] == get_permissions_for_role("doctor")


@pytest.mark.asyncio
async def test_session_doctor_cannot_access_admin_endpoint():
    session_user = _make_user_data("firebaseuid12345678901234569", "doctor")
    doctor_user = User(
        id=uuid4(),
        email=session_user["email"],
        full_name=session_user["full_name"],
        role=UserRole.DOCTOR,
        is_active=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_admin_user(current_user=doctor_user)

    assert exc_info.value.status_code == 403
