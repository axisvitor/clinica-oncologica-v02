"""
Backward Compatibility Tests for Encryption Services

These tests verify that the unified encryption package properly exports
all legacy functions and maintains backward compatibility.
"""


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
        """Verify canonical encryption service/base classes are importable."""
        from app.services.encryption import UnifiedEncryptionService
        from app.services.encryption.service import BaseEncryptionService

        assert BaseEncryptionService is not None
        assert UnifiedEncryptionService is not None
        assert issubclass(UnifiedEncryptionService, BaseEncryptionService)


class TestDLQServiceCanonicalImports:
    """Test canonical DLQ service imports."""

    def test_dlq_service_exported_from_canonical_package(self):
        """Verify package export matches canonical service implementation."""
        from app.services.dlq import DLQService
        from app.services.dlq.service import DLQService as CanonicalDLQService

        assert DLQService is CanonicalDLQService

    def test_dlq_error_category_exported_from_canonical_modules(self):
        """Verify ErrorCategory is consistently exported by canonical modules."""
        from app.services.dlq import ErrorCategory
        from app.services.dlq.base import ErrorCategory as BaseErrorCategory

        assert ErrorCategory is BaseErrorCategory
