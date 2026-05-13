"""Shared active web-content guard for upload validation.

This module intentionally returns only coarse reason codes.  Callers can emit the
codes in logs or HTTP errors without echoing filenames, storage paths, PHI, or
uploaded bytes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Pattern

ACTIVE_CONTENT_SAMPLE_BYTES = 64 * 1024

ACTIVE_WEB_EXTENSIONS = frozenset(
    {
        ".html",
        ".htm",
        ".shtml",
        ".xhtml",
        ".xht",
        ".svg",
        ".xml",
    }
)

ACTIVE_WEB_MIME_TYPES = frozenset(
    {
        "application/ecmascript",
        "application/javascript",
        "application/x-javascript",
        "application/xhtml+xml",
        "application/xml",
        "image/svg+xml",
        "text/ecmascript",
        "text/html",
        "text/javascript",
        "text/vbscript",
        "text/xml",
    }
)

REASON_ACTIVE_EXTENSION = "active_extension"
REASON_ACTIVE_DECLARED_MIME = "active_declared_mime"
REASON_ACTIVE_ACTUAL_MIME = "active_actual_mime"
REASON_ACTIVE_CONTENT_SIGNATURE = "active_content_signature"

_SAFE_INACTIVE_REASON = "none"

_SIGNATURE_PATTERNS: tuple[tuple[str, Pattern[bytes]], ...] = (
    ("html_doctype", re.compile(rb"^\s*(?:\xef\xbb\xbf)?\s*<!doctype\s+html\b", re.IGNORECASE | re.DOTALL)),
    ("html_tag", re.compile(rb"<\s*html\b", re.IGNORECASE | re.DOTALL)),
    ("html_body_tag", re.compile(rb"<\s*body\b", re.IGNORECASE | re.DOTALL)),
    ("html_head_tag", re.compile(rb"<\s*head\b", re.IGNORECASE | re.DOTALL)),
    ("svg_tag", re.compile(rb"<\s*svg\b", re.IGNORECASE | re.DOTALL)),
    ("xml_declaration", re.compile(rb"^\s*(?:\xef\xbb\xbf)?\s*<\?xml\b", re.IGNORECASE | re.DOTALL)),
    ("script_tag", re.compile(rb"<\s*script\b", re.IGNORECASE | re.DOTALL)),
    ("javascript_url", re.compile(rb"javascript\s*:", re.IGNORECASE | re.DOTALL)),
    ("event_handler_attr", re.compile(rb"\bon[a-z][a-z0-9_-]{2,32}\s*=", re.IGNORECASE | re.DOTALL)),
)


@dataclass(frozen=True)
class ActiveContentResult:
    """Coarse active-content classification result safe for diagnostics."""

    is_active: bool
    reason: str | None = None
    signature: str | None = None
    sample_size: int = 0

    def safe_log_extra(self) -> dict[str, str]:
        """Return PHI/path/byte-safe metadata for logs or HTTP errors."""

        return {"reason": self.reason or _SAFE_INACTIVE_REASON}


def normalize_mime(mime_type: str | None) -> str:
    """Normalize a MIME type for deterministic comparisons."""

    normalized = (mime_type or "").lower().strip()
    if ";" in normalized:
        normalized = normalized.split(";", 1)[0].strip()
    return normalized


def is_active_mime(mime_type: str | None) -> bool:
    """Return True for executable web-document/script MIME families."""

    normalized = normalize_mime(mime_type)
    if not normalized:
        return False
    return normalized in ACTIVE_WEB_MIME_TYPES or normalized.endswith("+xml")


def _suffixes(filename_or_extension: str | None) -> tuple[str, ...]:
    raw_value = (filename_or_extension or "").strip().lower()
    if not raw_value:
        return ()
    if raw_value.startswith(".") and "/" not in raw_value and "\\" not in raw_value:
        return (raw_value,)
    return tuple(Path(raw_value).suffixes)


def is_active_extension(filename_or_extension: str | None) -> bool:
    """Return True when any suffix is an active web-document extension."""

    return any(suffix in ACTIVE_WEB_EXTENSIONS for suffix in _suffixes(filename_or_extension))


def detect_active_signature(content: bytes | bytearray | memoryview, *, sample_size: int = ACTIVE_CONTENT_SAMPLE_BYTES) -> ActiveContentResult:
    """Inspect only a bounded byte sample for active web-content signatures."""

    sample = bytes(content[:sample_size])
    for signature, pattern in _SIGNATURE_PATTERNS:
        if pattern.search(sample):
            return ActiveContentResult(
                is_active=True,
                reason=REASON_ACTIVE_CONTENT_SIGNATURE,
                signature=signature,
                sample_size=len(sample),
            )
    return ActiveContentResult(is_active=False, sample_size=len(sample))


def detect_active_content_bytes(
    content: bytes | bytearray | memoryview,
    *,
    declared_mime: str | None = None,
    filename: str | None = None,
    actual_mime: str | None = None,
    sample_size: int = ACTIVE_CONTENT_SAMPLE_BYTES,
) -> ActiveContentResult:
    """Classify upload metadata and first bytes for active web content."""

    if is_active_extension(filename):
        return ActiveContentResult(is_active=True, reason=REASON_ACTIVE_EXTENSION)
    if is_active_mime(declared_mime):
        return ActiveContentResult(is_active=True, reason=REASON_ACTIVE_DECLARED_MIME)
    if is_active_mime(actual_mime):
        return ActiveContentResult(is_active=True, reason=REASON_ACTIVE_ACTUAL_MIME)
    return detect_active_signature(content, sample_size=sample_size)


def detect_active_content_from_path(
    file_path: Path,
    *,
    declared_mime: str | None = None,
    filename: str | None = None,
    actual_mime: str | None = None,
    sample_size: int = ACTIVE_CONTENT_SAMPLE_BYTES,
) -> ActiveContentResult:
    """Read a bounded sample from disk and classify it for active content."""

    logical_name = filename if filename is not None else file_path.name
    if is_active_extension(logical_name):
        return ActiveContentResult(is_active=True, reason=REASON_ACTIVE_EXTENSION)
    if is_active_mime(declared_mime):
        return ActiveContentResult(is_active=True, reason=REASON_ACTIVE_DECLARED_MIME)
    if is_active_mime(actual_mime):
        return ActiveContentResult(is_active=True, reason=REASON_ACTIVE_ACTUAL_MIME)

    with file_path.open("rb") as handle:
        sample = handle.read(sample_size)
    return detect_active_signature(sample, sample_size=sample_size)
