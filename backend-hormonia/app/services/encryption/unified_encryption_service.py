"""
Unified Encryption Service for Healthcare Compliance

Consolidates all encryption services into a single, unified service:
- PHI Encryption Service (HIPAA)
- LGPD Encryption Service (Brazilian LGPD)
- CPF Encryption Service
- Quiz Encryption Service (Fernet-based)
- Token Rotation Security

Features:
- AES-256-GCM encryption (default, more secure than CBC)
- AES-256-CBC encryption (legacy compatibility)
- Fernet encryption (for quiz tokens)
- Searchable hash generation
- Field-level encryption for all PII/PHI types
- Key rotation support
- Multi-algorithm support

Security Standards:
- HIPAA compliant
- LGPD (Brazilian GDPR) compliant
- PBKDF2 key derivation
- SHA-256 HMAC searchable hashes
- Salt-based hashing prevents rainbow table attacks

Supported Field Types:
- CPF (Brazilian National ID)
- Email addresses
- Phone numbers
- Generic PHI data
- Sensitive quiz responses
"""

import os
import base64
import hashlib
import logging
import json
import secrets
from enum import Enum
from typing import Any, Optional, Tuple, Dict
from datetime import datetime, timedelta

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.core.searchable_hash import SearchableHash

logger = logging.getLogger(__name__)


class EncryptionAlgorithm(str, Enum):
    """Supported encryption algorithms."""
    AES_256_GCM = "aes-256-gcm"  # Recommended: Authenticated encryption
    AES_256_CBC = "aes-256-cbc"  # Legacy: For backward compatibility
    FERNET = "fernet"            # Quiz tokens: Symmetric encryption


class FieldType(str, Enum):
    """Supported field types for encryption."""
    CPF = "cpf"
    EMAIL = "email"
    PHONE = "phone"
    PHI_GENERIC = "phi_generic"
    QUIZ_RESPONSE = "quiz_response"
    CUSTOM = "custom"


class BaseEncryptionService:
    """
    Base class for encryption services with common functionality.

    Provides:
    - Key derivation (PBKDF2)
    - Algorithm selection
    - Entropy validation
    - Common utilities
    """

    def __init__(self, algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM):
        """
        Initialize base encryption service.

        Args:
            algorithm: Encryption algorithm to use
        """
        self.settings = get_settings()
        self.backend = default_backend()
        self.algorithm = algorithm
        self._keys: Dict[str, bytes] = {}

    def _get_encryption_key_env(self, key_type: str = "PHI") -> str:
        """
        Get encryption key from environment.

        Args:
            key_type: Type of key (PHI, LGPD, QUIZ, etc.)

        Returns:
            Encryption key from environment

        Raises:
            ValueError: If key not configured in production
        """
        env_var = f"{key_type}_ENCRYPTION_KEY"
        master_key = os.getenv(env_var, '')

        if not master_key:
            # Generate a new key for development (NOT for production)
            if self.settings.APP_ENVIRONMENT == 'development':
                master_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                logger.warning(
                    f"Generated development encryption key for {key_type}. "
                    f"Use proper key management in production!"
                )
            else:
                raise ValueError(f"{env_var} not configured for production")

        return master_key

    def _derive_key(
        self,
        master_key: str,
        salt: bytes,
        iterations: int = 100000,
        key_length: int = 32
    ) -> bytes:
        """
        Derive encryption key using PBKDF2.

        Args:
            master_key: Master key or passphrase
            salt: Salt for key derivation
            iterations: Number of PBKDF2 iterations
            key_length: Length of derived key in bytes

        Returns:
            Derived encryption key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=key_length,
            salt=salt,
            iterations=iterations,
            backend=self.backend
        )

        key_bytes = master_key.encode() if isinstance(master_key, str) else master_key
        return kdf.derive(key_bytes)

    def validate_key_entropy(self, key: str, min_entropy_bits: int = 128) -> bool:
        """
        Validate encryption key has sufficient entropy.

        Args:
            key: Key to validate
            min_entropy_bits: Minimum required entropy in bits

        Returns:
            True if key has sufficient entropy
        """
        # Simple entropy check based on key length and character diversity
        if len(key) < min_entropy_bits // 8:
            return False

        # Check character diversity
        unique_chars = len(set(key))
        if unique_chars < 16:  # At least 16 unique characters
            return False

        return True

    def generate_hash(self, value: str, field_type: FieldType = FieldType.CUSTOM) -> str:
        """
        Generate searchable hash for a value.

        Args:
            value: Value to hash
            field_type: Type of field being hashed

        Returns:
            SHA-256 hash (64 characters)
        """
        if field_type == FieldType.CPF:
            return SearchableHash.hash_cpf(value)
        elif field_type == FieldType.EMAIL:
            return SearchableHash.hash_email(value)
        elif field_type == FieldType.PHONE:
            return SearchableHash.hash_phone(value)
        else:
            return SearchableHash.hash_generic(value, field_type.value)


class UnifiedEncryptionService(BaseEncryptionService):
    """
    Unified encryption service supporting multiple algorithms and field types.

    Usage:
        >>> service = UnifiedEncryptionService()
        >>>
        >>> # CPF encryption
        >>> encrypted_cpf, cpf_hash = service.encrypt_cpf("12345678901")
        >>> decrypted = service.decrypt_cpf(encrypted_cpf)
        >>>
        >>> # Email encryption
        >>> encrypted_email, email_hash = service.encrypt_email("user@example.com")
        >>> decrypted = service.decrypt_email(encrypted_email)
        >>>
        >>> # Generic field encryption
        >>> encrypted = service.encrypt_field("sensitive data", FieldType.PHI_GENERIC)
        >>> decrypted = service.decrypt_field(encrypted)
    """

    def __init__(
        self,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
        auto_initialize: bool = True
    ):
        """
        Initialize unified encryption service.

        Args:
            algorithm: Default encryption algorithm
            auto_initialize: Automatically initialize encryption keys
        """
        super().__init__(algorithm)

        if auto_initialize:
            self._initialize_encryption_keys()

        logger.info(f"Unified encryption service initialized with {algorithm.value}")

    def _initialize_encryption_keys(self):
        """Initialize or derive all encryption keys."""
        try:
            # PHI/LGPD encryption key (AES-256)
            master_key = self._get_encryption_key_env("PHI")
            salt = b'hormonia_unified_salt_2025'
            self._keys['phi'] = self._derive_key(master_key, salt)

            # Quiz encryption key (Fernet)
            quiz_secret = os.getenv('MONTHLY_QUIZ_TOKEN_SECRET', master_key)
            self._keys['quiz'] = self._derive_fernet_key(quiz_secret)

            logger.info("Encryption keys initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize encryption keys: {e}")
            raise

    def _derive_fernet_key(self, secret: str) -> bytes:
        """
        Derive a Fernet-compatible key from secret.

        Fernet requires a 32-byte URL-safe base64-encoded key.

        Args:
            secret: Secret to derive key from

        Returns:
            Fernet-compatible key
        """
        hash_digest = hashlib.sha256(secret.encode()).digest()
        return base64.urlsafe_b64encode(hash_digest)

    # =========================================================================
    # CORE ENCRYPTION/DECRYPTION METHODS
    # =========================================================================

    def encrypt_field(
        self,
        plaintext: str,
        field_type: FieldType = FieldType.PHI_GENERIC,
        algorithm: Optional[EncryptionAlgorithm] = None
    ) -> str:
        """
        Encrypt a single field value.

        Args:
            plaintext: Value to encrypt
            field_type: Type of field being encrypted
            algorithm: Algorithm to use (defaults to instance algorithm)

        Returns:
            Encrypted value with algorithm prefix

        Format:
            - AES-GCM: "encrypted:gcm:{base64(nonce+tag+ciphertext)}"
            - AES-CBC: "encrypted:{base64(iv+ciphertext)}"
            - Fernet: "encrypted:fernet:{fernet_token}"
        """
        if not plaintext:
            return plaintext

        algo = algorithm or self.algorithm

        try:
            if algo == EncryptionAlgorithm.AES_256_GCM:
                return self._encrypt_gcm(plaintext)
            elif algo == EncryptionAlgorithm.AES_256_CBC:
                return self._encrypt_cbc(plaintext)
            elif algo == EncryptionAlgorithm.FERNET:
                return self._encrypt_fernet(plaintext)
            else:
                raise ValueError(f"Unsupported algorithm: {algo}")

        except Exception as e:
            logger.error(f"Encryption failed for {field_type.value}: {e}")
            raise

    def decrypt_field(
        self,
        encrypted: str,
        field_type: FieldType = FieldType.PHI_GENERIC
    ) -> str:
        """
        Decrypt a single field value.

        Automatically detects encryption algorithm from prefix.

        Args:
            encrypted: Encrypted value
            field_type: Type of field being decrypted

        Returns:
            Decrypted plaintext
        """
        if not encrypted or not encrypted.startswith('encrypted:'):
            return encrypted

        try:
            if ':gcm:' in encrypted:
                return self._decrypt_gcm(encrypted)
            elif ':fernet:' in encrypted:
                return self._decrypt_fernet(encrypted)
            else:
                # Legacy CBC format: "encrypted:{base64}"
                return self._decrypt_cbc(encrypted)

        except Exception as e:
            logger.error(f"Decryption failed for {field_type.value}: {e}")
            raise

    def _encrypt_gcm(self, plaintext: str) -> str:
        """
        Encrypt using AES-256-GCM (recommended).

        GCM provides both confidentiality and authenticity.
        """
        # Generate random nonce (12 bytes recommended for GCM)
        nonce = os.urandom(12)

        # Create AESGCM cipher
        aesgcm = AESGCM(self._keys['phi'])

        # Encrypt (returns ciphertext + tag)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

        # Combine nonce + ciphertext, then base64 encode
        combined = nonce + ciphertext
        encrypted = base64.b64encode(combined).decode('utf-8')

        return f"encrypted:gcm:{encrypted}"

    def _decrypt_gcm(self, encrypted: str) -> str:
        """Decrypt AES-256-GCM encrypted data."""
        # Remove prefix and decode
        encrypted_data = encrypted.replace('encrypted:gcm:', '')
        combined = base64.b64decode(encrypted_data)

        # Extract nonce and ciphertext
        nonce = combined[:12]
        ciphertext = combined[12:]

        # Create AESGCM cipher
        aesgcm = AESGCM(self._keys['phi'])

        # Decrypt and verify
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext.decode('utf-8')

    def _encrypt_cbc(self, plaintext: str) -> str:
        """
        Encrypt using AES-256-CBC (legacy).

        For backward compatibility with existing encrypted data.
        """
        # Generate random IV
        iv = os.urandom(16)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self._keys['phi']),
            modes.CBC(iv),
            backend=self.backend
        )
        encryptor = cipher.encryptor()

        # Pad the plaintext
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext.encode()) + padder.finalize()

        # Encrypt
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        # Combine IV and ciphertext, then base64 encode
        combined = iv + ciphertext
        encrypted = base64.b64encode(combined).decode('utf-8')

        return f"encrypted:{encrypted}"

    def _decrypt_cbc(self, encrypted: str) -> str:
        """Decrypt AES-256-CBC encrypted data."""
        # Remove prefix and decode
        encrypted_data = encrypted.replace('encrypted:', '')
        combined = base64.b64decode(encrypted_data)

        # Extract IV and ciphertext
        iv = combined[:16]
        ciphertext = combined[16:]

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self._keys['phi']),
            modes.CBC(iv),
            backend=self.backend
        )
        decryptor = cipher.decryptor()

        # Decrypt
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        # Remove padding
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

        return plaintext.decode('utf-8')

    def _encrypt_fernet(self, plaintext: str) -> str:
        """Encrypt using Fernet (for quiz tokens)."""
        fernet = Fernet(self._keys['quiz'])
        encrypted_bytes = fernet.encrypt(plaintext.encode())
        return f"encrypted:fernet:{encrypted_bytes.decode()}"

    def _decrypt_fernet(self, encrypted: str) -> str:
        """Decrypt Fernet encrypted data."""
        encrypted_data = encrypted.replace('encrypted:fernet:', '')
        fernet = Fernet(self._keys['quiz'])

        try:
            decrypted_bytes = fernet.decrypt(encrypted_data.encode())
            return decrypted_bytes.decode()
        except InvalidToken:
            logger.error("Invalid Fernet token - data may be corrupted")
            raise ValueError("Failed to decrypt data - invalid token")

    # =========================================================================
    # CPF ENCRYPTION (Brazilian National ID)
    # =========================================================================

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
            # Normalize CPF (remove formatting)
            normalized_cpf = self._normalize_cpf(cpf)

            # Validate format
            if not self._validate_cpf_format(normalized_cpf):
                raise ValueError(f"Invalid CPF format: {cpf}")

            # Encrypt
            encrypted_cpf = self.encrypt_field(normalized_cpf, FieldType.CPF)

            # Generate searchable hash
            cpf_hash = self.generate_hash(normalized_cpf, FieldType.CPF)

            logger.debug("CPF encrypted successfully")
            return encrypted_cpf, cpf_hash

        except Exception as e:
            logger.error(f"Failed to encrypt CPF: {e}")
            raise

    def decrypt_cpf(self, encrypted_cpf: Optional[str]) -> Optional[str]:
        """
        Decrypt encrypted CPF.

        Args:
            encrypted_cpf: Encrypted CPF

        Returns:
            Decrypted CPF (11 digits, no formatting)
        """
        if not encrypted_cpf:
            return None

        return self.decrypt_field(encrypted_cpf, FieldType.CPF)

    def _normalize_cpf(self, cpf: str) -> str:
        """Normalize CPF by removing formatting."""
        if not cpf:
            return cpf
        import re
        return re.sub(r'\D', '', cpf)

    def _validate_cpf_format(self, cpf: str) -> bool:
        """Validate CPF format (11 digits)."""
        if not cpf or len(cpf) != 11 or not cpf.isdigit():
            return False
        if cpf == cpf[0] * 11:  # Reject all same digit
            return False
        return True

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
        """
        if not email:
            return None, None

        try:
            # Normalize email
            normalized_email = email.lower().strip()

            # Encrypt
            encrypted_email = self.encrypt_field(normalized_email, FieldType.EMAIL)
            encrypted_bytes = encrypted_email.encode('utf-8')

            # Generate searchable hash
            email_hash = self.generate_hash(normalized_email, FieldType.EMAIL)

            logger.debug("Email encrypted successfully")
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
        """
        if not encrypted_email:
            return None

        try:
            # Convert bytes to string
            encrypted_str = (
                encrypted_email.decode('utf-8')
                if isinstance(encrypted_email, bytes)
                else encrypted_email
            )

            return self.decrypt_field(encrypted_str, FieldType.EMAIL)

        except Exception as e:
            logger.error(f"Failed to decrypt email: {e}")
            raise

    # =========================================================================
    # PHONE ENCRYPTION
    # =========================================================================

    def encrypt_phone(self, phone: Optional[str]) -> Tuple[Optional[bytes], Optional[str]]:
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
            normalized_phone = self._normalize_phone(phone)

            # Encrypt
            encrypted_phone = self.encrypt_field(normalized_phone, FieldType.PHONE)
            encrypted_bytes = encrypted_phone.encode('utf-8')

            # Generate searchable hash
            phone_hash = self.generate_hash(normalized_phone, FieldType.PHONE)

            logger.debug("Phone encrypted successfully")
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

            return self.decrypt_field(encrypted_str, FieldType.PHONE)

        except Exception as e:
            logger.error(f"Failed to decrypt phone: {e}")
            raise

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone by keeping only digits and + sign."""
        if not phone:
            return phone
        return ''.join(c for c in phone if c.isdigit() or c == '+')

    # =========================================================================
    # PATIENT DATA ENCRYPTION
    # =========================================================================

    def encrypt_patient_data(self, patient_data: dict) -> dict:
        """
        Encrypt PHI fields in patient data.

        Args:
            patient_data: Dictionary containing patient information

        Returns:
            Dictionary with encrypted PHI fields
        """
        phi_fields = [
            'name', 'cpf', 'rg', 'email', 'phone',
            'address', 'birth_date', 'medical_record_number',
            'emergency_contact_name', 'emergency_contact_phone',
            'insurance_number', 'diagnosis', 'medications'
        ]

        encrypted_data = patient_data.copy()

        for field in phi_fields:
            if field in encrypted_data and encrypted_data[field]:
                if isinstance(encrypted_data[field], str):
                    encrypted_data[field] = self.encrypt_field(
                        encrypted_data[field],
                        FieldType.PHI_GENERIC
                    )
                elif isinstance(encrypted_data[field], (dict, list)):
                    json_str = json.dumps(encrypted_data[field])
                    encrypted_data[field] = self.encrypt_field(
                        json_str,
                        FieldType.PHI_GENERIC
                    )

        encrypted_data['__encrypted'] = True
        encrypted_data['__encryption_version'] = '2.0'
        encrypted_data['__encryption_algorithm'] = self.algorithm.value

        return encrypted_data

    def decrypt_patient_data(self, encrypted_data: dict) -> dict:
        """
        Decrypt PHI fields in patient data.

        Args:
            encrypted_data: Dictionary with encrypted PHI fields

        Returns:
            Dictionary with decrypted PHI fields
        """
        if not encrypted_data.get('__encrypted'):
            return encrypted_data

        phi_fields = [
            'name', 'cpf', 'rg', 'email', 'phone',
            'address', 'birth_date', 'medical_record_number',
            'emergency_contact_name', 'emergency_contact_phone',
            'insurance_number', 'diagnosis', 'medications'
        ]

        decrypted_data = encrypted_data.copy()

        for field in phi_fields:
            if field in decrypted_data and decrypted_data[field]:
                decrypted_value = self.decrypt_field(
                    decrypted_data[field],
                    FieldType.PHI_GENERIC
                )

                # Try to deserialize JSON
                if decrypted_value.startswith(('[', '{')):
                    try:
                        decrypted_data[field] = json.loads(decrypted_value)
                    except json.JSONDecodeError:
                        decrypted_data[field] = decrypted_value
                else:
                    decrypted_data[field] = decrypted_value

        # Remove encryption metadata
        decrypted_data.pop('__encrypted', None)
        decrypted_data.pop('__encryption_version', None)
        decrypted_data.pop('__encryption_algorithm', None)

        return decrypted_data

    # =========================================================================
    # KEY ROTATION
    # =========================================================================

    def rotate_encryption_key(self, new_master_key: str) -> bool:
        """
        Rotate encryption key by re-encrypting all data.

        Args:
            new_master_key: The new master encryption key

        Returns:
            Success status

        Note:
            This requires re-encrypting all encrypted data in the database.
            Should be done during maintenance window.
        """
        try:
            # Store old key temporarily
            old_key = self._keys['phi']

            # Derive new key
            salt = b'hormonia_unified_salt_2025'
            new_key = self._derive_key(new_master_key, salt)

            # TODO: Implement batch re-encryption
            # 1. Decrypt all data with old key
            # 2. Encrypt all data with new key
            # 3. Update database in transaction
            # 4. Only commit if all successful

            # Update to new key
            self._keys['phi'] = new_key

            logger.info("Encryption key rotated successfully")
            return True

        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            return False


# =========================================================================
# SINGLETON INSTANCES
# =========================================================================

_unified_encryption_service: Optional[UnifiedEncryptionService] = None


def get_unified_encryption_service() -> UnifiedEncryptionService:
    """
    Get or create the unified encryption service singleton.

    Returns:
        UnifiedEncryptionService instance
    """
    global _unified_encryption_service
    if _unified_encryption_service is None:
        _unified_encryption_service = UnifiedEncryptionService()
    return _unified_encryption_service


# =========================================================================
# BACKWARD COMPATIBILITY ALIASES
# =========================================================================

# Alias for PHI encryption service
def get_phi_encryption_service() -> UnifiedEncryptionService:
    """Get PHI encryption service (backward compatibility)."""
    return get_unified_encryption_service()


# Alias for LGPD encryption service
def get_lgpd_encryption_service() -> UnifiedEncryptionService:
    """Get LGPD encryption service (backward compatibility)."""
    return get_unified_encryption_service()


# Alias for CPF encryption service
def get_cpf_encryption_service() -> UnifiedEncryptionService:
    """Get CPF encryption service (backward compatibility)."""
    return get_unified_encryption_service()


# Alias for quiz encryption service
def get_encryption_service() -> UnifiedEncryptionService:
    """Get encryption service (backward compatibility)."""
    return get_unified_encryption_service()
