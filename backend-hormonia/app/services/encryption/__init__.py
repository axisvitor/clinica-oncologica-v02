"""
Unified Encryption Services Package

This package consolidates all encryption services into a single, unified service
that supports multiple algorithms and field types.

Main Classes:
- UnifiedEncryptionService: Main encryption service
- BaseEncryptionService: Base class with common functionality
- EncryptionAlgorithm: Enum of supported algorithms
- FieldType: Enum of supported field types

Quick Start:
    >>> from app.services.encryption import get_unified_encryption_service
    >>>
    >>> service = get_unified_encryption_service()
    >>>
    >>> # Encrypt CPF
    >>> encrypted_cpf, cpf_hash = service.encrypt_cpf("12345678901")
    >>> decrypted = service.decrypt_cpf(encrypted_cpf)
    >>>
    >>> # Encrypt email
    >>> encrypted_email, email_hash = service.encrypt_email("user@example.com")
    >>> decrypted = service.decrypt_email(encrypted_email)

Backward Compatibility:
    The following imports maintain backward compatibility with existing code:

    >>> from app.services.encryption import get_phi_encryption_service
    >>> from app.services.encryption import get_lgpd_encryption_service
    >>> from app.services.encryption import get_cpf_encryption_service
    >>> from app.services.encryption import get_encryption_service

    All these functions return the same UnifiedEncryptionService instance.

Migration Guide:
    Old code:
        from app.services.phi_encryption_service import get_phi_encryption_service
        service = get_phi_encryption_service()
        encrypted = service.encrypt_field(data)

    New code (recommended):
        from app.services.encryption import get_unified_encryption_service
        service = get_unified_encryption_service()
        encrypted = service.encrypt_field(data, FieldType.PHI_GENERIC)

    Or keep old code (backward compatible):
        from app.services.encryption import get_phi_encryption_service
        service = get_phi_encryption_service()
        encrypted = service.encrypt_field(data)
"""

from .unified_encryption_service import (
    # Main classes
    BaseEncryptionService,
    UnifiedEncryptionService,

    # Enums
    EncryptionAlgorithm,
    FieldType,

    # Main service getter
    get_unified_encryption_service,

    # Backward compatibility aliases
    get_phi_encryption_service,
    get_lgpd_encryption_service,
    get_cpf_encryption_service,
    get_encryption_service,
)

# Key management (existing)
try:
    from app.services.encryption.key_manager import KeyManagementService, KeyNotFoundError, AWSError
    _has_key_manager = True
except ImportError:
    _has_key_manager = False

__all__ = [
    # Main classes
    "BaseEncryptionService",
    "UnifiedEncryptionService",

    # Enums
    "EncryptionAlgorithm",
    "FieldType",

    # Service getters
    "get_unified_encryption_service",

    # Backward compatibility
    "get_phi_encryption_service",
    "get_lgpd_encryption_service",
    "get_cpf_encryption_service",
    "get_encryption_service",
]

# Add key manager to exports if available
if _has_key_manager:
    __all__.extend(["KeyManagementService", "KeyNotFoundError", "AWSError"])

# Package metadata
__version__ = "2.0.0"
__author__ = "Hormonia Development Team"
__description__ = "Unified encryption services for healthcare compliance (HIPAA, LGPD)"
