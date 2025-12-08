"""
Base field encryptor interface.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Callable

from ..types import FieldType


class BaseFieldEncryptor(ABC):
    """
    Abstract base class for field-specific encryption.

    Implements Strategy Pattern for field type-specific logic.
    """

    def __init__(
        self,
        encrypt_func: Callable[[str, FieldType], str],
        decrypt_func: Callable[[str, FieldType], str],
        hash_func: Callable[[str, FieldType], str]
    ):
        """
        Initialize field encryptor.

        Args:
            encrypt_func: Core encryption function
            decrypt_func: Core decryption function
            hash_func: Hash generation function
        """
        self.encrypt_func = encrypt_func
        self.decrypt_func = decrypt_func
        self.hash_func = hash_func

    @abstractmethod
    def encrypt(self, value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Encrypt field value and generate searchable hash.

        Args:
            value: Field value to encrypt

        Returns:
            Tuple of (encrypted_value, hash)
        """
        pass

    @abstractmethod
    def decrypt(self, encrypted: Optional[str]) -> Optional[str]:
        """
        Decrypt field value.

        Args:
            encrypted: Encrypted field value

        Returns:
            Decrypted value
        """
        pass

    @abstractmethod
    def normalize(self, value: str) -> str:
        """
        Normalize field value before encryption.

        Args:
            value: Raw field value

        Returns:
            Normalized value
        """
        pass

    @abstractmethod
    def validate(self, value: str) -> bool:
        """
        Validate field value format.

        Args:
            value: Field value to validate

        Returns:
            True if valid
        """
        pass
