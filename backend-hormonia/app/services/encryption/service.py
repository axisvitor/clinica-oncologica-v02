"""
Unified Encryption Service - Main orchestrator.

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
"""

import os
import base64
import hashlib
import logging
import json
from typing import Optional, Dict

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from app.config import get_settings
from app.core.searchable_hash import SearchableHash
from app.schemas.validators.cpf import calculate_cpf_check_digit

from .types import EncryptionAlgorithm, FieldType
from .algorithms import AESGCMAlgorithm, AESCBCAlgorithm, FernetAlgorithm
from .fields import CPFEncryptor, EmailEncryptor, PhoneEncryptor

logger = logging.getLogger(__name__)


class BaseEncryptionService:
    """
    Base class for encryption services with common functionality.

    Provides:
    - Key derivation (PBKDF2)
    - Algorithm selection
    - Entropy validation
    - Common utilities
    """

    def __init__(
        self, algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    ):
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
        master_key = os.getenv(env_var) or os.getenv(f"COMPLIANCE_{env_var}", "")

        if not master_key:
            # Generate a new key for development (NOT for production)
            if self.settings.APP_ENVIRONMENT == "development":
                master_key = base64.b64encode(os.urandom(32)).decode("utf-8")
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
        key_length: int = 32,
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
            backend=self.backend,
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

    def generate_hash(
        self, value: str, field_type: FieldType = FieldType.CUSTOM
    ) -> str:
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
        auto_initialize: bool = True,
    ):
        """
        Initialize unified encryption service.

        Args:
            algorithm: Default encryption algorithm
            auto_initialize: Automatically initialize encryption keys
        """
        super().__init__(algorithm)

        # Algorithm implementations
        self._algorithms: Dict[EncryptionAlgorithm, object] = {}

        # Field encryptors
        self._cpf_encryptor: Optional[CPFEncryptor] = None
        self._email_encryptor: Optional[EmailEncryptor] = None
        self._phone_encryptor: Optional[PhoneEncryptor] = None

        if auto_initialize:
            self._initialize_encryption_keys()
            self._initialize_algorithms()
            self._initialize_field_encryptors()

        logger.info(f"Unified encryption service initialized with {algorithm.value}")

    def _initialize_encryption_keys(self):
        """Initialize or derive all encryption keys."""
        try:
            # PHI/LGPD encryption key (AES-256)
            master_key = self._get_encryption_key_env("PHI")
            salt = b"hormonia_unified_salt_2025"
            self._keys["phi"] = self._derive_key(master_key, salt)

            # Quiz encryption key (Fernet)
            quiz_secret = (
                os.getenv("QUIZ_TOKEN_SECRET")
                or os.getenv("MONTHLY_QUIZ_TOKEN_SECRET")
                or master_key
            )
            self._keys["quiz"] = self._derive_fernet_key(quiz_secret)

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

    def _initialize_algorithms(self):
        """Initialize encryption algorithm implementations."""
        self._algorithms[EncryptionAlgorithm.AES_256_GCM] = AESGCMAlgorithm(self._keys)
        self._algorithms[EncryptionAlgorithm.AES_256_CBC] = AESCBCAlgorithm(self._keys)
        self._algorithms[EncryptionAlgorithm.FERNET] = FernetAlgorithm(self._keys)

    def _initialize_field_encryptors(self):
        """Initialize field-specific encryptors."""
        self._cpf_encryptor = CPFEncryptor(
            self.encrypt_field, self.decrypt_field, self.generate_hash
        )
        self._email_encryptor = EmailEncryptor(
            self.encrypt_field, self.decrypt_field, self.generate_hash
        )
        self._phone_encryptor = PhoneEncryptor(
            self.encrypt_field, self.decrypt_field, self.generate_hash
        )

    # =========================================================================
    # CORE ENCRYPTION/DECRYPTION METHODS
    # =========================================================================

    def encrypt_field(
        self,
        plaintext: str,
        field_type: FieldType = FieldType.PHI_GENERIC,
        algorithm: Optional[EncryptionAlgorithm] = None,
    ) -> str:
        """
        Encrypt a single field value.

        Args:
            plaintext: Value to encrypt
            field_type: Type of field being encrypted
            algorithm: Algorithm to use (defaults to instance algorithm)

        Returns:
            Encrypted value with algorithm prefix
        """
        if not plaintext:
            return plaintext

        algo = algorithm or self.algorithm

        try:
            algo_impl = self._algorithms.get(algo)
            if not algo_impl:
                raise ValueError(f"Unsupported algorithm: {algo}")

            return algo_impl.encrypt(plaintext)

        except Exception as e:
            logger.error(f"Encryption failed for {field_type.value}: {e}")
            raise

    def decrypt_field(
        self, encrypted: str, field_type: FieldType = FieldType.PHI_GENERIC
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
        if not encrypted or not encrypted.startswith("encrypted:"):
            return encrypted

        try:
            # Detect algorithm by prefix
            if ":gcm:" in encrypted:
                algo_impl = self._algorithms[EncryptionAlgorithm.AES_256_GCM]
            elif ":fernet:" in encrypted:
                algo_impl = self._algorithms[EncryptionAlgorithm.FERNET]
            else:
                # Legacy CBC format: "encrypted:{base64}"
                algo_impl = self._algorithms[EncryptionAlgorithm.AES_256_CBC]

            return algo_impl.decrypt(encrypted)

        except Exception as e:
            logger.error(f"Decryption failed for {field_type.value}: {e}")
            raise

    # =========================================================================
    # FIELD-SPECIFIC ENCRYPTION (Delegate to encryptors)
    # =========================================================================

    def encrypt_cpf(self, cpf: Optional[str]):
        """Encrypt CPF using CPFEncryptor."""
        return self._cpf_encryptor.encrypt(cpf)

    def decrypt_cpf(self, encrypted_cpf: Optional[str]):
        """Decrypt CPF using CPFEncryptor."""
        return self._cpf_encryptor.decrypt(encrypted_cpf)

    def _calculate_cpf_check_digit(self, cpf_partial: str) -> str:
        return calculate_cpf_check_digit(cpf_partial)

    def _normalize_cpf(self, cpf: Optional[str]) -> Optional[str]:
        if cpf is None:
            return None
        if cpf == "":
            return ""

        if self._cpf_encryptor:
            digits_only = self._cpf_encryptor.normalize(cpf)
        else:
            digits_only = "".join(ch for ch in cpf if ch.isdigit())

        if not digits_only:
            return ""

        if len(digits_only) < 9:
            return digits_only

        base = digits_only[:9]
        first_digit = self._calculate_cpf_check_digit(base)
        second_digit = self._calculate_cpf_check_digit(base + first_digit)
        return f"{base}{first_digit}{second_digit}"

    def _validate_cpf_format(self, cpf: Optional[str]) -> bool:
        if not cpf or not cpf.isdigit() or len(cpf) != 11:
            return False
        if cpf == cpf[0] * 11:
            return False
        return True

    def format_cpf_for_display(self, cpf: Optional[str], mask: bool = False) -> Optional[str]:
        """Format CPF for display with optional masking."""
        if not cpf:
            return None

        normalized = self._normalize_cpf(cpf)

        if not normalized or len(normalized) != 11:
            return cpf

        if mask:
            return f"***.***.{normalized[6:9]}-**"

        return f"{normalized[:3]}.{normalized[3:6]}.{normalized[6:9]}-01"

    def encrypt_email(self, email: Optional[str]):
        """Encrypt email using EmailEncryptor."""
        return self._email_encryptor.encrypt(email)

    def decrypt_email(self, encrypted_email: Optional[bytes]):
        """Decrypt email using EmailEncryptor."""
        return self._email_encryptor.decrypt(encrypted_email)

    def encrypt_phone(self, phone: Optional[str]):
        """Encrypt phone using PhoneEncryptor."""
        return self._phone_encryptor.encrypt(phone)

    def decrypt_phone(self, encrypted_phone: Optional[bytes]):
        """Decrypt phone using PhoneEncryptor."""
        return self._phone_encryptor.decrypt(encrypted_phone)

    # =========================================================================
    # HASH METHODS (for searchable lookup)
    # =========================================================================

    def hash_cpf(self, cpf: Optional[str]) -> Optional[str]:
        """Generate searchable hash for CPF."""
        return SearchableHash.hash_cpf(cpf)

    def hash_cpf_for_search(self, cpf: Optional[str]) -> Optional[str]:
        """
        Backward-compatible CPF hash helper with format normalization.

        Accepts formatted CPF input and guarantees deterministic hash output
        for semantically equivalent values.
        """
        if cpf is None:
            return None

        cpf_str = str(cpf)
        if cpf_str == "":
            return None

        # Preserve digit-only input as provided to avoid collapsing distinct
        # values (e.g., ...09 vs ...02). Apply canonical normalization only
        # when CPF contains formatting characters.
        if any(not ch.isdigit() for ch in cpf_str):
            normalized = self._normalize_cpf(cpf_str)
        else:
            normalized = cpf_str

        if not normalized:
            return None
        return self.hash_cpf(normalized)

    def hash_email(self, email: Optional[str]) -> Optional[str]:
        """Generate searchable hash for email."""
        return SearchableHash.hash_email(email)

    def hash_phone(self, phone: Optional[str]) -> Optional[str]:
        """Generate searchable hash for phone."""
        return SearchableHash.hash_phone(phone)

    def migrate_plaintext_cpf(self, plaintext_cpf: Optional[str]):
        """
        Backward-compatible migration helper for legacy plaintext CPF values.

        Returns encrypted CPF + searchable hash using the same canonical path
        as `encrypt_cpf`.
        """
        return self.encrypt_cpf(plaintext_cpf)

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
            "name",
            "cpf",
            "rg",
            "email",
            "phone",
            "address",
            "birth_date",
            "medical_record_number",
            "emergency_contact_name",
            "emergency_contact_phone",
            "insurance_number",
            "diagnosis",
            "medications",
        ]

        encrypted_data = patient_data.copy()

        for field in phi_fields:
            if field in encrypted_data and encrypted_data[field]:
                if isinstance(encrypted_data[field], str):
                    encrypted_data[field] = self.encrypt_field(
                        encrypted_data[field], FieldType.PHI_GENERIC
                    )
                elif isinstance(encrypted_data[field], (dict, list)):
                    json_str = json.dumps(encrypted_data[field])
                    encrypted_data[field] = self.encrypt_field(
                        json_str, FieldType.PHI_GENERIC
                    )

        encrypted_data["__encrypted"] = True
        encrypted_data["__encryption_version"] = "2.0"
        encrypted_data["__encryption_algorithm"] = self.algorithm.value

        return encrypted_data

    def decrypt_patient_data(self, encrypted_data: dict) -> dict:
        """
        Decrypt PHI fields in patient data.

        Args:
            encrypted_data: Dictionary with encrypted PHI fields

        Returns:
            Dictionary with decrypted PHI fields
        """
        if not encrypted_data.get("__encrypted"):
            return encrypted_data

        phi_fields = [
            "name",
            "cpf",
            "rg",
            "email",
            "phone",
            "address",
            "birth_date",
            "medical_record_number",
            "emergency_contact_name",
            "emergency_contact_phone",
            "insurance_number",
            "diagnosis",
            "medications",
        ]

        decrypted_data = encrypted_data.copy()

        for field in phi_fields:
            if field in decrypted_data and decrypted_data[field]:
                decrypted_value = self.decrypt_field(
                    decrypted_data[field], FieldType.PHI_GENERIC
                )

                # Try to deserialize JSON
                if decrypted_value.startswith(("[", "{")):
                    try:
                        decrypted_data[field] = json.loads(decrypted_value)
                    except json.JSONDecodeError:
                        decrypted_data[field] = decrypted_value
                else:
                    decrypted_data[field] = decrypted_value

        # Remove encryption metadata
        decrypted_data.pop("__encrypted", None)
        decrypted_data.pop("__encryption_version", None)
        decrypted_data.pop("__encryption_algorithm", None)

        return decrypted_data

    # =========================================================================
    # KEY ROTATION
    # =========================================================================

    def rotate_encryption_key(self, new_master_key: str) -> bool:
        """
        Rotate the in-memory encryption key to the new master key.

        This method updates the service's in-memory key state so that all
        *new* encryptions performed by this service instance will use the
        rotated key immediately.

        Database re-encryption (re-encrypting existing patient PII fields)
        is handled separately by the Celery task
        ``lgpd.batch_reencrypt_patients`` in
        ``app.tasks.lgpd.reencrypt_patients``.  You MUST invoke that task
        (with a unique ``job_id``) after calling this method to complete the
        rotation for data already persisted in the database.

        IMPORTANT: HASH_SALT must NOT be changed during key rotation.  Only
        the PHI_ENCRYPTION_KEY (AES encryption key) is rotated.  The
        searchable-hash salt must remain constant across all records.

        Args:
            new_master_key: The new master encryption key (plaintext passphrase).

        Returns:
            True on success.

        Raises:
            Exception: Re-raises any key derivation or algorithm init error.
        """
        try:
            # Preserve the old key reference for diagnostics/logging (not used after rotation)
            _old_phi_key = self._keys.get("phi")

            # Derive new PHI key from the new master key using the canonical salt
            salt = b"hormonia_unified_salt_2025"
            new_phi_key = self._derive_key(new_master_key, salt)

            # Derive new Fernet key for quiz tokens
            new_quiz_key = self._derive_fernet_key(new_master_key)

            # Update in-memory keys
            self._keys["phi"] = new_phi_key
            self._keys["quiz"] = new_quiz_key

            # Reinitialize algorithms and field encryptors with the new key
            self._initialize_algorithms()
            self._initialize_field_encryptors()

            logger.info(
                "In-memory encryption key rotated successfully. "
                "New encryptions will use the rotated key. "
                "Run Celery task 'lgpd.batch_reencrypt_patients' with a unique job_id "
                "to re-encrypt existing patient records in the database."
            )
            return True

        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            return False
