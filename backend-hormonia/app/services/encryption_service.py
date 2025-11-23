"""
Encryption Service for Sensitive Data.

Provides encryption/decryption for sensitive quiz responses using Fernet symmetric encryption.
"""

import logging
from typing import Any, Optional
from cryptography.fernet import Fernet, InvalidToken
import base64
import hashlib

from app.core.monthly_quiz_config import get_monthly_quiz_config

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""

    def __init__(self):
        self.config = get_monthly_quiz_config()
        self._fernet = None

    @property
    def fernet(self) -> Fernet:
        """Lazy initialization of Fernet cipher."""
        if self._fernet is None:
            # Derive encryption key from token secret
            key = self._derive_key(self.config.MONTHLY_QUIZ_TOKEN_SECRET)
            self._fernet = Fernet(key)
        return self._fernet

    def _derive_key(self, secret: str) -> bytes:
        """
        Derive a Fernet-compatible key from secret.

        Fernet requires a 32-byte URL-safe base64-encoded key.
        """
        # Use SHA-256 to hash the secret
        hash_digest = hashlib.sha256(secret.encode()).digest()
        # Base64 encode for Fernet
        return base64.urlsafe_b64encode(hash_digest)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext data.

        Args:
            plaintext: Data to encrypt

        Returns:
            Encrypted data as base64 string
        """
        if not self.config.MONTHLY_QUIZ_ENABLE_ENCRYPTION:
            return plaintext

        try:
            encrypted_bytes = self.fernet.encrypt(plaintext.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt encrypted data.

        Args:
            ciphertext: Encrypted data as base64 string

        Returns:
            Decrypted plaintext
        """
        if not self.config.MONTHLY_QUIZ_ENABLE_ENCRYPTION:
            return ciphertext

        try:
            decrypted_bytes = self.fernet.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except InvalidToken:
            logger.error("Invalid encryption token - data may be corrupted")
            raise ValueError("Failed to decrypt data - invalid token")
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise

    def encrypt_sensitive_fields(self, data: dict, sensitive_fields: list[str]) -> dict:
        """
        Encrypt specific fields in a dictionary.

        Args:
            data: Dictionary containing data
            sensitive_fields: List of field names to encrypt

        Returns:
            Dictionary with encrypted fields
        """
        encrypted_data = data.copy()

        for field in sensitive_fields:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = self.encrypt(str(encrypted_data[field]))
                # Mark as encrypted
                encrypted_data[f"{field}_encrypted"] = True

        return encrypted_data

    def decrypt_sensitive_fields(self, data: dict, sensitive_fields: list[str]) -> dict:
        """
        Decrypt specific fields in a dictionary.

        Args:
            data: Dictionary containing encrypted data
            sensitive_fields: List of field names to decrypt

        Returns:
            Dictionary with decrypted fields
        """
        decrypted_data = data.copy()

        for field in sensitive_fields:
            if f"{field}_encrypted" in decrypted_data and decrypted_data.get(f"{field}_encrypted"):
                if field in decrypted_data:
                    decrypted_data[field] = self.decrypt(decrypted_data[field])
                    # Remove encryption flag
                    del decrypted_data[f"{field}_encrypted"]

        return decrypted_data

    def hash_for_storage(self, data: str) -> str:
        """
        Create a one-way hash for data that doesn't need to be retrieved.

        Useful for storing tokens that only need to be verified, not retrieved.
        """
        return hashlib.sha256(data.encode()).hexdigest()

    def verify_hash(self, data: str, hash_value: str) -> bool:
        """Verify data matches a stored hash."""
        return self.hash_for_storage(data) == hash_value


# Global instance
encryption_service = EncryptionService()


def get_encryption_service() -> EncryptionService:
    """Get encryption service instance."""
    return encryption_service
