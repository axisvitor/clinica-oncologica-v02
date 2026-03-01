"""
FirebaseUserSyncService unit tests.

Focuses on async Firebase Admin SDK calls, timeout behavior, and fallback claims.
"""

import time
from unittest.mock import Mock

import pytest

from app.services.firebase_user_sync_service import FirebaseUserSyncService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def user_sync_service(mocker):
    """Create FirebaseUserSyncService with mocked dependencies."""
    db = mocker.MagicMock()
    firebase_service = mocker.MagicMock()
    return FirebaseUserSyncService(db=db, firebase_service=firebase_service)


@pytest.fixture
def mock_firebase_auth(mocker):
    """Mock Firebase Admin SDK auth.get_user."""
    return mocker.patch("firebase_admin.auth.get_user")


@pytest.fixture
def mock_logger(mocker):
    """Mock logger for performance log verification."""
    return mocker.patch("app.services.firebase_user_sync_service.logger")


@pytest.fixture
def test_firebase_uid():
    """Sample Firebase UID (28 chars)."""
    return "uid_123456789012345678901234"


@pytest.fixture
def test_id_token_claims():
    """Sample ID token claims."""
    return {"custom_claims": {"role": "doctor"}}


# ============================================================================
# Tests
# ============================================================================

@pytest.mark.asyncio
async def test_fetch_fresh_claims_success(
    user_sync_service, mock_firebase_auth, test_firebase_uid
):
    """Fetch fresh claims successfully via Firebase Admin SDK."""
    mock_firebase_auth.return_value = Mock(custom_claims={"role": "doctor"})

    claims = await user_sync_service._extract_claims(
        test_firebase_uid, {}, {}, skip_admin_sdk=False
    )

    assert claims == {"role": "doctor"}
    mock_firebase_auth.assert_called_once_with(test_firebase_uid)


@pytest.mark.asyncio
async def test_fetch_fresh_claims_timeout(
    user_sync_service, mock_firebase_auth, test_firebase_uid
):
    """Timeout falls back to ID token claims without raising."""

    def slow_get_user(_firebase_uid):
        time.sleep(11)
        return Mock(custom_claims={"role": "doctor"})

    mock_firebase_auth.side_effect = slow_get_user
    id_token_claims = {"custom_claims": {"role": "admin"}}

    start_time = time.perf_counter()
    claims = await user_sync_service._extract_claims(
        test_firebase_uid, {}, id_token_claims, skip_admin_sdk=False
    )
    duration = time.perf_counter() - start_time

    assert claims == {"role": "admin"}
    assert duration >= user_sync_service._firebase_admin_sdk_timeout
    assert duration < user_sync_service._firebase_admin_sdk_timeout + 5


@pytest.mark.asyncio
async def test_fetch_fresh_claims_error(
    user_sync_service, mock_firebase_auth, mock_logger, test_firebase_uid
):
    """Errors fall back to ID token claims without propagating."""
    mock_firebase_auth.side_effect = Exception("Firebase error")
    id_token_claims = {"custom_claims": {"role": "doctor"}}

    claims = await user_sync_service._extract_claims(
        test_firebase_uid, {}, id_token_claims, skip_admin_sdk=False
    )

    assert claims == {"role": "doctor"}
    mock_logger.error.assert_called()


@pytest.mark.asyncio
async def test_fetch_fresh_claims_performance_logging(
    user_sync_service, mock_firebase_auth, mock_logger, test_firebase_uid
):
    """Performance logging includes duration and UID prefix."""
    mock_firebase_auth.return_value = Mock(custom_claims={"role": "doctor"})

    await user_sync_service._extract_claims(
        test_firebase_uid, {}, {}, skip_admin_sdk=False
    )

    info_messages = [call.args[0] for call in mock_logger.info.call_args_list]
    assert any(
        "Firebase Admin SDK call completed in" in message
        and test_firebase_uid[:8] in message
        for message in info_messages
    )
