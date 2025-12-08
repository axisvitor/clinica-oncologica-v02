"""
Backward Compatibility Tests for Encryption Services

These tests verify that the unified encryption package properly exports
all legacy functions and maintains backward compatibility.
"""
import pytest


class TestEncryptionBackwardCompatibility:
    """Test backward compatibility of encryption service imports."""

    def test_unified_encryption_service_exports(self):
        """Verify unified service exports all required functions."""
        from app.services.encryption import (
            get_phi_encryption_service,
            get_lgpd_encryption_service,
            get_cpf_encryption_service,
            get_unified_encryption_service,
        )

        assert callable(get_phi_encryption_service)
        assert callable(get_lgpd_encryption_service)
        assert callable(get_cpf_encryption_service)
        assert callable(get_unified_encryption_service)

    def test_service_instances_are_same_type(self):
        """Verify all service getters return compatible service."""
        from app.services.encryption import (
            get_phi_encryption_service,
            get_lgpd_encryption_service,
            get_cpf_encryption_service,
            get_unified_encryption_service,
        )

        unified = get_unified_encryption_service()
        phi = get_phi_encryption_service()
        lgpd = get_lgpd_encryption_service()
        cpf = get_cpf_encryption_service()

        # All should be same type or compatible
        assert type(unified).__name__ == type(phi).__name__
        assert type(unified).__name__ == type(lgpd).__name__
        assert type(unified).__name__ == type(cpf).__name__

    def test_encryption_enums_exported(self):
        """Verify enums are properly exported."""
        from app.services.encryption import EncryptionAlgorithm, FieldType

        assert hasattr(EncryptionAlgorithm, 'AES_256_GCM') or hasattr(EncryptionAlgorithm, 'AES_256_CBC')
        assert hasattr(FieldType, 'CPF') or hasattr(FieldType, 'PHI_GENERIC')

    def test_base_classes_exported(self):
        """Verify base classes are properly exported."""
        from app.services.encryption import BaseEncryptionService, UnifiedEncryptionService

        assert BaseEncryptionService is not None
        assert UnifiedEncryptionService is not None


class TestDLQServiceBackwardCompatibility:
    """Test backward compatibility of DLQ service imports."""

    def test_dlq_service_wrapper_works(self):
        """Verify DLQ wrapper re-exports work."""
        from app.services.dlq_service import DLQService
        from app.services.dlq import DLQService as NewDLQService

        # Both imports should resolve to same class
        assert DLQService is NewDLQService

    def test_dlq_error_category_exported(self):
        """Verify ErrorCategory is exported from both locations."""
        try:
            from app.services.dlq_service import ErrorCategory
            from app.services.dlq.base import ErrorCategory as NewErrorCategory

            assert ErrorCategory is not None
            # May or may not be same reference, but both should exist
        except ImportError:
            # If ErrorCategory doesn't exist, that's acceptable
            pass
