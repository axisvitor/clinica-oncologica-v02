"""
Email field encryptor.
"""

import logging
from typing import Optional, Tuple

from .base import BaseFieldEncryptor
from ..types import FieldType

logger = logging.getLogger(__name__)


class EmailEncryptor(BaseFieldEncryptor):
    """
    Email-specific encryption with normalization.

    Features:
    - Case normalization (lowercase)
    - Whitespace trimming
    - Searchable hash generation
    - Byte encoding for storage
    """

    def encrypt(self, email: Optional[str]) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Encrypt email and generate searchable hash.

        Args:
            email: Email address to encrypt

        Returns:
            Tuple of (encrypted_email_bytes, email_hash)
        """
        if not email:
            return None, None

        try:
            # Normalize email
            normalized_email = self.normalize(email)

            # Encrypt
            encrypted_email = self.encrypt_func(normalized_email, FieldType.EMAIL)
            encrypted_bytes = encrypted_email.encode("utf-8")

            # Generate searchable hash
            email_hash = self.hash_func(normalized_email, FieldType.EMAIL)

            logger.debug("Email encrypted successfully")
            return encrypted_bytes, email_hash

        except Exception as e:
            logger.error(f"Failed to encrypt email: {e}")
            raise

    def decrypt(self, encrypted_email: Optional[bytes]) -> Optional[str]:
        """
        Decrypt encrypted email.

        Args:
            encrypted_email: Encrypted email bytes

        Returns:
            Decrypted email address
        """
        if not encrypted_email:
            return None

        try:
            # Convert bytes to string
            encrypted_str = (
                encrypted_email.decode("utf-8")
                if isinstance(encrypted_email, bytes)
                else encrypted_email
            )

            return self.decrypt_func(encrypted_str, FieldType.EMAIL)

        except Exception as e:
            logger.error(f"Failed to decrypt email: {e}")
            raise

    def normalize(self, email: str) -> str:
        """
        Normalize email address.

        Rules:
        - Convert to lowercase
        - Strip whitespace

        Args:
            email: Raw email address

        Returns:
            Normalized email
        """
        if not email:
            return email
        return email.lower().strip()

    def validate(self, email: str) -> bool:
        """
        Validate email format (basic check).

        Args:
            email: Email address

        Returns:
            True if valid
        """
        if not email:
            return False
        return "@" in email and "." in email.split("@")[1]
