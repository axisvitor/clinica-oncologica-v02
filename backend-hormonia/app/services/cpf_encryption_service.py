"""
CPF Encryption Service for LGPD Compliance

This service handles encryption and decryption of CPF (Brazilian tax ID) data
to comply with LGPD (Brazilian General Data Protection Law) requirements.

Features:
- AES-256-CBC encryption via PHI encryption service
- Searchable hash generation for encrypted CPF values
- Transparent encryption/decryption layer
- Format normalization and validation

Security Design:
- Encryption: AES-256-CBC with PBKDF2 key derivation (via PHIEncryptionService)
- Searchable hash: SHA-256 HMAC with application salt
- Deterministic hashing enables searching without decryption
- Salt-based hashing prevents rainbow table attacks
"""

import logging
from typing import Optional, Tuple
import re

from app.services.phi_encryption_service import get_phi_encryption_service
from app.core.searchable_hash import SearchableHash

logger = logging.getLogger(__name__)


class CPFEncryptionService:
    """
    Service for encrypting CPF data with searchable hash support.

    This service provides LGPD-compliant encryption for CPF (Cadastro de Pessoas Físicas),
    Brazil's national identification number.

    Usage:
        >>> service = CPFEncryptionService()
        >>> encrypted_cpf, cpf_hash = service.encrypt_cpf("12345678901")
        >>> decrypted = service.decrypt_cpf(encrypted_cpf)
        >>> search_hash = service.hash_cpf_for_search("123.456.789-01")
    """

    def __init__(self):
        """Initialize CPF encryption service with PHI encryption backend."""
        self.phi_service = get_phi_encryption_service()
        logger.info("CPF encryption service initialized")

    def _normalize_cpf(self, cpf: str) -> str:
        """
        Normalize CPF by removing formatting characters.

        Args:
            cpf: CPF with or without formatting (e.g., "123.456.789-01" or "12345678901")

        Returns:
            CPF with only digits (11 characters)

        Example:
            >>> service._normalize_cpf("123.456.789-01")
            "12345678901"
        """
        if not cpf:
            return cpf

        # Remove all non-digit characters (dots, dashes, spaces)
        normalized = re.sub(r'\D', '', cpf)
        return normalized

    def _validate_cpf_format(self, cpf: str) -> bool:
        """
        Validate CPF format (basic check for 11 digits).

        Note: This does NOT validate CPF checksum digits.
        For production, consider adding full CPF validation.

        Args:
            cpf: Normalized CPF (digits only)

        Returns:
            True if format is valid (11 digits)
        """
        if not cpf:
            return False

        # CPF must be exactly 11 digits
        if len(cpf) != 11 or not cpf.isdigit():
            return False

        # Reject known invalid patterns (all same digit)
        if cpf == cpf[0] * 11:
            return False

        return True

    def encrypt_cpf(self, cpf: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Encrypt CPF and generate searchable hash.

        Args:
            cpf: CPF to encrypt (with or without formatting)

        Returns:
            Tuple of (encrypted_cpf, cpf_hash)
            - encrypted_cpf: AES-256 encrypted CPF with "encrypted:" prefix
            - cpf_hash: SHA-256 hash for searching

        Raises:
            ValueError: If CPF format is invalid

        Example:
            >>> encrypted_cpf, cpf_hash = service.encrypt_cpf("123.456.789-01")
            >>> encrypted_cpf.startswith("encrypted:")
            True
            >>> len(cpf_hash)
            64
        """
        if not cpf:
            return None, None

        try:
            # Normalize CPF (remove formatting)
            normalized_cpf = self._normalize_cpf(cpf)

            # Validate format
            if not self._validate_cpf_format(normalized_cpf):
                raise ValueError(f"Invalid CPF format: {cpf}")

            # Encrypt using PHI service
            encrypted_cpf = self.phi_service.encrypt_field(normalized_cpf)

            # Generate searchable hash
            cpf_hash = SearchableHash.hash_cpf(normalized_cpf)

            logger.debug(f"CPF encrypted successfully (hash: {cpf_hash[:16]}...)")
            return encrypted_cpf, cpf_hash

        except Exception as e:
            logger.error(f"Failed to encrypt CPF: {e}")
            raise

    def decrypt_cpf(self, encrypted_cpf: Optional[str]) -> Optional[str]:
        """
        Decrypt encrypted CPF.

        Args:
            encrypted_cpf: Encrypted CPF with "encrypted:" prefix

        Returns:
            Decrypted CPF (11 digits, no formatting)

        Raises:
            ValueError: If decryption fails

        Example:
            >>> decrypted = service.decrypt_cpf("encrypted:...")
            >>> len(decrypted)
            11
        """
        if not encrypted_cpf:
            return None

        # Handle already decrypted or plain text CPF (for backward compatibility)
        if not encrypted_cpf.startswith("encrypted:"):
            logger.warning("CPF is not encrypted, returning as-is (backward compatibility)")
            return encrypted_cpf

        try:
            # Decrypt using PHI service
            decrypted_cpf = self.phi_service.decrypt_field(encrypted_cpf)

            logger.debug("CPF decrypted successfully")
            return decrypted_cpf

        except Exception as e:
            logger.error(f"Failed to decrypt CPF: {e}")
            raise

    def hash_cpf_for_search(self, cpf: Optional[str]) -> Optional[str]:
        """
        Generate searchable hash for CPF lookup.

        This method is used to query encrypted CPF fields without decryption.
        The hash is deterministic, so the same CPF always produces the same hash.

        Args:
            cpf: CPF to hash (with or without formatting)

        Returns:
            SHA-256 hash (64 characters) or None

        Example:
            >>> hash1 = service.hash_cpf_for_search("123.456.789-01")
            >>> hash2 = service.hash_cpf_for_search("12345678901")
            >>> hash1 == hash2
            True
        """
        if not cpf:
            return None

        # Normalize CPF before hashing (ensures consistent hashes)
        normalized_cpf = self._normalize_cpf(cpf)

        # Generate hash using SearchableHash
        return SearchableHash.hash_cpf(normalized_cpf)

    def format_cpf_for_display(self, cpf: Optional[str], mask: bool = False) -> Optional[str]:
        """
        Format CPF for display with optional masking.

        Args:
            cpf: CPF to format (11 digits)
            mask: If True, mask most digits for privacy

        Returns:
            Formatted CPF (e.g., "123.456.789-01" or "***.***.789-**")

        Example:
            >>> service.format_cpf_for_display("12345678901")
            "123.456.789-01"
            >>> service.format_cpf_for_display("12345678901", mask=True)
            "***.***.789-**"
        """
        if not cpf:
            return None

        # Normalize first
        normalized = self._normalize_cpf(cpf)

        if len(normalized) != 11:
            return cpf  # Return as-is if invalid

        if mask:
            # Mask for privacy: ***.***.789-**
            return f"***.***.{normalized[6:9]}-**"
        else:
            # Full format: 123.456.789-01
            return f"{normalized[0:3]}.{normalized[3:6]}.{normalized[6:9]}-{normalized[9:11]}"

    def migrate_plaintext_cpf(self, plaintext_cpf: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Migrate existing plaintext CPF to encrypted format.

        This method is designed for use in database migrations to convert
        existing plaintext CPF values to encrypted format.

        Args:
            plaintext_cpf: Existing plaintext CPF

        Returns:
            Tuple of (encrypted_cpf, cpf_hash)

        Example:
            >>> encrypted, hash_val = service.migrate_plaintext_cpf("12345678901")
        """
        if not plaintext_cpf:
            return None, None

        logger.info(f"Migrating plaintext CPF to encrypted format")
        return self.encrypt_cpf(plaintext_cpf)


# Singleton instance
_cpf_encryption_service: Optional[CPFEncryptionService] = None


def get_cpf_encryption_service() -> CPFEncryptionService:
    """
    Get or create the CPF encryption service singleton.

    Returns:
        CPFEncryptionService instance
    """
    global _cpf_encryption_service
    if _cpf_encryption_service is None:
        _cpf_encryption_service = CPFEncryptionService()
    return _cpf_encryption_service
