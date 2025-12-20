"""
Unit tests for PhoneNormalizer utility.

Tests E.164 phone number normalization with multiple fallback strategies.
"""
import pytest
from unittest.mock import Mock
from uuid import uuid4

from app.services.webhook.utils.phone_normalizer import PhoneNormalizer


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def normalizer(mock_db):
    """Create PhoneNormalizer instance."""
    return PhoneNormalizer(mock_db)


class TestPhoneNormalization:
    """Test phone number normalization to E.164 format."""

    def test_normalize_already_e164_format(self, normalizer):
        """Test that valid E.164 numbers remain unchanged."""
        phone = "+5511987654321"
        result = normalizer.normalize_phone_e164(phone)
        assert result == "+5511987654321"

    def test_normalize_brazilian_number_without_plus(self, normalizer):
        """Test normalization of Brazilian number without + prefix."""
        phone = "5511987654321"
        result = normalizer.normalize_phone_e164(phone)
        assert result == "+5511987654321"

    def test_normalize_local_brazilian_number(self, normalizer):
        """Test normalization of local Brazilian number (without country code)."""
        phone = "11987654321"
        result = normalizer.normalize_phone_e164(phone)
        assert result == "+5511987654321"

    def test_normalize_number_with_spaces(self, normalizer):
        """Test normalization removes spaces."""
        phone = "+55 11 98765 4321"
        result = normalizer.normalize_phone_e164(phone)
        assert result == "+5511987654321"

    def test_normalize_number_with_dashes(self, normalizer):
        """Test normalization removes dashes."""
        phone = "+55-11-98765-4321"
        result = normalizer.normalize_phone_e164(phone)
        assert result == "+5511987654321"

    def test_normalize_number_with_parentheses(self, normalizer):
        """Test normalization removes parentheses."""
        phone = "+55 (11) 98765-4321"
        result = normalizer.normalize_phone_e164(phone)
        assert result == "+5511987654321"

    def test_normalize_number_with_dots(self, normalizer):
        """Test normalization removes dots."""
        phone = "+55.11.98765.4321"
        result = normalizer.normalize_phone_e164(phone)
        assert result == "+5511987654321"

    def test_normalize_whatsapp_jid_format(self, normalizer):
        """Test normalization of WhatsApp JID format."""
        phone = "5511987654321@s.whatsapp.net"
        result = normalizer.normalize_phone_e164(phone)
        assert result == "+5511987654321"

    def test_normalize_group_jid_returns_original(self, normalizer):
        """Test that group JIDs are returned as-is (not a valid phone)."""
        phone = "123456789@g.us"
        result = normalizer.normalize_phone_e164(phone)
        # Group JIDs cannot be normalized to phone numbers
        assert "@g.us" in result or result.startswith("+123456789")


class TestPhoneCleaning:
    """Test phone number cleaning utilities."""

    def test_clean_removes_all_non_digits(self, normalizer):
        """Test that clean_phone_number removes all non-digit characters."""
        phone = "+55 (11) 98765-4321"
        result = normalizer.clean_phone_number(phone)
        assert result == "5511987654321"

    def test_clean_empty_string(self, normalizer):
        """Test cleaning empty string."""
        result = normalizer.clean_phone_number("")
        assert result == ""

    def test_clean_only_special_chars(self, normalizer):
        """Test cleaning string with only special characters."""
        result = normalizer.clean_phone_number("+-() ")
        assert result == ""


class TestPatientLookup:
    """Test patient lookup by phone number."""

    def test_find_patient_exact_match(self, normalizer, mock_db):
        """Test finding patient with exact phone match."""
        mock_patient = Mock()
        mock_patient.id = uuid4()
        mock_patient.phone = "+5511987654321"
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_patient
        mock_db.query.return_value = mock_query
        
        result = normalizer.find_patient_by_phone("+5511987654321")
        
        assert result is not None
        assert result.id == mock_patient.id

    def test_find_patient_normalized_match(self, normalizer, mock_db):
        """Test finding patient with normalized phone match."""
        mock_patient = Mock()
        mock_patient.id = uuid4()
        mock_patient.phone = "+5511987654321"
        
        mock_query = Mock()
        mock_query.filter.return_value.first.side_effect = [None, mock_patient]
        mock_db.query.return_value = mock_query
        
        # Input phone in different format should still match
        result = normalizer.find_patient_by_phone("55 11 98765-4321")
        
        assert result is not None

    def test_find_patient_not_found(self, normalizer, mock_db):
        """Test when patient is not found by phone."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        result = normalizer.find_patient_by_phone("+5511999999999")
        
        assert result is None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_normalize_none_input(self, normalizer):
        """Test handling of None input."""
        with pytest.raises(AttributeError):
            normalizer.normalize_phone_e164(None)

    def test_normalize_very_short_number(self, normalizer):
        """Test handling of very short numbers."""
        phone = "123"
        result = normalizer.normalize_phone_e164(phone)
        # Should still try to normalize, even if invalid
        assert "123" in result

    def test_normalize_very_long_number(self, normalizer):
        """Test handling of very long numbers."""
        phone = "1234567890923456789"
        result = normalizer.normalize_phone_e164(phone)
        # Should still process the number
        assert len(result) > 0

    def test_normalize_international_number(self, normalizer):
        """Test normalization of non-Brazilian international numbers."""
        phone = "+14155551234"  # US number
        result = normalizer.normalize_phone_e164(phone)
        assert result == "+14155551234"

    def test_find_patient_database_error(self, normalizer, mock_db):
        """Test error handling when database query fails."""
        mock_db.query.side_effect = Exception("Database connection error")
        
        result = normalizer.find_patient_by_phone("+5511987654321")
        
        # Should handle error gracefully and return None
        assert result is None
