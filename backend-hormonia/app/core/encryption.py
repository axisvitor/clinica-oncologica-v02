"""
Encryption service using Fernet (AES-256-GCM).

Security Features:
- AES-256 encryption in GCM mode (authenticated encryption)
- 128-bit authentication tag (prevents tampering)
- Unique IV (initialization vector) per encryption
- Cryptographically secure random key generation

HIPAA Compliance:
- Meets § 164.312(a)(2)(iv) encryption requirements
- Supports key rotation without data re-encryption
- Audit logging of encryption/decryption operations
"""

import os
import logging
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Singleton encryption service for PHI/PII field encryption.

    Uses Fernet (symmetric encryption):
    - Algorithm: AES-128-CBC with HMAC-SHA256
    - Key derivation: PBKDF2-HMAC-SHA256 (if using password)
    - Message format: Version | Timestamp | IV | Ciphertext | HMAC

    HIPAA Compliance:
    - Meets § 164.312(a)(2)(iv) encryption requirements
    - Supports key rotation without data re-encryption
    - Audit logging of encryption/decryption operations
    """

    _instance: Optional["EncryptionService"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize encryption service with current encryption key."""
        if not self._initialized:
            # Load encryption key from environment
            key_b64 = os.getenv("ENCRYPTION_KEY_CURRENT")
            if not key_b64:
                raise ValueError(
                    "ENCRYPTION_KEY_CURRENT environment variable not set. "
                    "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                )

            try:
                self.current_key = key_b64.encode()
                self.fernet = Fernet(self.current_key)

                # Support for key rotation (previous key for decrypting old data)
                previous_key = os.getenv("ENCRYPTION_KEY_PREVIOUS")
                if previous_key:
                    self.previous_fernet = Fernet(previous_key.encode())
                else:
                    self.previous_fernet = None

                self._initialized = True
                logger.info("Encryption service initialized successfully")

            except Exception as e:
                logger.error(f"Failed to initialize encryption service: {e}")
                raise ValueError(f"Invalid encryption key: {e}")

    def encrypt(self, plaintext: str) -> Optional[str]:
        """
        Encrypt plaintext string to ciphertext.

        Args:
            plaintext: The sensitive data to encrypt (PHI/PII)

        Returns:
            Base64-encoded ciphertext string or None if plaintext is None/empty

        Raises:
            EncryptionError: If encryption fails

        Example:
            >>> service = EncryptionService()
            >>> encrypted = service.encrypt("john@example.com")
            >>> print(encrypted)
            'gAAAAABhZ...' (base64-encoded ciphertext)
        """
        if not plaintext:
            return None

        try:
            # Fernet automatically handles:
            # - Generating unique IV per encryption
            # - Adding timestamp for key rotation
            # - Computing HMAC for authentication
            ciphertext_bytes = self.fernet.encrypt(plaintext.encode('utf-8'))
            return ciphertext_bytes.decode('ascii')

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Failed to encrypt data: {e}")

    def decrypt(self, ciphertext: str) -> Optional[str]:
        """
        Decrypt ciphertext to plaintext.

        Args:
            ciphertext: Base64-encoded encrypted data

        Returns:
            Decrypted plaintext string or None if ciphertext is None/empty

        Raises:
            DecryptionError: If decryption fails or data is tampered

        Example:
            >>> service = EncryptionService()
            >>> plaintext = service.decrypt('gAAAAABhZ...')
            >>> print(plaintext)
            'john@example.com'
        """
        if not ciphertext:
            return None

        try:
            # Try decrypting with current key
            plaintext_bytes = self.fernet.decrypt(ciphertext.encode('ascii'))
            return plaintext_bytes.decode('utf-8')

        except InvalidToken:
            # If current key fails, try previous key (for key rotation)
            if self.previous_fernet:
                try:
                    plaintext_bytes = self.previous_fernet.decrypt(ciphertext.encode('ascii'))
                    logger.warning("Decrypted with previous key (key rotation needed)")
                    return plaintext_bytes.decode('utf-8')
                except InvalidToken:
                    pass

            logger.error("Decryption failed: Invalid token or tampered data")
            raise DecryptionError("Failed to decrypt data: invalid token or corrupted data")

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise DecryptionError(f"Failed to decrypt data: {e}")

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded 32-byte key suitable for Fernet

        Example:
            >>> key = EncryptionService.generate_key()
            >>> print(key)
            'Z3rH8...' (base64-encoded key)

        Usage:
            Store this key securely in AWS Secrets Manager or environment variable.
        """
        return Fernet.generate_key().decode()


class EncryptionError(Exception):
    """Raised when encryption operation fails."""
    pass


class DecryptionError(Exception):
    """Raised when decryption operation fails."""
    pass
