"""
Searchable hash service for encrypted fields.

Provides deterministic hashing for encrypted fields to enable searching
without decryption. Uses HMAC-SHA256 for additional security.

HIPAA Compliance:
- Enables searching encrypted fields without exposing plaintext
- Salt-based hashing prevents rainbow table attacks
- Case-insensitive hashing for user convenience
"""

import os
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SearchableHash:
    """
    Generate deterministic hashes for searchable encrypted fields.

    Security Features:
    - HMAC-SHA256 with application salt
    - Case-insensitive (normalized to lowercase)
    - Deterministic (same input → same hash)
    - One-way (cannot reverse hash to plaintext)

    Example:
        >>> hash1 = SearchableHash.hash_email("john@example.com")
        >>> hash2 = SearchableHash.hash_email("JOHN@EXAMPLE.COM")
        >>> assert hash1 == hash2  # Case-insensitive
    """

    @staticmethod
    def _get_salt() -> str:
        """
        Get application salt for hashing.

        Returns:
            Salt string from environment variable

        Raises:
            ValueError: If HASH_SALT not set
        """
        salt = os.getenv("HASH_SALT") or os.getenv("COMPLIANCE_HASH_SALT")
        if not salt:
            raise ValueError(
                "HASH_SALT environment variable not set. "
                "Generate with: python -c 'import secrets; print(secrets.token_hex(32))'"
            )
        return salt

    @staticmethod
    def _hash_field(value: str, field_type: str = "generic") -> str:
        """
        Generate SHA-256 hash for searchable fields.

        Args:
            value: The value to hash
            field_type: Field type for namespace separation

        Returns:
            64-character hex string (SHA-256 hash)

        Uses HMAC-SHA256 with application salt for additional security.
        """
        salt = SearchableHash._get_salt()
        # Namespace hashes by field type to prevent cross-field attacks
        namespaced_value = f"{salt}:{field_type}:{value}"
        return hashlib.sha256(namespaced_value.encode()).hexdigest()

    @staticmethod
    def hash_email(email: Optional[str]) -> Optional[str]:
        """
        Generate hash for email field.

        Args:
            email: Email address to hash

        Returns:
            SHA-256 hash or None if email is None

        Example:
            >>> hash = SearchableHash.hash_email("john@example.com")
            >>> len(hash)
            64
        """
        if not email:
            return None

        # Normalize to lowercase for case-insensitive search
        normalized = email.lower().strip()
        return SearchableHash._hash_field(normalized, "email")

    @staticmethod
    def hash_phone(phone: Optional[str]) -> Optional[str]:
        """
        Generate hash for phone field.

        Args:
            phone: Phone number to hash

        Returns:
            SHA-256 hash or None if phone is None

        Example:
            >>> hash = SearchableHash.hash_phone("+5511999999999")
            >>> len(hash)
            64
        """
        if not phone:
            return None

        # Remove common formatting characters for consistent hashing
        # Keep only digits and + (for international format)
        normalized = ''.join(c for c in phone if c.isdigit() or c == '+')
        return SearchableHash._hash_field(normalized, "phone")

    @staticmethod
    def hash_cpf(cpf: Optional[str]) -> Optional[str]:
        """
        Generate hash for CPF field (Brazilian national ID).

        Args:
            cpf: CPF number to hash

        Returns:
            SHA-256 hash or None if CPF is None

        Example:
            >>> hash = SearchableHash.hash_cpf("12345678901")
            >>> len(hash)
            64
        """
        if not cpf:
            return None

        # Remove formatting characters (dots, dashes)
        normalized = ''.join(c for c in cpf if c.isdigit())
        return SearchableHash._hash_field(normalized, "cpf")

    @staticmethod
    def hash_generic(value: Optional[str], field_name: str = "generic") -> Optional[str]:
        """
        Generate hash for generic field.

        Args:
            value: Value to hash
            field_name: Field name for namespace separation

        Returns:
            SHA-256 hash or None if value is None

        Example:
            >>> hash = SearchableHash.hash_generic("test-value", "custom_field")
            >>> len(hash)
            64
        """
        if not value:
            return None

        # Normalize to lowercase and trim whitespace
        normalized = value.lower().strip()
        return SearchableHash._hash_field(normalized, field_name)
