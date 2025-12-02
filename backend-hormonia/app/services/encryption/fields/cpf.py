"""
CPF (Brazilian National ID) field encryptor.
"""

import re
import logging
from typing import Optional, Tuple

from .base import BaseFieldEncryptor
from ..types import FieldType

logger = logging.getLogger(__name__)


class CPFEncryptor(BaseFieldEncryptor):
    """
    CPF-specific encryption with validation and normalization.

    Features:
    - Format validation (11 digits)
    - Automatic formatting removal
    - Rejection of invalid sequences (e.g., "111.111.111-11")
    - Searchable hash generation
    """

    def encrypt(self, cpf: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Encrypt CPF and generate searchable hash.

        Args:
            cpf: CPF to encrypt (with or without formatting)

        Returns:
            Tuple of (encrypted_cpf, cpf_hash)

        Raises:
            ValueError: If CPF format is invalid
        """
        if not cpf:
            return None, None

        try:
            # Normalize CPF (remove formatting)
            normalized_cpf = self.normalize(cpf)

            # Validate format
            if not self.validate(normalized_cpf):
                raise ValueError(f"Invalid CPF format: {cpf}")

            # Encrypt
            encrypted_cpf = self.encrypt_func(normalized_cpf, FieldType.CPF)

            # Generate searchable hash
            cpf_hash = self.hash_func(normalized_cpf, FieldType.CPF)

            logger.debug("CPF encrypted successfully")
            return encrypted_cpf, cpf_hash

        except Exception as e:
            logger.error(f"Failed to encrypt CPF: {e}")
            raise

    def decrypt(self, encrypted_cpf: Optional[str]) -> Optional[str]:
        """
        Decrypt encrypted CPF.

        Args:
            encrypted_cpf: Encrypted CPF

        Returns:
            Decrypted CPF (11 digits, no formatting)
        """
        if not encrypted_cpf:
            return None

        return self.decrypt_func(encrypted_cpf, FieldType.CPF)

    def normalize(self, cpf: str) -> str:
        """
        Normalize CPF by removing formatting.

        Args:
            cpf: CPF with or without formatting

        Returns:
            CPF with only digits (11 characters)
        """
        if not cpf:
            return cpf
        return re.sub(r'\D', '', cpf)

    def validate(self, cpf: str) -> bool:
        """
        Validate CPF format.

        Rules:
        - Must have exactly 11 digits
        - Cannot be all same digit (e.g., "11111111111")

        Args:
            cpf: Normalized CPF (digits only)

        Returns:
            True if valid
        """
        if not cpf or len(cpf) != 11 or not cpf.isdigit():
            return False
        if cpf == cpf[0] * 11:  # Reject all same digit
            return False
        return True
