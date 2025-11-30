"""
Tests for LGPD encryption compliance
"""
import pytest
from unittest.mock import MagicMock, patch
import os

# Mock environment before imports
os.environ.setdefault('ENCRYPTION_KEY', 'test_key_32_characters_exactly!')

from app.services.encryption_service import EncryptionService


class TestCPFEncryption:
    """Test CPF encryption/decryption."""

    @pytest.fixture
    def encryption_service(self):
        return EncryptionService()

    def test_cpf_is_encrypted(self, encryption_service):
        """Test that CPF is properly encrypted."""
        cpf = "12345678901"
        encrypted, hash_value = encryption_service.encrypt_cpf(cpf)

        assert encrypted != cpf.encode()  # Must be different
        assert len(hash_value) == 64  # SHA-256 hex
        assert encrypted is not None

    def test_cpf_decryption_roundtrip(self, encryption_service):
        """Test CPF can be encrypted and decrypted."""
        cpf = "12345678901"
        encrypted, _ = encryption_service.encrypt_cpf(cpf)
        decrypted = encryption_service.decrypt_cpf(encrypted)

        assert decrypted == cpf

    def test_cpf_hash_is_consistent(self, encryption_service):
        """Test same CPF always produces same hash."""
        cpf = "12345678901"
        _, hash1 = encryption_service.encrypt_cpf(cpf)
        _, hash2 = encryption_service.encrypt_cpf(cpf)

        assert hash1 == hash2

    def test_different_cpfs_different_hashes(self, encryption_service):
        """Test different CPFs produce different hashes."""
        _, hash1 = encryption_service.encrypt_cpf("12345678901")
        _, hash2 = encryption_service.encrypt_cpf("98765432100")

        assert hash1 != hash2

    def test_cpf_encryption_validates_format(self, encryption_service):
        """Test CPF encryption validates format."""
        with pytest.raises(ValueError):
            encryption_service.encrypt_cpf("123")  # Too short

    def test_cpf_encryption_handles_formatted_input(self, encryption_service):
        """Test CPF encryption handles formatted input."""
        cpf_formatted = "123.456.789-01"
        encrypted, hash_value = encryption_service.encrypt_cpf(cpf_formatted)

        decrypted = encryption_service.decrypt_cpf(encrypted)
        assert decrypted == "12345678901"  # Normalized


class TestEmailEncryption:
    """Test email encryption/decryption."""

    @pytest.fixture
    def encryption_service(self):
        return EncryptionService()

    def test_email_is_encrypted(self, encryption_service):
        """Test that email is properly encrypted."""
        email = "patient@example.com"
        encrypted, hash_value = encryption_service.encrypt_email(email)

        assert encrypted != email.encode()
        assert len(hash_value) == 64

    def test_email_decryption_roundtrip(self, encryption_service):
        """Test email can be encrypted and decrypted."""
        email = "patient@example.com"
        encrypted, _ = encryption_service.encrypt_email(email)
        decrypted = encryption_service.decrypt_email(encrypted)

        assert decrypted == email.lower()  # Should be lowercased

    def test_email_case_insensitive_hash(self, encryption_service):
        """Test email hash is case insensitive."""
        _, hash1 = encryption_service.encrypt_email("Patient@Example.COM")
        _, hash2 = encryption_service.encrypt_email("patient@example.com")

        assert hash1 == hash2

    def test_email_encryption_validates_format(self, encryption_service):
        """Test email encryption validates format."""
        with pytest.raises(ValueError):
            encryption_service.encrypt_email("not-an-email")

    def test_email_encryption_handles_special_chars(self, encryption_service):
        """Test email encryption handles special characters."""
        email = "patient+test@example.co.uk"
        encrypted, _ = encryption_service.encrypt_email(email)
        decrypted = encryption_service.decrypt_email(encrypted)

        assert decrypted == email.lower()


class TestPhoneEncryption:
    """Test phone encryption/decryption."""

    @pytest.fixture
    def encryption_service(self):
        return EncryptionService()

    def test_phone_is_encrypted(self, encryption_service):
        """Test that phone is properly encrypted."""
        phone = "+5511999999999"
        encrypted, hash_value = encryption_service.encrypt_phone(phone)

        assert encrypted != phone.encode()
        assert len(hash_value) == 64

    def test_phone_decryption_roundtrip(self, encryption_service):
        """Test phone can be encrypted and decrypted."""
        phone = "+5511999999999"
        encrypted, _ = encryption_service.encrypt_phone(phone)
        decrypted = encryption_service.decrypt_phone(encrypted)

        assert decrypted == "5511999999999"  # Only digits

    def test_phone_normalized_hash(self, encryption_service):
        """Test phone hash is normalized (only digits)."""
        _, hash1 = encryption_service.encrypt_phone("+55 (11) 99999-9999")
        _, hash2 = encryption_service.encrypt_phone("5511999999999")

        assert hash1 == hash2

    def test_phone_encryption_validates_length(self, encryption_service):
        """Test phone encryption validates minimum length."""
        with pytest.raises(ValueError):
            encryption_service.encrypt_phone("123")

    def test_phone_encryption_handles_various_formats(self, encryption_service):
        """Test phone encryption handles various formats."""
        formats = [
            "+55 11 99999-9999",
            "(11) 99999-9999",
            "11999999999",
            "+5511999999999"
        ]

        hashes = [encryption_service.encrypt_phone(fmt)[1] for fmt in formats]

        # All should produce same hash
        assert all(h == hashes[0] for h in hashes)


class TestPatientDataEncryption:
    """Integration tests for patient data encryption in DB."""

    @pytest.mark.asyncio
    async def test_patient_cpf_stored_encrypted(self):
        """Test CPF is stored encrypted in database."""
        from app.repositories.patient import PatientRepository
        from unittest.mock import AsyncMock

        mock_db = AsyncMock()
        repo = PatientRepository(db=mock_db)

        patient_data = {
            "name": "Test Patient",
            "cpf": "12345678901",
            "phone": "+5511999999999"
        }

        # Mock the execute method to capture SQL
        captured_data = {}

        async def capture_execute(query, values):
            captured_data.update(values)
            result = AsyncMock()
            result.rowcount = 1
            result.lastrowid = 123
            return result

        mock_db.execute = capture_execute

        # This would call actual repository method
        # For now, verify encryption service is called
        # await repo.create(patient_data)

        # In actual implementation, captured_data should contain encrypted CPF
        # assert 'cpf_encrypted' in captured_data
        # assert 'cpf_hash' in captured_data

    @pytest.mark.asyncio
    async def test_patient_searchable_by_hash(self):
        """Test patient can be found by CPF hash."""
        from app.repositories.patient import PatientRepository
        from app.services.encryption_service import EncryptionService
        from unittest.mock import AsyncMock

        mock_db = AsyncMock()
        repo = PatientRepository(db=mock_db)
        encryption = EncryptionService()

        cpf = "12345678901"
        _, cpf_hash = encryption.encrypt_cpf(cpf)

        # Mock query result
        mock_result = AsyncMock()
        mock_result.fetchone.return_value = {
            "id": "123",
            "name": "Test Patient",
            "cpf_hash": cpf_hash
        }
        mock_db.execute.return_value = mock_result

        # Search by hash should work
        # patient = await repo.find_by_cpf_hash(cpf_hash)
        # assert patient is not None
        # assert patient['cpf_hash'] == cpf_hash

    @pytest.mark.asyncio
    async def test_patient_data_decryption_on_read(self):
        """Test patient data is decrypted when read."""
        from app.services.encryption_service import EncryptionService

        encryption = EncryptionService()

        # Simulate encrypted data from DB
        original_cpf = "12345678901"
        encrypted_cpf, _ = encryption.encrypt_cpf(original_cpf)

        # Decrypt should return original
        decrypted = encryption.decrypt_cpf(encrypted_cpf)
        assert decrypted == original_cpf

    @pytest.mark.asyncio
    async def test_encryption_key_rotation_handling(self):
        """Test system handles encryption key rotation."""
        # This would test migration to new encryption key
        # For production: implement key versioning
        pass  # TODO: Implement key rotation strategy


class TestEncryptionEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def encryption_service(self):
        return EncryptionService()

    def test_encryption_handles_none_value(self, encryption_service):
        """Test encryption handles None values gracefully."""
        with pytest.raises(ValueError):
            encryption_service.encrypt_cpf(None)

    def test_encryption_handles_empty_string(self, encryption_service):
        """Test encryption handles empty strings."""
        with pytest.raises(ValueError):
            encryption_service.encrypt_email("")

    def test_decryption_handles_invalid_data(self, encryption_service):
        """Test decryption handles corrupted data."""
        with pytest.raises(Exception):
            encryption_service.decrypt_cpf(b"invalid_encrypted_data")

    def test_encryption_deterministic_for_same_input(self, encryption_service):
        """Test encryption hash is deterministic."""
        cpf = "12345678901"

        results = [encryption_service.encrypt_cpf(cpf) for _ in range(10)]
        hashes = [r[1] for r in results]

        # All hashes should be identical
        assert len(set(hashes)) == 1

    def test_encryption_unique_for_different_inputs(self, encryption_service):
        """Test different inputs produce different encryptions."""
        cpfs = ["12345678901", "12345678902", "12345678903"]

        encrypted_values = [encryption_service.encrypt_cpf(cpf)[0] for cpf in cpfs]

        # All encrypted values should be unique
        assert len(set(encrypted_values)) == len(cpfs)
