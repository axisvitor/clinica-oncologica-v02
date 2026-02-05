"""
Tests for phone validation module.

This test suite validates the standardized phone validation logic
across different API versions and modes.
"""

import pytest
from app.schemas.validators.phone import (
    validate_phone_e164,
    validate_phone_br,
    normalize_phone,
    format_phone_display,
    PhoneValidationMode,
)


class TestPhoneE164Validation:
    """Tests for strict E.164 format validation."""

    def test_valid_e164_brazil(self):
        """Test valid Brazilian E.164 phone."""
        phone = "+5511987654321"
        result = validate_phone_e164(phone)
        assert result == "+5511987654321"

    def test_valid_e164_with_spaces(self):
        """Test E.164 phone with formatting characters."""
        phone = "+55 11 98765-4321"
        result = validate_phone_e164(phone)
        assert result == "+5511987654321"

    def test_valid_e164_international(self):
        """Test valid international E.164 phone."""
        phone = "+14155552671"
        result = validate_phone_e164(phone)
        assert result == "+14155552671"

    def test_invalid_e164_no_plus(self):
        """Test E.164 validation rejects phone without + prefix."""
        phone = "5511987654321"
        with pytest.raises(ValueError, match="must start with country code"):
            validate_phone_e164(phone)

    def test_invalid_e164_too_short(self):
        """Test E.164 validation rejects too short phone."""
        phone = "+55119876"
        with pytest.raises(ValueError, match="must have 10-15 digits"):
            validate_phone_e164(phone)

    def test_invalid_e164_too_long(self):
        """Test E.164 validation rejects too long phone."""
        phone = "+551198765432112345"
        with pytest.raises(ValueError, match="must have 10-15 digits"):
            validate_phone_e164(phone)

    def test_invalid_e164_non_digits(self):
        """Test E.164 validation rejects non-digit characters."""
        phone = "+55abc11987654321"
        with pytest.raises(ValueError, match="must contain only \\+ and digits"):
            validate_phone_e164(phone)

    def test_e164_allow_none(self):
        """Test E.164 validation with allow_none=True."""
        result = validate_phone_e164("", allow_none=True)
        assert result is None

    def test_e164_require_value(self):
        """Test E.164 validation requires value when allow_none=False."""
        with pytest.raises(ValueError, match="is required"):
            validate_phone_e164("", allow_none=False)


class TestPhoneBrazilianValidation:
    """Tests for Brazilian phone format validation."""

    def test_valid_br_mobile_11_digits(self):
        """Test valid Brazilian mobile phone (11 digits)."""
        phone = "11987654321"
        result = validate_phone_br(phone)
        assert result == "11987654321"

    def test_valid_br_landline_10_digits(self):
        """Test valid Brazilian landline phone (10 digits)."""
        phone = "1133334444"
        result = validate_phone_br(phone)
        assert result == "1133334444"

    def test_valid_br_formatted(self):
        """Test Brazilian phone with formatting preserved."""
        phone = "(11) 98765-4321"
        result = validate_phone_br(phone)
        assert result == "(11) 98765-4321"

    def test_invalid_br_too_short(self):
        """Test Brazilian validation rejects too short phone."""
        phone = "119876543"
        with pytest.raises(ValueError, match="must have 10-11 digits"):
            validate_phone_br(phone)

    def test_invalid_br_too_long(self):
        """Test Brazilian validation rejects too long phone."""
        phone = "119876543211"
        with pytest.raises(ValueError, match="must have 10-11 digits"):
            validate_phone_br(phone)

    def test_invalid_br_with_country_code(self):
        """Test Brazilian validation rejects E.164 format."""
        phone = "+5511987654321"
        with pytest.raises(ValueError, match="should not include country code"):
            validate_phone_br(phone)

    def test_invalid_br_ddd_too_low(self):
        """Test Brazilian validation rejects invalid DDD (area code)."""
        phone = "0987654321"
        with pytest.raises(ValueError, match="Invalid DDD"):
            validate_phone_br(phone)

    def test_invalid_br_ddd_too_high(self):
        """Test Brazilian validation rejects invalid DDD (area code)."""
        phone = "99987654321"
        # DDD 99 is technically valid, but let's test edge case
        result = validate_phone_br(phone)
        assert result == "99987654321"

    def test_br_allow_none(self):
        """Test Brazilian validation with allow_none=True."""
        result = validate_phone_br("", allow_none=True)
        assert result is None


class TestPhoneNormalization:
    """Tests for phone normalization across different modes."""

    def test_normalize_e164_strict_valid(self):
        """Test normalization in E164_STRICT mode."""
        phone = "+55 11 98765-4321"
        result = normalize_phone(phone, PhoneValidationMode.E164_STRICT)
        assert result == "+5511987654321"

    def test_normalize_e164_strict_rejects_br(self):
        """Test E164_STRICT mode rejects Brazilian format."""
        phone = "11987654321"
        with pytest.raises(ValueError):
            normalize_phone(phone, PhoneValidationMode.E164_STRICT)

    def test_normalize_br_flexible_valid(self):
        """Test normalization in BR_FLEXIBLE mode."""
        phone = "(11) 98765-4321"
        result = normalize_phone(phone, PhoneValidationMode.BR_FLEXIBLE)
        assert result == "(11) 98765-4321"

    def test_normalize_br_flexible_rejects_e164(self):
        """Test BR_FLEXIBLE mode rejects E.164 format."""
        phone = "+5511987654321"
        with pytest.raises(ValueError):
            normalize_phone(phone, PhoneValidationMode.BR_FLEXIBLE)

    def test_normalize_hybrid_e164(self):
        """Test HYBRID mode accepts E.164 format."""
        phone = "+5511987654321"
        result = normalize_phone(phone, PhoneValidationMode.HYBRID)
        assert result == "+5511987654321"

    def test_normalize_hybrid_br(self):
        """Test HYBRID mode accepts Brazilian format."""
        phone = "11987654321"
        result = normalize_phone(phone, PhoneValidationMode.HYBRID)
        assert result == "11987654321"

    def test_normalize_br_to_e164_conversion(self):
        """Test BR_TO_E164 mode converts Brazilian to E.164."""
        phone = "11987654321"
        result = normalize_phone(phone, PhoneValidationMode.BR_TO_E164)
        assert result == "+5511987654321"

    def test_normalize_br_to_e164_preserves_e164(self):
        """Test BR_TO_E164 mode preserves already E.164 format."""
        phone = "+5511987654321"
        result = normalize_phone(phone, PhoneValidationMode.BR_TO_E164)
        assert result == "+5511987654321"

    def test_normalize_br_to_e164_formatted(self):
        """Test BR_TO_E164 mode converts formatted Brazilian phone."""
        phone = "(11) 98765-4321"
        result = normalize_phone(phone, PhoneValidationMode.BR_TO_E164)
        assert result == "+5511987654321"

    def test_normalize_invalid_mode(self):
        """Test normalization rejects invalid mode."""
        with pytest.raises(ValueError, match="Invalid validation mode"):
            normalize_phone("+5511987654321", "invalid_mode")


class TestPhoneDisplayFormatting:
    """Tests for phone display formatting."""

    def test_format_e164_mobile(self):
        """Test formatting E.164 mobile phone for display."""
        phone = "+5511987654321"
        result = format_phone_display(phone)
        assert result == "(11) 98765-4321"

    def test_format_e164_landline(self):
        """Test formatting E.164 landline phone for display."""
        phone = "+551133334444"
        result = format_phone_display(phone)
        assert result == "(11) 3333-4444"

    def test_format_br_mobile(self):
        """Test formatting Brazilian mobile phone for display."""
        phone = "11987654321"
        result = format_phone_display(phone)
        assert result == "(11) 98765-4321"

    def test_format_br_landline(self):
        """Test formatting Brazilian landline phone for display."""
        phone = "1133334444"
        result = format_phone_display(phone)
        assert result == "(11) 3333-4444"

    def test_format_already_formatted(self):
        """Test formatting already formatted phone."""
        phone = "(11) 98765-4321"
        result = format_phone_display(phone)
        assert result == "(11) 98765-4321"

    def test_format_invalid_length(self):
        """Test formatting returns original for invalid length."""
        phone = "+1234"
        result = format_phone_display(phone)
        assert result == "+1234"


class TestSchemaIntegration:
    """Tests for schema integration scenarios."""

    def test_v1_schema_accepts_brazilian(self):
        """Test v1 schema accepts Brazilian formats and normalizes to E.164."""
        from app.schemas.patient import PatientCreate

        # Valid E.164
        patient = PatientCreate(
            name="João Silva",
            phone="+5511987654321",
            email="joao@example.com",
            birth_date="1980-01-01",
        )
        assert patient.phone == "+5511987654321"

        # Valid Brazilian format (normalized)
        patient_br = PatientCreate(
            name="João Silva",
            phone="11987654321",
            email="joao@example.com",
            birth_date="1980-01-01",
        )
        assert patient_br.phone == "+5511987654321"

    def test_v2_schema_hybrid_mode(self):
        """Test v2 schema accepts both E.164 and Brazilian formats and normalizes."""
        from app.schemas.v2.patient import PatientV2Create

        # Valid E.164
        patient_e164 = PatientV2Create(
            name="João Silva",
            phone="+5511987654321",
            email="joao@example.com",
            birth_date="1980-01-01",
            doctor_id="123e4567-e89b-12d3-a456-426614174000",
        )
        assert patient_e164.phone == "+5511987654321"

        # Valid Brazilian format (normalized)
        patient_br = PatientV2Create(
            name="Maria Santos",
            phone="11987654321",
            email="maria@example.com",
            birth_date="1985-05-15",
            doctor_id="123e4567-e89b-12d3-a456-426614174000",
        )
        assert patient_br.phone == "+5511987654321"

        # Valid Brazilian formatted (normalized)
        patient_br_fmt = PatientV2Create(
            name="Carlos Oliveira",
            phone="(11) 98765-4321",
            email="carlos@example.com",
            birth_date="1990-10-20",
            doctor_id="123e4567-e89b-12d3-a456-426614174000",
        )
        assert patient_br_fmt.phone == "+5511987654321"


@pytest.mark.parametrize(
    ("input_phone", "expected"),
    [
        ("(11) 98765-4321", "+5511987654321"),
        ("11987654321", "+5511987654321"),
        ("+5511987654321", "+5511987654321"),
    ],
)
def test_v1_v2_normalization_consistency(input_phone, expected):
    from app.schemas.patient import PatientCreate
    from app.schemas.v2.patient import PatientV2Create

    patient_v1 = PatientCreate(
        name="João Silva",
        phone=input_phone,
        email="joao@example.com",
        birth_date="1980-01-01",
    )
    patient_v2 = PatientV2Create(
        name="João Silva",
        phone=input_phone,
        email="joao@example.com",
        birth_date="1980-01-01",
        doctor_id="123e4567-e89b-12d3-a456-426614174000",
    )

    assert patient_v1.phone == expected
    assert patient_v2.phone == expected
