"""
LGPD PII Encryption Service

This service handles encryption and decryption of all PII (Personally Identifiable Information)
to comply with LGPD (Brazilian General Data Protection Law) requirements.

Extends CPF encryption to cover email, phone, and other sensitive fields.

Features:
- AES-256-CBC encryption via PHI encryption service
- Searchable hash generation for encrypted values
- Transparent encryption/decryption layer
- Format normalization and validation

Security Design:
- Encryption: AES-256-CBC with PBKDF2 key derivation (via PHIEncryptionService)
- Searchable hash: SHA-256 HMAC with application salt
- Deterministic hashing enables searching without decryption
- Salt-based hashing prevents rainbow table attacks

LGPD Articles Implemented:
- Art. 46: Security, technical and administrative measures
- Art. 49: International data transfer requirements
"""

import logging
from typing import Optional, Tuple
import re

from app.services.phi_encryption_service import get_phi_encryption_service
from app.core.searchable_hash import SearchableHash

logger = logging.getLogger(__name__)


class LGPDEncryptionService:
    """
    LGPD-compliant service for encrypting PII data with searchable hash support.

    This service provides LGPD-compliant encryption for all sensitive fields:
    - CPF (Cadastro de Pessoas Físicas) - Brazilian national ID
    - Email addresses
    - Phone numbers
    - Other PII as needed

    Usage:
        >>> service = LGPDEncryptionService()
        >>> encrypted_email, email_hash = service.encrypt_email("user@example.com")
        >>> decrypted = service.decrypt_email(encrypted_email)
        >>> search_hash = service.hash_email_for_search("USER@EXAMPLE.COM")
    """

    def __init__(self):
        """Initialize LGPD encryption service with PHI encryption backend."""
        self.phi_service = get_phi_encryption_service()
        logger.info("LGPD PII encryption service initialized")

    # =========================================================================
    # CPF ENCRYPTION (Brazilian National ID)
    # =========================================================================

    def _normalize_cpf(self, cpf: str) -> str:
        """
        Normalize CPF by removing formatting characters.

        Args:
            cpf: CPF with or without formatting (e.g., "123.456.789-01" or "12345678901")

        Returns:
            CPF with only digits (11 characters)
        """
        if not cpf:
            return cpf
        return re.sub(r'\D', '', cpf)

    def _validate_cpf_format(self, cpf: str) -> bool:
        """
        Validate CPF format (basic check for 11 digits).

        Args:
            cpf: Normalized CPF (digits only)

        Returns:
            True if format is valid (11 digits)
        """
        if not cpf:
            return False
        if len(cpf) != 11 or not cpf.isdigit():
            return False
        if cpf == cpf[0] * 11:  # Reject all same digit
            return False
        return True

    def encrypt_cpf(self, cpf: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
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
            normalized_cpf = self._normalize_cpf(cpf)
            if not self._validate_cpf_format(normalized_cpf):
                raise ValueError(f"Invalid CPF format: {cpf}")

            encrypted_cpf = self.phi_service.encrypt_field(normalized_cpf)
            cpf_hash = SearchableHash.hash_cpf(normalized_cpf)

            logger.debug(f"CPF encrypted successfully")
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
        """
        if not encrypted_cpf:
            return None

        if not encrypted_cpf.startswith("encrypted:"):
            logger.warning("CPF is not encrypted, returning as-is")
            return encrypted_cpf

        try:
            return self.phi_service.decrypt_field(encrypted_cpf)
        except Exception as e:
            logger.error(f"Failed to decrypt CPF: {e}")
            raise

    def hash_cpf_for_search(self, cpf: Optional[str]) -> Optional[str]:
        """Generate searchable hash for CPF lookup."""
        if not cpf:
            return None
        normalized_cpf = self._normalize_cpf(cpf)
        return SearchableHash.hash_cpf(normalized_cpf)

    def format_cpf_for_display(self, cpf: Optional[str], mask: bool = False) -> Optional[str]:
        """
        Format CPF for display with optional masking.

        Args:
            cpf: CPF to format (11 digits)
            mask: If True, mask most digits for privacy

        Returns:
            Formatted CPF (e.g., "123.456.789-01" or "***.***.789-**")
        """
        if not cpf:
            return None

        normalized = self._normalize_cpf(cpf)
        if len(normalized) != 11:
            return cpf

        if mask:
            return f"***.***.{normalized[6:9]}-**"
        else:
            return f"{normalized[0:3]}.{normalized[3:6]}.{normalized[6:9]}-{normalized[9:11]}"

    # =========================================================================
    # EMAIL ENCRYPTION
    # =========================================================================

    def encrypt_email(self, email: Optional[str]) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Encrypt email and generate searchable hash.

        Args:
            email: Email address to encrypt

        Returns:
            Tuple of (encrypted_email_bytes, email_hash)

        Example:
            >>> encrypted, hash_val = service.encrypt_email("user@example.com")
            >>> len(hash_val)
            64
        """
        if not email:
            return None, None

        try:
            # Normalize email (lowercase, strip whitespace)
            normalized_email = email.lower().strip()

            # Encrypt using PHI service
            encrypted_email = self.phi_service.encrypt_field(normalized_email)

            # Convert encrypted string to bytes for LargeBinary storage
            encrypted_bytes = encrypted_email.encode('utf-8')

            # Generate searchable hash
            email_hash = SearchableHash.hash_email(normalized_email)

            logger.debug(f"Email encrypted successfully")
            return encrypted_bytes, email_hash

        except Exception as e:
            logger.error(f"Failed to encrypt email: {e}")
            raise

    def decrypt_email(self, encrypted_email: Optional[bytes]) -> Optional[str]:
        """
        Decrypt encrypted email.

        Args:
            encrypted_email: Encrypted email bytes

        Returns:
            Decrypted email address

        Example:
            >>> decrypted = service.decrypt_email(encrypted_bytes)
            >>> "@" in decrypted
            True
        """
        if not encrypted_email:
            return None

        try:
            # Convert bytes back to string
            encrypted_str = encrypted_email.decode('utf-8') if isinstance(encrypted_email, bytes) else encrypted_email

            # Handle backward compatibility
            if not encrypted_str.startswith("encrypted:"):
                logger.warning("Email is not encrypted, returning as-is")
                return encrypted_str

            # Decrypt using PHI service
            decrypted_email = self.phi_service.decrypt_field(encrypted_str)

            logger.debug("Email decrypted successfully")
            return decrypted_email

        except Exception as e:
            logger.error(f"Failed to decrypt email: {e}")
            raise

    def hash_email_for_search(self, email: Optional[str]) -> Optional[str]:
        """
        Generate searchable hash for email lookup.

        Args:
            email: Email address to hash

        Returns:
            SHA-256 hash (64 characters) or None
        """
        if not email:
            return None
        normalized_email = email.lower().strip()
        return SearchableHash.hash_email(normalized_email)

    # =========================================================================
    # PHONE ENCRYPTION
    # =========================================================================

    def _normalize_phone(self, phone: str) -> str:
        """
        Normalize phone by keeping only digits and + sign.

        Args:
            phone: Phone number with or without formatting

        Returns:
            Phone with only digits and + (e.g., "+5511999999999")
        """
        if not phone:
            return phone
        # Keep only digits and + for international format
        return ''.join(c for c in phone if c.isdigit() or c == '+')

    def encrypt_phone(self, phone: Optional[str]) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Encrypt phone and generate searchable hash.

        Args:
            phone: Phone number to encrypt

        Returns:
            Tuple of (encrypted_phone_bytes, phone_hash)

        Example:
            >>> encrypted, hash_val = service.encrypt_phone("+5511999999999")
            >>> len(hash_val)
            64
        """
        if not phone:
            return None, None

        try:
            # Normalize phone (remove formatting, keep only digits and +)
            normalized_phone = self._normalize_phone(phone)

            # Encrypt using PHI service
            encrypted_phone = self.phi_service.encrypt_field(normalized_phone)

            # Convert encrypted string to bytes for LargeBinary storage
            encrypted_bytes = encrypted_phone.encode('utf-8')

            # Generate searchable hash
            phone_hash = SearchableHash.hash_phone(normalized_phone)

            logger.debug(f"Phone encrypted successfully")
            return encrypted_bytes, phone_hash

        except Exception as e:
            logger.error(f"Failed to encrypt phone: {e}")
            raise

    def decrypt_phone(self, encrypted_phone: Optional[bytes]) -> Optional[str]:
        """
        Decrypt encrypted phone.

        Args:
            encrypted_phone: Encrypted phone bytes

        Returns:
            Decrypted phone number

        Example:
            >>> decrypted = service.decrypt_phone(encrypted_bytes)
            >>> decrypted.startswith("+") or decrypted.isdigit()
            True
        """
        if not encrypted_phone:
            return None

        try:
            # Convert bytes back to string
            encrypted_str = encrypted_phone.decode('utf-8') if isinstance(encrypted_phone, bytes) else encrypted_phone

            # Handle backward compatibility
            if not encrypted_str.startswith("encrypted:"):
                logger.warning("Phone is not encrypted, returning as-is")
                return encrypted_str

            # Decrypt using PHI service
            decrypted_phone = self.phi_service.decrypt_field(encrypted_str)

            logger.debug("Phone decrypted successfully")
            return decrypted_phone

        except Exception as e:
            logger.error(f"Failed to decrypt phone: {e}")
            raise

    def hash_phone_for_search(self, phone: Optional[str]) -> Optional[str]:
        """
        Generate searchable hash for phone lookup.

        Args:
            phone: Phone number to hash

        Returns:
            SHA-256 hash (64 characters) or None
        """
        if not phone:
            return None
        normalized_phone = self._normalize_phone(phone)
        return SearchableHash.hash_phone(normalized_phone)

    # =========================================================================
    # MIGRATION UTILITIES
    # =========================================================================

    def migrate_plaintext_email(self, plaintext_email: Optional[str]) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Migrate existing plaintext email to encrypted format.

        Args:
            plaintext_email: Existing plaintext email

        Returns:
            Tuple of (encrypted_email_bytes, email_hash)
        """
        if not plaintext_email:
            return None, None
        logger.info(f"Migrating plaintext email to encrypted format")
        return self.encrypt_email(plaintext_email)

    def migrate_plaintext_phone(self, plaintext_phone: Optional[str]) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Migrate existing plaintext phone to encrypted format.

        Args:
            plaintext_phone: Existing plaintext phone

        Returns:
            Tuple of (encrypted_phone_bytes, phone_hash)
        """
        if not plaintext_phone:
            return None, None
        logger.info(f"Migrating plaintext phone to encrypted format")
        return self.encrypt_phone(plaintext_phone)


# Singleton instance
_lgpd_encryption_service: Optional[LGPDEncryptionService] = None


def get_lgpd_encryption_service() -> LGPDEncryptionService:
    """
    Get or create the LGPD encryption service singleton.

    Returns:
        LGPDEncryptionService instance
    """
    global _lgpd_encryption_service
    if _lgpd_encryption_service is None:
        _lgpd_encryption_service = LGPDEncryptionService()
    return _lgpd_encryption_service
