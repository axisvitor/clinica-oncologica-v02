"""
Critical API Tests: Firebase Auth Session
Validates Firebase token verification and Redis session creation.
"""
import pytest
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.dependencies import auth_dependencies
from app.models.user import User, UserRole
from app.service_provider import ServiceProvider


class FakeFirebaseCache:
    def __init__(self, redis_client):
        self._cached_tokens = {}
        self._cached_users = {}

    def get_cached_token(self, token):
        return None

    def cache_validated_token(self, token, data):
        self._cached_tokens[token] = data

    def get_cached_user(self, firebase_uid):
        return None

    def cache_user(self, firebase_uid, user_dict):
        self._cached_users[firebase_uid] = user_dict


@pytest.mark.api
@pytest.mark.auth
@pytest.mark.integration
def test_firebase_verify_creates_session(real_client: TestClient, real_session_id: str):
    """Verify Firebase token exchange creates a valid session."""
    response = real_client.get(
        "/api/v2/auth/verify-session",
        headers={"Authorization": f"Bearer {real_session_id}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data.get("session_id")
    assert data.get("user")


@pytest.mark.api
@pytest.mark.auth
@pytest.mark.integration
def test_real_session_allows_patients_list(real_authenticated_client: TestClient):
    """Ensure real session grants access to protected endpoints."""
    response = real_authenticated_client.get("/api/v2/patients/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_token_with_admin_custom_claim_sets_admin_role(db_session, monkeypatch):
    firebase_uid = "firebaseuid12345678901234567"
    token_value = "token_admin_claim"
    user_data = {
        "uid": firebase_uid,
        "email": "admin_claim@example.com",
        "name": "Admin Claim",
        "custom_claims": {"role": "admin"},
    }

    firebase_service = AsyncMock()
    firebase_service.verify_token.return_value = user_data
    monkeypatch.setattr(auth_dependencies, "_firebase_service", firebase_service)
    monkeypatch.setattr(auth_dependencies, "_get_user_from_db_sync", lambda uid, db: None)

    from app.core import redis_manager as redis_manager_module
    monkeypatch.setattr(
        redis_manager_module,
        "get_redis_manager",
        lambda: MagicMock(get_compatible_client=lambda mode: MagicMock()),
    )
    monkeypatch.setattr(redis_manager_module, "FirebaseRedisCache", FakeFirebaseCache)

    request = SimpleNamespace(state=SimpleNamespace())
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_value)
    services = ServiceProvider(db_session, redis_client=None)

    user = await auth_dependencies.get_current_user(
        request=request,
        credentials=credentials,
        services=services,
    )

    assert user.role == UserRole.ADMIN
    db_user = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    assert db_user is not None
    assert db_user.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_token_with_doctor_custom_claim_sets_doctor_role(db_session, monkeypatch):
    firebase_uid = "firebaseuid12345678901234568"
    token_value = "token_doctor_claim"
    user_data = {
        "uid": firebase_uid,
        "email": "doctor_claim@example.com",
        "name": "Doctor Claim",
        "custom_claims": {"role": "doctor"},
    }

    firebase_service = AsyncMock()
    firebase_service.verify_token.return_value = user_data
    monkeypatch.setattr(auth_dependencies, "_firebase_service", firebase_service)
    monkeypatch.setattr(auth_dependencies, "_get_user_from_db_sync", lambda uid, db: None)

    from app.core import redis_manager as redis_manager_module
    monkeypatch.setattr(
        redis_manager_module,
        "get_redis_manager",
        lambda: MagicMock(get_compatible_client=lambda mode: MagicMock()),
    )
    monkeypatch.setattr(redis_manager_module, "FirebaseRedisCache", FakeFirebaseCache)

    request = SimpleNamespace(state=SimpleNamespace())
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_value)
    services = ServiceProvider(db_session, redis_client=None)

    user = await auth_dependencies.get_current_user(
        request=request,
        credentials=credentials,
        services=services,
    )

    assert user.role == UserRole.DOCTOR
    db_user = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    assert db_user is not None
    assert db_user.role == UserRole.DOCTOR


@pytest.mark.asyncio
async def test_token_without_custom_claims_defaults_to_doctor(db_session, monkeypatch):
    firebase_uid = "firebaseuid12345678901234569"
    token_value = "token_no_claims"
    user_data = {
        "uid": firebase_uid,
        "email": "default_role@example.com",
        "name": "Default Role",
        "custom_claims": {},
    }

    firebase_service = AsyncMock()
    firebase_service.verify_token.return_value = user_data
    monkeypatch.setattr(auth_dependencies, "_firebase_service", firebase_service)
    monkeypatch.setattr(auth_dependencies, "_get_user_from_db_sync", lambda uid, db: None)

    from app.core import redis_manager as redis_manager_module
    monkeypatch.setattr(
        redis_manager_module,
        "get_redis_manager",
        lambda: MagicMock(get_compatible_client=lambda mode: MagicMock()),
    )
    monkeypatch.setattr(redis_manager_module, "FirebaseRedisCache", FakeFirebaseCache)

    request = SimpleNamespace(state=SimpleNamespace())
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_value)
    services = ServiceProvider(db_session, redis_client=None)

    user = await auth_dependencies.get_current_user(
        request=request,
        credentials=credentials,
        services=services,
    )

    assert user.role == UserRole.DOCTOR
    db_user = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    assert db_user is not None
    assert db_user.role == UserRole.DOCTOR
