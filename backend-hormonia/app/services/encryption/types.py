"""
Encryption service type definitions.
"""

from enum import Enum


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
