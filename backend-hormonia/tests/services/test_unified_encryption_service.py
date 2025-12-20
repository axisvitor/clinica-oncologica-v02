"""
Tests for Unified Encryption Service

Tests the consolidated encryption service that replaces:
- PHIEncryptionService
- LGPDEncryptionService
- CPFEncryptionService
- EncryptionService (quiz)
"""

import pytest
import os
from unittest.mock import patch

from app.services.encryption import (
    UnifiedEncryptionService,
    get_unified_encryption_service,
    EncryptionAlgorithm,
    FieldType,
    # Backward compatibility
    get_phi_encryption_service,
    get_lgpd_encryption_service,
    get_cpf_encryption_service,
    get_encryption_service,
)


class TestBackwardCompatibility:
    """Test that old service getters return the same unified service."""

    def test_all_getters_return_same_instance(self):
        """All service getters should return the same singleton instance."""
        phi_service = get_phi_encryption_service()
        lgpd_service = get_lgpd_encryption_service()
        cpf_service = get_cpf_encryption_service()
        quiz_service = get_encryption_service()
        unified_service = get_unified_encryption_service()

        # All should be the same instance
        assert phi_service is lgpd_service
        assert lgpd_service is cpf_service
        assert cpf_service is quiz_service
        assert quiz_service is unified_service

    def test_backward_compatible_api(self):
        """Old API methods should still work."""
        service = get_phi_encryption_service()

        # Test encrypt_field (PHI service API)
        encrypted = service.encrypt_field("test data")
        assert encrypted.startswith("encrypted:")

        decrypted = service.decrypt_field(encrypted)
        assert decrypted == "test data"


class TestCPFEncryption:
    """Test CPF encryption functionality."""

    @pytest.fixture
    def service(self):
        return get_unified_encryption_service()

    def test_encrypt_cpf_valid(self, service):
        """Should encrypt valid CPF and generate hash."""
        cpf = "12345678909"
        encrypted_cpf, cpf_hash = service.encrypt_cpf(cpf)

        assert encrypted_cpf is not None
        assert encrypted_cpf.startswith("encrypted:")
        assert cpf_hash is not None
        assert len(cpf_hash) == 64  # SHA-256 hash

    def test_encrypt_cpf_with_formatting(self, service):
        """Should normalize CPF with formatting."""
        cpf_formatted = "123.456.789-01"
        encrypted_cpf, cpf_hash = service.encrypt_cpf(cpf_formatted)

        assert encrypted_cpf is not None

        # Decrypt should return normalized CPF (no formatting)
        decrypted = service.decrypt_cpf(encrypted_cpf)
        assert decrypted == "12345678909"

    def test_encrypt_cpf_invalid(self, service):
        """Should reject invalid CPF format."""
        with pytest.raises(ValueError, match="Invalid CPF format"):
            service.encrypt_cpf("123")  # Too short

        with pytest.raises(ValueError, match="Invalid CPF format"):
            service.encrypt_cpf("11111111111")  # All same digit

    def test_encrypt_cpf_none(self, service):
        """Should handle None CPF."""
        encrypted_cpf, cpf_hash = service.encrypt_cpf(None)
        assert encrypted_cpf is None
        assert cpf_hash is None

    def test_decrypt_cpf(self, service):
        """Should decrypt CPF correctly."""
        cpf = "12345678909"
        encrypted_cpf, _ = service.encrypt_cpf(cpf)
        decrypted_cpf = service.decrypt_cpf(encrypted_cpf)

        assert decrypted_cpf == cpf

    def test_hash_cpf_deterministic(self, service):
        """CPF hash should be deterministic."""
        cpf = "12345678909"
        _, hash1 = service.encrypt_cpf(cpf)
        _, hash2 = service.encrypt_cpf(cpf)

        assert hash1 == hash2

    def test_hash_cpf_normalization(self, service):
        """CPF hash should be same regardless of formatting."""
        cpf_plain = "12345678909"
        cpf_formatted = "123.456.789-01"

        _, hash1 = service.encrypt_cpf(cpf_plain)
        _, hash2 = service.encrypt_cpf(cpf_formatted)

        assert hash1 == hash2


class TestEmailEncryption:
    """Test email encryption functionality."""

    @pytest.fixture
    def service(self):
        return get_unified_encryption_service()

    def test_encrypt_email_valid(self, service):
        """Should encrypt valid email and generate hash."""
        email = "user@example.com"
        encrypted_email, email_hash = service.encrypt_email(email)

        assert encrypted_email is not None
        assert email_hash is not None
        assert len(email_hash) == 64  # SHA-256 hash

    def test_encrypt_email_normalization(self, service):
        """Should normalize email to lowercase."""
        email_mixed = "User@Example.COM"
        encrypted_email, email_hash = service.encrypt_email(email_mixed)

        decrypted = service.decrypt_email(encrypted_email)
        assert decrypted == "user@example.com"

    def test_encrypt_email_none(self, service):
        """Should handle None email."""
        encrypted_email, email_hash = service.encrypt_email(None)
        assert encrypted_email is None
        assert email_hash is None

    def test_decrypt_email(self, service):
        """Should decrypt email correctly."""
        email = "test@domain.com"
        encrypted_email, _ = service.encrypt_email(email)
        decrypted_email = service.decrypt_email(encrypted_email)

        assert decrypted_email == email

    def test_email_bytes_handling(self, service):
        """Should handle email as bytes (for LargeBinary storage)."""
        email = "test@example.com"
        encrypted_bytes, _ = service.encrypt_email(email)

        # encrypted_bytes should be bytes
        assert isinstance(encrypted_bytes, bytes)

        # Should decrypt from bytes
        decrypted = service.decrypt_email(encrypted_bytes)
        assert decrypted == email

    def test_hash_email_case_insensitive(self, service):
        """Email hash should be case-insensitive."""
        email1 = "User@Example.com"
        email2 = "user@example.com"

        _, hash1 = service.encrypt_email(email1)
        _, hash2 = service.encrypt_email(email2)

        assert hash1 == hash2


class TestPhoneEncryption:
    """Test phone encryption functionality."""

    @pytest.fixture
    def service(self):
        return get_unified_encryption_service()

    def test_encrypt_phone_valid(self, service):
        """Should encrypt valid phone and generate hash."""
        phone = "+5511999999999"
        encrypted_phone, phone_hash = service.encrypt_phone(phone)

        assert encrypted_phone is not None
        assert phone_hash is not None
        assert len(phone_hash) == 64

    def test_encrypt_phone_normalization(self, service):
        """Should normalize phone (remove formatting)."""
        phone_formatted = "+55 (11) 99999-9999"
        encrypted_phone, _ = service.encrypt_phone(phone_formatted)

        decrypted = service.decrypt_phone(encrypted_phone)
        assert decrypted == "+5511999999999"

    def test_encrypt_phone_none(self, service):
        """Should handle None phone."""
        encrypted_phone, phone_hash = service.encrypt_phone(None)
        assert encrypted_phone is None
        assert phone_hash is None

    def test_decrypt_phone(self, service):
        """Should decrypt phone correctly."""
        phone = "+5521987654321"
        encrypted_phone, _ = service.encrypt_phone(phone)
        decrypted_phone = service.decrypt_phone(encrypted_phone)

        assert decrypted_phone == phone

    def test_phone_bytes_handling(self, service):
        """Should handle phone as bytes (for LargeBinary storage)."""
        phone = "+5511999999999"
        encrypted_bytes, _ = service.encrypt_phone(phone)

        # encrypted_bytes should be bytes
        assert isinstance(encrypted_bytes, bytes)

        # Should decrypt from bytes
        decrypted = service.decrypt_phone(encrypted_bytes)
        assert decrypted == phone


class TestGenericFieldEncryption:
    """Test generic field encryption."""

    @pytest.fixture
    def service(self):
        return get_unified_encryption_service()

    def test_encrypt_field_gcm(self, service):
        """Should encrypt using AES-256-GCM by default."""
        plaintext = "sensitive data"
        encrypted = service.encrypt_field(plaintext, FieldType.PHI_GENERIC)

        assert encrypted.startswith("encrypted:gcm:")

    def test_encrypt_field_cbc(self):
        """Should encrypt using AES-256-CBC when specified."""
        service = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.AES_256_CBC)
        plaintext = "sensitive data"
        encrypted = service.encrypt_field(plaintext, FieldType.PHI_GENERIC)

        # CBC format: "encrypted:{base64}" (no algorithm suffix)
        assert encrypted.startswith("encrypted:")
        assert ":gcm:" not in encrypted
        assert ":fernet:" not in encrypted

    def test_encrypt_field_fernet(self):
        """Should encrypt using Fernet when specified."""
        service = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.FERNET)
        plaintext = "quiz response"
        encrypted = service.encrypt_field(plaintext, FieldType.QUIZ_RESPONSE)

        assert encrypted.startswith("encrypted:fernet:")

    def test_decrypt_field_auto_detect(self, service):
        """Should auto-detect encryption algorithm when decrypting."""
        plaintext = "test data"

        # Test GCM
        service_gcm = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.AES_256_GCM)
        encrypted_gcm = service_gcm.encrypt_field(plaintext)
        assert service.decrypt_field(encrypted_gcm) == plaintext

        # Test CBC
        service_cbc = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.AES_256_CBC)
        encrypted_cbc = service_cbc.encrypt_field(plaintext)
        assert service.decrypt_field(encrypted_cbc) == plaintext

        # Test Fernet
        service_fernet = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.FERNET)
        encrypted_fernet = service_fernet.encrypt_field(plaintext)
        assert service.decrypt_field(encrypted_fernet) == plaintext

    def test_encrypt_empty_string(self, service):
        """Should handle empty string."""
        encrypted = service.encrypt_field("")
        assert encrypted == ""

    def test_encrypt_none(self, service):
        """Should handle None value."""
        encrypted = service.encrypt_field(None)
        assert encrypted is None


class TestPatientDataEncryption:
    """Test patient data encryption functionality."""

    @pytest.fixture
    def service(self):
        return get_unified_encryption_service()

    def test_encrypt_patient_data(self, service):
        """Should encrypt all PHI fields in patient data."""
        patient_data = {
            "name": "John Doe",
            "cpf": "12345678909",
            "email": "john@example.com",
            "phone": "+5511999999999",
            "diagnosis": "Test diagnosis",
            "non_phi_field": "not encrypted"
        }

        encrypted_data = service.encrypt_patient_data(patient_data)

        # PHI fields should be encrypted
        assert encrypted_data["name"].startswith("encrypted:")
        assert encrypted_data["cpf"].startswith("encrypted:")
        assert encrypted_data["email"].startswith("encrypted:")
        assert encrypted_data["phone"].startswith("encrypted:")
        assert encrypted_data["diagnosis"].startswith("encrypted:")

        # Non-PHI field should not be encrypted
        assert encrypted_data["non_phi_field"] == "not encrypted"

        # Metadata should be added
        assert encrypted_data["__encrypted"] is True
        assert encrypted_data["__encryption_version"] == "2.0"

    def test_decrypt_patient_data(self, service):
        """Should decrypt all PHI fields in patient data."""
        patient_data = {
            "name": "John Doe",
            "cpf": "12345678909",
            "email": "john@example.com",
        }

        encrypted_data = service.encrypt_patient_data(patient_data)
        decrypted_data = service.decrypt_patient_data(encrypted_data)

        # Should match original data
        assert decrypted_data["name"] == patient_data["name"]
        assert decrypted_data["cpf"] == patient_data["cpf"]
        assert decrypted_data["email"] == patient_data["email"]

        # Metadata should be removed
        assert "__encrypted" not in decrypted_data
        assert "__encryption_version" not in decrypted_data

    def test_encrypt_patient_data_with_complex_types(self, service):
        """Should handle complex types (dict, list)."""
        patient_data = {
            "medications": ["Med1", "Med2"],
            "diagnosis": {"primary": "Test", "secondary": "Test2"}
        }

        encrypted_data = service.encrypt_patient_data(patient_data)
        decrypted_data = service.decrypt_patient_data(encrypted_data)

        # Should preserve complex types
        assert decrypted_data["medications"] == patient_data["medications"]
        assert decrypted_data["diagnosis"] == patient_data["diagnosis"]


class TestSearchableHashes:
    """Test searchable hash generation."""

    @pytest.fixture
    def service(self):
        return get_unified_encryption_service()

    def test_generate_hash_cpf(self, service):
        """Should generate deterministic hash for CPF."""
        cpf = "12345678909"
        hash1 = service.generate_hash(cpf, FieldType.CPF)
        hash2 = service.generate_hash(cpf, FieldType.CPF)

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_generate_hash_email(self, service):
        """Should generate deterministic hash for email."""
        email = "test@example.com"
        hash1 = service.generate_hash(email, FieldType.EMAIL)
        hash2 = service.generate_hash(email, FieldType.EMAIL)

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_generate_hash_phone(self, service):
        """Should generate deterministic hash for phone."""
        phone = "+5511999999999"
        hash1 = service.generate_hash(phone, FieldType.PHONE)
        hash2 = service.generate_hash(phone, FieldType.PHONE)

        assert hash1 == hash2
        assert len(hash1) == 64


class TestKeyManagement:
    """Test encryption key management."""

    @patch.dict(os.environ, {"PHI_ENCRYPTION_KEY": "test-key-12345678909234567890123456789092"})
    def test_custom_encryption_key(self):
        """Should use custom encryption key from environment."""
        service = UnifiedEncryptionService()
        encrypted = service.encrypt_field("test")
        decrypted = service.decrypt_field(encrypted)

        assert decrypted == "test"

    def test_validate_key_entropy(self):
        """Should validate key entropy."""
        service = UnifiedEncryptionService()

        # Good key (32 chars, diverse)
        good_key = "abcdef1234567890ABCDEF1234567890"
        assert service.validate_key_entropy(good_key) is True

        # Bad key (too short)
        short_key = "short"
        assert service.validate_key_entropy(short_key) is False

        # Bad key (not diverse)
        simple_key = "aaaaaaaaaaaaaaaa"
        assert service.validate_key_entropy(simple_key) is False


class TestAlgorithmInteroperability:
    """Test that different algorithms can decrypt each other's data."""

    def test_gcm_encryption_decryption(self):
        """Test GCM encryption/decryption."""
        service = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.AES_256_GCM)
        plaintext = "test data"

        encrypted = service.encrypt_field(plaintext)
        decrypted = service.decrypt_field(encrypted)

        assert encrypted.startswith("encrypted:gcm:")
        assert decrypted == plaintext

    def test_cbc_encryption_decryption(self):
        """Test CBC encryption/decryption."""
        service = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.AES_256_CBC)
        plaintext = "test data"

        encrypted = service.encrypt_field(plaintext)
        decrypted = service.decrypt_field(encrypted)

        assert encrypted.startswith("encrypted:")
        assert ":gcm:" not in encrypted
        assert decrypted == plaintext

    def test_cross_service_decryption(self):
        """Test that GCM service can decrypt CBC data and vice versa."""
        plaintext = "test data"

        # Encrypt with CBC
        service_cbc = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.AES_256_CBC)
        encrypted_cbc = service_cbc.encrypt_field(plaintext)

        # Decrypt with GCM service (should auto-detect CBC)
        service_gcm = UnifiedEncryptionService(algorithm=EncryptionAlgorithm.AES_256_GCM)
        decrypted = service_gcm.decrypt_field(encrypted_cbc)

        assert decrypted == plaintext


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
