"""
Unit tests for CPF Encryption Service

Tests the CPFEncryptionService for LGPD compliance functionality:
- CPF encryption and decryption
- Searchable hash generation
- Format normalization and validation
- Display formatting (masked/unmasked)
"""

import pytest
from app.services.encryption import get_cpf_encryption_service


class TestCPFEncryptionService:
    """Test suite for CPF encryption service"""

    @pytest.fixture
    def service(self):
        """Get CPF encryption service instance"""
        return get_cpf_encryption_service()

    def test_singleton_instance(self):
        """Test that get_cpf_encryption_service returns singleton"""
        service1 = get_cpf_encryption_service()
        service2 = get_cpf_encryption_service()
        assert service1 is service2

    # =========================================================================
    # Normalization Tests
    # =========================================================================

    def test_normalize_cpf_with_formatting(self, service):
        """Test CPF normalization removes dots and dashes"""
        formatted_cpf = "123.456.789-01"
        normalized = service._normalize_cpf(formatted_cpf)
        assert normalized == "12345678909"
        assert len(normalized) == 11
        assert normalized.isdigit()

    def test_normalize_cpf_without_formatting(self, service):
        """Test CPF normalization handles plain digits"""
        plain_cpf = "12345678909"
        normalized = service._normalize_cpf(plain_cpf)
        assert normalized == "12345678909"

    def test_normalize_cpf_with_spaces(self, service):
        """Test CPF normalization removes spaces"""
        cpf_with_spaces = "123 456 789 01"
        normalized = service._normalize_cpf(cpf_with_spaces)
        assert normalized == "12345678909"

    def test_normalize_cpf_empty(self, service):
        """Test CPF normalization handles empty string"""
        assert service._normalize_cpf("") == ""
        assert service._normalize_cpf(None) is None

    # =========================================================================
    # Validation Tests
    # =========================================================================

    def test_validate_cpf_format_valid(self, service):
        """Test CPF format validation accepts valid format"""
        valid_cpf = "12345678909"
        assert service._validate_cpf_format(valid_cpf) is True

    def test_validate_cpf_format_invalid_length(self, service):
        """Test CPF format validation rejects invalid length"""
        assert service._validate_cpf_format("123456789") is False  # Too short
        assert service._validate_cpf_format("123456789092") is False  # Too long

    def test_validate_cpf_format_non_digits(self, service):
        """Test CPF format validation rejects non-digits"""
        assert service._validate_cpf_format("1234567890a") is False
        assert service._validate_cpf_format("123.456.789-01") is False

    def test_validate_cpf_format_all_same_digit(self, service):
        """Test CPF format validation rejects known invalid patterns"""
        assert service._validate_cpf_format("00000000000") is False
        assert service._validate_cpf_format("11111111111") is False
        assert service._validate_cpf_format("99999999999") is False

    def test_validate_cpf_format_empty(self, service):
        """Test CPF format validation handles empty values"""
        assert service._validate_cpf_format("") is False
        assert service._validate_cpf_format(None) is False

    # =========================================================================
    # Encryption/Decryption Tests
    # =========================================================================

    def test_encrypt_cpf_basic(self, service):
        """Test basic CPF encryption"""
        cpf = "12345678909"
        encrypted_cpf, cpf_hash = service.encrypt_cpf(cpf)

        # Verify encrypted format
        assert encrypted_cpf.startswith("encrypted:")
        assert len(encrypted_cpf) > len(cpf)

        # Verify hash format
        assert len(cpf_hash) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in cpf_hash)

    def test_encrypt_cpf_with_formatting(self, service):
        """Test CPF encryption handles formatted input"""
        formatted_cpf = "123.456.789-01"
        encrypted_cpf, cpf_hash = service.encrypt_cpf(formatted_cpf)

        assert encrypted_cpf.startswith("encrypted:")
        assert len(cpf_hash) == 64

    def test_encrypt_cpf_empty(self, service):
        """Test CPF encryption handles empty values"""
        encrypted_cpf, cpf_hash = service.encrypt_cpf(None)
        assert encrypted_cpf is None
        assert cpf_hash is None

        encrypted_cpf, cpf_hash = service.encrypt_cpf("")
        assert encrypted_cpf is None
        assert cpf_hash is None

    def test_encrypt_cpf_invalid_format(self, service):
        """Test CPF encryption rejects invalid format"""
        with pytest.raises(ValueError, match="Invalid CPF format"):
            service.encrypt_cpf("123")  # Too short

        with pytest.raises(ValueError, match="Invalid CPF format"):
            service.encrypt_cpf("00000000000")  # All zeros

    def test_decrypt_cpf_basic(self, service):
        """Test basic CPF decryption"""
        original_cpf = "12345678909"
        encrypted_cpf, _ = service.encrypt_cpf(original_cpf)

        decrypted_cpf = service.decrypt_cpf(encrypted_cpf)
        assert decrypted_cpf == original_cpf

    def test_decrypt_cpf_empty(self, service):
        """Test CPF decryption handles empty values"""
        assert service.decrypt_cpf(None) is None
        assert service.decrypt_cpf("") is None

    def test_decrypt_cpf_plaintext_backward_compatibility(self, service):
        """Test CPF decryption handles plaintext for backward compatibility"""
        plaintext_cpf = "12345678909"
        # Should return as-is (not encrypted)
        decrypted = service.decrypt_cpf(plaintext_cpf)
        assert decrypted == plaintext_cpf

    def test_encrypt_decrypt_roundtrip(self, service):
        """Test full encryption/decryption roundtrip"""
        original_cpf = "98765432109"

        # Encrypt
        encrypted_cpf, cpf_hash = service.encrypt_cpf(original_cpf)
        assert encrypted_cpf != original_cpf
        assert encrypted_cpf.startswith("encrypted:")

        # Decrypt
        decrypted_cpf = service.decrypt_cpf(encrypted_cpf)
        assert decrypted_cpf == original_cpf

    def test_encrypt_decrypt_with_formatting_roundtrip(self, service):
        """Test roundtrip with formatted input"""
        formatted_cpf = "987.654.321-09"
        normalized_cpf = "98765432109"

        # Encrypt
        encrypted_cpf, _ = service.encrypt_cpf(formatted_cpf)

        # Decrypt (should return normalized, not formatted)
        decrypted_cpf = service.decrypt_cpf(encrypted_cpf)
        assert decrypted_cpf == normalized_cpf

    # =========================================================================
    # Searchable Hash Tests
    # =========================================================================

    def test_hash_cpf_for_search_basic(self, service):
        """Test basic searchable hash generation"""
        cpf = "12345678909"
        hash_value = service.hash_cpf_for_search(cpf)

        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_hash_cpf_for_search_deterministic(self, service):
        """Test hash generation is deterministic"""
        cpf = "12345678909"

        hash1 = service.hash_cpf_for_search(cpf)
        hash2 = service.hash_cpf_for_search(cpf)

        assert hash1 == hash2

    def test_hash_cpf_for_search_format_independent(self, service):
        """Test hash is same regardless of formatting"""
        formatted_cpf = "123.456.789-01"
        plain_cpf = "12345678909"

        hash1 = service.hash_cpf_for_search(formatted_cpf)
        hash2 = service.hash_cpf_for_search(plain_cpf)

        assert hash1 == hash2

    def test_hash_cpf_for_search_different_cpfs(self, service):
        """Test different CPFs produce different hashes"""
        cpf1 = "12345678909"
        cpf2 = "98765432109"

        hash1 = service.hash_cpf_for_search(cpf1)
        hash2 = service.hash_cpf_for_search(cpf2)

        assert hash1 != hash2

    def test_hash_cpf_for_search_empty(self, service):
        """Test hash handles empty values"""
        assert service.hash_cpf_for_search(None) is None
        assert service.hash_cpf_for_search("") is None

    def test_encrypt_and_hash_consistency(self, service):
        """Test that encrypt_cpf and hash_cpf_for_search produce same hash"""
        cpf = "12345678909"

        # Get hash from encryption
        _, hash_from_encrypt = service.encrypt_cpf(cpf)

        # Get hash directly
        hash_from_search = service.hash_cpf_for_search(cpf)

        assert hash_from_encrypt == hash_from_search

    # =========================================================================
    # Display Formatting Tests
    # =========================================================================

    def test_format_cpf_for_display_unmasked(self, service):
        """Test CPF display formatting without masking"""
        cpf = "12345678909"
        formatted = service.format_cpf_for_display(cpf, mask=False)

        assert formatted == "123.456.789-01"

    def test_format_cpf_for_display_masked(self, service):
        """Test CPF display formatting with masking"""
        cpf = "12345678909"
        masked = service.format_cpf_for_display(cpf, mask=True)

        assert masked == "***.***.789-**"
        assert "789" in masked  # Last 3 middle digits visible

    def test_format_cpf_for_display_empty(self, service):
        """Test display formatting handles empty values"""
        assert service.format_cpf_for_display(None) is None
        assert service.format_cpf_for_display("") is None

    def test_format_cpf_for_display_invalid_length(self, service):
        """Test display formatting handles invalid length"""
        invalid_cpf = "123"
        result = service.format_cpf_for_display(invalid_cpf)

        # Should return as-is if invalid
        assert result == invalid_cpf

    def test_format_cpf_for_display_with_formatting_input(self, service):
        """Test display formatting normalizes formatted input"""
        formatted_cpf = "123.456.789-01"
        result = service.format_cpf_for_display(formatted_cpf, mask=False)

        assert result == "123.456.789-01"

    # =========================================================================
    # Migration Tests
    # =========================================================================

    def test_migrate_plaintext_cpf(self, service):
        """Test migration of plaintext CPF to encrypted format"""
        plaintext_cpf = "12345678909"

        encrypted_cpf, cpf_hash = service.migrate_plaintext_cpf(plaintext_cpf)

        # Verify encryption
        assert encrypted_cpf.startswith("encrypted:")
        assert len(cpf_hash) == 64

        # Verify decryption
        decrypted = service.decrypt_cpf(encrypted_cpf)
        assert decrypted == plaintext_cpf

    def test_migrate_plaintext_cpf_empty(self, service):
        """Test migration handles empty values"""
        encrypted_cpf, cpf_hash = service.migrate_plaintext_cpf(None)
        assert encrypted_cpf is None
        assert cpf_hash is None

    # =========================================================================
    # Security Tests
    # =========================================================================

    def test_encrypted_values_are_different(self, service):
        """Test that same CPF encrypts to different ciphertexts (due to random IV)"""
        cpf = "12345678909"

        encrypted1, _ = service.encrypt_cpf(cpf)
        encrypted2, _ = service.encrypt_cpf(cpf)

        # Different ciphertexts (random IV)
        assert encrypted1 != encrypted2

        # But same hash (deterministic)
        _, hash1 = service.encrypt_cpf(cpf)
        _, hash2 = service.encrypt_cpf(cpf)
        assert hash1 == hash2

    def test_cannot_reverse_hash(self, service):
        """Test that hash cannot be reversed to get original CPF"""
        cpf = "12345678909"
        cpf_hash = service.hash_cpf_for_search(cpf)

        # Hash should not contain CPF digits
        assert cpf not in cpf_hash
        assert len(cpf_hash) == 64  # Fixed length, no information leakage

    def test_encrypted_data_format(self, service):
        """Test encrypted data follows expected format"""
        cpf = "12345678909"
        encrypted_cpf, _ = service.encrypt_cpf(cpf)

        # Should have prefix
        assert encrypted_cpf.startswith("encrypted:")

        # Should be base64 encoded after prefix
        encrypted_part = encrypted_cpf.replace("encrypted:", "")
        try:
            import base64
            base64.b64decode(encrypted_part)
        except Exception:
            pytest.fail("Encrypted data is not valid base64")

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_cpf_with_leading_zeros(self, service):
        """Test CPF with leading zeros is preserved"""
        cpf = "00123456789"

        encrypted_cpf, _ = service.encrypt_cpf(cpf)
        decrypted_cpf = service.decrypt_cpf(encrypted_cpf)

        assert decrypted_cpf == cpf
        assert decrypted_cpf.startswith("00")

    def test_multiple_encryptions_same_session(self, service):
        """Test multiple encryptions in same session work correctly"""
        cpfs = ["12345678909", "98765432109", "12345678909"]

        encrypted_list = [service.encrypt_cpf(cpf) for cpf in cpfs]
        decrypted_list = [service.decrypt_cpf(enc[0]) for enc in encrypted_list]

        assert decrypted_list == cpfs

    def test_hash_collision_resistance(self, service):
        """Test that similar CPFs produce different hashes"""
        cpf1 = "12345678909"
        cpf2 = "12345678902"  # Only last digit different

        hash1 = service.hash_cpf_for_search(cpf1)
        hash2 = service.hash_cpf_for_search(cpf2)

        assert hash1 != hash2
        # Hashes should be very different (avalanche effect)
        different_chars = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
        assert different_chars > 30  # Should differ in most positions


class TestCPFEncryptionIntegration:
    """Integration tests for CPF encryption with other components"""

    @pytest.fixture
    def service(self):
        """Get CPF encryption service instance"""
        return get_cpf_encryption_service()

    def test_phi_encryption_service_integration(self, service):
        """Test integration with PHI encryption service"""
        cpf = "12345678909"

        # Encrypt
        encrypted_cpf, _ = service.encrypt_cpf(cpf)

        # Should use PHI service's encryption format
        assert encrypted_cpf.startswith("encrypted:")

        # Should decrypt successfully
        decrypted = service.decrypt_cpf(encrypted_cpf)
        assert decrypted == cpf

    def test_searchable_hash_integration(self, service):
        """Test integration with SearchableHash utility"""
        cpf = "12345678909"

        # Get hash from service
        service_hash = service.hash_cpf_for_search(cpf)

        # Get hash directly from SearchableHash
        from app.core.searchable_hash import SearchableHash
        direct_hash = SearchableHash.hash_cpf(cpf)

        # Should produce same hash
        assert service_hash == direct_hash

    def test_encryption_with_different_formats(self, service):
        """Test that different input formats encrypt to searchable equivalents"""
        formats = [
            "12345678909",
            "123.456.789-01",
            "123 456 789 01",
        ]

        hashes = [service.hash_cpf_for_search(cpf) for cpf in formats]

        # All formats should produce same hash
        assert len(set(hashes)) == 1
