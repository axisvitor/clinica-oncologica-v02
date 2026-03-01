"""
AI Output Guardrails.

Validates and normalizes AI outputs for safety and quality. No fallbacks.
"""

from __future__ import annotations

import json
import re
from enum import Enum
from typing import Iterable, Optional


class OutputKind(str, Enum):
    MESSAGE = "message"
    JSON = "json"


class GuardrailViolation(ValueError):
    """Raised when AI output violates guardrails."""


_BANNED_PATTERNS = [
    r"(?i)\b(as an? ai|as a language model|language model)\b",
    r"(?i)\b(system prompt|system message|developer message)\b",
    r"(?i)\b(chain[- ]?of[- ]?thought|cot|reasoning)\b",
    r"(?i)\b(wait,? the instruction says|finish the sentence)\b",
    r"(?i)```|<think>|</think>",
]

_PROMPT_LEAK_MARKERS = [
    "MENSAGEM HUMANIZADA",
    "NOVA PERGUNTA",
    "RESPOSTA EMPÁTICA",
    "ANÁLISE",
    "EXEMPLOS DE REFERÊNCIA",
]

_PLACEHOLDER_PATTERNS = [
    r"\{[^}]+\}",  # {variable}
    r"\[[A-Z_ ]+\]",  # [NOME]
]

_ENDING_PUNCTUATION_PATTERN = re.compile(r"[.!?…][\"')\]]*$")


def _is_terminal_placeholder(text: str) -> bool:
    """Allow templates that intentionally end with placeholders."""
    if not text:
        return False
    trimmed = text.strip()
    return bool(
        re.search(r"\{[^}]+\}\s*$", trimmed)
        or re.search(r"\[[A-Z_ ]+\]\s*$", trimmed)
    )


def normalize_ai_output(text: str) -> str:
    """Normalize AI output without changing meaning."""
    if not text:
        return ""
    cleaned = text.strip()
    # Strip wrapping quotes
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()
    # Strip code fences if model wrapped the response
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned.strip("`").strip()
    return cleaned


def _extract_json_block(text: str) -> Optional[str]:
    """Extract the first valid JSON object/array from text."""
    if not text:
        return None

    for start in range(len(text)):
        if text[start] not in "{[":
            continue

        stack = [text[start]]
        in_string = False
        escape = False

        for idx in range(start + 1, len(text)):
            ch = text[idx]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if not stack:
                    break
                opener = stack.pop()
                if (opener == "{" and ch != "}") or (opener == "[" and ch != "]"):
                    break
                if not stack:
                    candidate = text[start : idx + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except Exception:
                        break
    return None


def normalize_json_output(text: str) -> str:
    """Normalize and repair JSON output when possible."""
    cleaned = normalize_ai_output(text)
    try:
        json.loads(cleaned)
        return cleaned
    except Exception:
        candidate = _extract_json_block(cleaned)
        return candidate or cleaned




def validate_ai_output(
    text: str,
    kind: OutputKind,
    min_length: int = 3,
    max_length: int = 1600,
    required_keys: Optional[Iterable[str]] = None,
    require_ending_punctuation: bool = False,
    allow_placeholders: bool = False,
) -> None:
    """Validate AI output for the expected kind."""
    if not text or not text.strip():
        raise GuardrailViolation("empty_output")

    normalized = text.strip()
    if len(normalized) < min_length:
        raise GuardrailViolation("output_too_short")
    if max_length and len(normalized) > max_length:
        raise GuardrailViolation("output_too_long")

    if kind == OutputKind.MESSAGE:
        for pattern in _BANNED_PATTERNS:
            if re.search(pattern, normalized):
                raise GuardrailViolation("meta_or_instruction_leak")
        for marker in _PROMPT_LEAK_MARKERS:
            if marker in normalized:
                raise GuardrailViolation("prompt_echo_detected")
        if not allow_placeholders:
            for pattern in _PLACEHOLDER_PATTERNS:
                if re.search(pattern, normalized):
                    raise GuardrailViolation("placeholder_detected")
        if require_ending_punctuation:
            if _is_terminal_placeholder(normalized):
                return
            if not _ENDING_PUNCTUATION_PATTERN.search(normalized):
                raise GuardrailViolation("missing_ending_punctuation")

    elif kind == OutputKind.JSON:
        try:
            parsed = json.loads(normalized)
        except Exception as exc:  # noqa: BLE001
            raise GuardrailViolation("invalid_json") from exc

        if required_keys:
            missing = [key for key in required_keys if key not in parsed]
            if missing:
                raise GuardrailViolation(f"missing_keys:{','.join(missing)}")
    else:
        raise GuardrailViolation(f"unsupported_output_kind:{kind}")
