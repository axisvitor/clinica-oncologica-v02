"""
Phone number validation utilities for Brazilian and E.164 formats.

Canonical module -- every phone helper in the project should be imported from
``app.schemas.validators.phone``.

Supported Formats:
    - E.164: International format with country code (+5511987654321)
    - Brazilian: Local format with DDD (11987654321 or (11) 98765-4321)

References:
    - E.164: ITU-T Recommendation E.164
    - Brazilian phone format: ANATEL regulations
"""

import logging
import re
from enum import Enum
from typing import List, Optional, Tuple

try:
    import phonenumbers
    from phonenumbers import NumberParseException

    PHONENUMBERS_AVAILABLE = True
except ImportError:
    PHONENUMBERS_AVAILABLE = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class PhoneValidationError(ValueError):
    """Raised when phone number validation fails."""

    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PhoneValidationMode(str, Enum):
    """Phone validation modes for different use cases."""

    E164_STRICT = "e164_strict"
    BR_FLEXIBLE = "br_flexible"
    HYBRID = "hybrid"
    BR_TO_E164 = "br_to_e164"


# ---------------------------------------------------------------------------
# Core validators (regex-based, no external deps)
# ---------------------------------------------------------------------------


def validate_phone_e164(phone: str, allow_none: bool = False) -> Optional[str]:
    """Validate phone number in strict E.164 format."""
    if not phone:
        if allow_none:
            return None
        raise ValueError("Phone number is required")

    cleaned = re.sub(r"[\s\-\(\)]", "", phone)

    if not cleaned.startswith("+"):
        raise ValueError("Phone number must start with country code (+)")

    digits_only = cleaned[1:]

    if not digits_only.isdigit():
        raise ValueError("Phone number must contain only + and digits")

    if len(digits_only) < 10 or len(digits_only) > 15:
        raise ValueError(
            f"Phone number must have 10-15 digits, got {len(digits_only)}"
        )

    return cleaned


def validate_phone_br(phone: str, allow_none: bool = False) -> Optional[str]:
    """Validate phone number in Brazilian format (with or without formatting)."""
    if not phone:
        if allow_none:
            return None
        raise ValueError("Phone number is required")

    cleaned = re.sub(r"[\s\-\(\)]", "", phone)

    if cleaned.startswith("+"):
        raise ValueError("Brazilian phone format should not include country code")

    digits_only = re.sub(r"\D", "", phone)

    if len(digits_only) < 10 or len(digits_only) > 11:
        raise ValueError(
            f"Brazilian phone must have 10-11 digits (DDD + number), "
            f"got {len(digits_only)}"
        )

    ddd = int(digits_only[:2])
    if ddd < 11 or ddd > 99:
        raise ValueError(f"Invalid DDD (area code): {ddd}. Must be between 11-99")

    return phone


def is_valid_e164(phone: str) -> bool:
    """Quick check if *phone* is in valid E.164 format."""
    if not phone:
        return False
    return bool(re.match(r"^\+[1-9]\d{1,14}$", phone))


# ---------------------------------------------------------------------------
# Normalize / convert
# ---------------------------------------------------------------------------


def normalize_phone(
    phone: str,
    mode: PhoneValidationMode = PhoneValidationMode.HYBRID,
    allow_none: bool = False,
) -> Optional[str]:
    """Normalize phone number according to *mode*."""
    if not phone:
        if allow_none:
            return None
        raise ValueError("Phone number is required")

    cleaned = re.sub(r"[\s\-\(\)]", "", phone)

    if mode == PhoneValidationMode.E164_STRICT:
        return validate_phone_e164(phone, allow_none=allow_none)

    elif mode == PhoneValidationMode.BR_FLEXIBLE:
        return validate_phone_br(phone, allow_none=allow_none)

    elif mode == PhoneValidationMode.BR_TO_E164:
        if cleaned.startswith("+"):
            return validate_phone_e164(phone, allow_none=allow_none)
        digits_only = re.sub(r"\D", "", phone)
        if digits_only.startswith("55") and len(digits_only) in (12, 13):
            return validate_phone_e164(f"+{digits_only}", allow_none=allow_none)
        if len(digits_only) < 10 or len(digits_only) > 11:
            raise ValueError(
                f"Brazilian phone must have 10-11 digits, got {len(digits_only)}"
            )
        return validate_phone_e164(f"+55{digits_only}", allow_none=allow_none)

    elif mode == PhoneValidationMode.HYBRID:
        if cleaned.startswith("+"):
            return validate_phone_e164(phone, allow_none=allow_none)
        return validate_phone_br(phone, allow_none=allow_none)

    raise ValueError(f"Invalid validation mode: {mode}")


def format_phone_display(phone: str) -> str:
    """Format phone number for display (Brazilian format with mask)."""
    digits_only = re.sub(r"\D", "", phone)

    if digits_only.startswith("55") and len(digits_only) > 11:
        digits_only = digits_only[2:]

    if len(digits_only) == 11:
        return f"({digits_only[:2]}) {digits_only[2:7]}-{digits_only[7:]}"
    elif len(digits_only) == 10:
        return f"({digits_only[:2]}) {digits_only[2:6]}-{digits_only[6:]}"
    return phone


# ---------------------------------------------------------------------------
# phonenumbers-based validation (graceful fallback when lib absent)
# ---------------------------------------------------------------------------


def _validate_phone_regex_fallback(
    normalized: str, strict: bool = True,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Fallback phone validation using regex when phonenumbers is absent."""
    pattern = r"^\+55\d{10,11}$"

    if normalized.startswith("+"):
        if re.match(pattern, normalized):
            return True, normalized, None
        error_msg = f"Invalid Brazilian phone format (E.164): {normalized}"
        if strict:
            raise PhoneValidationError(error_msg)
        return False, None, error_msg

    if len(normalized) in (10, 11):
        e164 = f"+55{normalized}"
        if re.match(pattern, e164):
            return True, e164, None

    error_msg = (
        f"Invalid phone format: {normalized}. "
        "Expected 10-11 digits or E.164 format."
    )
    if strict:
        raise PhoneValidationError(error_msg)
    return False, None, error_msg


def validate_and_format_phone(
    phone: str, default_region: str = "BR", strict: bool = True,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate and format phone number to E.164 using phonenumbers (or regex).

    Returns:
        Tuple of (is_valid, formatted_phone, error_message)
    """
    if not phone:
        error_msg = "Phone number is required"
        if strict:
            raise PhoneValidationError(error_msg)
        return False, None, error_msg

    if phone.startswith("+"):
        normalized: str = "+" + re.sub(r"\D", "", phone[1:])
    else:
        normalized = re.sub(r"\D", "", phone)

    if not normalized:
        error_msg = "Phone number cannot be empty after normalization"
        if strict:
            raise PhoneValidationError(error_msg)
        return False, None, error_msg

    if PHONENUMBERS_AVAILABLE:
        try:
            parsed = phonenumbers.parse(normalized, default_region)
            if not phonenumbers.is_valid_number(parsed):
                if not strict:
                    fb_ok, fb_phone, _ = _validate_phone_regex_fallback(
                        normalized, strict=False,
                    )
                    if fb_ok:
                        return True, fb_phone, None
                error_msg = f"Invalid phone number: {phone}"
                if strict:
                    raise PhoneValidationError(error_msg)
                return False, None, error_msg
            e164 = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164,
            )
            return True, e164, None
        except NumberParseException as exc:
            error_msg = f"Failed to parse phone number: {phone} - {exc}"
            if strict:
                raise PhoneValidationError(error_msg)
            return False, None, error_msg

    return _validate_phone_regex_fallback(normalized, strict)


# ---------------------------------------------------------------------------
# Brazilian phone variant builder (for lookup / matching)
# ---------------------------------------------------------------------------


def _digits_only_str(value: str) -> str:
    """Return only digit characters from *value*."""
    return "".join(ch for ch in (value or "") if ch.isdigit())


def build_br_phone_variants(phone: str) -> List[str]:
    """Build normalized Brazilian phone variants for lookup and matching."""
    digits = _digits_only_str(phone)
    variants: List[str] = []
    seen: set = set()

    def _add(value: str) -> None:
        if value and value not in seen:
            variants.append(value)
            seen.add(value)

    _add(digits)
    _add(f"+{digits}")

    def _add_cc_variants(cc_digits: str) -> None:
        if not cc_digits:
            return
        _add(cc_digits)
        _add(f"+{cc_digits}")
        if cc_digits.startswith("55") and len(cc_digits) >= 12:
            local = cc_digits[2:]
            _add(local)
            _add(f"+{local}")
        if cc_digits.startswith("55") and len(cc_digits) >= 12:
            ddd = cc_digits[2:4]
            local_part = cc_digits[4:]
            if len(local_part) == 8:
                mobile = f"55{ddd}9{local_part}"
                _add(mobile)
                _add(f"+{mobile}")
                _add(f"{ddd}9{local_part}")
            elif len(local_part) == 9 and local_part.startswith("9"):
                landline = f"55{ddd}{local_part[1:]}"
                _add(landline)
                _add(f"+{landline}")
                _add(f"{ddd}{local_part[1:]}")

    if digits and not digits.startswith("55") and len(digits) in (10, 11):
        _add_cc_variants(f"55{digits}")
    elif digits.startswith("55") and len(digits) >= 12:
        _add_cc_variants(digits)

    return variants


def normalize_br_phone(phone: str) -> str:
    """Return a single, best-effort normalized Brazilian phone (digits only)."""
    variants = build_br_phone_variants(phone)
    for v in variants:
        if not v.startswith("+") and v.startswith("55") and len(v) == 13:
            return v
    for v in variants:
        if not v.startswith("+") and v.startswith("55") and len(v) == 12:
            return v
    for v in variants:
        if not v.startswith("+"):
            return v
    return ""


# ---------------------------------------------------------------------------
# WhatsApp / Evolution API helper
# ---------------------------------------------------------------------------


def format_phone_for_whatsapp(phone_number: str) -> str:
    """Format phone for Evolution API (digits only, 55 prefix)."""
    clean_number = "".join(filter(str.isdigit, phone_number))
    if not clean_number.startswith("55") and len(clean_number) in (10, 11):
        clean_number = "55" + clean_number
    return clean_number


# Alias kept so callers importing format_phone_number still work.
format_phone_number = format_phone_for_whatsapp
