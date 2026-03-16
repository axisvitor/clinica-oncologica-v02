from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.models.user import UserRole
from app.services.firebase_user_sync_service import FirebaseUserSyncService


class _FakeExecuteResult:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _QueueAsyncSession:
    def __init__(self, responses=None):
        self._responses = list(responses or [])
        self.execute = AsyncMock(side_effect=self._execute)
        self.commit = AsyncMock()
        self.refresh = AsyncMock()
        self.rollback = AsyncMock()
        self.add = Mock()
        self.query = Mock(side_effect=AssertionError("sync db.query should not be used"))

    async def _execute(self, *args, **kwargs):
        if not self._responses:
            raise AssertionError("Unexpected execute call with no queued response")
        return self._responses.pop(0)


@pytest.fixture
def firebase_sync_service(monkeypatch):
    monkeypatch.setattr(
        "app.services.firebase_user_sync_service.get_firebase_security_config",
        lambda: {
            "allowed_domains": ["hospital.org"],
            "block_public_domains": True,
            "public_domains_blocklist": ["gmail.com", "yahoo.com"],
            "require_custom_claims": True,
            "allowed_roles": ["admin", "doctor"],
            "enable_audit_logging": False,
        },
    )
    monkeypatch.setattr(
        "app.services.firebase_user_sync_service.get_settings",
        lambda: SimpleNamespace(FIREBASE_ADMIN_SDK_TIMEOUT=1),
    )
    monkeypatch.setattr(
        "app.services.firebase_user_sync_service._get_redis_client",
        AsyncMock(return_value=None),
    )

    db = _QueueAsyncSession()
    service = FirebaseUserSyncService(db=db, firebase_service=SimpleNamespace())
    return service, db


@pytest.mark.asyncio
async def test_sync_firebase_user_create_flow_uses_async_execute(firebase_sync_service):
    service, db = firebase_sync_service
    db._responses = [_FakeExecuteResult(None), _FakeExecuteResult(None)]
    created_user = SimpleNamespace(id=uuid4(), email="doctor@hospital.org", is_active=True)
    service._create_user_from_firebase = AsyncMock(return_value=created_user)

    user, created = await service.sync_firebase_user(
        "uid-create",
        {
            "email": "doctor@hospital.org",
            "custom_claims": {"role": "doctor"},
            "email_verified": True,
        },
        auto_create=True,
    )

    assert created is True
    assert user is created_user
    assert db.execute.await_count == 2
    db.query.assert_not_called()


@pytest.mark.asyncio
async def test_update_user_from_firebase_commits_async(firebase_sync_service):
    service, db = firebase_sync_service
    user = SimpleNamespace(
        id=uuid4(),
        email="old@hospital.org",
        full_name="Old Name",
        firebase_display_name="Old Name",
        firebase_email_verified=False,
        firebase_photo_url=None,
        firebase_custom_claims={"role": "doctor"},
        role=UserRole.DOCTOR,
        firebase_uid="uid-update",
    )

    changed = await service._update_user_from_firebase(
        user,
        {
            "email": "new@hospital.org",
            "name": "New Name",
            "email_verified": True,
            "picture": "http://pic",
            "custom_claims": {"role": "admin"},
        },
        cached_claims={"role": "admin"},
    )

    assert changed is True
    assert user.email == "new@hospital.org"
    assert user.role == UserRole.ADMIN
    db.commit.assert_awaited_once()
    db.query.assert_not_called()


@pytest.mark.asyncio
async def test_link_firebase_to_user_commits_async(firebase_sync_service):
    service, db = firebase_sync_service
    user = SimpleNamespace(email="doctor@hospital.org", firebase_uid=None)

    linked = await service._link_firebase_to_user(
        user,
        "uid-link",
        {
            "name": "Doctor",
            "email_verified": True,
            "picture": "http://photo",
            "auth_time": None,
            "custom_claims": {"role": "doctor"},
        },
    )

    assert linked is True
    assert user.firebase_uid == "uid-link"
    db.commit.assert_awaited_once()
    db.query.assert_not_called()


@pytest.mark.asyncio
async def test_validate_firebase_user_uses_async_execute(firebase_sync_service):
    service, db = firebase_sync_service
    user = SimpleNamespace(firebase_uid="uid-validate", is_active=True, role=UserRole.ADMIN)
    db._responses = [_FakeExecuteResult(user)]

    validated = await service.validate_firebase_user("uid-validate", required_role=UserRole.ADMIN)

    assert validated is user
    db.execute.assert_awaited_once()
    db.query.assert_not_called()



