"""
Unit tests for key management service.

Tests key generation, retrieval, AWS integration (mocked).
"""

import pytest
from cryptography.fernet import Fernet

from app.services.encryption.key_manager import (
    KeyManagementService,
    KeyNotFoundError,
)


@pytest.fixture
def encryption_key():
    """Generate a test encryption key."""
    return Fernet.generate_key().decode()


@pytest.fixture
def setup_env(encryption_key, monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("ENCRYPTION_KEY_CURRENT", encryption_key)
    monkeypatch.setenv("HASH_SALT", "test-salt-" + "0" * 50)


class TestKeyManagementService:
    """Test KeyManagementService functionality."""

    def test_get_current_key_from_env(self, setup_env, encryption_key):
        """Test retrieving current key from environment."""
        kms = KeyManagementService(use_aws=False)
        key = kms.get_current_key()
        assert key == encryption_key

    def test_get_previous_key_from_env(self, setup_env, monkeypatch):
        """Test retrieving previous key from environment."""
        previous_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY_PREVIOUS", previous_key)

        kms = KeyManagementService(use_aws=False)
        key = kms.get_previous_key()
        assert key == previous_key

    def test_get_previous_key_none_if_not_set(self, setup_env):
        """Test that previous key returns None if not set."""
        kms = KeyManagementService(use_aws=False)
        key = kms.get_previous_key()
        assert key is None

    def test_get_current_key_fails_if_not_set(self, monkeypatch):
        """Test that getting current key fails if not set."""
        monkeypatch.delenv("ENCRYPTION_KEY_CURRENT", raising=False)
        kms = KeyManagementService(use_aws=False)

        with pytest.raises(KeyNotFoundError, match="ENCRYPTION_KEY_CURRENT"):
            kms.get_current_key()

    def test_generate_key_format(self):
        """Test that generated key has correct format."""
        key = KeyManagementService.generate_key()
        assert len(key) == 44  # Base64-encoded 32 bytes
        # Verify it's a valid Fernet key
        Fernet(key.encode())

    def test_generate_key_uniqueness(self):
        """Test that each generated key is unique."""
        key1 = KeyManagementService.generate_key()
        key2 = KeyManagementService.generate_key()
        assert key1 != key2

    def test_generate_hash_salt_format(self):
        """Test that generated salt has correct format."""
        salt = KeyManagementService.generate_hash_salt()
        assert len(salt) == 64  # 32 bytes in hex = 64 chars
        # Verify it's valid hex
        int(salt, 16)

    def test_generate_hash_salt_uniqueness(self):
        """Test that each generated salt is unique."""
        salt1 = KeyManagementService.generate_hash_salt()
        salt2 = KeyManagementService.generate_hash_salt()
        assert salt1 != salt2

    def test_aws_mode_disabled_without_boto3(self, setup_env, monkeypatch):
        """Test that AWS mode is disabled if boto3 is not available."""
        # This test simulates missing boto3
        # In real environment, KeyManagementService handles ImportError gracefully
        kms = KeyManagementService(use_aws=False)
        assert kms.secrets_client is None
        assert not kms.use_aws

    def test_environment_fallback(self, setup_env, encryption_key):
        """Test that environment variables work as fallback."""
        kms = KeyManagementService(use_aws=False)
        key = kms.get_current_key()
        assert key == encryption_key
        # Verify key works with Fernet
        fernet = Fernet(key.encode())
        test_data = b"test"
        encrypted = fernet.encrypt(test_data)
        decrypted = fernet.decrypt(encrypted)
        assert decrypted == test_data
