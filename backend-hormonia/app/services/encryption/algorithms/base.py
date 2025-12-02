"""
Base algorithm interface for encryption.
"""

from abc import ABC, abstractmethod
from typing import Dict


class BaseAlgorithm(ABC):
    """
    Abstract base class for encryption algorithms.

    Implements Strategy Pattern for algorithm-specific encryption/decryption.
    """

    def __init__(self, keys: Dict[str, bytes]):
        """
        Initialize algorithm with encryption keys.

        Args:
            keys: Dictionary of encryption keys (e.g., {'phi': bytes, 'quiz': bytes})
        """
        self.keys = keys

    @abstractmethod
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext.

        Args:
            plaintext: Value to encrypt

        Returns:
            Encrypted value with algorithm-specific prefix
        """
        pass

    @abstractmethod
    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt encrypted value.

        Args:
            encrypted: Encrypted value

        Returns:
            Decrypted plaintext
        """
        pass

    @abstractmethod
    def get_prefix(self) -> str:
        """
        Get algorithm-specific prefix for encrypted values.

        Returns:
            Prefix string (e.g., "encrypted:gcm:")
        """
        pass
