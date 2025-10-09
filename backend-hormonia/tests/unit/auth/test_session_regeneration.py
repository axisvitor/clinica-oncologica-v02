"""
Tests for Session Regeneration Security

Verifies that session IDs are regenerated after authentication to prevent
session fixation attacks, and that session IDs have 256-bit entropy.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
import secrets
import base64

from app.routers.auth_session import generate_session_id, regenerate_session


class TestSessionIDGeneration:
    """Test cryptographically secure session ID generation."""

    def test_generate_session_id_returns_string(self):
        """Session ID should be a string."""
        session_id = generate_session_id()
        assert isinstance(session_id, str)

    def test_generate_session_id_has_256_bit_entropy(self):
        """Session ID should have 256 bits of entropy (32 bytes)."""
        session_id = generate_session_id()

        # secrets.token_urlsafe(32) generates 32 bytes = 256 bits
        # Base64 encoding: 32 bytes -> 43 characters (with padding removed)
        # URL-safe base64 uses: A-Z, a-z, 0-9, -, _ (64 chars)
        assert len(session_id) == 43, "Session ID should be 43 characters (256 bits)"

        # Verify it's URL-safe base64 (alphanumeric + - and _)
        allowed_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_')
        assert all(c in allowed_chars for c in session_id), "Session ID should be URL-safe"

    def test_generate_session_id_is_unpredictable(self):
        """Session IDs should be cryptographically random (no patterns)."""
        # Generate 100 session IDs
        session_ids = [generate_session_id() for _ in range(100)]

        # All should be unique
        assert len(set(session_ids)) == 100, "Session IDs should be unique"

        # No two should share the same prefix (first 8 chars)
        prefixes = [sid[:8] for sid in session_ids]
        assert len(set(prefixes)) == 100, "Session ID prefixes should be unique"

    def test_generate_session_id_entropy_calculation(self):
        """Verify session ID has exactly 256 bits of entropy."""
        session_id = generate_session_id()

        # Decode base64 to get raw bytes
        # Add padding if necessary
        padded = session_id + '=' * (4 - len(session_id) % 4)
        try:
            # Replace URL-safe characters
            standard_b64 = padded.replace('-', '+').replace('_', '/')
            decoded = base64.b64decode(standard_b64)

            # Should be exactly 32 bytes = 256 bits
            assert len(decoded) == 32, f"Session ID should decode to 32 bytes, got {len(decoded)}"
        except Exception as e:
            pytest.fail(f"Failed to decode session ID: {e}")

    def test_generate_session_id_uses_secrets_module(self):
        """Should use secrets module (not random) for cryptographic strength."""
        with patch('app.routers.auth_session.secrets.token_urlsafe') as mock_secrets:
            mock_secrets.return_value = 'test_session_id'

            session_id = generate_session_id()

            mock_secrets.assert_called_once_with(32)
            assert session_id == 'test_session_id'

    @pytest.mark.benchmark
    def test_generate_session_id_performance(self, benchmark):
        """Session ID generation should be fast (<1ms)."""
        result = benchmark(generate_session_id)
        assert isinstance(result, str)
        # Should complete in under 1ms
        assert benchmark.stats['mean'] < 0.001


class TestSessionRegeneration:
    """Test session regeneration after authentication."""

    @pytest.mark.asyncio
    async def test_regenerate_session_creates_new_id(self):
        """Should create a new session ID with 256-bit entropy."""
        mock_cache = AsyncMock()
        mock_cache.invalidate_session = AsyncMock(return_value=True)
        mock_cache.create_session = AsyncMock(return_value=True)

        old_session_id = "old_session_123"
        new_session_id = await regenerate_session(
            firebase_cache=mock_cache,
            old_session_id=old_session_id,
            user_id="user_123",
            firebase_uid="firebase_uid_123",
            metadata={"email": "test@example.com"}
        )

        # New session ID should be different
        assert new_session_id != old_session_id

        # New session ID should have 256-bit entropy (43 chars)
        assert len(new_session_id) == 43

        # Should invalidate old session
        mock_cache.invalidate_session.assert_called_once_with(old_session_id)

        # Should create new session
        mock_cache.create_session.assert_called_once()
        call_kwargs = mock_cache.create_session.call_args.kwargs
        assert call_kwargs['session_id'] == new_session_id
        assert call_kwargs['user_id'] == "user_123"
        assert call_kwargs['firebase_uid'] == "firebase_uid_123"

    @pytest.mark.asyncio
    async def test_regenerate_session_without_old_session(self):
        """Should create new session even if no old session exists."""
        mock_cache = AsyncMock()
        mock_cache.create_session = AsyncMock(return_value=True)

        new_session_id = await regenerate_session(
            firebase_cache=mock_cache,
            old_session_id=None,  # No old session
            user_id="user_123",
            firebase_uid="firebase_uid_123",
            metadata={"email": "test@example.com"}
        )

        # Should create new session
        assert len(new_session_id) == 43
        mock_cache.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_regenerate_session_handles_invalidation_failure(self):
        """Should continue if old session invalidation fails."""
        mock_cache = AsyncMock()
        mock_cache.invalidate_session = AsyncMock(side_effect=Exception("Redis error"))
        mock_cache.create_session = AsyncMock(return_value=True)

        # Should not raise exception
        new_session_id = await regenerate_session(
            firebase_cache=mock_cache,
            old_session_id="old_session_123",
            user_id="user_123",
            firebase_uid="firebase_uid_123",
            metadata={"email": "test@example.com"}
        )

        # Should still create new session
        assert len(new_session_id) == 43
        mock_cache.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_regenerate_session_raises_on_create_failure(self):
        """Should raise HTTPException if session creation fails."""
        mock_cache = AsyncMock()
        mock_cache.invalidate_session = AsyncMock(return_value=True)
        mock_cache.create_session = AsyncMock(return_value=False)  # Creation failed

        with pytest.raises(HTTPException) as exc_info:
            await regenerate_session(
                firebase_cache=mock_cache,
                old_session_id="old_session_123",
                user_id="user_123",
                firebase_uid="firebase_uid_123",
                metadata={"email": "test@example.com"}
            )

        assert exc_info.value.status_code == 500
        assert "Failed to regenerate session" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_regenerate_session_preserves_metadata(self):
        """Should preserve user metadata in new session."""
        mock_cache = AsyncMock()
        mock_cache.create_session = AsyncMock(return_value=True)

        metadata = {
            "email": "test@example.com",
            "role": "doctor",
            "device_type": "mobile",
            "os": "iOS"
        }

        await regenerate_session(
            firebase_cache=mock_cache,
            old_session_id=None,
            user_id="user_123",
            firebase_uid="firebase_uid_123",
            metadata=metadata
        )

        # Verify metadata was passed to create_session
        call_kwargs = mock_cache.create_session.call_args.kwargs
        assert call_kwargs['metadata'] == metadata

    @pytest.mark.asyncio
    async def test_regenerate_session_prevents_fixation_attack(self):
        """Simulate session fixation attack scenario."""
        mock_cache = AsyncMock()
        mock_cache.invalidate_session = AsyncMock(return_value=True)
        mock_cache.create_session = AsyncMock(return_value=True)

        # Attacker's session ID
        attacker_session_id = "attacker_controlled_session"

        # User authenticates (should get NEW session)
        new_session_id = await regenerate_session(
            firebase_cache=mock_cache,
            old_session_id=attacker_session_id,
            user_id="user_123",
            firebase_uid="firebase_uid_123",
            metadata={"email": "victim@example.com"}
        )

        # Attacker's session should be invalidated
        mock_cache.invalidate_session.assert_called_once_with(attacker_session_id)

        # New session should be completely different
        assert new_session_id != attacker_session_id

        # New session should be unpredictable (256-bit entropy)
        assert len(new_session_id) == 43


class TestSessionFixationPrevention:
    """Integration tests for session fixation prevention."""

    @pytest.mark.asyncio
    async def test_login_flow_regenerates_session(self):
        """Complete login flow should regenerate session ID."""
        # This would be an integration test with actual endpoint
        # For now, verify the logic is in place

        # 1. User visits login page (no session)
        # 2. User submits credentials
        # 3. Backend validates credentials
        # 4. Backend generates NEW session ID (256-bit entropy)
        # 5. Backend sets httpOnly cookie with new session ID
        # 6. User is authenticated with NEW session

        # The key security property:
        # - Attacker cannot predict session ID (256-bit entropy)
        # - Attacker's session ID is invalidated (if it existed)
        # - User gets fresh session after authentication

        pass  # Placeholder for integration test

    def test_session_entropy_distribution(self):
        """Session IDs should have uniform distribution (no bias)."""
        # Generate 1000 session IDs
        session_ids = [generate_session_id() for _ in range(1000)]

        # Check first character distribution
        # With 64 possible characters (base64), each should appear ~15-16 times
        first_chars = [sid[0] for sid in session_ids]
        char_counts = {}
        for char in first_chars:
            char_counts[char] = char_counts.get(char, 0) + 1

        # Chi-square test would be ideal here, but simple check:
        # No character should appear more than 30 times (2x expected)
        # or less than 5 times (0.3x expected)
        for char, count in char_counts.items():
            assert 5 <= count <= 30, f"Character '{char}' appears {count} times (biased)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
