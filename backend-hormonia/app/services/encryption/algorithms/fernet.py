"""
Fernet encryption algorithm implementation.

Symmetric encryption for quiz tokens and time-limited data.
"""

import logging
from cryptography.fernet import Fernet, InvalidToken

from .base import BaseAlgorithm

logger = logging.getLogger(__name__)


class FernetAlgorithm(BaseAlgorithm):
    """
    Fernet encryption algorithm.

    Features:
    - Symmetric encryption
    - Built-in timestamp
    - TTL support
    - Integrity verification

    Format: "encrypted:fernet:{fernet_token}"
    """

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt using Fernet.

        Args:
            plaintext: Value to encrypt

        Returns:
            Encrypted value: "encrypted:fernet:{token}"
        """
        fernet = Fernet(self.keys['quiz'])
        encrypted_bytes = fernet.encrypt(plaintext.encode())
        return f"{self.get_prefix()}{encrypted_bytes.decode()}"

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt Fernet encrypted data.

        Args:
            encrypted: Encrypted value with prefix

        Returns:
            Decrypted plaintext

        Raises:
            ValueError: If token is invalid or corrupted
        """
        encrypted_data = encrypted.replace(self.get_prefix(), '')
        fernet = Fernet(self.keys['quiz'])

        try:
            decrypted_bytes = fernet.decrypt(encrypted_data.encode())
            return decrypted_bytes.decode()
        except InvalidToken:
            logger.error("Invalid Fernet token - data may be corrupted")
            raise ValueError("Failed to decrypt data - invalid token")

    def get_prefix(self) -> str:
        """Get Fernet prefix."""
        return "encrypted:fernet:"
