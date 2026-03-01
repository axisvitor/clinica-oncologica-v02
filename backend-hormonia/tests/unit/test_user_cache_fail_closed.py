from unittest.mock import MagicMock, patch

from app.utils.user_cache import check_password_change_rate_limit


def test_password_change_rate_limit_fails_closed_when_redis_unavailable():
    with patch("app.utils.user_cache.get_sync_redis", return_value=None), patch(
        "app.utils.user_cache.logger"
    ) as mock_logger:
        is_allowed = check_password_change_rate_limit("firebase-user-1")

    assert is_allowed is False
    assert mock_logger.error.called
    assert "fail-closed" in mock_logger.error.call_args.args[0]


def test_password_change_rate_limit_fails_closed_on_backend_error():
    redis_client = MagicMock()
    redis_client.get.side_effect = RuntimeError("redis read timeout")

    with patch(
        "app.utils.user_cache.get_sync_redis", return_value=redis_client
    ), patch("app.utils.user_cache.logger") as mock_logger:
        is_allowed = check_password_change_rate_limit("firebase-user-2")

    assert is_allowed is False
    assert mock_logger.error.called
    assert "fail-closed" in mock_logger.error.call_args.args[0]


def test_password_change_rate_limit_still_allows_when_below_limit():
    redis_client = MagicMock()
    redis_client.get.return_value = "1"

    with patch("app.utils.user_cache.get_sync_redis", return_value=redis_client):
        is_allowed = check_password_change_rate_limit("firebase-user-3", max_attempts=3)

    assert is_allowed is True
    redis_client.incr.assert_called_once_with("password_change_attempts:firebase-user-3")
