"""
Comprehensive Unit Tests for Token Blacklisting System

This test suite provides comprehensive coverage of the Redis-based token
blacklisting system to ensure security and reliability.

Test Coverage:
- Token blacklisting operations
- Token validation and checking
- Bulk operations
- TTL and expiry handling
- Error handling and edge cases
- Performance and concurrency
- Security scenarios
- Integration with Redis

Author: Claude Code (Backend API Developer)
"""

import asyncio
import json
import pytest
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

import jwt
from freezegun import freeze_time

from app.core.token_blacklist import (
    TokenBlacklistManager,
    TokenBlacklistConfig,
    TokenMetadata,
    BlacklistStats,
    get_token_blacklist_manager,
    is_token_blacklisted,
    blacklist_token
)


# =============================================================================
# TEST FIXTURES AND HELPERS
# =============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = Mock()
    redis_mock.exists.return_value = False
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.pipeline.return_value = Mock()
    return redis_mock


@pytest.fixture
def blacklist_config():
    """Test configuration for token blacklisting."""
    return TokenBlacklistConfig(
        blacklist_prefix="test_blacklist",
        audit_prefix="test_audit",
        stats_prefix="test_stats",
        bulk_operation_size=10,
        hash_token_content=True,
        audit_token_operations=True
    )


@pytest.fixture
def blacklist_manager(mock_redis, blacklist_config):
    """Token blacklist manager with mocked Redis."""
    manager = TokenBlacklistManager(config=blacklist_config)
    manager.redis = mock_redis
    return manager


@pytest.fixture
def sample_jwt_token():
    """Sample JWT token for testing."""
    payload = {
        "sub": "user123",
        "jti": "token123",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,  # 1 hour from now
        "type": "access"
    }
    # Create token without signature verification for testing
    return jwt.encode(payload, "secret", algorithm="HS256")


@pytest.fixture
def expired_jwt_token():
    """Expired JWT token for testing."""
    payload = {
        "sub": "user123",
        "jti": "expired123",
        "iat": int(time.time()) - 7200,  # 2 hours ago
        "exp": int(time.time()) - 3600,  # 1 hour ago
        "type": "access"
    }
    return jwt.encode(payload, "secret", algorithm="HS256")


@pytest.fixture
def refresh_jwt_token():
    """Refresh JWT token for testing."""
    payload = {
        "sub": "user123",
        "jti": "refresh123",
        "iat": int(time.time()),
        "exp": int(time.time()) + (30 * 24 * 3600),  # 30 days from now
        "type": "refresh"
    }
    return jwt.encode(payload, "secret", algorithm="HS256")


# =============================================================================
# TOKEN BLACKLISTING TESTS
# =============================================================================

class TestTokenBlacklistManager:
    """Test suite for TokenBlacklistManager class."""

    def test_initialization(self, blacklist_config):
        """Test manager initialization."""
        with patch('app.core.token_blacklist.get_redis_client') as mock_get_redis:
            mock_redis = Mock()
            mock_get_redis.return_value = mock_redis

            manager = TokenBlacklistManager(config=blacklist_config)

            assert manager.config == blacklist_config
            assert manager.redis == mock_redis
            mock_get_redis.assert_called_once()

    def test_hash_token(self, blacklist_manager):
        """Test token hashing functionality."""
        token = "test.jwt.token"

        # Test with hashing enabled
        blacklist_manager.config.hash_token_content = True
        hashed = blacklist_manager._hash_token(token)
        assert hashed != token
        assert len(hashed) == 64  # SHA-256 hex length

        # Test with hashing disabled
        blacklist_manager.config.hash_token_content = False
        unhashed = blacklist_manager._hash_token(token)
        assert unhashed == token

    def test_parse_token_claims(self, blacklist_manager, sample_jwt_token):
        """Test JWT token claims parsing."""
        claims = blacklist_manager._parse_token_claims(sample_jwt_token)

        assert claims is not None
        assert "sub" in claims
        assert "jti" in claims
        assert "exp" in claims
        assert claims["sub"] == "user123"

    def test_parse_invalid_token_claims(self, blacklist_manager):
        """Test parsing invalid token claims."""
        invalid_token = "invalid.jwt.token"
        claims = blacklist_manager._parse_token_claims(invalid_token)

        assert claims is None

    def test_get_token_ttl(self, blacklist_manager, sample_jwt_token, expired_jwt_token):
        """Test TTL calculation for tokens."""
        # Test valid token
        ttl = blacklist_manager._get_token_ttl(sample_jwt_token)
        assert ttl is not None
        assert ttl > 0
        assert ttl <= 3600  # Should be close to 1 hour

        # Test expired token
        expired_ttl = blacklist_manager._get_token_ttl(expired_jwt_token)
        assert expired_ttl == 1  # Minimum TTL

    def test_blacklist_token_success(self, blacklist_manager, mock_redis, sample_jwt_token):
        """Test successful token blacklisting."""
        mock_redis.exists.return_value = False  # Token not already blacklisted

        result = blacklist_manager.blacklist_token(
            token=sample_jwt_token,
            reason="test_logout",
            user_id="user123"
        )

        assert result is True
        mock_redis.setex.assert_called_once()

        # Verify the call arguments
        call_args = mock_redis.setex.call_args
        assert call_args[0][0].startswith("test_blacklist:")  # Key prefix
        assert call_args[0][1] > 0  # TTL > 0

        # Verify metadata in stored value
        stored_data = json.loads(call_args[0][2])
        assert stored_data["user_id"] == "user123"
        assert stored_data["reason"] == "test_logout"
        assert stored_data["token_type"] == "access"

    def test_blacklist_token_already_blacklisted(self, blacklist_manager, mock_redis, sample_jwt_token):
        """Test blacklisting already blacklisted token."""
        mock_redis.exists.return_value = True  # Token already blacklisted

        result = blacklist_manager.blacklist_token(token=sample_jwt_token)

        assert result is True
        mock_redis.setex.assert_not_called()

    def test_blacklist_expired_token(self, blacklist_manager, mock_redis, expired_jwt_token):
        """Test blacklisting expired token."""
        mock_redis.exists.return_value = False

        result = blacklist_manager.blacklist_token(token=expired_jwt_token)

        assert result is True
        # Should not store expired tokens
        mock_redis.setex.assert_not_called()

    def test_blacklist_invalid_token(self, blacklist_manager, mock_redis):
        """Test blacklisting invalid token."""
        invalid_token = "invalid.jwt.token"

        result = blacklist_manager.blacklist_token(token=invalid_token)

        assert result is False
        mock_redis.setex.assert_not_called()

    def test_is_blacklisted_true(self, blacklist_manager, mock_redis, sample_jwt_token):
        """Test checking blacklisted token."""
        mock_redis.exists.return_value = True

        result = blacklist_manager.is_blacklisted(sample_jwt_token)

        assert result is True
        mock_redis.exists.assert_called_once()

    def test_is_blacklisted_false(self, blacklist_manager, mock_redis, sample_jwt_token):
        """Test checking non-blacklisted token."""
        mock_redis.exists.return_value = False

        result = blacklist_manager.is_blacklisted(sample_jwt_token)

        assert result is False
        mock_redis.exists.assert_called_once()

    def test_is_blacklisted_redis_error(self, blacklist_manager, mock_redis, sample_jwt_token):
        """Test blacklist check with Redis error."""
        mock_redis.exists.side_effect = Exception("Redis connection error")

        # Should fail secure (assume blacklisted)
        result = blacklist_manager.is_blacklisted(sample_jwt_token)

        assert result is True

    def test_get_token_metadata(self, blacklist_manager, mock_redis, sample_jwt_token):
        """Test retrieving token metadata."""
        # Mock metadata storage
        metadata = {
            "token_id": "token123",
            "user_id": "user123",
            "token_type": "access",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "blacklisted_at": datetime.now(timezone.utc).isoformat(),
            "reason": "test_logout"
        }
        mock_redis.get.return_value = json.dumps(metadata)

        result = blacklist_manager.get_token_metadata(sample_jwt_token)

        assert result is not None
        assert result.token_id == "token123"
        assert result.user_id == "user123"
        assert result.reason == "test_logout"

    def test_get_token_metadata_not_found(self, blacklist_manager, mock_redis, sample_jwt_token):
        """Test retrieving metadata for non-blacklisted token."""
        mock_redis.get.return_value = None

        result = blacklist_manager.get_token_metadata(sample_jwt_token)

        assert result is None


# =============================================================================
# BULK OPERATIONS TESTS
# =============================================================================

class TestBulkOperations:
    """Test suite for bulk token operations."""

    def test_blacklist_tokens_bulk_success(self, blacklist_manager, mock_redis):
        """Test successful bulk token blacklisting."""
        # Create sample tokens
        tokens_data = []
        for i in range(3):
            payload = {
                "sub": f"user{i}",
                "jti": f"token{i}",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
                "type": "access"
            }
            token = jwt.encode(payload, "secret", algorithm="HS256")
            tokens_data.append({
                "token": token,
                "reason": "bulk_test",
                "user_id": f"user{i}"
            })

        # Mock pipeline
        mock_pipeline = Mock()
        mock_redis.pipeline.return_value = mock_pipeline

        result = blacklist_manager.blacklist_tokens_bulk(tokens_data)

        assert len(result) == 3
        assert all(success for success in result.values())
        mock_pipeline.execute.assert_called()

    def test_blacklist_tokens_bulk_mixed_results(self, blacklist_manager, mock_redis):
        """Test bulk blacklisting with mixed success/failure."""
        # Create mix of valid and invalid tokens
        tokens_data = [
            {
                "token": jwt.encode({
                    "sub": "user1",
                    "jti": "token1",
                    "iat": int(time.time()),
                    "exp": int(time.time()) + 3600
                }, "secret", algorithm="HS256"),
                "reason": "bulk_test"
            },
            {
                "token": "invalid.token",
                "reason": "bulk_test"
            }
        ]

        mock_pipeline = Mock()
        mock_redis.pipeline.return_value = mock_pipeline

        result = blacklist_manager.blacklist_tokens_bulk(tokens_data)

        assert len(result) == 2
        # First token should succeed, second should fail
        results_list = list(result.values())
        assert results_list[0] is True
        assert results_list[1] is False

    def test_blacklist_tokens_bulk_empty(self, blacklist_manager):
        """Test bulk blacklisting with empty list."""
        result = blacklist_manager.blacklist_tokens_bulk([])

        assert result == {}

    def test_revoke_user_tokens_not_implemented(self, blacklist_manager):
        """Test user token revocation (not implemented)."""
        result = blacklist_manager.revoke_user_tokens("user123")

        # Should return 0 as it's not implemented
        assert result == 0


# =============================================================================
# STATISTICS AND MONITORING TESTS
# =============================================================================

class TestStatisticsAndMonitoring:
    """Test suite for statistics and monitoring functionality."""

    def test_get_blacklist_stats_with_data(self, blacklist_manager, mock_redis):
        """Test retrieving blacklist statistics."""
        stats_data = {
            "total_blacklisted": 10,
            "blacklisted_today": 3,
            "access_tokens": 8,
            "refresh_tokens": 2,
            "reason_counts": {"logout": 5, "revoked": 3, "expired": 2},
            "cleanup_runs": 2,
            "last_cleanup": None
        }
        mock_redis.get.return_value = json.dumps(stats_data)

        stats = blacklist_manager.get_blacklist_stats()

        assert stats.total_blacklisted == 10
        assert stats.blacklisted_today == 3
        assert stats.access_tokens == 8
        assert stats.refresh_tokens == 2
        assert stats.reason_counts["logout"] == 5

    def test_get_blacklist_stats_no_data(self, blacklist_manager, mock_redis):
        """Test retrieving statistics when no data exists."""
        mock_redis.get.return_value = None

        stats = blacklist_manager.get_blacklist_stats()

        assert stats.total_blacklisted == 0
        assert stats.blacklisted_today == 0
        assert stats.access_tokens == 0
        assert stats.refresh_tokens == 0
        assert stats.reason_counts == {}

    def test_health_check_success(self, blacklist_manager, mock_redis):
        """Test successful health check."""
        # Mock successful Redis operations
        mock_redis.setex.return_value = True
        mock_redis.get.return_value = "test_value"
        mock_redis.delete.return_value = 1

        # Mock stats
        stats_data = {"total_blacklisted": 5, "blacklisted_today": 1}
        mock_redis.get.side_effect = ["test_value", json.dumps(stats_data)]

        health = blacklist_manager.health_check()

        assert health["healthy"] is True
        assert health["redis_connection"] is True
        assert health["total_blacklisted"] == 5

    def test_health_check_failure(self, blacklist_manager, mock_redis):
        """Test health check with Redis failure."""
        mock_redis.setex.side_effect = Exception("Redis error")

        health = blacklist_manager.health_check()

        assert health["healthy"] is False
        assert "error" in health

    def test_cleanup_expired_tokens(self, blacklist_manager):
        """Test cleanup of expired tokens."""
        # With Redis TTL, this should return 0
        result = blacklist_manager.cleanup_expired_tokens()

        assert result == 0


# =============================================================================
# CONFIGURATION AND EDGE CASES TESTS
# =============================================================================

class TestConfigurationAndEdgeCases:
    """Test suite for configuration and edge cases."""

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = TokenBlacklistConfig()
        assert config.bulk_operation_size >= 10
        assert config.redis_pipeline_size >= 10

        # Test with custom values
        custom_config = TokenBlacklistConfig(
            blacklist_prefix="custom_prefix",
            bulk_operation_size=50,
            hash_token_content=False
        )
        assert custom_config.blacklist_prefix == "custom_prefix"
        assert custom_config.bulk_operation_size == 50
        assert custom_config.hash_token_content is False

    def test_token_metadata_model(self):
        """Test TokenMetadata model."""
        now = datetime.now(timezone.utc)
        metadata = TokenMetadata(
            token_id="test123",
            user_id="user123",
            token_type="access",
            issued_at=now,
            expires_at=now + timedelta(hours=1),
            blacklisted_at=now,
            reason="test"
        )

        assert metadata.token_id == "test123"
        assert metadata.user_id == "user123"
        assert metadata.token_type == "access"
        assert metadata.reason == "test"

    def test_blacklist_stats_model(self):
        """Test BlacklistStats model."""
        stats = BlacklistStats(
            total_blacklisted=10,
            access_tokens=8,
            refresh_tokens=2
        )

        assert stats.total_blacklisted == 10
        assert stats.access_tokens == 8
        assert stats.refresh_tokens == 2
        assert stats.blacklisted_today == 0  # Default value

    @freeze_time("2024-01-01 12:00:00")
    def test_token_with_specific_time(self, blacklist_manager):
        """Test token operations with frozen time."""
        # Create token with specific expiry
        payload = {
            "sub": "user123",
            "jti": "token123",
            "iat": int(time.time()),
            "exp": int(time.time()) + 1800,  # 30 minutes
            "type": "access"
        }
        token = jwt.encode(payload, "secret", algorithm="HS256")

        ttl = blacklist_manager._get_token_ttl(token)
        assert ttl == 1800  # Should be exactly 30 minutes

    def test_redis_key_generation(self, blacklist_manager):
        """Test Redis key generation."""
        token_hash = "abcd1234"

        blacklist_key = blacklist_manager._create_blacklist_key(token_hash)
        audit_key = blacklist_manager._create_audit_key("audit123")

        assert blacklist_key.startswith("test_blacklist:")
        assert blacklist_key.endswith(token_hash)
        assert audit_key.startswith("test_audit:")
        assert audit_key.endswith("audit123")


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for the complete blacklisting system."""

    def test_full_blacklist_workflow(self, blacklist_manager, mock_redis, sample_jwt_token):
        """Test complete blacklist workflow."""
        # Mock Redis responses
        mock_redis.exists.return_value = False
        mock_redis.get.return_value = None

        # 1. Blacklist token
        result = blacklist_manager.blacklist_token(
            token=sample_jwt_token,
            reason="integration_test",
            user_id="user123"
        )
        assert result is True

        # 2. Check if blacklisted
        mock_redis.exists.return_value = True
        is_blacklisted = blacklist_manager.is_blacklisted(sample_jwt_token)
        assert is_blacklisted is True

        # 3. Get metadata
        metadata = {
            "token_id": "token123",
            "user_id": "user123",
            "reason": "integration_test"
        }
        mock_redis.get.return_value = json.dumps(metadata)
        token_metadata = blacklist_manager.get_token_metadata(sample_jwt_token)
        assert token_metadata is not None
        assert token_metadata.reason == "integration_test"


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================

class TestUtilityFunctions:
    """Test suite for utility functions."""

    @patch('app.core.token_blacklist.get_token_blacklist_manager')
    def test_is_token_blacklisted_function(self, mock_get_manager):
        """Test is_token_blacklisted utility function."""
        mock_manager = Mock()
        mock_manager.is_blacklisted.return_value = True
        mock_get_manager.return_value = mock_manager

        result = is_token_blacklisted("test.token")

        assert result is True
        mock_manager.is_blacklisted.assert_called_once_with("test.token")

    @patch('app.core.token_blacklist.get_token_blacklist_manager')
    def test_blacklist_token_function(self, mock_get_manager):
        """Test blacklist_token utility function."""
        mock_manager = Mock()
        mock_manager.blacklist_token.return_value = True
        mock_get_manager.return_value = mock_manager

        result = blacklist_token("test.token", reason="test", user_id="user123")

        assert result is True
        mock_manager.blacklist_token.assert_called_once_with(
            "test.token", "test", "user123"
        )

    @patch('app.core.token_blacklist.TokenBlacklistManager')
    def test_get_token_blacklist_manager(self, mock_manager_class):
        """Test get_token_blacklist_manager function."""
        # Reset global instance
        import app.core.token_blacklist
        app.core.token_blacklist._token_blacklist_manager = None

        mock_instance = Mock()
        mock_manager_class.return_value = mock_instance

        # First call should create instance
        manager1 = get_token_blacklist_manager()
        assert manager1 == mock_instance
        mock_manager_class.assert_called_once()

        # Second call should return same instance
        mock_manager_class.reset_mock()
        manager2 = get_token_blacklist_manager()
        assert manager2 == mock_instance
        mock_manager_class.assert_not_called()


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Performance tests for the blacklisting system."""

    def test_bulk_operation_performance(self, blacklist_manager, mock_redis):
        """Test performance of bulk operations."""
        # Create large number of tokens
        tokens_data = []
        for i in range(100):
            payload = {
                "sub": f"user{i}",
                "jti": f"token{i}",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600
            }
            token = jwt.encode(payload, "secret", algorithm="HS256")
            tokens_data.append({
                "token": token,
                "reason": "performance_test"
            })

        mock_pipeline = Mock()
        mock_redis.pipeline.return_value = mock_pipeline

        start_time = time.time()
        result = blacklist_manager.blacklist_tokens_bulk(tokens_data)
        end_time = time.time()

        # Should complete in reasonable time
        assert end_time - start_time < 1.0  # Less than 1 second
        assert len(result) == 100

    def test_hash_performance(self, blacklist_manager):
        """Test token hashing performance."""
        token = "test.jwt.token" * 100  # Large token

        start_time = time.time()
        for _ in range(1000):
            blacklist_manager._hash_token(token)
        end_time = time.time()

        # Should be fast
        assert end_time - start_time < 1.0  # Less than 1 second for 1000 hashes


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test suite for error handling scenarios."""

    def test_redis_connection_error_handling(self, blacklist_manager, mock_redis):
        """Test handling of Redis connection errors."""
        mock_redis.setex.side_effect = Exception("Connection lost")

        # Should handle gracefully
        result = blacklist_manager.blacklist_token("test.token")
        assert result is False

    def test_invalid_json_in_redis(self, blacklist_manager, mock_redis):
        """Test handling of invalid JSON data in Redis."""
        mock_redis.get.return_value = "invalid json data"

        # Should handle gracefully
        result = blacklist_manager.get_token_metadata("test.token")
        assert result is None

    def test_corrupted_stats_data(self, blacklist_manager, mock_redis):
        """Test handling of corrupted statistics data."""
        mock_redis.get.return_value = "corrupted stats"

        # Should return default stats
        stats = blacklist_manager.get_blacklist_stats()
        assert isinstance(stats, BlacklistStats)
        assert stats.total_blacklisted == 0


# =============================================================================
# CONCURRENCY TESTS
# =============================================================================

class TestConcurrency:
    """Test suite for concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_blacklist_operations(self, blacklist_manager, mock_redis):
        """Test concurrent blacklisting operations."""
        mock_redis.exists.return_value = False

        async def blacklist_operation(token_suffix):
            payload = {
                "sub": f"user{token_suffix}",
                "jti": f"token{token_suffix}",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600
            }
            token = jwt.encode(payload, "secret", algorithm="HS256")
            return blacklist_manager.blacklist_token(token)

        # Run multiple operations concurrently
        tasks = [blacklist_operation(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(results)
        assert len(results) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])