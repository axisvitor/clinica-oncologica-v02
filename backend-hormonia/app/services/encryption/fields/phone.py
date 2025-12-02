"""
Phone number field encryptor.
"""

import logging
from typing import Optional, Tuple

from .base import BaseFieldEncryptor
from ..types import FieldType

logger = logging.getLogger(__name__)


class PhoneEncryptor(BaseFieldEncryptor):
    """
    Phone-specific encryption with normalization.

    Features:
    - Formatting removal (keeps digits and + sign)
    - International format support
    - Searchable hash generation
    - Byte encoding for storage
    """

    def encrypt(self, phone: Optional[str]) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Encrypt phone and generate searchable hash.

        Args:
            phone: Phone number to encrypt

        Returns:
            Tuple of (encrypted_phone_bytes, phone_hash)
        """
        if not phone:
            return None, None

        try:
            # Normalize phone
            normalized_phone = self.normalize(phone)

            # Encrypt
            encrypted_phone = self.encrypt_func(normalized_phone, FieldType.PHONE)
            encrypted_bytes = encrypted_phone.encode('utf-8')

            # Generate searchable hash
            phone_hash = self.hash_func(normalized_phone, FieldType.PHONE)

            logger.debug("Phone encrypted successfully")
            return encrypted_bytes, phone_hash

        except Exception as e:
            logger.error(f"Failed to encrypt phone: {e}")
            raise

    def decrypt(self, encrypted_phone: Optional[bytes]) -> Optional[str]:
        """
        Decrypt encrypted phone.

        Args:
            encrypted_phone: Encrypted phone bytes

        Returns:
            Decrypted phone number
        """
        if not encrypted_phone:
            return None

        try:
            # Convert bytes to string
            encrypted_str = (
                encrypted_phone.decode('utf-8')
                if isinstance(encrypted_phone, bytes)
                else encrypted_phone
            )

            return self.decrypt_func(encrypted_str, FieldType.PHONE)

        except Exception as e:
            logger.error(f"Failed to decrypt phone: {e}")
            raise

    def normalize(self, phone: str) -> str:
        """
        Normalize phone by keeping only digits and + sign.

        Args:
            phone: Raw phone number

        Returns:
            Normalized phone (digits and + only)
        """
        if not phone:
            return phone
        return ''.join(c for c in phone if c.isdigit() or c == '+')

    def validate(self, phone: str) -> bool:
        """
        Validate phone format (basic check).

        Args:
            phone: Phone number

        Returns:
            True if valid
        """
        if not phone:
            return False
        normalized = self.normalize(phone)
        return len(normalized) >= 8  # Minimum 8 digits
