"""Split-contract tests for the planned auth dependency modules."""

from __future__ import annotations

import importlib
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

from app.config import settings
from app.dependencies import auth_dependencies
from app.models.user import User, UserRole


pytestmark = [pytest.mark.unit, pytest.mark.auth]


def _import_split_module(module_name: str):
    return importlib.import_module(f"app.dependencies.{module_name}")


def _build_request(session_id: str = "cookie-session") -> Request:
    request = MagicMock(spec=Request)
    request.cookies = {settings.SESSION_COOKIE_NAME: session_id}
    request.headers = {}
    request.state = SimpleNamespace()
    return request


def _canonical_session_payload(*, user_id: str | None = None, role: str = "doctor") -> dict:
    resolved_user_id = user_id or str(uuid4())
    return {
        "session_id": "cookie-session",
        "user_id": resolved_user_id,
        "email": "split.contract@example.com",
        "full_name": "Dra. Split Contract",
        "role": role,
        "is_active": True,
        "created_at": "2026-03-11T12:00:00-03:00",
        "updated_at": "2026-03-11T12:00:00-03:00",
        "last_login": "2026-03-11T12:30:00-03:00",
    }


@pytest.mark.parametrize(
    ("cookie_priority", "expected_session_id", "expected_source"),
    [
        (True, "cookie-session", "cookie"),
        (False, "bearer-session", "authorization"),
    ],
)
def test_auth_session_contract_resolves_request_session_id_with_explicit_precedence(
    monkeypatch: pytest.MonkeyPatch,
    cookie_priority: bool,
    expected_session_id: str,
    expected_source: str,
):
    monkeypatch.setattr(settings, "ENABLE_COOKIE_PRIORITY", cookie_priority)

    auth_session_contract = _import_split_module("auth_session_contract")

    final_session_id, session_source = auth_session_contract.resolve_request_session_id(
        session_cookie_id="cookie-session",
        x_session_id="header-session",
        authorization="Bearer bearer-session",
    )

    assert final_session_id == expected_session_id
    assert session_source == expected_source


def test_auth_session_contract_extracts_canonical_embedded_user_without_firebase_uid():
    auth_session_contract = _import_split_module("auth_session_contract")
    session_payload = _canonical_session_payload()

    user_data = auth_session_contract.session_payload_to_user_data(session_payload)

    assert user_data == {
        "id": session_payload["user_id"],
        "firebase_uid": None,
        "email": session_payload["email"],
        "full_name": session_payload["full_name"],
        "role": session_payload["role"],
        "is_active": True,
        "created_at": session_payload["created_at"],
        "updated_at": session_payload["updated_at"],
        "last_login": session_payload["last_login"],
        "photo_url": None,
    }


@pytest.mark.asyncio
async def test_auth_session_cache_hydrates_canonical_and_compat_identity_keys():
    auth_session_cache = _import_split_module("auth_session_cache")
    user_data = {
        **_canonical_session_payload(),
        "id": str(uuid4()),
        "firebase_uid": "firebaseuid12345678901234567",
        "photo_url": "https://example.com/photo.png",
    }
    user_data.pop("user_id", None)

    redis_cache = AsyncMock()
    redis_cache.cache_user_data_by_user_id = AsyncMock(return_value=True)
    redis_cache.cache_user_data = AsyncMock(return_value=True)
    redis_cache.create_session = AsyncMock(return_value=True)

    await auth_session_cache.cache_user_data_by_identity(redis_cache, user_data, ttl=900)
    await auth_session_cache.rehydrate_session_cache(
        redis_cache,
        session_id="session-contract-123",
        user_data=user_data,
        session_ttl=86400,
    )

    redis_cache.cache_user_data_by_user_id.assert_awaited_once_with(
        user_data["id"], user_data, ttl=900
    )
    redis_cache.cache_user_data.assert_awaited_once_with(
        user_data["firebase_uid"], user_data, ttl=900
    )
    redis_cache.create_session.assert_awaited_once()
    create_call = redis_cache.create_session.await_args
    assert create_call.kwargs["session_id"] == "session-contract-123"
    assert create_call.kwargs["user_id"] == user_data["id"]
    assert create_call.kwargs["firebase_uid"] == user_data["firebase_uid"]
    assert create_call.kwargs["metadata"]["session_id"] == "session-contract-123"
    assert create_call.kwargs["metadata"]["email"] == user_data["email"]
    assert create_call.kwargs["metadata"]["full_name"] == user_data["full_name"]
    assert create_call.kwargs["metadata"]["max_age_seconds"] == 86400


def test_auth_user_adapter_converts_canonical_session_payload_to_user_model():
    auth_user_adapter = _import_split_module("auth_user_adapter")
    session_user_id = str(uuid4())
    session_payload = {
        **_canonical_session_payload(user_id=session_user_id, role="ADMIN"),
        "cached_at": "2026-03-11T12:31:00-03:00",
        "unexpected_claim": "ignore-me",
    }

    user = auth_user_adapter.session_user_data_to_user(session_payload)

    assert isinstance(user, User)
    assert str(user.id) == session_user_id
    assert user.email == session_payload["email"]
    assert user.full_name == session_payload["full_name"]
    assert user.role == UserRole.ADMIN
    assert isinstance(user.created_at, datetime)
    assert isinstance(user.updated_at, datetime)
    assert isinstance(user.firebase_last_sign_in, datetime)
    assert not hasattr(user, "unexpected_claim")
    assert not hasattr(user, "cached_at")


@pytest.mark.asyncio
async def test_get_current_user_object_from_session_delegates_to_auth_user_adapter(
    monkeypatch: pytest.MonkeyPatch,
):
    auth_user_adapter = _import_split_module("auth_user_adapter")
    expected_user = User(
        id=uuid4(),
        email="delegated.adapter@example.com",
        full_name="Delegated Adapter",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    adapter = MagicMock(return_value=expected_user)
    monkeypatch.setattr(auth_user_adapter, "session_user_data_to_user", adapter)

    user_data = _canonical_session_payload()
    result = await auth_dependencies.get_current_user_object_from_session(user_data=user_data)

    assert result is expected_user
    adapter.assert_called_once()
    delegated_user_data = adapter.call_args.args[0]
    assert delegated_user_data["user_id"] == user_data["user_id"]
    assert delegated_user_data["email"] == user_data["email"]


@pytest.mark.asyncio
async def test_get_current_user_from_session_delegates_to_split_session_contract(
    monkeypatch: pytest.MonkeyPatch,
):
    auth_session_contract = _import_split_module("auth_session_contract")
    request = _build_request()
    redis_cache = AsyncMock()
    expected_user_data = {
        "id": str(uuid4()),
        "email": "delegated.session@example.com",
        "full_name": "Delegated Session",
        "role": "doctor",
        "is_active": True,
        "permissions": ["patients.read"],
    }
    resolver = AsyncMock(return_value=expected_user_data)
    monkeypatch.setattr(
        auth_session_contract,
        "resolve_authenticated_session_user",
        resolver,
    )

    result = await auth_dependencies.get_current_user_from_session(
        request=request,
        session_cookie_id="cookie-session",
        x_session_id=None,
        authorization=None,
        redis_cache=redis_cache,
    )

    assert result is expected_user_data
    resolver.assert_awaited_once()
    assert resolver.await_args.kwargs["request"] is request
    assert resolver.await_args.kwargs["session_cookie_id"] == "cookie-session"
    assert resolver.await_args.kwargs["x_session_id"] is None
    assert resolver.await_args.kwargs["authorization"] is None
    assert resolver.await_args.kwargs["redis_cache"] is redis_cache


@pytest.mark.asyncio
async def test_verify_firebase_token_delegates_to_auth_legacy_firebase(
    monkeypatch: pytest.MonkeyPatch,
):
    auth_legacy_firebase = _import_split_module("auth_legacy_firebase")
    firebase_service = object()
    expected_user_data = {"uid": "firebaseuid12345678901234567"}
    verifier = AsyncMock(return_value=expected_user_data)
    monkeypatch.setattr(auth_legacy_firebase, "verify_firebase_token", verifier)
    monkeypatch.setattr(auth_dependencies, "_firebase_service", firebase_service)

    result = await auth_dependencies.verify_firebase_token("firebase-token")

    assert result is expected_user_data
    verifier.assert_awaited_once_with(
        "firebase-token",
        firebase_service=firebase_service,
    )


@pytest.mark.asyncio
async def test_get_current_user_delegates_legacy_bearer_auth_to_split_module(
    monkeypatch: pytest.MonkeyPatch,
):
    auth_legacy_firebase = _import_split_module("auth_legacy_firebase")
    request = MagicMock(spec=Request)
    request.cookies = {}
    request.headers = {}
    request.state = SimpleNamespace()
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="legacy-bearer-token",
    )
    services = SimpleNamespace(db=MagicMock())
    firebase_service = object()
    expected_user = User(
        id=uuid4(),
        email="legacy.delegate@example.com",
        full_name="Legacy Delegate",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    authenticator = AsyncMock(return_value=expected_user)
    monkeypatch.setattr(
        auth_legacy_firebase,
        "authenticate_legacy_bearer_user",
        authenticator,
    )
    monkeypatch.setattr(auth_dependencies, "_firebase_service", firebase_service)

    result = await auth_dependencies.get_current_user(
        request=request,
        credentials=credentials,
        services=services,
    )

    assert result is expected_user
    authenticator.assert_awaited_once()
    assert authenticator.await_args.kwargs["request"] is request
    assert authenticator.await_args.kwargs["credentials"] is credentials
    assert authenticator.await_args.kwargs["services"] is services
    assert authenticator.await_args.kwargs["firebase_service"] is firebase_service
    assert authenticator.await_args.kwargs["validate_firebase_uid"] is auth_dependencies._validate_firebase_uid
    assert authenticator.await_args.kwargs["validate_email"] is auth_dependencies._validate_email
    assert authenticator.await_args.kwargs["resolve_user_role"] is auth_dependencies._resolve_user_role
    assert authenticator.await_args.kwargs["should_use_sync_db"] is auth_dependencies._should_use_sync_db
    assert authenticator.await_args.kwargs["get_user_from_db_sync"] is auth_dependencies._get_user_from_db_sync
    assert authenticator.await_args.kwargs["get_user_from_db_async"] is auth_dependencies._get_user_from_db_async
    assert authenticator.await_args.kwargs["serialize_user"] is auth_dependencies.user_to_cache_dict


@pytest.mark.asyncio
async def test_get_current_user_websocket_delegates_to_auth_legacy_firebase(
    monkeypatch: pytest.MonkeyPatch,
):
    auth_legacy_firebase = _import_split_module("auth_legacy_firebase")
    websocket = SimpleNamespace()
    services = SimpleNamespace(user_repository=MagicMock())
    firebase_service = object()
    expected_user = User(
        id=uuid4(),
        email="socket.delegate@example.com",
        full_name="Socket Delegate",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    resolver = AsyncMock(return_value=expected_user)
    monkeypatch.setattr(auth_legacy_firebase, "get_current_user_websocket", resolver)
    monkeypatch.setattr(auth_dependencies, "_firebase_service", firebase_service)

    result = await auth_dependencies.get_current_user_websocket(
        websocket=websocket,
        services=services,
    )

    assert result is expected_user
    resolver.assert_awaited_once_with(
        websocket,
        services=services,
        firebase_service=firebase_service,
    )


def test_resolve_user_role_delegates_to_auth_user_adapter(
    monkeypatch: pytest.MonkeyPatch,
):
    auth_user_adapter = _import_split_module("auth_user_adapter")
    resolver = MagicMock(return_value=UserRole.ADMIN)
    monkeypatch.setattr(auth_user_adapter, "resolve_user_role", resolver)

    result = auth_dependencies._resolve_user_role(
        firebase_custom_claims={"role": "admin"},
        db_role=UserRole.DOCTOR,
    )

    assert result == UserRole.ADMIN
    resolver.assert_called_once_with(
        firebase_custom_claims={"role": "admin"},
        db_role=UserRole.DOCTOR,
        default_role=UserRole.DOCTOR,
    )


def test_user_to_cache_dict_delegates_to_auth_user_adapter(
    monkeypatch: pytest.MonkeyPatch,
):
    auth_user_adapter = _import_split_module("auth_user_adapter")
    user = User(
        id=uuid4(),
        email="cache.delegate@example.com",
        full_name="Cache Delegate",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    expected_payload = {"id": str(user.id), "role": "doctor"}
    serializer = MagicMock(return_value=expected_payload)
    monkeypatch.setattr(auth_user_adapter, "user_to_cache_dict", serializer)

    result = auth_dependencies.user_to_cache_dict(user)

    assert result is expected_payload
    serializer.assert_called_once_with(user)


@pytest.mark.asyncio
async def test_get_current_active_user_delegates_to_split_role_dependency(
    monkeypatch: pytest.MonkeyPatch,
):
    auth_role_dependencies = _import_split_module("auth_role_dependencies")
    user = User(
        id=uuid4(),
        email="active.delegate@example.com",
        full_name="Active Delegate",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    checker = AsyncMock(return_value=user)
    monkeypatch.setattr(auth_role_dependencies, "require_active_user", checker)

    result = await auth_dependencies.get_current_active_user(current_user=user)

    assert result is user
    checker.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_get_admin_user_delegates_to_split_role_dependency(
    monkeypatch: pytest.MonkeyPatch,
):
    auth_role_dependencies = _import_split_module("auth_role_dependencies")
    admin_user = User(
        id=uuid4(),
        email="admin.delegate@example.com",
        full_name="Admin Delegate",
        role=UserRole.ADMIN,
        is_active=True,
    )
    checker = AsyncMock(return_value=admin_user)
    monkeypatch.setattr(auth_role_dependencies, "require_admin_user", checker)

    result = await auth_dependencies.get_admin_user(current_user=admin_user)

    assert result is admin_user
    checker.assert_awaited_once_with(admin_user)


@pytest.mark.asyncio
async def test_get_doctor_user_delegates_to_split_role_dependency(
    monkeypatch: pytest.MonkeyPatch,
):
    auth_role_dependencies = _import_split_module("auth_role_dependencies")
    doctor_user = User(
        id=uuid4(),
        email="doctor.delegate@example.com",
        full_name="Doctor Delegate",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    checker = AsyncMock(return_value=doctor_user)
    monkeypatch.setattr(auth_role_dependencies, "require_doctor_user", checker)

    result = await auth_dependencies.get_doctor_user(current_user=doctor_user)

    assert result is doctor_user
    checker.assert_awaited_once_with(doctor_user)
