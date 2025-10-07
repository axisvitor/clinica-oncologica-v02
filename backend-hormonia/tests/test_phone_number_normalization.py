"""
Unit tests for phone number normalization and matching.

Tests P0-3 fix: Phone Number Matching with + Prefix
Ensures webhook processor correctly finds patients regardless of phone format.
"""
import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from app.services.webhook_processor import WebhookProcessor
from app.models.patient import Patient


class TestPhoneNormalization:
    """Test phone number normalization utilities."""

    def setup_method(self):
        """Setup test fixtures."""
        self.db = Mock(spec=Session)
        self.processor = WebhookProcessor(self.db)

    def test_normalize_phone_e164_with_plus(self):
        """Test normalization of phone with + prefix."""
        result = self.processor._normalize_phone_e164("+5511987654321")
        assert result == "+5511987654321"

    def test_normalize_phone_e164_without_plus(self):
        """Test normalization adds + to Brazilian number."""
        result = self.processor._normalize_phone_e164("5511987654321")
        assert result == "+5511987654321"

    def test_normalize_phone_e164_local_only(self):
        """Test normalization adds country code to local number."""
        result = self.processor._normalize_phone_e164("11987654321")
        assert result == "+5511987654321"

    def test_normalize_phone_e164_with_leading_zeros(self):
        """Test normalization removes leading zeros."""
        result = self.processor._normalize_phone_e164("0005511987654321")
        assert result == "+5511987654321"

    def test_normalize_phone_e164_with_special_chars(self):
        """Test normalization removes special characters."""
        result = self.processor._normalize_phone_e164("+55 (11) 98765-4321")
        assert result == "+5511987654321"


class TestCleanPhoneNumber:
    """Test phone number cleaning from WhatsApp format."""

    def setup_method(self):
        """Setup test fixtures."""
        self.db = Mock(spec=Session)
        self.processor = WebhookProcessor(self.db)

    def test_clean_whatsapp_format(self):
        """Test cleaning WhatsApp format number."""
        result = self.processor._clean_phone_number("5511987654321@s.whatsapp.net")
        assert result == "5511987654321"

    def test_clean_with_plus_prefix(self):
        """Test cleaning preserves + prefix."""
        result = self.processor._clean_phone_number("+5511987654321@s.whatsapp.net")
        assert result == "+5511987654321"

    def test_clean_removes_special_chars(self):
        """Test cleaning removes special characters."""
        result = self.processor._clean_phone_number("+55 (11) 98765-4321")
        assert result == "+5511987654321"

    def test_clean_removes_leading_zeros(self):
        """Test cleaning removes leading zeros."""
        result = self.processor._clean_phone_number("005511987654321")
        assert result == "5511987654321"

    def test_clean_preserves_plus_removes_zeros(self):
        """Test cleaning preserves + but removes zeros after it."""
        result = self.processor._clean_phone_number("+005511987654321")
        assert result == "+5511987654321"


class TestFindPatientByPhone:
    """Test patient lookup with multiple fallback strategies."""

    def setup_method(self):
        """Setup test fixtures."""
        self.db = Mock(spec=Session)
        self.processor = WebhookProcessor(self.db)
        self.mock_patient = Patient(
            id="123e4567-e89b-12d3-a456-426614174000",
            name="Test Patient",
            phone="+5511987654321"
        )

    def test_find_patient_e164_exact_match(self):
        """Test finding patient with E.164 exact match."""
        # Mock patient service to return patient on first call
        self.processor.patient_service.get_by_phone = Mock(
            side_effect=[self.mock_patient]
        )

        patient = self.processor._find_patient_by_phone("+5511987654321")

        assert patient == self.mock_patient
        assert self.processor.patient_service.get_by_phone.call_count == 1
        self.processor.patient_service.get_by_phone.assert_called_with("+5511987654321")

    def test_find_patient_without_plus_fallback(self):
        """Test finding patient without + prefix fallback."""
        # Mock patient service to return None first, then patient
        self.processor.patient_service.get_by_phone = Mock(
            side_effect=[None, self.mock_patient]
        )

        patient = self.processor._find_patient_by_phone("5511987654321")

        assert patient == self.mock_patient
        assert self.processor.patient_service.get_by_phone.call_count == 2

    def test_find_patient_add_country_code(self):
        """Test finding patient by adding country code."""
        # Mock patient service to return None twice, then patient
        self.processor.patient_service.get_by_phone = Mock(
            side_effect=[None, None, self.mock_patient]
        )

        patient = self.processor._find_patient_by_phone("11987654321")

        assert patient == self.mock_patient
        # Should try: +5511987654321, 5511987654321, +5511987654321 (duplicate)
        assert self.processor.patient_service.get_by_phone.call_count >= 3

    def test_find_patient_local_digits_fallback(self):
        """Test finding patient with local digits fallback."""
        # Mock patient service to return None multiple times, then patient
        self.processor.patient_service.get_by_phone = Mock(
            side_effect=[None, None, None, None, self.mock_patient]
        )

        patient = self.processor._find_patient_by_phone("+555511987654321")

        assert patient == self.mock_patient

    def test_find_patient_not_found(self):
        """Test patient not found after all strategies."""
        # Mock patient service to always return None
        self.processor.patient_service.get_by_phone = Mock(return_value=None)

        patient = self.processor._find_patient_by_phone("99999999999")

        assert patient is None
        # Should have tried multiple strategies
        assert self.processor.patient_service.get_by_phone.call_count >= 2


class TestPhoneMatchingIntegration:
    """Integration tests for complete phone matching flow."""

    def setup_method(self):
        """Setup test fixtures."""
        self.db = Mock(spec=Session)
        self.processor = WebhookProcessor(self.db)

    def test_whatsapp_webhook_to_patient_match(self):
        """
        Test complete flow: WhatsApp webhook -> clean -> normalize -> find patient.

        Simulates real scenario:
        1. WhatsApp sends: "5511987654321@s.whatsapp.net"
        2. Cleaned to: "5511987654321"
        3. Normalized to: "+5511987654321"
        4. Patient found with: "+5511987654321"
        """
        # Create mock patient stored with + prefix
        mock_patient = Patient(
            id="123e4567-e89b-12d3-a456-426614174000",
            name="Test Patient",
            phone="+5511987654321"
        )

        # Mock patient service
        self.processor.patient_service.get_by_phone = Mock(
            side_effect=lambda phone: mock_patient if phone == "+5511987654321" else None
        )

        # Simulate webhook data
        whatsapp_phone = "5511987654321@s.whatsapp.net"

        # Clean phone number (as done in _extract_message_data)
        cleaned = self.processor._clean_phone_number(whatsapp_phone)
        assert cleaned == "5511987654321"

        # Find patient (will normalize and try multiple strategies)
        patient = self.processor._find_patient_by_phone(cleaned)

        assert patient == mock_patient
        assert patient.phone == "+5511987654321"

    def test_backward_compatibility_without_plus(self):
        """
        Test backward compatibility for patients stored without + prefix.

        Some patients may be stored as "5511987654321" without +
        """
        # Create mock patient stored WITHOUT + prefix
        mock_patient = Patient(
            id="123e4567-e89b-12d3-a456-426614174000",
            name="Test Patient",
            phone="5511987654321"
        )

        # Mock patient service
        self.processor.patient_service.get_by_phone = Mock(
            side_effect=lambda phone: mock_patient if phone == "5511987654321" else None
        )

        # Simulate webhook data
        whatsapp_phone = "5511987654321@s.whatsapp.net"

        # Clean and find
        cleaned = self.processor._clean_phone_number(whatsapp_phone)
        patient = self.processor._find_patient_by_phone(cleaned)

        assert patient == mock_patient
        assert patient.phone == "5511987654321"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def setup_method(self):
        """Setup test fixtures."""
        self.db = Mock(spec=Session)
        self.processor = WebhookProcessor(self.db)

    def test_empty_phone_number(self):
        """Test handling of empty phone number."""
        result = self.processor._clean_phone_number("")
        assert result == ""

    def test_invalid_phone_format(self):
        """Test handling of invalid phone format."""
        result = self.processor._clean_phone_number("invalid")
        assert result == "invalid"  # Non-digits removed, but won't match

    def test_phone_with_only_special_chars(self):
        """Test phone with only special characters."""
        result = self.processor._clean_phone_number("+++---()()@@@")
        assert result == "+"  # Only + preserved

    def test_exception_handling_in_find_patient(self):
        """Test exception handling in _find_patient_by_phone."""
        # Mock patient service to raise exception
        self.processor.patient_service.get_by_phone = Mock(
            side_effect=Exception("Database error")
        )

        patient = self.processor._find_patient_by_phone("5511987654321")

        assert patient is None  # Should return None on exception


@pytest.mark.parametrize("input_phone,expected_e164", [
    ("+5511987654321", "+5511987654321"),
    ("5511987654321", "+5511987654321"),
    ("11987654321", "+5511987654321"),
    ("+55 11 98765-4321", "+5511987654321"),
    ("0005511987654321", "+5511987654321"),
    ("+5521987654321", "+5521987654321"),  # Rio de Janeiro
    ("5521987654321", "+5521987654321"),
    ("21987654321", "+5521987654321"),
])
def test_phone_normalization_parametrized(input_phone, expected_e164):
    """Parametrized test for various phone number formats."""
    db = Mock(spec=Session)
    processor = WebhookProcessor(db)
    result = processor._normalize_phone_e164(input_phone)
    assert result == expected_e164


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
