"""
Unit tests for encryption service.

Tests encryption/decryption correctness, key rotation, error handling.
"""

import os
import pytest
from cryptography.fernet import Fernet

from app.core.encryption import EncryptionService, EncryptionError, DecryptionError


@pytest.fixture
def encryption_key():
    """Generate a test encryption key."""
    return Fernet.generate_key().decode()


@pytest.fixture
def setup_env(encryption_key, monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("ENCRYPTION_KEY_CURRENT", encryption_key)
    # Reset singleton for testing
    EncryptionService._instance = None
    EncryptionService._initialized = False
    yield
    # Cleanup
    EncryptionService._instance = None
    EncryptionService._initialized = False


class TestEncryptionService:
    """Test EncryptionService functionality."""

    def test_singleton_pattern(self, setup_env):
        """Test that EncryptionService is a singleton."""
        service1 = EncryptionService()
        service2 = EncryptionService()
        assert service1 is service2

    def test_encrypt_decrypt_cycle(self, setup_env):
        """Test basic encryption and decryption."""
        service = EncryptionService()
        plaintext = "sensitive-data@example.com"

        # Encrypt
        ciphertext = service.encrypt(plaintext)
        assert ciphertext is not None
        assert ciphertext != plaintext
        assert ciphertext.startswith("gAAAAA")  # Fernet format

        # Decrypt
        decrypted = service.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_none_returns_none(self, setup_env):
        """Test that encrypting None returns None."""
        service = EncryptionService()
        assert service.encrypt(None) is None
        assert service.encrypt("") is None

    def test_decrypt_none_returns_none(self, setup_env):
        """Test that decrypting None returns None."""
        service = EncryptionService()
        assert service.decrypt(None) is None
        assert service.decrypt("") is None

    def test_encrypt_unicode_text(self, setup_env):
        """Test encryption of unicode text."""
        service = EncryptionService()
        plaintext = "Olá, こんにちは, 你好"

        ciphertext = service.encrypt(plaintext)
        decrypted = service.decrypt(ciphertext)

        assert decrypted == plaintext

    def test_encrypt_long_text(self, setup_env):
        """Test encryption of long text."""
        service = EncryptionService()
        plaintext = "A" * 10000  # 10KB of text

        ciphertext = service.encrypt(plaintext)
        decrypted = service.decrypt(ciphertext)

        assert decrypted == plaintext

    def test_decrypt_tampered_data_fails(self, setup_env):
        """Test that tampered ciphertext raises DecryptionError."""
        service = EncryptionService()
        plaintext = "test-data"

        ciphertext = service.encrypt(plaintext)
        tampered = ciphertext[:-10] + "XXXXXXXXXX"  # Modify last 10 chars

        with pytest.raises(DecryptionError):
            service.decrypt(tampered)

    def test_decrypt_with_wrong_key_fails(self, setup_env, monkeypatch):
        """Test that decrypting with wrong key fails."""
        service1 = EncryptionService()
        plaintext = "test-data"
        ciphertext = service1.encrypt(plaintext)

        # Reset and use different key
        EncryptionService._instance = None
        EncryptionService._initialized = False
        new_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY_CURRENT", new_key)

        service2 = EncryptionService()
        with pytest.raises(DecryptionError):
            service2.decrypt(ciphertext)

    def test_key_rotation_support(self, encryption_key, monkeypatch):
        """Test decryption with previous key during rotation."""
        # Setup with current key
        monkeypatch.setenv("ENCRYPTION_KEY_CURRENT", encryption_key)
        EncryptionService._instance = None
        EncryptionService._initialized = False

        service1 = EncryptionService()
        plaintext = "rotated-data"
        ciphertext = service1.encrypt(plaintext)

        # Rotate key (current becomes previous)
        new_key = Fernet.generate_key().decode()
        EncryptionService._instance = None
        EncryptionService._initialized = False
        monkeypatch.setenv("ENCRYPTION_KEY_CURRENT", new_key)
        monkeypatch.setenv("ENCRYPTION_KEY_PREVIOUS", encryption_key)

        service2 = EncryptionService()
        # Should decrypt with previous key
        decrypted = service2.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_generate_key_format(self):
        """Test that generated key has correct format."""
        key = EncryptionService.generate_key()
        assert len(key) == 44  # Base64-encoded 32 bytes
        # Verify it's a valid Fernet key
        Fernet(key.encode())

    def test_initialization_without_key_fails(self, monkeypatch):
        """Test that initialization fails without ENCRYPTION_KEY_CURRENT."""
        monkeypatch.delenv("ENCRYPTION_KEY_CURRENT", raising=False)
        EncryptionService._instance = None
        EncryptionService._initialized = False

        with pytest.raises(ValueError, match="ENCRYPTION_KEY_CURRENT"):
            EncryptionService()

    def test_deterministic_encryption(self, setup_env):
        """Test that same plaintext produces different ciphertext (IV)."""
        service = EncryptionService()
        plaintext = "deterministic-test"

        ciphertext1 = service.encrypt(plaintext)
        ciphertext2 = service.encrypt(plaintext)

        # Different ciphertexts (unique IV per encryption)
        assert ciphertext1 != ciphertext2

        # But both decrypt to same plaintext
        assert service.decrypt(ciphertext1) == plaintext
        assert service.decrypt(ciphertext2) == plaintext
