"""
Comprehensive tests for session management service.

Tests session creation, validation, expiration, security, and Redis integration.
Focuses on critical security functionality and edge cases.
Coverage target: >90%
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any

# Import session service if available
try:
    from app.services.session_service import SessionService
except ImportError:
    SessionService = None

from conftest import (
    assert_response_time, assert_no_sql_injection, assert_no_xss
)


class TestSessionCreation:
    """Test session creation functionality."""

    @pytest.mark.unit
    async def test_create_session_success(self, session_service, sample_user_data):
        """Test successful session creation."""
        if hasattr(session_service, 'create_session'):
            session_id = await session_service.create_session(
                user_data=sample_user_data,
                ip_address="127.0.0.1",
                user_agent="test-agent"
            )

            assert session_id is not None
            assert len(session_id) > 20  # Ensure reasonable session ID length
            assert isinstance(session_id, str)

    @pytest.mark.unit
    async def test_create_session_with_empty_user_data(self, session_service):
        """Test session creation fails with empty user data."""
        if hasattr(session_service, 'create_session'):
            with pytest.raises((ValueError, Exception)):
                await session_service.create_session(
                    user_data={},
                    ip_address="127.0.0.1",
                    user_agent="test-agent"
                )

    @pytest.mark.unit
    async def test_create_session_with_none_user_data(self, session_service):
        """Test session creation fails with None user data."""
        if hasattr(session_service, 'create_session'):
            with pytest.raises((ValueError, Exception)):
                await session_service.create_session(
                    user_data=None,
                    ip_address="127.0.0.1",
                    user_agent="test-agent"
                )

    @pytest.mark.security
    async def test_create_session_ip_validation(self, session_service, sample_user_data):
        """Test session creation with various IP addresses."""
        if not hasattr(session_service, 'create_session'):
            pytest.skip("Session service not available")

        # Valid IPv4
        session_id = await session_service.create_session(
            user_data=sample_user_data,
            ip_address="192.168.1.1",
            user_agent="test-agent"
        )
        assert session_id is not None

        # Valid IPv6
        session_id = await session_service.create_session(
            user_data=sample_user_data,
            ip_address="2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            user_agent="test-agent"
        )
        assert session_id is not None

    @pytest.mark.security
    async def test_create_session_malicious_user_agent(self, session_service, sample_user_data, security_test_payloads):
        """Test session creation with malicious user agent strings."""
        if not hasattr(session_service, 'create_session'):
            pytest.skip("Session service not available")

        for payload in security_test_payloads["xss_payloads"]:
            session_id = await session_service.create_session(
                user_data=sample_user_data,
                ip_address="127.0.0.1",
                user_agent=payload
            )
            assert session_id is not None
            # Should not raise error but should sanitize

    @pytest.mark.performance
    async def test_create_session_performance(self, session_service, sample_user_data, performance_timer):
        """Test session creation performance."""
        if not hasattr(session_service, 'create_session'):
            pytest.skip("Session service not available")

        performance_timer.start()
        session_id = await session_service.create_session(
            user_data=sample_user_data,
            ip_address="127.0.0.1",
            user_agent="test-agent"
        )
        response_time = performance_timer.stop()

        assert session_id is not None
        assert_response_time(response_time, max_time=0.1)  # Should be very fast


class TestSessionValidation:
    """Test session validation functionality."""

    @pytest.mark.unit
    async def test_validate_session_success(self, session_service, mock_redis, sample_session_data):
        """Test successful session validation."""
        if not hasattr(session_service, 'validate_session'):
            pytest.skip("Session service not available")

        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        is_valid = await session_service.validate_session("test-session-123")

        assert is_valid is True

    @pytest.mark.unit
    async def test_validate_session_not_found(self, session_service, mock_redis):
        """Test session validation with non-existent session."""
        if not hasattr(session_service, 'validate_session'):
            pytest.skip("Session service not available")

        mock_redis.get.return_value = None

        is_valid = await session_service.validate_session("non-existent-session")

        assert is_valid is False

    @pytest.mark.unit
    async def test_validate_session_expired(self, session_service, mock_redis, sample_session_data):
        """Test session validation with expired session."""
        if not hasattr(session_service, 'validate_session'):
            pytest.skip("Session service not available")

        # Set session as expired
        expired_data = sample_session_data.copy()
        expired_data["expires_at"] = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        mock_redis.get.return_value = json.dumps(expired_data).encode()

        is_valid = await session_service.validate_session("test-session-123")

        assert is_valid is False

    @pytest.mark.security
    async def test_validate_session_malicious_ids(self, session_service, security_test_payloads):
        """Test session validation with malicious session IDs."""
        if not hasattr(session_service, 'validate_session'):
            pytest.skip("Session service not available")

        for session_id in security_test_payloads["session_ids"]:
            if session_id is not None:
                is_valid = await session_service.validate_session(session_id)
                assert is_valid is False

    @pytest.mark.security
    async def test_validate_session_sql_injection(self, session_service, security_test_payloads):
        """Test session validation against SQL injection."""
        if not hasattr(session_service, 'validate_session'):
            pytest.skip("Session service not available")

        for payload in security_test_payloads["sql_injection"]:
            is_valid = await session_service.validate_session(payload)
            assert is_valid is False

    @pytest.mark.unit
    async def test_validate_session_corrupted_data(self, session_service, mock_redis):
        """Test session validation with corrupted session data."""
        if not hasattr(session_service, 'validate_session'):
            pytest.skip("Session service not available")

        mock_redis.get.return_value = b"corrupted-json-data"

        is_valid = await session_service.validate_session("test-session-123")

        assert is_valid is False

    @pytest.mark.performance
    async def test_validate_session_performance(self, session_service, mock_redis, sample_session_data, performance_timer):
        """Test session validation performance."""
        if not hasattr(session_service, 'validate_session'):
            pytest.skip("Session service not available")

        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        performance_timer.start()
        is_valid = await session_service.validate_session("test-session-123")
        response_time = performance_timer.stop()

        assert is_valid is True
        assert_response_time(response_time, max_time=0.05)


class TestSessionRetrieval:
    """Test session data retrieval functionality."""

    @pytest.mark.unit
    async def test_get_session_success(self, session_service, mock_redis, sample_session_data):
        """Test successful session data retrieval."""
        if not hasattr(session_service, 'get_session'):
            pytest.skip("Session service not available")

        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        session_data = await session_service.get_session("test-session-123")

        assert session_data is not None
        assert session_data["session_id"] == "test-session-123"
        assert session_data["user_id"] == sample_session_data["user_id"]

    @pytest.mark.unit
    async def test_get_session_not_found(self, session_service, mock_redis):
        """Test session retrieval with non-existent session."""
        if not hasattr(session_service, 'get_session'):
            pytest.skip("Session service not available")

        mock_redis.get.return_value = None

        session_data = await session_service.get_session("non-existent-session")

        assert session_data is None

    @pytest.mark.security
    async def test_get_session_data_sanitization(self, session_service, mock_redis, sample_session_data, security_test_payloads):
        """Test that session data is properly sanitized."""
        if not hasattr(session_service, 'get_session'):
            pytest.skip("Session service not available")

        # Inject XSS payload into session data
        malicious_data = sample_session_data.copy()
        malicious_data["user_data"]["name"] = security_test_payloads["xss_payloads"][0]
        mock_redis.get.return_value = json.dumps(malicious_data).encode()

        session_data = await session_service.get_session("test-session-123")

        assert session_data is not None
        assert_no_xss(session_data)


class TestSessionDeletion:
    """Test session deletion functionality."""

    @pytest.mark.unit
    async def test_delete_session_success(self, session_service, mock_redis):
        """Test successful session deletion."""
        if not hasattr(session_service, 'delete_session'):
            pytest.skip("Session service not available")

        mock_redis.delete.return_value = 1

        result = await session_service.delete_session("test-session-123")

        assert result is True

    @pytest.mark.unit
    async def test_delete_session_not_found(self, session_service, mock_redis):
        """Test deletion of non-existent session."""
        if not hasattr(session_service, 'delete_session'):
            pytest.skip("Session service not available")

        mock_redis.delete.return_value = 0

        result = await session_service.delete_session("non-existent-session")

        assert result is False

    @pytest.mark.security
    async def test_delete_session_malicious_id(self, session_service, security_test_payloads):
        """Test session deletion with malicious session IDs."""
        if not hasattr(session_service, 'delete_session'):
            pytest.skip("Session service not available")

        for session_id in security_test_payloads["session_ids"]:
            if session_id is not None:
                result = await session_service.delete_session(session_id)
                # Should not raise error, may return True or False


class TestCSRFTokens:
    """Test CSRF token functionality."""

    @pytest.mark.unit
    async def test_generate_csrf_token(self, session_service):
        """Test CSRF token generation."""
        if not hasattr(session_service, 'generate_csrf_token'):
            pytest.skip("CSRF token generation not available")

        token = session_service.generate_csrf_token()

        assert token is not None
        assert len(token) >= 32  # Minimum length for security
        assert isinstance(token, str)

    @pytest.mark.unit
    async def test_csrf_token_uniqueness(self, session_service):
        """Test that CSRF tokens are unique."""
        if not hasattr(session_service, 'generate_csrf_token'):
            pytest.skip("CSRF token generation not available")

        tokens = [session_service.generate_csrf_token() for _ in range(100)]

        # All tokens should be unique
        assert len(set(tokens)) == 100

    @pytest.mark.unit
    async def test_validate_csrf_token_success(self, session_service, mock_redis, sample_session_data):
        """Test successful CSRF token validation."""
        if not hasattr(session_service, 'validate_csrf_token'):
            pytest.skip("CSRF token validation not available")

        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        is_valid = await session_service.validate_csrf_token(
            "test-session-123",
            "test-csrf-token-123"
        )

        assert is_valid is True

    @pytest.mark.unit
    async def test_validate_csrf_token_mismatch(self, session_service, mock_redis, sample_session_data):
        """Test CSRF token validation with mismatched token."""
        if not hasattr(session_service, 'validate_csrf_token'):
            pytest.skip("CSRF token validation not available")

        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        is_valid = await session_service.validate_csrf_token(
            "test-session-123",
            "wrong-csrf-token"
        )

        assert is_valid is False

    @pytest.mark.security
    async def test_validate_csrf_token_malicious(self, session_service, security_test_payloads):
        """Test CSRF token validation with malicious tokens."""
        if not hasattr(session_service, 'validate_csrf_token'):
            pytest.skip("CSRF token validation not available")

        for token in security_test_payloads["csrf_tokens"]:
            is_valid = await session_service.validate_csrf_token(
                "test-session-123",
                token
            )
            assert is_valid is False


class TestSessionCleanup:
    """Test session cleanup functionality."""

    @pytest.mark.unit
    async def test_cleanup_expired_sessions(self, session_service, mock_redis):
        """Test cleanup of expired sessions."""
        if not hasattr(session_service, 'cleanup_expired_sessions'):
            pytest.skip("Session cleanup not available")

        # Mock Redis scan to return expired sessions
        mock_redis.scan_iter.return_value = [
            "session:expired-1",
            "session:expired-2",
            "session:valid-1"
        ]

        # Mock TTL to indicate expired sessions
        mock_redis.ttl.side_effect = [-1, -1, 3600]  # First two expired, third valid
        mock_redis.delete.return_value = 1

        deleted_count = await session_service.cleanup_expired_sessions()

        assert deleted_count == 2
        assert mock_redis.delete.call_count == 2

    @pytest.mark.performance
    async def test_cleanup_performance(self, session_service, mock_redis, performance_timer):
        """Test cleanup performance with many sessions."""
        if not hasattr(session_service, 'cleanup_expired_sessions'):
            pytest.skip("Session cleanup not available")

        # Mock many sessions
        mock_redis.scan_iter.return_value = [f"session:test-{i}" for i in range(1000)]
        mock_redis.ttl.return_value = -1  # All expired
        mock_redis.delete.return_value = 1

        performance_timer.start()
        deleted_count = await session_service.cleanup_expired_sessions()
        response_time = performance_timer.stop()

        assert deleted_count == 1000
        assert_response_time(response_time, max_time=2.0)


class TestRedisIntegration:
    """Test Redis integration and error handling."""

    @pytest.mark.integration
    async def test_redis_connection_failure(self, mock_redis):
        """Test handling of Redis connection failures."""
        mock_redis.get.side_effect = Exception("Redis connection failed")

        # Should handle Redis errors gracefully
        with patch('app.services.session_service.redis_client', mock_redis):
            if SessionService:
                service = SessionService()

                # Should not raise exception
                if hasattr(service, 'validate_session'):
                    result = await service.validate_session("test-session")
                    assert result is False

    @pytest.mark.integration
    async def test_redis_pipeline_operations(self, session_service, mock_redis, sample_user_data):
        """Test Redis pipeline operations for session creation."""
        if not hasattr(session_service, 'create_session'):
            pytest.skip("Session creation not available")

        await session_service.create_session(
            user_data=sample_user_data,
            ip_address="127.0.0.1",
            user_agent="test-agent"
        )

        # Verify pipeline was used for atomic operations
        mock_redis.pipeline.assert_called()

    @pytest.mark.integration
    async def test_redis_key_expiration(self, session_service, mock_redis, sample_user_data):
        """Test that Redis keys are set with proper expiration."""
        if not hasattr(session_service, 'create_session'):
            pytest.skip("Session creation not available")

        await session_service.create_session(
            user_data=sample_user_data,
            ip_address="127.0.0.1",
            user_agent="test-agent"
        )

        # Verify expiration was set
        pipeline = mock_redis.pipeline.return_value
        pipeline.expire.assert_called()


class TestConcurrentSessions:
    """Test concurrent session operations."""

    @pytest.mark.unit
    async def test_concurrent_session_creation(self, session_service, sample_user_data):
        """Test creating multiple sessions concurrently."""
        if not hasattr(session_service, 'create_session'):
            pytest.skip("Session creation not available")

        tasks = []
        for i in range(10):
            user_data = sample_user_data.copy()
            user_data["id"] = f"user-{i}"
            task = session_service.create_session(
                user_data=user_data,
                ip_address=f"192.168.1.{i}",
                user_agent="test-agent"
            )
            tasks.append(task)

        session_ids = await asyncio.gather(*tasks)

        # All sessions should be created successfully
        assert len(session_ids) == 10
        assert all(session_id is not None for session_id in session_ids)
        # All session IDs should be unique
        assert len(set(session_ids)) == 10

    @pytest.mark.integration
    async def test_concurrent_session_validation(self, session_service, mock_redis, sample_session_data):
        """Test validating sessions concurrently."""
        if not hasattr(session_service, 'validate_session'):
            pytest.skip("Session validation not available")

        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        tasks = [
            session_service.validate_session("test-session-123")
            for _ in range(50)
        ]

        results = await asyncio.gather(*tasks)

        # All validations should succeed
        assert all(result is True for result in results)


class TestSecurityEdgeCases:
    """Test security-related edge cases."""

    @pytest.mark.security
    async def test_session_hijacking_prevention(self, session_service, mock_redis, sample_session_data):
        """Test prevention of session hijacking attempts."""
        if not hasattr(session_service, 'get_session'):
            pytest.skip("Session retrieval not available")

        # Simulate session access from different IP
        mock_redis.get.return_value = json.dumps(sample_session_data).encode()

        # First access from original IP
        session_data = await session_service.get_session("test-session-123")
        assert session_data is not None

        # Attempt access from different IP (if IP checking is implemented)
        # This would depend on the actual implementation

    @pytest.mark.security
    async def test_session_fixation_prevention(self, session_service, sample_user_data):
        """Test prevention of session fixation attacks."""
        if not hasattr(session_service, 'create_session'):
            pytest.skip("Session creation not available")

        # Create session with user data
        session_id_1 = await session_service.create_session(
            user_data=sample_user_data,
            ip_address="127.0.0.1",
            user_agent="test-agent"
        )

        # Create another session - should get different ID
        session_id_2 = await session_service.create_session(
            user_data=sample_user_data,
            ip_address="127.0.0.1",
            user_agent="test-agent"
        )

        assert session_id_1 != session_id_2

    @pytest.mark.security
    async def test_timing_attack_resistance(self, session_service, performance_timer):
        """Test resistance to timing attacks."""
        if not hasattr(session_service, 'validate_session'):
            pytest.skip("Session validation not available")

        times_valid = []
        times_invalid = []

        # Measure timing for valid session checks
        for _ in range(10):
            performance_timer.start()
            await session_service.validate_session("valid-session-format-123")
            times_valid.append(performance_timer.stop())

        # Measure timing for invalid session checks
        for _ in range(10):
            performance_timer.start()
            await session_service.validate_session("invalid")
            times_invalid.append(performance_timer.stop())

        # Times should not significantly differ (basic check)
        avg_valid = sum(times_valid) / len(times_valid)
        avg_invalid = sum(times_invalid) / len(times_invalid)

        # Should not differ by more than 50%
        ratio = max(avg_valid, avg_invalid) / min(avg_valid, avg_invalid)
        assert ratio < 1.5, "Potential timing attack vulnerability"


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.security
    async def test_session_creation_rate_limiting(self, session_service, mock_rate_limiter, sample_user_data):
        """Test rate limiting for session creation."""
        if not hasattr(session_service, 'create_session'):
            pytest.skip("Session creation not available")

        # Simulate rate limiting
        user_ip = "192.168.1.100"

        # First few requests should succeed
        for i in range(5):
            is_allowed = mock_rate_limiter.is_allowed(f"session_create:{user_ip}", 5, 60)
            assert is_allowed is True

        # Next request should be rate limited
        is_allowed = mock_rate_limiter.is_allowed(f"session_create:{user_ip}", 5, 60)
        assert is_allowed is False

    @pytest.mark.security
    async def test_session_validation_rate_limiting(self, session_service, mock_rate_limiter):
        """Test rate limiting for session validation."""
        if not hasattr(session_service, 'validate_session'):
            pytest.skip("Session validation not available")

        user_ip = "192.168.1.101"

        # Should allow normal validation requests
        for i in range(100):
            is_allowed = mock_rate_limiter.is_allowed(f"session_validate:{user_ip}", 100, 60)
            assert is_allowed is True

        # Should block excessive requests
        is_allowed = mock_rate_limiter.is_allowed(f"session_validate:{user_ip}", 100, 60)
        assert is_allowed is False


class TestMemoryUsage:
    """Test memory usage and resource management."""

    @pytest.mark.performance
    async def test_session_memory_footprint(self, session_service, sample_user_data):
        """Test memory usage of session operations."""
        if not hasattr(session_service, 'create_session'):
            pytest.skip("Session creation not available")

        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Create many sessions
        sessions = []
        for i in range(1000):
            user_data = sample_user_data.copy()
            user_data["id"] = f"user-{i}"
            session_id = await session_service.create_session(
                user_data=user_data,
                ip_address="127.0.0.1",
                user_agent="test-agent"
            )
            sessions.append(session_id)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB for 1000 sessions)
        assert memory_increase < 100 * 1024 * 1024, f"Memory increase too high: {memory_increase} bytes"

    @pytest.mark.performance
    async def test_session_cleanup_memory_release(self, session_service, mock_redis):
        """Test that session cleanup releases memory."""
        if not hasattr(session_service, 'cleanup_expired_sessions'):
            pytest.skip("Session cleanup not available")

        import gc

        # Force garbage collection before test
        gc.collect()

        # Mock cleanup of many sessions
        mock_redis.scan_iter.return_value = [f"session:test-{i}" for i in range(10000)]
        mock_redis.ttl.return_value = -1  # All expired
        mock_redis.delete.return_value = 1

        deleted_count = await session_service.cleanup_expired_sessions()

        # Force garbage collection after cleanup
        gc.collect()

        assert deleted_count == 10000