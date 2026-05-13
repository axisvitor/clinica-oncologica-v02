"""Low-level proof for M014/S04 active web-content upload denial.

The fixtures here are inline bytes/tmp_path only: no planning artifacts, local
ignored directories, or external services are read.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from app.api.v2.routers.upload.active_content import (
    ACTIVE_CONTENT_SAMPLE_BYTES,
    REASON_ACTIVE_CONTENT_SIGNATURE,
    REASON_ACTIVE_DECLARED_MIME,
    REASON_ACTIVE_EXTENSION,
    REASON_ACTIVE_ACTUAL_MIME,
    detect_active_content_bytes,
)
from app.api.v2.routers.upload.validators import validate_file_type
from app.services.file_security import FileSecurityService
from app.services.mime_validator import MimeTypeValidator


@pytest.mark.parametrize(
    "filename",
    [
        "payload.html",
        "payload.HTM",
        "payload.xhtml",
        "diagram.svg",
        "data.xml",
        "report.pdf.svg",
    ],
)
def test_active_content_guard_rejects_active_web_extensions(filename: str):
    result = detect_active_content_bytes(
        b"benign bytes",
        filename=filename,
        declared_mime="text/plain",
    )

    assert result.is_active is True
    assert result.reason == REASON_ACTIVE_EXTENSION
    assert result.safe_log_extra() == {"reason": REASON_ACTIVE_EXTENSION}
    assert filename not in str(result.safe_log_extra())


@pytest.mark.parametrize(
    "declared_mime",
    [
        "text/html",
        "TEXT/HTML; charset=utf-8",
        "image/svg+xml",
        "application/xml",
        "application/xhtml+xml",
        "application/atom+xml",
    ],
)
def test_active_content_guard_rejects_declared_active_mime(declared_mime: str):
    result = detect_active_content_bytes(b"plain bytes", filename="note.txt", declared_mime=declared_mime)

    assert result.is_active is True
    assert result.reason == REASON_ACTIVE_DECLARED_MIME


@pytest.mark.parametrize(
    "payload",
    [
        b"   <!doctype html><title>stored xss</title>",
        b"\xef\xbb\xbf<?xml version='1.0'?><root />",
        b"<svg viewBox='0 0 10 10'></svg>",
        b"Clinical note header\n<script>alert('stored-xss')</script>",
        b"<a href='javascript:alert(1)'>open</a>",
        b"<img src=x onerror=alert(1)>",
    ],
)
def test_active_content_guard_rejects_spoofed_active_signatures(payload: bytes):
    result = detect_active_content_bytes(payload, declared_mime="text/plain", filename="notes.txt")

    assert result.is_active is True
    assert result.reason == REASON_ACTIVE_CONTENT_SIGNATURE
    assert result.safe_log_extra() == {"reason": REASON_ACTIVE_CONTENT_SIGNATURE}
    assert payload.decode("latin-1", errors="ignore") not in str(result.safe_log_extra())


def test_active_content_guard_uses_bounded_byte_sample():
    payload = b"A" * (ACTIVE_CONTENT_SAMPLE_BYTES + 16) + b"<script>alert('past-bound')</script>"

    result = detect_active_content_bytes(payload, declared_mime="text/plain", filename="notes.txt")

    assert result.is_active is False
    assert result.sample_size == ACTIVE_CONTENT_SAMPLE_BYTES


@pytest.mark.parametrize(
    ("filename", "declared_mime"),
    [
        ("payload.html", "text/plain"),
        ("payload.txt.svg", "image/png"),
        ("payload.txt", "text/html"),
        ("payload.txt", "image/svg+xml"),
    ],
)
def test_upload_file_type_validation_rejects_active_extensions_and_declared_mimes(
    filename: str,
    declared_mime: str,
):
    with pytest.raises(HTTPException) as exc_info:
        validate_file_type(filename, declared_mime)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "active_" in str(exc_info.value.detail)
    assert filename not in str(exc_info.value.detail)


@pytest.mark.parametrize(
    ("filename", "declared_mime"),
    [
        ("notes.txt", "text/plain"),
        ("image.png", "image/png"),
        ("report.pdf", "application/pdf"),
    ],
)
def test_upload_file_type_validation_allows_benign_controls(filename: str, declared_mime: str):
    validate_file_type(filename, declared_mime)


@pytest.mark.asyncio
async def test_mime_validator_denies_active_signatures_when_magic_unavailable(tmp_path):
    payload = tmp_path / "notes.txt"
    payload.write_bytes(b"clinical note\n<script>alert(1)</script>")
    validator = MimeTypeValidator(enabled=True)
    validator._magic_available = False
    validator.magic = None

    result = await validator.validate_file(payload, "text/plain")

    assert result.is_valid is False
    assert result.actual_mime == "unknown"
    assert REASON_ACTIVE_CONTENT_SIGNATURE in str(result.message)
    assert str(payload) not in str(result.message)


@pytest.mark.asyncio
async def test_mime_validator_denies_active_declared_mime_without_magic(tmp_path):
    payload = tmp_path / "notes.txt"
    payload.write_bytes(b"plain clinical text")
    validator = MimeTypeValidator(enabled=True)
    validator._magic_available = False
    validator.magic = None

    result = await validator.validate_file(payload, "text/html")

    assert result.is_valid is False
    assert result.actual_mime == "unknown"
    assert REASON_ACTIVE_DECLARED_MIME in str(result.message)


@pytest.mark.asyncio
async def test_mime_validator_denies_active_actual_mime_even_when_same_top_level(tmp_path):
    payload = tmp_path / "notes.txt"
    payload.write_bytes(b"plain clinical text")
    validator = MimeTypeValidator(enabled=True, allow_variance=True)
    validator._magic_available = True
    validator.magic = SimpleNamespace(from_file=lambda *_args, **_kwargs: "text/html")

    result = await validator.validate_file(payload, "text/plain")

    assert result.is_valid is False
    assert result.actual_mime == "text/html"
    assert REASON_ACTIVE_ACTUAL_MIME in str(result.message)


@pytest.mark.asyncio
async def test_mime_validator_allows_benign_same_category_variance(tmp_path):
    payload = tmp_path / "image.png"
    payload.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    validator = MimeTypeValidator(enabled=True, allow_variance=True)
    validator._magic_available = True
    validator.magic = SimpleNamespace(from_file=lambda *_args, **_kwargs: "image/jpeg")

    result = await validator.validate_file(payload, "image/png")

    assert result.is_valid is True
    assert result.confidence == 0.8


@pytest.mark.asyncio
async def test_mime_validator_allows_benign_content_when_magic_unavailable(tmp_path):
    payload = tmp_path / "notes.txt"
    payload.write_bytes(b"clinical note without active markup")
    validator = MimeTypeValidator(enabled=True)
    validator._magic_available = False
    validator.magic = None

    result = await validator.validate_file(payload, "text/plain")

    assert result.is_valid is True
    assert result.actual_mime == "unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "payload"),
    [
        ("spoofed.txt", b"<script>alert('generic')</script>"),
        ("feed.xml", b"<?xml version='1.0'?><root><script>alert(1)</script></root>"),
        ("diagram.svg", b"<svg><script>alert(1)</script></svg>"),
    ],
)
async def test_file_security_detects_generic_script_and_xml_svg_shapes(
    tmp_path,
    filename: str,
    payload: bytes,
):
    file_path = tmp_path / filename
    file_path.write_bytes(payload)
    scanner = FileSecurityService(enabled=True)

    result = await scanner.scan_file(file_path)

    assert result.is_safe is False
    assert any(
        REASON_ACTIVE_CONTENT_SIGNATURE in threat or "script" in threat.lower()
        for threat in result.threats_found
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "payload"),
    [
        ("notes.txt", b"plain clinical note without active markup"),
        ("image.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32),
    ],
)
async def test_file_security_allows_benign_controls(tmp_path, filename: str, payload: bytes):
    file_path = tmp_path / filename
    file_path.write_bytes(payload)
    scanner = FileSecurityService(enabled=True)

    result = await scanner.scan_file(file_path)

    assert result.is_safe is True
    assert result.threats_found == []
