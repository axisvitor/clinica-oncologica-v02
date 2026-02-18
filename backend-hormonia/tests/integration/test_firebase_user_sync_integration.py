"""
Integration tests for FirebaseUserSyncService async Admin SDK behavior.
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock

import pytest

from app.config import settings
from app.models.user import UserRole
from app.monitoring.prometheus_exporters import (
    firebase_admin_sdk_duration_seconds,
    firebase_admin_sdk_error_total,
    firebase_admin_sdk_timeout_total,
)
from app.services.firebase_user_sync_service import FirebaseUserSyncService


class _FalseyDict(dict):
    """Dict that evaluates to False for timeout fallback testing."""

    def __bool__(self):
        return False


def _histogram_count(metric) -> float:
    """Return histogram _count in a prometheus-client compatible way."""
    for family in metric.collect():
        for sample in family.samples:
            if sample.name.endswith("_count"):
                return float(sample.value)
    raise AssertionError("Histogram count sample not found")


@pytest.fixture
def firebase_security_settings(monkeypatch):
    """Ensure Firebase security settings allow test domains."""
    monkeypatch.setattr(settings, "FIREBASE_ALLOWED_DOMAINS", ["example.com"])
    monkeypatch.setattr(settings, "FIREBASE_ENABLE_REQUIRE_CUSTOM_CLAIMS", True)
    monkeypatch.setattr(settings, "FIREBASE_ENABLE_BLOCK_PUBLIC_DOMAINS", True)
    monkeypatch.setattr(settings, "FIREBASE_ALLOWED_ROLES", ["admin", "doctor", "medico"])
    yield


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sync_user_with_firebase_timeout(
    db_session, mocker, firebase_security_settings
):
    """Sync user succeeds with timeout fallback claims."""
    mocker.patch(
        "app.services.firebase_user_sync_service._get_redis_client",
        new=AsyncMock(return_value=None),
    )

    firebase_uid = "uid_timeout_123456789012345678"
    firebase_data = {
        "email": "timeout@example.com",
        "email_verified": True,
        "name": "Timeout User",
        "custom_claims": _FalseyDict({"role": "admin"}),
    }

    def slow_get_user(_firebase_uid):
        time.sleep(11)
        return Mock(custom_claims={"role": "admin"})

    mocker.patch("firebase_admin.auth.get_user", side_effect=slow_get_user)

    timeout_start = firebase_admin_sdk_timeout_total._value.get()
    service = FirebaseUserSyncService(
        db=db_session, firebase_service=mocker.MagicMock()
    )

    user, created = await service.sync_firebase_user(
        firebase_uid, firebase_data, auto_create=True
    )

    assert created is True
    assert user.role == UserRole.ADMIN
    # Current flow may trigger more than one timeout increment in fallback paths.
    assert firebase_admin_sdk_timeout_total._value.get() >= timeout_start + 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_requests_not_blocked(mocker):
    """Concurrent claim fetches complete quickly despite one slow call."""
    service = FirebaseUserSyncService(
        db=mocker.MagicMock(), firebase_service=mocker.MagicMock()
    )
    slow_uid = "uid_slow_12345678901234567890"
    fast_uids = [
        "uid_fast_12345678901234567890",
        "uid_fast_22345678901234567890",
    ]

    def get_user(firebase_uid):
        if firebase_uid == slow_uid:
            time.sleep(8)
        return Mock(custom_claims={"role": "doctor"})

    mocker.patch("firebase_admin.auth.get_user", side_effect=get_user)

    async def run_extract(uid):
        start_time = time.perf_counter()
        claims = await service._extract_claims(uid, {}, {}, skip_admin_sdk=False)
        return uid, time.perf_counter() - start_time, claims

    results = await asyncio.gather(
        run_extract(slow_uid),
        run_extract(fast_uids[0]),
        run_extract(fast_uids[1]),
    )

    fast_durations = [duration for uid, duration, _ in results if uid != slow_uid]
    assert all(duration < 2 for duration in fast_durations)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_metrics_recorded_correctly(mocker):
    """Histogram and counters update for success, timeout, and error."""
    service = FirebaseUserSyncService(
        db=mocker.MagicMock(), firebase_service=mocker.MagicMock()
    )

    duration_start = _histogram_count(firebase_admin_sdk_duration_seconds)
    timeout_start = firebase_admin_sdk_timeout_total._value.get()
    error_counter = firebase_admin_sdk_error_total.labels(error_type="general")
    error_start = error_counter._value.get()

    mock_firebase_auth = mocker.patch("firebase_admin.auth.get_user")

    mock_firebase_auth.side_effect = None
    mock_firebase_auth.return_value = Mock(custom_claims={"role": "doctor"})
    await service._extract_claims("uid_metrics_success_1234567890", {}, {}, False)

    def slow_get_user(_firebase_uid):
        time.sleep(11)
        return Mock(custom_claims={"role": "doctor"})

    mock_firebase_auth.side_effect = slow_get_user
    await service._extract_claims(
        "uid_metrics_timeout_1234567890",
        {},
        {"custom_claims": {"role": "doctor"}},
        False,
    )

    mock_firebase_auth.side_effect = Exception("Firebase error")
    await service._extract_claims(
        "uid_metrics_error_1234567890",
        {},
        {"custom_claims": {"role": "doctor"}},
        False,
    )

    assert _histogram_count(firebase_admin_sdk_duration_seconds) == duration_start + 3
    assert firebase_admin_sdk_timeout_total._value.get() >= timeout_start + 1
    assert error_counter._value.get() == error_start + 1
