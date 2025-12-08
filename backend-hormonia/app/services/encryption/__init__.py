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
"""

from typing import Optional

from .types import EncryptionAlgorithm, FieldType
from .service import UnifiedEncryptionService

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


__all__ = [
    # Types
    'EncryptionAlgorithm',
    'FieldType',

    # Service
    'UnifiedEncryptionService',
    'get_unified_encryption_service',

    # Backward compatibility
    'get_phi_encryption_service',
    'get_lgpd_encryption_service',
    'get_cpf_encryption_service',
    'get_encryption_service',
]
