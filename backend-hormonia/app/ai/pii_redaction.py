"""
PII Redaction Layer for AI integrations.

Sanitizes patient data before sending to external AI services (Gemini)
to comply with PHI/LGPD requirements. No real patient identifiers should
ever reach external AI providers.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List

# Fields that must be completely removed from AI context
_PII_FIELD_PATTERNS: frozenset[str] = frozenset(
    {
        "patient_id",
        "phone",
        "phone_number",
        "telefone",
        "celular",
        "email",
        "e_mail",
        "cpf",
        "rg",
        "address",
        "endereco",
        "birth_date",
        "data_nascimento",
        "date_of_birth",
        "zip_code",
        "cep",
        "social_security",
        "insurance_number",
    }
)

# Clinical fields that are safe and needed for AI context
_CLINICAL_ALLOWLIST: frozenset[str] = frozenset(
    {
        "treatment_type",
        "treatment_phase",
        "flow_type",
        "flow_kind",
        "current_day",
        "treatment_day",
        "emotional_state",
        "mood",
        "mood_trend",
        "send_mode",
        "current_day_message_index",
        "awaiting_response",
        "timestamp",
        "diagnosis",
        "engagement_level",
        "engagement_score",
        "stress_level",
        "communication_preferences",
        "medical_context",
        "recent_interactions",
        "days_since_enrollment",
    }
)

# Keys whose values should be replaced with "[REDACTED]" in logs
_LOG_REDACT_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "patient_name",
        "phone",
        "phone_number",
        "telefone",
        "celular",
        "email",
        "e_mail",
        "cpf",
        "rg",
        "address",
        "endereco",
        "birth_date",
        "data_nascimento",
        "date_of_birth",
    }
)

_REDACTED = "[REDACTED]"
_PSEUDONYM = "Paciente"
PROMPT_PSEUDONYM = _PSEUDONYM

_PROMPT_EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b")
_PROMPT_CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_PROMPT_PHONE_PATTERN = re.compile(r"\b(?:\+55\s?)?\(?\d{2}\)?\s?\d{4,5}-?\d{4}\b")
_PROMPT_NAME_CAPTURE_PATTERN = re.compile(
    r"""(?ix)
    (?:["']?(?:patient_name|name|nome)["']?\s*[:=]\s*)
    (?P<value>"[^"]*"|'[^']*'|[^\n,}]+)
    """
)
_PROMPT_NAME_FOLLOWED_BY_PUNCT_PATTERN = re.compile(
    r"(?P<value>\b[A-ZÀ-Ý][a-zà-ÿ]{1,30}(?:\s+[A-ZÀ-Ý][a-zà-ÿ]{1,30}){1,2}\b)(?=[,\?])"
)
_PROMPT_NAME_AT_START_PATTERN = re.compile(
    r"^\s*(?P<value>[A-ZÀ-Ý][a-zà-ÿ]{1,30}(?:\s+[A-ZÀ-Ý][a-zà-ÿ]{1,30}){1,2})\b(?=\s+[a-zà-ÿ])"
)
_PROMPT_NAME_VALUE_PATTERN = re.compile(
    r"""(?ix)
    (?P<prefix>["']?(?:patient_name|name|nome)["']?\s*[:=]\s*)
    (?P<value>"[^"]*"|'[^']*'|[^\n,}]+)
    """
)
_PROMPT_SENSITIVE_VALUE_PATTERN = re.compile(
    r"""(?ix)
    (?P<prefix>
        ["']?(?:patient_id|id_paciente|cpf|rg|phone|phone_number|telefone|celular|
        email|e_mail|address|endereco|birth_date|data_nascimento|date_of_birth)["']?
        \s*[:=]\s*
    )
    (?P<value>"[^"]*"|'[^']*'|[^\n,}]+)
    """
)


def _is_pii_key(key: str) -> bool:
    """Check if a key name corresponds to a PII field."""
    lower = key.lower()
    if lower in _PII_FIELD_PATTERNS:
        return True
    for pattern in ("phone", "email", "cpf", "rg_", "address", "endereco", "birth"):
        if pattern in lower:
            return True
    return False


def redact_patient_context(context: dict) -> dict:
    """
    Sanitize a patient context dict before sending to external AI.

    - Removes patient_id entirely.
    - Replaces patient_name / name with the pseudonym "Paciente".
    - Strips any key that matches PII patterns (phone, email, cpf, etc.).
    - Preserves clinical fields needed for AI reasoning.
    - Returns a deep copy; the original dict is never mutated.
    """
    if not context:
        return {}

    redacted: Dict[str, Any] = {}
    for key, value in context.items():
        lower_key = key.lower()

        # Always remove patient_id
        if lower_key == "patient_id" or lower_key == "id":
            continue

        # Replace name fields with pseudonym
        if lower_key in ("patient_name", "name"):
            redacted[key] = _PSEUDONYM
            continue

        # Remove any field that looks like PII
        if _is_pii_key(key):
            continue

        # Deep copy nested structures to avoid mutation
        redacted[key] = copy.deepcopy(value)

    return redacted


def redact_conversation_history(
    history: list,
    patient_names: list[str] | None = None,
) -> list:
    """
    Remove patient names and identifiers from conversation history text.

    Replaces occurrences of known patient names with the pseudonym.
    Also strips common Brazilian PII patterns (CPF, phone numbers).
    """
    if not history:
        return []

    names_to_strip = list(patient_names or [])

    # Build regex patterns for known names (case-insensitive)
    name_patterns: list[re.Pattern[str]] = []
    for name in names_to_strip:
        if name and len(name) >= 2:
            escaped = re.escape(name.strip())
            name_patterns.append(re.compile(escaped, re.IGNORECASE))

    # Common PII patterns for Brazilian context
    cpf_pattern = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
    phone_pattern = re.compile(r"\b(?:\+55\s?)?\(?\d{2}\)?\s?\d{4,5}-?\d{4}\b")

    def _scrub_text(text: str) -> str:
        result = text
        for pattern in name_patterns:
            result = pattern.sub(_PSEUDONYM, result)
        result = cpf_pattern.sub(_REDACTED, result)
        result = phone_pattern.sub(_REDACTED, result)
        return result

    redacted_history: List[Any] = []
    for item in history:
        if isinstance(item, str):
            redacted_history.append(_scrub_text(item))
        elif isinstance(item, dict):
            new_item = {}
            for key, value in item.items():
                if isinstance(value, str):
                    new_item[key] = _scrub_text(value)
                else:
                    new_item[key] = copy.deepcopy(value)
            redacted_history.append(new_item)
        else:
            redacted_history.append(copy.deepcopy(item))

    return redacted_history


def sanitize_prompt_text_for_external_ai(prompt: str) -> str:
    """
    Redact patient identifiers from free text prompts before external AI calls.
    """
    if not prompt:
        return ""

    redacted = (
        prompt.replace("{patient_name}", _PSEUDONYM)
        .replace("[NOME]", _PSEUDONYM)
        .replace("[nome]", _PSEUDONYM)
    )

    patient_names: list[str] = []
    for pattern in (
        _PROMPT_NAME_CAPTURE_PATTERN,
        _PROMPT_NAME_FOLLOWED_BY_PUNCT_PATTERN,
        _PROMPT_NAME_AT_START_PATTERN,
    ):
        for match in pattern.finditer(redacted):
            raw_value = match.group("value").strip().strip('"').strip("'").strip()
            if raw_value and raw_value.lower() not in {
                _PSEUDONYM.lower(),
                _REDACTED.lower(),
            }:
                patient_names.append(raw_value)

    redacted = _PROMPT_NAME_VALUE_PATTERN.sub(
        lambda m: f'{m.group("prefix")}"{_PSEUDONYM}"',
        redacted,
    )
    redacted = _PROMPT_SENSITIVE_VALUE_PATTERN.sub(
        lambda m: f'{m.group("prefix")}"{_REDACTED}"',
        redacted,
    )

    scrubbed = redact_conversation_history(
        [redacted],
        patient_names=patient_names or None,
    )
    if scrubbed and isinstance(scrubbed[0], str):
        redacted = scrubbed[0]

    redacted = _PROMPT_EMAIL_PATTERN.sub(_REDACTED, redacted)
    redacted = _PROMPT_CPF_PATTERN.sub(_REDACTED, redacted)
    redacted = _PROMPT_PHONE_PATTERN.sub(_REDACTED, redacted)
    return redacted


def sanitize_for_logging(data: dict) -> dict:
    """
    Prepare a dict for structured logging by redacting PII values.

    Any key whose name matches name, phone, email, cpf,
    etc. will have its value replaced with "[REDACTED]".

    Operates recursively on nested dicts. Returns a new dict;
    the original is not mutated.
    """
    if not isinstance(data, dict):
        return data

    sanitized: Dict[str, Any] = {}
    for key, value in data.items():
        lower_key = key.lower()
        if lower_key in _LOG_REDACT_KEYS or _is_pii_key(key):
            sanitized[key] = _REDACTED
        elif isinstance(value, dict):
            sanitized[key] = sanitize_for_logging(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_for_logging(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized
