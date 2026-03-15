from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.user_sync_log import FirebaseSyncHistory
from app.services.firebase_user_sync_service import FirebaseUserSyncService


class _AppendOnlyAsyncSession:
    def __init__(self, *, commit_side_effect=None):
        self.added: list[FirebaseSyncHistory] = []
        self.execute = AsyncMock(
            side_effect=AssertionError(
                "append_only_history_write unexpected_query_before_append=true"
            )
        )
        self.commit = AsyncMock(side_effect=commit_side_effect)
        self.rollback = AsyncMock()

    def add(self, value):
        self.added.append(value)


@pytest.fixture
def firebase_sync_history_service(monkeypatch):
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

    db = _AppendOnlyAsyncSession()
    service = FirebaseUserSyncService(db=db, firebase_service=SimpleNamespace())
    return service, db


@pytest.mark.asyncio
async def test_append_only_history_write_records_explicit_firebase_history(
    firebase_sync_history_service,
):
    service, db = firebase_sync_history_service
    canonical_user_id = uuid4()

    await service._append_firebase_sync_history(
        firebase_uid="masked-firebase-uid-append-1",
        user_id=canonical_user_id,
        operation="link",
        sync_direction="firebase_to_pg",
        changes={"source": "link"},
        success=True,
    )
    await service._append_firebase_sync_history(
        firebase_uid="masked-firebase-uid-append-1",
        user_id=canonical_user_id,
        operation="update",
        sync_direction="firebase_to_pg",
        changes={"source": "update"},
        success=True,
    )

    assert len(db.added) == 2, "append_only_history_write appended_rows=2 expected=true"
    assert all(isinstance(entry, FirebaseSyncHistory) for entry in db.added), (
        "append_only_history_write explicit_history_surface=false"
    )
    assert [entry.operation for entry in db.added] == ["link", "update"], (
        "append_only_history_write operation_sequence_changed=true"
    )
    assert [entry.sync_direction for entry in db.added] == [
        "firebase_to_pg",
        "firebase_to_pg",
    ], "append_only_history_write sync_direction_changed=true"
    assert db.commit.await_count == 2, (
        "append_only_history_write commit_count_mismatch=true"
    )
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_append_only_history_write_rolls_back_without_breaking_sync(monkeypatch):
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

    db = _AppendOnlyAsyncSession(commit_side_effect=RuntimeError("commit failed"))
    service = FirebaseUserSyncService(db=db, firebase_service=SimpleNamespace())

    await service._append_firebase_sync_history(
        firebase_uid="masked-firebase-uid-failure-1",
        user_id=None,
        operation="sync",
        sync_direction="firebase_to_pg",
        changes={"source": "failure-path"},
        success=False,
        error_message="masked failure",
    )

    assert len(db.added) == 1, "append_only_history_write failure_path_dropped_row=true"
    db.rollback.assert_awaited_once()
    db.execute.assert_not_called()
