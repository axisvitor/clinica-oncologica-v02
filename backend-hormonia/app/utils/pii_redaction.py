"""Reusable PII/secret redaction helpers for runtime payloads."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

REDACTED = "[REDACTED]"
REDACTED_SECRET = "[REDACTED_SECRET]"
REDACTED_TOKEN = "[REDACTED_TOKEN]"

CPF_PATTERN = re.compile(r"(?<!\d)(\d{3})[.\s-]?\d{3}[.\s-]?\d{3}[.\s-]?(\d{2})(?!\d)")
EMAIL_PATTERN = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
PHONE_PATTERN = re.compile(r"(?<!\w)(\+?\d[\d().\s-]{8,}\d)(?!\w)")
BEARER_PATTERN = re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._~+/=-]{8,})")
JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9._-]{8,}\.[A-Za-z0-9._-]{8,}\b")
INLINE_SECRET_JSON_PATTERN = re.compile(
    r'(?i)("(?:api[_-]?key|password|passcode|secret|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization|token)"\s*:\s*")([^"]*)(")'
)
INLINE_SECRET_PATTERN = re.compile(
    r"(?i)(\b(?:api[_-]?key|password|passcode|secret|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization|token)\b\s*[:=]\s*)([^\s,;]+)"
)


def redact_pii(value: Any) -> Any:
    """
    Recursively redact PII/secrets in strings, dicts and lists.

    Safe for None and non-string primitive values.
    """
    if value is None:
        return None

    if isinstance(value, str):
        return redact_pii_text(value)

    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_secret_key(key_text):
                redacted[key] = _redact_secret_value(item)
            elif _is_pii_key(key_text):
                redacted[key] = _redact_pii_key_value(item, key_text)
            else:
                redacted[key] = redact_pii(item)
        return redacted

    if isinstance(value, list):
        return [redact_pii(item) for item in value]

    if isinstance(value, tuple):
        return tuple(redact_pii(item) for item in value)

    if isinstance(value, set):
        redacted_items = [redact_pii(item) for item in value]
        return sorted(redacted_items, key=lambda item: str(item))

    return value


def redact_pii_text(value: Any) -> Any:
    """Redact PII/secrets inside a free-text string."""
    if value is None or not isinstance(value, str):
        return value
    if not value:
        return value

    redacted = BEARER_PATTERN.sub(
        lambda match: f"{match.group(1)} {REDACTED_TOKEN}",
        value,
    )
    redacted = JWT_PATTERN.sub(REDACTED_TOKEN, redacted)
    redacted = INLINE_SECRET_JSON_PATTERN.sub(
        lambda match: f"{match.group(1)}{REDACTED_SECRET}{match.group(3)}",
        redacted,
    )
    redacted = INLINE_SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}{REDACTED_SECRET}",
        redacted,
    )
    redacted = EMAIL_PATTERN.sub(_mask_email_match, redacted)
    redacted = CPF_PATTERN.sub(_mask_cpf_match, redacted)
    redacted = PHONE_PATTERN.sub(_mask_phone_match, redacted)
    return redacted


def _mask_email_match(match: re.Match[str]) -> str:
    local_part = match.group(1)
    domain = match.group(2)
    keep = 2 if len(local_part) > 1 else 1
    return f"{local_part[:keep]}***@{domain}"


def _mask_cpf_match(match: re.Match[str]) -> str:
    return f"{match.group(1)}.***.***-{match.group(2)}"


def _mask_phone_match(match: re.Match[str]) -> str:
    raw = match.group(1)
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 10 or len(digits) > 14:
        return raw

    suffix = digits[-4:]
    if digits.startswith("55") and len(digits) >= 12:
        return f"+55***{suffix}"
    if raw.strip().startswith("+"):
        return f"+***{suffix}"
    return f"***{suffix}"


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def _is_secret_key(key: str) -> bool:
    normalized = _normalize_key(key)
    if not normalized:
        return False
    segments = set(normalized.split("_"))

    if {"api", "key"}.issubset(segments):
        return True
    if {"access", "token"}.issubset(segments):
        return True
    if {"refresh", "token"}.issubset(segments):
        return True
    if {"client", "secret"}.issubset(segments):
        return True
    return bool(
        segments
        & {
            "password",
            "passcode",
            "secret",
            "token",
            "authorization",
            "auth",
            "cookie",
            "session",
            "private",
        }
    )


def _is_pii_key(key: str) -> bool:
    normalized = _normalize_key(key)
    if not normalized:
        return False
    segments = set(normalized.split("_"))
    return bool(
        segments
        & {
            "cpf",
            "email",
            "name",
            "phone",
            "telefone",
            "celular",
            "whatsapp",
            "rg",
            "cns",
            "birth",
            "identifier",
        }
    )


def _redact_secret_value(value: Any) -> Any:
    if value is None:
        return None
    return REDACTED_SECRET


def _redact_pii_key_value(value: Any, key: str) -> Any:
    if value is None:
        return None

    normalized_key = _normalize_key(key)

    if isinstance(value, str):
        if any(token in normalized_key for token in ("phone", "telefone", "celular", "whatsapp")):
            return _mask_phone_value(value)
        if "email" in normalized_key:
            return _mask_email_value(value)
        if "cpf" in normalized_key:
            return _mask_cpf_value(value)
        return redact_pii_text(value)

    if isinstance(value, (int, float)):
        value = str(value)
        if any(token in normalized_key for token in ("phone", "telefone", "celular", "whatsapp")):
            return _mask_phone_value(value)
        if "cpf" in normalized_key:
            return _mask_cpf_value(value)
        return redact_pii_text(value)

    if isinstance(value, Mapping):
        return {key: redact_pii(item) for key, item in value.items()}

    if isinstance(value, list):
        return [redact_pii(item) for item in value]

    if isinstance(value, tuple):
        return tuple(redact_pii(item) for item in value)

    if isinstance(value, set):
        redacted_items = [redact_pii(item) for item in value]
        return sorted(redacted_items, key=lambda item: str(item))

    return REDACTED


def _mask_phone_value(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 8:
        return REDACTED
    suffix = digits[-4:]
    if digits.startswith("55") and len(digits) >= 12:
        return f"+55***{suffix}"
    return f"***{suffix}"


def _mask_email_value(value: str) -> str:
    match = EMAIL_PATTERN.search(value)
    if not match:
        return REDACTED
    return _mask_email_match(match)


def _mask_cpf_value(value: str) -> str:
    match = CPF_PATTERN.search(value)
    if not match:
        return REDACTED
    return _mask_cpf_match(match)


def mask_cpf(cpf: str | None) -> str:
    """Mask CPF preserving only the first 3 and last 2 digits."""
    if not cpf:
        return "***.***.***-**"

    digits_only = re.sub(r"\D", "", str(cpf))
    if len(digits_only) < 5:
        return "***.***.***-**"

    return f"{digits_only[:3]}.***.***-{digits_only[-2:]}"


def mask_phone(phone: str | None) -> str:
    """Mask phone number preserving only country prefix and last 4 digits."""
    if not phone:
        return "***"

    cleaned = re.sub(r"[^\d+]", "", str(phone))
    if len(cleaned) < 4:
        return "***"

    last_four = cleaned[-4:]
    if cleaned.startswith("+55") or cleaned.startswith("55"):
        return f"+55***{last_four}"
    if cleaned.startswith("+"):
        return f"+***{last_four}"
    return f"***{last_four}"


def mask_email(email: str | None) -> str:
    """Mask email preserving only the first 1-2 chars of local-part."""
    if not email or "@" not in str(email):
        return "***@***.***"

    try:
        local, domain = str(email).split("@", 1)
    except ValueError:
        return "***@***.***"

    if not local or not domain:
        return "***@***.***"

    if len(local) <= 1:
        masked_local = f"{local[0]}***"
    else:
        masked_local = f"{local[:2]}***"

    return f"{masked_local}@{domain}"


def mask_name(name: str | None) -> str:
    """Mask full name preserving first name and last initial."""
    if not name:
        return "***"

    parts = str(name).strip().split()
    if not parts:
        return "***"
    if len(parts) == 1:
        return parts[0]

    return f"{parts[0]} {parts[-1][0].upper()}."


def safe_patient_log_context(patient_id: UUID, **kwargs: Any) -> dict[str, Any]:
    """
    Build safe logging context preserving metadata while masking known PII fields.
    """
    context: dict[str, Any] = {"patient_id": str(patient_id)}

    pii_maskers = {
        "cpf": mask_cpf,
        "phone": mask_phone,
        "email": mask_email,
        "name": mask_name,
    }

    for key, value in kwargs.items():
        if key in pii_maskers and value:
            context[key] = pii_maskers[key](str(value))
        else:
            context[key] = value

    return context


def mask_pii_in_log_message(message: str) -> str:
    """
    Mask common PII in log messages while preserving non-PII numeric content.

    This intentionally uses narrow patterns (CPF, BR phone, email) to avoid
    false positives on timestamps and generic numeric fields.
    """
    if not message:
        return ""

    masked = re.sub(
        r"\b(\d{3})\.?\d{3}\.?\d{3}-?(\d{2})\b",
        r"\1.***.***-\2",
        message,
    )
    masked = re.sub(
        r"\+?55\s?\(?\d{2}\)?\s?\d{4,5}-?\d{4}",
        lambda match: mask_phone(match.group(0)),
        masked,
    )
    masked = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        lambda match: mask_email(match.group(0)),
        masked,
    )
    return masked


__all__ = [
    "REDACTED",
    "REDACTED_SECRET",
    "REDACTED_TOKEN",
    "mask_cpf",
    "mask_phone",
    "mask_email",
    "mask_name",
    "safe_patient_log_context",
    "mask_pii_in_log_message",
    "redact_pii",
    "redact_pii_text",
]
