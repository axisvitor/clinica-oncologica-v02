"""Safe file-download response helpers.

The helpers in this module keep application-served private artifacts from being
rendered inline by a browser.  They intentionally avoid embedding raw storage
paths or caller-supplied filenames in response headers.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from fastapi.responses import FileResponse

from app.api.v2.routers.upload.active_content import (
    is_active_extension,
    is_active_mime,
    normalize_mime,
)

OCTET_STREAM = "application/octet-stream"

_UNKNOWN_MIME_TYPES = frozenset(
    {
        "",
        "application/octet-stream",
        "application/unknown",
        "binary/octet-stream",
        "unknown/unknown",
    }
)

_SAFE_DOWNLOAD_MIME_TYPES = frozenset(
    {
        "application/msword",
        "application/pdf",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "audio/mp3",
        "audio/mpeg",
        "audio/ogg",
        "audio/wav",
        "audio/webm",
        "image/gif",
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "text/csv",
        "text/plain",
        "video/mp4",
        "video/mpeg",
        "video/quicktime",
        "video/webm",
    }
)

_CONTROL_OR_SEPARATOR = re.compile(r'[\x00-\x1f\x7f"\\/;]')


def safe_attachment_filename(filename: str | None, *, fallback: str = "download") -> str:
    """Return a basename-only attachment filename safe for response headers."""

    raw_name = Path(str(filename or "")).name
    cleaned = _CONTROL_OR_SEPARATOR.sub("_", raw_name).strip(" ._")
    if not cleaned:
        cleaned = fallback

    if len(cleaned) <= 120:
        return cleaned

    suffix = Path(cleaned).suffix
    if len(suffix) > 16:
        suffix = ""
    stem_limit = max(1, 120 - len(suffix))
    return f"{cleaned[:stem_limit].rstrip(' ._')}{suffix}" or fallback


def safe_download_media_type(
    declared_media_type: str | None,
    *,
    filename: str | None = None,
    storage_path: str | None = None,
) -> str:
    """Choose a browser-safe media type for attachment downloads."""

    normalized = normalize_mime(declared_media_type)
    names = (filename, storage_path)
    if any(is_active_extension(name) for name in names) or is_active_mime(normalized):
        return OCTET_STREAM
    if normalized in _UNKNOWN_MIME_TYPES or normalized not in _SAFE_DOWNLOAD_MIME_TYPES:
        return OCTET_STREAM
    return normalized


def attachment_headers(filename: str) -> dict[str, str]:
    """Build non-executable attachment headers for private/gated downloads."""

    quoted = quote(filename)
    if quoted == filename:
        disposition = f'attachment; filename="{filename}"'
    else:
        disposition = f"attachment; filename*=utf-8''{quoted}"

    return {
        "Content-Disposition": disposition,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }


def build_attachment_file_response(
    path: Path,
    *,
    filename: str | None,
    declared_media_type: str | None,
    storage_path: str | None = None,
) -> FileResponse:
    """Build a ``FileResponse`` that always downloads rather than inline-renders."""

    safe_filename = safe_attachment_filename(filename)
    media_type = safe_download_media_type(
        declared_media_type,
        filename=safe_filename,
        storage_path=storage_path,
    )
    return FileResponse(
        path=path,
        media_type=media_type,
        headers=attachment_headers(safe_filename),
    )
