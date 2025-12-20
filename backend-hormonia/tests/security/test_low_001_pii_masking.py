"""
LOW-001 Security Tests: PII Masking for LGPD/HIPAA Compliance

Tests for Personally Identifiable Information masking in logs.

Compliance:
- LGPD Art. 46: Minimização e Anonimização de Dados
- HIPAA §164.312(b): Audit Controls and Log Protection

File: backend-hormonia/tests/security/test_low_001_pii_masking.py
"""
import pytest
from uuid import uuid4

from app.utils.pii_masking import (
    mask_cpf,
    mask_phone,
    mask_email,
    mask_name,
    safe_patient_log_context,
    mask_pii_in_log_message
)


class TestCPFMasking:
    """Test suite for CPF masking (LGPD compliance)."""

    def test_mask_cpf_formatted(self):
        """Test masking formatted CPF."""
        assert mask_cpf("123.456.789-01") == "123.***.***-01"
        assert mask_cpf("987.654.321-00") == "987.***.***-00"

    def test_mask_cpf_unformatted(self):
        """Test masking unformatted CPF."""
        assert mask_cpf("12345678909") == "123.***.***-09"
        assert mask_cpf("98765432100") == "987.***.***-00"

    def test_mask_cpf_partial(self):
        """Test masking partial or malformed CPF."""
        assert mask_cpf("123") == "***.***.***-**"
        assert mask_cpf("1234") == "***.***.***-**"

    def test_mask_cpf_empty(self):
        """Test masking empty CPF."""
        assert mask_cpf("") == "***.***.***-**"
        assert mask_cpf(None) == "***.***.***-**"

    def test_mask_cpf_preserves_first_and_last(self):
        """Test that masking preserves first 3 and last 2 digits."""
        cpf = "12345678909"
        masked = mask_cpf(cpf)

        # First 3 digits
        assert masked.startswith("123")

        # Last 2 digits (09 from the CPF)
        assert masked.endswith("-09")

        # Middle is masked
        assert "***" in masked


class TestPhoneMasking:
    """Test suite for phone number masking (LGPD/HIPAA compliance)."""

    def test_mask_phone_e164_format(self):
        """Test masking E.164 formatted phone."""
        assert mask_phone("+5511987654321") == "+55***4321"
        assert mask_phone("+5521912345678") == "+55***5678"

    def test_mask_phone_without_plus(self):
        """Test masking phone without + prefix."""
        assert mask_phone("5511987654321") == "+55***4321"
        # Phone without country code shows last 4 digits only
        assert mask_phone("11987654321") == "***4321"

    def test_mask_phone_local_format(self):
        """Test masking local phone number."""
        assert mask_phone("987654321") == "***4321"

    def test_mask_phone_empty(self):
        """Test masking empty phone."""
        assert mask_phone("") == "***"
        assert mask_phone(None) == "***"

    def test_mask_phone_preserves_country_code(self):
        """Test that country code is preserved."""
        phone = "+5511987654321"
        masked = mask_phone(phone)

        # Country code preserved
        assert masked.startswith("+55")

        # Last 4 digits preserved
        assert masked.endswith("4321")

        # Middle masked
        assert "***" in masked


class TestEmailMasking:
    """Test suite for email masking (LGPD/HIPAA compliance)."""

    def test_mask_email_standard(self):
        """Test masking standard email."""
        assert mask_email("paciente@example.com") == "pa***@example.com"
        assert mask_email("joao.silva@hospital.com.br") == "jo***@hospital.com.br"

    def test_mask_email_short_local(self):
        """Test masking email with short local part."""
        assert mask_email("a@example.com") == "a***@example.com"

    def test_mask_email_invalid(self):
        """Test masking invalid email."""
        assert mask_email("not_an_email") == "***@***.***"
        assert mask_email("") == "***@***.***"
        assert mask_email(None) == "***@***.***"

    def test_mask_email_preserves_domain(self):
        """Test that domain is fully preserved."""
        email = "patient@clinic.com"
        masked = mask_email(email)

        # Domain preserved
        assert "@clinic.com" in masked

        # Local part masked
        assert "pa***@" in masked


class TestNameMasking:
    """Test suite for name masking (LGPD/HIPAA compliance)."""

    def test_mask_name_full_name(self):
        """Test masking full name."""
        assert mask_name("João da Silva") == "João S."
        assert mask_name("Maria Oliveira Santos") == "Maria S."

    def test_mask_name_single_name(self):
        """Test masking single name (first name only)."""
        assert mask_name("Maria") == "Maria"
        assert mask_name("José") == "José"

    def test_mask_name_empty(self):
        """Test masking empty name."""
        assert mask_name("") == "***"
        assert mask_name(None) == "***"

    def test_mask_name_preserves_first_name(self):
        """Test that first name is preserved."""
        name = "João Carlos da Silva"
        masked = mask_name(name)

        # First name preserved
        assert masked.startswith("João")

        # Last name initial only
        assert masked.endswith("S.")


class TestSafePatientLogContext:
    """Test suite for safe patient logging context."""

    def test_safe_log_context_masks_pii(self):
        """Test that PII fields are masked in log context."""
        patient_id = uuid4()
        context = safe_patient_log_context(
            patient_id,
            cpf="12345678909",
            phone="+5511987654321",
            email="patient@example.com",
            name="João da Silva"
        )

        # UUID preserved
        assert context["patient_id"] == str(patient_id)

        # PII masked (CPF 12345678909 ends in 09)
        assert context["cpf"] == "123.***.***-09"
        assert context["phone"] == "+55***4321"
        assert context["email"] == "pa***@example.com"
        assert context["name"] == "João S."

    def test_safe_log_context_preserves_non_pii(self):
        """Test that non-PII fields are preserved."""
        patient_id = uuid4()
        context = safe_patient_log_context(
            patient_id,
            treatment_type="hormone_therapy",
            current_day=15,
            status="active"
        )

        # Non-PII preserved
        assert context["treatment_type"] == "hormone_therapy"
        assert context["current_day"] == 15
        assert context["status"] == "active"

    def test_safe_log_context_mixed_fields(self):
        """Test mixed PII and non-PII fields."""
        patient_id = uuid4()
        context = safe_patient_log_context(
            patient_id,
            cpf="12345678909",
            treatment_type="chemotherapy",
            phone="+5511987654321",
            current_day=10
        )

        # PII masked (CPF 12345678909 ends in 09)
        assert context["cpf"] == "123.***.***-09"
        assert context["phone"] == "+55***4321"

        # Non-PII preserved
        assert context["treatment_type"] == "chemotherapy"
        assert context["current_day"] == 10


class TestAutomaticPIIMasking:
    """Test suite for automatic PII detection and masking in log messages."""

    def test_mask_cpf_in_message(self):
        """Test automatic CPF masking in log messages."""
        message = "Patient 123.456.789-01 registered successfully"
        masked = mask_pii_in_log_message(message)

        assert "123.***.***-01" in masked
        assert "123.456.789-01" not in masked

    def test_mask_phone_in_message(self):
        """Test automatic phone masking in log messages."""
        message = "Patient called from +5511987654321"
        masked = mask_pii_in_log_message(message)

        assert "+55***4321" in masked
        assert "+5511987654321" not in masked

    def test_mask_email_in_message(self):
        """Test automatic email masking in log messages."""
        message = "Sent notification to patient@example.com"
        masked = mask_pii_in_log_message(message)

        assert "pa***@example.com" in masked
        assert "patient@example.com" not in masked

    def test_mask_multiple_pii_types(self):
        """Test masking multiple PII types in one message."""
        message = (
            "Patient 123.456.789-01 with phone +5511987654321 "
            "and email patient@example.com registered"
        )
        masked = mask_pii_in_log_message(message)

        # All PII masked
        assert "123.***.***-01" in masked
        assert "+55***4321" in masked
        assert "pa***@example.com" in masked

        # Original PII not present
        assert "123.456.789-01" not in masked
        assert "+5511987654321" not in masked
        assert "patient@example.com" not in masked

    def test_preserve_non_pii_in_message(self):
        """Test that non-PII content is preserved."""
        message = "Patient ID 12345 logged in at 2025-01-15 14:30:00"
        masked = mask_pii_in_log_message(message)

        # Non-PII preserved
        assert "Patient ID 12345" in masked
        assert "2025-01-15 14:30:00" in masked


class TestLGPDHIPAACompliance:
    """Test suite for LGPD/HIPAA compliance validation."""

    def test_lgpd_article_46_minimization(self):
        """
        Test LGPD Art. 46 compliance (Data Minimization).

        Ensures that logged PII is minimized to only necessary information.
        """
        patient_id = uuid4()
        context = safe_patient_log_context(
            patient_id,
            cpf="12345678909",
            phone="+5511987654321"
        )

        # Only patient_id should be fully visible
        assert str(patient_id) in str(context["patient_id"])

        # PII should be masked
        assert "***" in context["cpf"]
        assert "***" in context["phone"]

    def test_hipaa_164_312_b_audit_protection(self):
        """
        Test HIPAA §164.312(b) compliance (Audit Controls).

        Ensures audit logs don't contain unencrypted PHI.
        """
        log_message = (
            "Patient 123.456.789-01 accessed medical record. "
            "Contact: +5511987654321, email: patient@example.com"
        )
        masked = mask_pii_in_log_message(log_message)

        # PHI (Protected Health Information) should be masked
        assert "123.456.789-01" not in masked
        assert "+5511987654321" not in masked
        assert "patient@example.com" not in masked

        # Masked versions should be present
        assert "123.***.***-01" in masked
        assert "+55***4321" in masked
        assert "pa***@example.com" in masked


# Pytest fixtures
@pytest.fixture
def sample_patient_data():
    """Fixture providing sample patient data."""
    return {
        "id": uuid4(),
        "cpf": "12345678909",
        "phone": "+5511987654321",
        "email": "patient@example.com",
        "name": "João da Silva",
    }


def test_integration_logging_with_masking(sample_patient_data):
    """Integration test for logging patient operations with PII masking."""
    patient_id = sample_patient_data["id"]

    # Simulate creating log context
    log_context = safe_patient_log_context(
        patient_id,
        cpf=sample_patient_data["cpf"],
        phone=sample_patient_data["phone"],
        email=sample_patient_data["email"],
        name=sample_patient_data["name"],
        operation="patient_created",
        status="success"
    )

    # Verify all PII is masked
    assert "***" in log_context["cpf"]
    assert "***" in log_context["phone"]
    assert "***" in log_context["email"]
    assert "." in log_context["name"]  # Last name initial

    # Verify metadata preserved
    assert log_context["operation"] == "patient_created"
    assert log_context["status"] == "success"
    assert str(patient_id) == log_context["patient_id"]
