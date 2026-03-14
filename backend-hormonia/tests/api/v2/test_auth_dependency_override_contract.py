"""Override-sensitive contract tests for planned auth dependency splits."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import Request

from app.api.v2.routers.admin import dependencies as admin_dependencies
from app.api.v2.routers.roles import dependencies as roles_dependencies
from app.dependencies import auth_dependencies
from app.models.user import User, UserRole


pytestmark = [pytest.mark.api, pytest.mark.auth]


def _import_split_module(module_name: str):
    return importlib.import_module(f"app.dependencies.{module_name}")


def _build_request(*, session_id: str = "admin-session-contract") -> Request:
    request = MagicMock(spec=Request)
    request.headers = {"X-Session-ID": session_id}
    request.cookies = {"session_id": session_id}
    request.state = SimpleNamespace()
    request.app = SimpleNamespace(dependency_overrides={})
    return request


def _session_admin_payload(admin_user: User) -> dict:
    return {
        "id": str(admin_user.id),
        "email": admin_user.email,
        "full_name": admin_user.full_name,
        "role": "admin",
        "is_active": True,
    }


@pytest.mark.asyncio
async def test_admin_router_dependency_accepts_narrower_override_signatures():
    admin_user = User(
        id=uuid4(),
        email="admin.override@example.com",
        full_name="Admin Override",
        role=UserRole.ADMIN,
        is_active=True,
    )
    session_payload = _session_admin_payload(admin_user)
    request = _build_request()

    async def _session_override(request: Request):
<<<<<<< HEAD
        request.state.session_id = "admin-session-contract"
=======
>>>>>>> gsd/M003/S02
        request.state.user_id = session_payload["id"]
        request.state.user_role = session_payload["role"]
        return session_payload

    async def _user_object_override(user_data: dict):
        assert user_data["id"] == session_payload["id"]
        return admin_user

    request.app.dependency_overrides = {
        admin_dependencies.get_current_user_from_session: _session_override,
        admin_dependencies.get_current_user_object_from_session: _user_object_override,
    }

    result = await admin_dependencies.get_admin_user(
        request=request,
        db=AsyncMock(),
        redis_cache=object(),
    )

    assert result is admin_user
<<<<<<< HEAD
    assert request.state.session_id == "admin-session-contract"
=======
>>>>>>> gsd/M003/S02
    assert request.state.user_id == session_payload["id"]
    assert request.state.user_role == session_payload["role"]


@pytest.mark.asyncio
<<<<<<< HEAD
async def test_session_contract_sets_request_state_for_mapping_style_payloads():
    auth_session_contract = _import_split_module("auth_session_contract")
    admin_user = User(
        id=uuid4(),
        email="admin.session.contract@example.com",
        full_name="Admin Session Contract",
        role=UserRole.ADMIN,
        is_active=True,
    )
    request = _build_request(session_id="canonical-state-session")
    redis_cache = SimpleNamespace(
        get_session=AsyncMock(
            return_value={
                "user_id": str(admin_user.id),
                "email": admin_user.email,
                "full_name": admin_user.full_name,
                "role": "admin",
                "is_active": True,
            }
        ),
        update_session_activity=AsyncMock(return_value=None),
        get_user_by_id=AsyncMock(
            side_effect=AssertionError("Embedded canonical session should not require user_id cache lookup")
        ),
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError("Embedded canonical session should not require firebase_uid cache lookup")
        ),
    )

    user_data = await auth_session_contract.resolve_authenticated_session_user(
        request=request,
        session_cookie_id="canonical-state-session",
        x_session_id=None,
        authorization=None,
        redis_cache=redis_cache,
        get_permissions_for_role=lambda role: [f"{role}.read"],
        validate_firebase_uid=lambda firebase_uid: (_ for _ in ()).throw(
            AssertionError(f"firebase_uid fallback should not run (got {firebase_uid!r})")
        ),
        load_user_from_db_by_user_id=AsyncMock(
            side_effect=AssertionError("Embedded canonical session should not require DB lookup")
        ),
        load_user_from_db_by_firebase_uid=AsyncMock(
            side_effect=AssertionError("Embedded canonical session should not require firebase DB lookup")
        ),
        load_user_from_db_by_session=AsyncMock(
            side_effect=AssertionError("Embedded canonical session should not require session fallback lookup")
        ),
        serialize_user=lambda user: user,
    )

    assert user_data["id"] == str(admin_user.id)
    assert user_data["role"] == "admin"
    assert user_data["permissions"] == ["admin.read"]
    assert request.state.session_id == "canonical-state-session"
    assert request.state.user_id == str(admin_user.id)
    assert request.state.user_role == "admin"
    redis_cache.get_user_by_id.assert_not_called()
    redis_cache.get_user_by_uid.assert_not_called()


@pytest.mark.asyncio
=======
>>>>>>> gsd/M003/S02
async def test_roles_admin_dependency_accepts_canonical_user_id_without_firebase_uid():
    admin_user = User(
        id=uuid4(),
        email="admin.roles@example.com",
        full_name="Admin Roles",
        role=UserRole.ADMIN,
        is_active=True,
    )
    current_user = {
        "id": str(admin_user.id),
        "role": "admin",
        "email": admin_user.email,
        "full_name": admin_user.full_name,
        "is_active": True,
        # Intentionally omitted: firebase_uid should be compatibility-only here.
    }

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: admin_user)
    )

    result = await roles_dependencies.get_admin_user(current_user=current_user, db=db)

    assert result is admin_user
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_current_active_admin_delegates_to_split_role_dependency(
    monkeypatch: pytest.MonkeyPatch,
):
    auth_role_dependencies = _import_split_module("auth_role_dependencies")
    current_user = {
        "id": str(uuid4()),
        "role": "admin",
        "email": "delegated.admin@example.com",
        "is_active": True,
    }
    expected_admin = current_user | {"permissions": ["admin.read"]}
    checker = AsyncMock(return_value=expected_admin)
    monkeypatch.setattr(
        auth_role_dependencies,
        "require_admin_session_user",
        checker,
    )

    result = await auth_dependencies.get_current_active_admin(current_user=current_user)

    assert result is expected_admin
    checker.assert_awaited_once_with(current_user)


@pytest.mark.asyncio
async def test_auth_role_dependencies_require_admin_session_user_rejects_non_admin():
    auth_role_dependencies = _import_split_module("auth_role_dependencies")

    with pytest.raises(Exception) as exc_info:
        await auth_role_dependencies.require_admin_session_user(
            {
                "id": str(uuid4()),
                "role": "doctor",
                "email": "doctor.not.admin@example.com",
                "is_active": True,
            }
        )

    status_code = getattr(exc_info.value, "status_code", None)
    assert status_code == 403
