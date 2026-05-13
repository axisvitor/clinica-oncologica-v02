"""
MIME Type Validation Service

Prevents CVE-CLINIC-2025-002: MIME type spoofing vulnerability.

Uses python-magic (libmagic) to validate actual file content matches
declared MIME type, preventing attackers from uploading malicious files
by changing the extension or Content-Type header.

Example Attack Prevented:
    malware.exe renamed to document.pdf with Content-Type: application/pdf
    → Validation detects actual MIME type is application/x-msdownload
    → Upload rejected with HTTP 400
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.api.v2.routers.upload.active_content import (
    REASON_ACTIVE_ACTUAL_MIME,
    detect_active_content_from_path,
    is_active_mime,
)

logger = logging.getLogger(__name__)


@dataclass
class MimeValidationResult:
    """MIME validation result."""

    is_valid: bool
    declared_mime: str
    actual_mime: str
    message: Optional[str] = None
    confidence: float = 1.0  # 0.0 to 1.0


class MimeTypeValidator:
    """
    Validate actual file MIME type matches declared type.

    Prevents MIME type spoofing attacks by using libmagic to analyze
    file content, not just relying on file extension or headers.

    Configuration (via environment variables):
        MIME_VALIDATION_ENABLED: Enable MIME validation (default: True)
        MIME_VALIDATION_STRICT: Reject fuzzy matches (default: False)
        MIME_ALLOWED_VARIANCE: Allow similar types (e.g., image/jpg vs image/jpeg)
    """

    # MIME type aliases (different representations of same type)
    MIME_ALIASES = {
        "image/jpg": "image/jpeg",
        "image/pjpeg": "image/jpeg",
        "video/x-msvideo": "video/avi",
        "application/x-zip-compressed": "application/zip",
        "application/x-rar-compressed": "application/x-rar",
    }

    # Dangerous MIME types that should ALWAYS be blocked
    DANGEROUS_MIMES = {
        "application/x-msdownload",  # .exe
        "application/x-executable",  # Linux executables
        "application/x-mach-binary",  # macOS executables
        "application/x-sharedlib",  # .so files
        "application/x-sh",  # Shell scripts
        "application/x-bat",  # Batch files
        "application/x-dosexec",  # DOS executables
        "text/x-shellscript",  # Shell scripts
        "application/javascript",  # Standalone JS (different from in HTML)
        "application/x-python-code",  # Python bytecode
    }

    # File extensions that MUST match MIME type exactly
    STRICT_EXTENSIONS = {
        ".exe",
        ".dll",
        ".so",
        ".dylib",  # Executables/libraries
        ".sh",
        ".bat",
        ".cmd",
        ".ps1",  # Scripts
        ".jar",
        ".war",
        ".ear",  # Java archives
        ".deb",
        ".rpm",  # Package managers
    }

    def __init__(
        self, enabled: bool = True, strict: bool = False, allow_variance: bool = True
    ):
        """
        Initialize MIME validator.

        Args:
            enabled: Enable MIME validation (default: True)
            strict: Reject fuzzy matches (default: False)
            allow_variance: Allow similar types like image/jpg vs image/jpeg
        """
        self.enabled = enabled
        self.strict = strict
        self.allow_variance = allow_variance

        # Try to import python-magic
        try:
            import magic

            self.magic = magic
            self._magic_available = True
            logger.info("MIME validation initialized with python-magic")
        except ImportError:
            self.magic = None
            self._magic_available = False
            logger.warning(
                "python-magic not available - MIME validation disabled. "
                "Install with: pip install python-magic python-magic-bin"
            )

    async def validate_file(
        self, file_path: Path, declared_mime: str, file_extension: Optional[str] = None
    ) -> MimeValidationResult:
        """
        Validate file MIME type.

        Args:
            file_path: Path to file
            declared_mime: MIME type declared by client (from Content-Type header)
            file_extension: File extension (optional, extracted from filename if None)

        Returns:
            MimeValidationResult with validation outcome
        """
        active_check = None
        try:
            active_check = detect_active_content_from_path(
                file_path,
                declared_mime=declared_mime,
                filename=file_extension or file_path.name,
            )
        except Exception as e:
            logger.warning(
                "Active content precheck failed",
                extra={"reason": e.__class__.__name__, "status": "skipped"},
            )

        if active_check and active_check.is_active:
            logger.warning(
                "Active web content denied during MIME validation",
                extra=active_check.safe_log_extra(),
            )
            return MimeValidationResult(
                is_valid=False,
                declared_mime=declared_mime,
                actual_mime="unknown",
                message=f"Active web content denied: {active_check.reason}",
                confidence=1.0,
            )

        if not self.enabled or not self._magic_available:
            return MimeValidationResult(
                is_valid=True,
                declared_mime=declared_mime,
                actual_mime="unknown",
                message="MIME validation disabled or python-magic unavailable",
                confidence=0.0,
            )

        try:
            # Get actual MIME type from file content
            actual_mime = self.magic.from_file(str(file_path), mime=True)

            # Normalize MIME types (handle aliases)
            declared_normalized = self._normalize_mime(declared_mime)
            actual_normalized = self._normalize_mime(actual_mime)

            # Check if file extension requires strict validation
            extension = file_extension or file_path.suffix.lower()
            requires_strict = extension in self.STRICT_EXTENSIONS

            # Active web document/script MIME must never pass same-category variance.
            if is_active_mime(actual_normalized):
                logger.warning(
                    "Active actual MIME denied",
                    extra={
                        "reason": REASON_ACTIVE_ACTUAL_MIME,
                        "declared_mime": declared_mime,
                        "actual_mime": actual_mime,
                    },
                )
                return MimeValidationResult(
                    is_valid=False,
                    declared_mime=declared_mime,
                    actual_mime=actual_mime,
                    message=f"Active web content denied: {REASON_ACTIVE_ACTUAL_MIME}",
                    confidence=1.0,
                )

            # Block dangerous MIME types regardless of declared type
            if actual_normalized in self.DANGEROUS_MIMES:
                logger.error(
                    f"Dangerous MIME type detected: {actual_normalized}",
                    extra={
                        "file_path": str(file_path),
                        "declared_mime": declared_mime,
                        "actual_mime": actual_mime,
                    },
                )
                return MimeValidationResult(
                    is_valid=False,
                    declared_mime=declared_mime,
                    actual_mime=actual_mime,
                    message=f"Dangerous file type detected: {actual_normalized}",
                    confidence=1.0,
                )

            # Exact match
            if declared_normalized == actual_normalized:
                return MimeValidationResult(
                    is_valid=True,
                    declared_mime=declared_mime,
                    actual_mime=actual_mime,
                    message="MIME types match exactly",
                    confidence=1.0,
                )

            # Fuzzy match (same category)
            if self.allow_variance and not requires_strict:
                if self._is_similar_mime(declared_normalized, actual_normalized):
                    return MimeValidationResult(
                        is_valid=True,
                        declared_mime=declared_mime,
                        actual_mime=actual_mime,
                        message="MIME types are similar (same category)",
                        confidence=0.8,
                    )

            # Mismatch detected
            logger.warning(
                "MIME type mismatch detected",
                extra={
                    "file_path": str(file_path),
                    "declared_mime": declared_mime,
                    "actual_mime": actual_mime,
                    "extension": extension,
                    "requires_strict": requires_strict,
                },
            )

            return MimeValidationResult(
                is_valid=False,
                declared_mime=declared_mime,
                actual_mime=actual_mime,
                message=f"MIME type mismatch: declared {declared_mime}, actual {actual_mime}",
                confidence=1.0,
            )

        except Exception as e:
            logger.error(f"MIME validation failed: {e}", exc_info=True)
            # Fail open (allow) on validation error to prevent DoS
            return MimeValidationResult(
                is_valid=True,
                declared_mime=declared_mime,
                actual_mime="error",
                message=f"Validation error (fail-open): {str(e)}",
                confidence=0.0,
            )

    def _normalize_mime(self, mime_type: str) -> str:
        """
        Normalize MIME type by resolving aliases.

        Args:
            mime_type: Original MIME type

        Returns:
            Normalized MIME type
        """
        mime_type = mime_type.lower().strip()

        # Remove parameters (e.g., "text/html; charset=utf-8" → "text/html")
        if ";" in mime_type:
            mime_type = mime_type.split(";")[0].strip()

        # Resolve alias
        return self.MIME_ALIASES.get(mime_type, mime_type)

    def _is_similar_mime(self, mime1: str, mime2: str) -> bool:
        """
        Check if two MIME types are similar (same category).

        Args:
            mime1: First MIME type
            mime2: Second MIME type

        Returns:
            True if same category (e.g., both image/*, both video/*)
        """
        category1 = mime1.split("/")[0] if "/" in mime1 else mime1
        category2 = mime2.split("/")[0] if "/" in mime2 else mime2

        return category1 == category2


# Singleton instance
_mime_validator: Optional[MimeTypeValidator] = None


def get_mime_validator() -> MimeTypeValidator:
    """
    Get or create MIME validator singleton.

    Returns:
        MimeTypeValidator instance
    """
    global _mime_validator

    if _mime_validator is None:
        _mime_validator = MimeTypeValidator()

    return _mime_validator
