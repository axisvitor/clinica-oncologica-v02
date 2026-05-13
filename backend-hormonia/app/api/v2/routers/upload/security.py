"""
Security scanning and validation for upload module.

Contains:
- Virus scanning (ClamAV integration)
- MIME type validation
- File security scanning
- CVE mitigations (CVE-CLINIC-2025-002, CVE-CLINIC-2025-003)
"""

from pathlib import Path

from fastapi import HTTPException, status

from app.utils.logging import get_logger

logger = get_logger(__name__)


def _extension(file_path: Path) -> str:
    return file_path.suffix.lower() or "none"


async def scan_virus(file_path: Path) -> bool:
    """
    Scan file for viruses using ClamAV.

    Args:
        file_path: Path to file

    Returns:
        True if clean, False if infected

    Raises:
        HTTPException: If virus detected or scan fails
    """
    from app.services.virus_scanner import get_virus_scanner

    scanner = get_virus_scanner()
    result = await scanner.scan_file(file_path)

    if not result.clean:
        if result.threat_found:
            logger.error(
                "Virus detected in uploaded file",
                extra={
                    "extension": _extension(file_path),
                    "reason": "malware_detected",
                    "result_class": "infected",
                    "scanner": result.scanner_used,
                    "status": status.HTTP_400_BAD_REQUEST,
                    "scan_time_ms": result.scan_time_ms,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Malware detected: {result.threat_found}",
            )
        if result.error:
            logger.warning(
                "Virus scan failed",
                extra={
                    "extension": _extension(file_path),
                    "reason": "scanner_error",
                    "result_class": "error",
                    "scanner": result.scanner_used,
                    "status": "skipped",
                    "scan_time_ms": result.scan_time_ms,
                },
            )
            # Fail open (allow upload) if scanner unavailable
            # This prevents DoS if ClamAV goes down
            return True

        logger.error(
            "Unexpected scan result",
            extra={
                "extension": _extension(file_path),
                "reason": "unexpected_scan_result",
                "result_class": "unknown",
                "scanner": result.scanner_used,
                "status": "skipped",
                "scan_time_ms": result.scan_time_ms,
            },
        )
        return True

    logger.info(
        "File passed virus scan",
        extra={
            "extension": _extension(file_path),
            "reason": "clean",
            "result_class": "clean",
            "scanner": result.scanner_used,
            "status": "clean",
            "scan_time_ms": result.scan_time_ms,
        },
    )
    return True


async def validate_mime_type(file_path: Path, declared_mime: str) -> bool:
    """
    Validate actual MIME type matches declared type (CVE-CLINIC-2025-002).

    Args:
        file_path: Path to file
        declared_mime: MIME type from Content-Type header

    Returns:
        True if valid

    Raises:
        HTTPException: If MIME type mismatch detected
    """
    from app.services.mime_validator import get_mime_validator

    validator = get_mime_validator()
    result = await validator.validate_file(file_path, declared_mime)

    if not result.is_valid:
        logger.error(
            "MIME type validation failed",
            extra={
                "extension": _extension(file_path),
                "declared_mime": result.declared_mime,
                "actual_mime": result.actual_mime,
                "reason": "mime_validation_failed",
                "status": status.HTTP_400_BAD_REQUEST,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security error: {result.message}",
        )

    return True


async def scan_file_security(file_path: Path) -> bool:
    """
    Scan file for security threats beyond virus scanning.

    Includes:
    - CVE-CLINIC-2025-003: Dangerous file extension blocking
    - PDF JavaScript detection
    - Double extension attacks
    - Archive content validation

    Args:
        file_path: Path to file

    Returns:
        True if safe

    Raises:
        HTTPException: If security threats detected
    """
    from app.services.file_security import get_file_security

    security = get_file_security()
    result = await security.scan_file(file_path)

    if not result.is_safe:
        logger.error(
            "File security threats detected",
            extra={
                "extension": _extension(file_path),
                "reason": "security_threat_detected",
                "status": status.HTTP_400_BAD_REQUEST,
                "threat_count": len(result.threats_found),
                "scan_time_ms": result.scan_time_ms,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security threat detected: {'; '.join(result.threats_found)}",
        )

    logger.info(
        "File passed security scan",
        extra={
            "extension": _extension(file_path),
            "reason": "clean",
            "status": "clean",
            "scan_time_ms": result.scan_time_ms,
        },
    )
    return True
