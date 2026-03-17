"""Quiz link helpers extracted from app.tasks.quiz_link_tasks."""

import hashlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 100
_MAX_LIMIT = 500


def _sanitize_limit(limit: int) -> int:
    """Clamp list-processing limits to prevent oversized scans."""
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    return max(1, min(value, _MAX_LIMIT))


def _token_fingerprint(token: str) -> str:
    """Return non-reversible token fingerprint for diagnostics."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _sanitize_error_message(error: Exception | str) -> str:
    """Redact sensitive token/url patterns from persisted error messages."""
    message = str(error)
    message = re.sub(
        r"([?&](?:token|access_token|code)=)[^&\s]+",
        r"\1[REDACTED]",
        message,
        flags=re.IGNORECASE,
    )
    message = re.sub(
        r"(token\s*[:=]\s*)[A-Za-z0-9._\-]{8,}",
        r"\1[REDACTED]",
        message,
        flags=re.IGNORECASE,
    )
    if len(message) > 400:
        return f"{message[:397]}..."
    return message


def _sanitize_dlq_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a safe summary for DLQ responses without leaking sensitive payloads."""
    if not isinstance(record, dict):
        return None

    safe_record: dict[str, Any] = {}
    for key in (
        "reason",
        "retry_count",
        "is_regenerated",
        "token_fingerprint",
        "created_at",
        "timestamp",
    ):
        if key in record:
            safe_record[key] = record[key]

    if "error" in record:
        safe_record["error"] = _sanitize_error_message(record["error"])

    return safe_record
