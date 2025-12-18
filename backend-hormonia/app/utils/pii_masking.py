"""
PII (Personally Identifiable Information) Masking Utilities.

LOW-001 FIX: Implements LGPD/HIPAA compliant data masking for logging.

Compliance:
- LGPD Art. 46: Minimização e Anonimização de Dados
- HIPAA §164.312(b): Audit Controls and Log Protection

File: backend-hormonia/app/utils/pii_masking.py
"""

import re
from uuid import UUID


def mask_cpf(cpf: str) -> str:
    """
    Mask Brazilian CPF number for LGPD compliance.

    Format: XXX.***.***-XX -> Shows only first 3 and last 2 digits

    Args:
        cpf: CPF number (with or without formatting)

    Returns:
        Masked CPF string

    Examples:
        >>> mask_cpf("12345678901")
        "123.***.***-01"
        >>> mask_cpf("123.456.789-01")
        "123.***.***-01"
    """
    if not cpf:
        return "***.***.***-**"

    # Remove all non-digit characters
    digits_only = re.sub(r"\D", "", cpf)

    # Ensure we have at least some digits
    if len(digits_only) < 5:
        return "***.***.***-**"

    # Mask middle digits
    first_three = digits_only[:3]
    last_two = digits_only[-2:]

    return f"{first_three}.***.***-{last_two}"


def mask_phone(phone: str) -> str:
    """
    Mask Brazilian phone number for LGPD/HIPAA compliance.

    Format: +55***XXXX -> Shows only country code and last 4 digits

    Args:
        phone: Phone number (E.164 or local format)

    Returns:
        Masked phone string

    Examples:
        >>> mask_phone("+5511987654321")
        "+55***4321"
        >>> mask_phone("11987654321")
        "+55***4321"
        >>> mask_phone("987654321")
        "***4321"
    """
    if not phone:
        return "***"

    # Remove all non-digit characters except +
    cleaned = re.sub(r"[^\d+]", "", phone)

    # Get last 4 digits
    if len(cleaned) < 4:
        return "***"

    last_four = cleaned[-4:]

    # Check if it has country code
    if cleaned.startswith("+55") or cleaned.startswith("55"):
        return f"+55***{last_four}"
    elif cleaned.startswith("+"):
        # Other country codes
        return f"+***{last_four}"
    else:
        # No country code
        return f"***{last_four}"


def mask_email(email: str) -> str:
    """
    Mask email address for LGPD/HIPAA compliance.

    Format: XX***@domain.com -> Shows first 2 chars of local part

    Args:
        email: Email address

    Returns:
        Masked email string

    Examples:
        >>> mask_email("paciente@example.com")
        "pa***@example.com"
        >>> mask_email("a@example.com")
        "a***@example.com"
    """
    if not email or "@" not in email:
        return "***@***.***"

    try:
        local, domain = email.split("@", 1)

        # Show first 1-2 characters of local part
        if len(local) <= 1:
            masked_local = f"{local[0]}***"
        else:
            masked_local = f"{local[:2]}***"

        return f"{masked_local}@{domain}"
    except Exception:
        return "***@***.***"


def mask_name(name: str) -> str:
    """
    Mask patient name for LGPD/HIPAA compliance.

    Format: FirstName L. -> Shows first name and last name initial

    Args:
        name: Full name

    Returns:
        Masked name string

    Examples:
        >>> mask_name("João da Silva")
        "João S."
        >>> mask_name("Maria")
        "Maria"
    """
    if not name:
        return "***"

    # Split name into parts
    parts = name.strip().split()

    if len(parts) == 1:
        # Single name - return as is (first name only)
        return parts[0]

    # First name + last name initial
    first_name = parts[0]
    last_initial = parts[-1][0].upper()

    return f"{first_name} {last_initial}."


def safe_patient_log_context(patient_id: UUID, **kwargs) -> dict:
    """
    Create safe logging context for patient operations.

    Includes patient_id (UUID) and masks all PII fields.

    Args:
        patient_id: Patient UUID (safe to log)
        **kwargs: Additional fields to include (will be masked if PII)

    Returns:
        Dictionary with patient_id and masked fields

    Examples:
        >>> safe_patient_log_context(
        ...     uuid.uuid4(),
        ...     cpf="12345678901",
        ...     phone="+5511987654321"
        ... )
        {'patient_id': 'xxx-xxx-xxx', 'cpf': '123.***.***-01', 'phone': '+55***4321'}
    """
    context = {"patient_id": str(patient_id)}

    # Known PII fields to mask
    pii_maskers = {
        "cpf": mask_cpf,
        "phone": mask_phone,
        "email": mask_email,
        "name": mask_name,
    }

    for key, value in kwargs.items():
        if key in pii_maskers and value:
            # Mask PII field
            context[key] = pii_maskers[key](str(value))
        else:
            # Include non-PII field as-is
            context[key] = value

    return context


def mask_pii_in_log_message(message: str) -> str:
    """
    Automatically detect and mask PII in log messages.

    Detects and masks:
    - CPF patterns (XXX.XXX.XXX-XX)
    - Phone patterns (+55XXXXXXXXXXX)
    - Email patterns (xxx@domain.com)

    Args:
        message: Log message that may contain PII

    Returns:
        Message with PII masked

    Examples:
        >>> mask_pii_in_log_message("Patient 123.456.789-01 called from +5511987654321")
        "Patient 123.***.***-01 called from +55***4321"
    """
    # Mask CPF patterns (with or without formatting)
    message = re.sub(r"\b(\d{3})\.?\d{3}\.?\d{3}-?(\d{2})\b", r"\1.***.***-\2", message)

    # Mask phone patterns (Brazilian format)
    message = re.sub(
        r"\+?55\s?\(?\d{2}\)?\s?\d{4,5}-?\d{4}",
        lambda m: mask_phone(m.group(0)),
        message,
    )

    # Mask email patterns
    message = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        lambda m: mask_email(m.group(0)),
        message,
    )

    return message
