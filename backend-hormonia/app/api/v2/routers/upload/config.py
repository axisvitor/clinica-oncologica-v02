"""
Upload module configuration and path helpers.

The upload subsystem deliberately separates the public static mount from private
local storage.  ``/uploads`` must point only at the public root; private records
are resolved through the authenticated API route using the safe helpers below.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from app.config import settings

from .active_content import ACTIVE_WEB_EXTENSIONS, ACTIVE_WEB_MIME_TYPES

# ============================================================================
# Upload Limits
# ============================================================================

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB default
MAX_FILE_SIZE_ABSOLUTE = 50 * 1024 * 1024  # 50MB absolute max
DEFAULT_USER_QUOTA = 1 * 1024 * 1024 * 1024  # 1GB per user

# ============================================================================
# Cache TTLs (in seconds)
# ============================================================================

CACHE_TTL_METADATA = 1800  # 30 minutes for upload metadata
CACHE_TTL_FILE_INFO = 3600  # 1 hour for file info
CACHE_TTL_USER_STATS = 900  # 15 minutes for user stats

# ============================================================================
# Rate Limits (per hour)
# ============================================================================

RATE_LIMIT_SMALL_FILE = 20  # Files < 1MB
RATE_LIMIT_LARGE_FILE = 10  # Files >= 1MB

# ============================================================================
# Allowed MIME Types
# ============================================================================

ALLOWED_MIME_TYPES = {
    # Images
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
    # Videos
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/webm",
    # Audio
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # Text
    "text/plain",
    "text/csv",
}

# ============================================================================
# Active Web Content (always reject before persistence)
# ============================================================================

ACTIVE_UPLOAD_EXTENSIONS = ACTIVE_WEB_EXTENSIONS
ACTIVE_UPLOAD_MIME_TYPES = ACTIVE_WEB_MIME_TYPES

# ============================================================================
# Dangerous Extensions (always reject)
# ============================================================================

DANGEROUS_EXTENSIONS = {
    ".exe",
    ".bat",
    ".cmd",
    ".com",
    ".pif",
    ".scr",
    ".vbs",
    ".js",
    ".jar",
    ".sh",
    ".app",
} | ACTIVE_UPLOAD_EXTENSIONS

# ============================================================================
# Upload Directory Helpers
# ============================================================================

PUBLIC_STORAGE_PREFIX = "public"
PRIVATE_STORAGE_PREFIX = "private"
_STORAGE_PREFIXES = {PUBLIC_STORAGE_PREFIX, PRIVATE_STORAGE_PREFIX}

# Compatibility seam for tests and older imports.  Runtime helpers consult this
# only when it has been monkeypatched; otherwise they read settings lazily.
UPLOAD_DIR: Path | None = None


class UnsafeUploadPath(ValueError):
    """Raised when persisted upload metadata cannot be resolved safely."""


@dataclass(frozen=True)
class ResolvedUploadPath:
    """Safe local storage resolution result."""

    path: Path
    relative_path: str
    visibility: str
    legacy: bool = False


def _configured_upload_directory() -> Path:
    configured = UPLOAD_DIR
    if configured is None:
        configured = Path(getattr(settings, "UPLOAD_DIRECTORY", "uploads"))
    return Path(configured)


def _ensure_directory(path: Path, *, create: bool) -> Path:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def get_upload_root(*, create: bool = True) -> Path:
    """Return the common upload root from current settings/test patches."""

    return _ensure_directory(_configured_upload_directory(), create=create)


def get_public_upload_root(*, create: bool = True) -> Path:
    """Return the only directory that may be mounted at ``/uploads``."""

    public_dir = getattr(settings, "UPLOAD_PUBLIC_SUBDIRECTORY", PUBLIC_STORAGE_PREFIX)
    return _ensure_directory(get_upload_root(create=create) / public_dir, create=create)


def get_private_upload_root(*, create: bool = True) -> Path:
    """Return the unmounted local private upload root.

    By default this is a sibling hidden directory rather than a child of the
    public mount root.  That fail-closed choice prevents accidental exposure even
    if an older test or local app accidentally mounts the common upload root.
    """

    explicit_private_dir = getattr(settings, "UPLOAD_PRIVATE_DIRECTORY", "")
    if explicit_private_dir:
        private_root = Path(explicit_private_dir)
    else:
        common_root = get_upload_root(create=create)
        private_root = common_root.parent / f".{common_root.name}_private"
    return _ensure_directory(private_root, create=create)


def get_storage_root(*, public: bool, create: bool = True) -> Path:
    """Return the physical root for a public or private upload."""

    return get_public_upload_root(create=create) if public else get_private_upload_root(create=create)


def _to_posix_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def build_storage_path(file_path: Path, *, public: bool) -> str:
    """Build an unambiguous persisted storage path for a local file."""

    visibility = PUBLIC_STORAGE_PREFIX if public else PRIVATE_STORAGE_PREFIX
    root = get_storage_root(public=public, create=False)
    relative = _to_posix_relative(file_path, root)
    return f"{visibility}/{relative}"


def gated_download_url(upload_id) -> str:
    """Return the authenticated download endpoint for an upload ID."""

    return f"/api/v2/upload/{upload_id}/download"


def public_url_for_storage_path(storage_path: str) -> str:
    """Return a public URL for a public storage path."""

    visibility, relative_path = split_storage_path(storage_path)
    if visibility == PRIVATE_STORAGE_PREFIX:
        raise UnsafeUploadPath("private storage path has no public URL")
    return f"/uploads/{relative_path}"


def response_url_for_upload(upload_id, storage_path: str, *, public: bool) -> str:
    """Return the client-facing URL for an upload without exposing private files."""

    if public:
        return public_url_for_storage_path(storage_path)
    return gated_download_url(upload_id)


def _validate_relative_storage_path(storage_path: str) -> str:
    raw_path = str(storage_path or "").strip()
    if not raw_path:
        raise UnsafeUploadPath("empty storage path")
    if "\\" in raw_path:
        raise UnsafeUploadPath("backslash storage path")
    if raw_path.startswith("/"):
        raise UnsafeUploadPath("absolute storage path")

    normalized = PurePosixPath(raw_path)
    parts = normalized.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise UnsafeUploadPath("unsafe storage path segment")
    if any(":" in part for part in parts):
        raise UnsafeUploadPath("unsafe storage path segment")

    return normalized.as_posix()


def split_storage_path(storage_path: str) -> tuple[str | None, str]:
    """Split an optional visibility prefix from a persisted storage path."""

    safe_path = _validate_relative_storage_path(storage_path)
    parts = safe_path.split("/", 1)
    if parts[0] in _STORAGE_PREFIXES:
        if len(parts) == 1 or not parts[1]:
            raise UnsafeUploadPath("storage path missing relative segment")
        return parts[0], parts[1]
    return None, safe_path


def _safe_candidate(root: Path, relative_path: str) -> Path:
    candidate = root / relative_path
    resolved_root = root.resolve(strict=False)
    resolved_candidate = candidate.resolve(strict=False)
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise UnsafeUploadPath("storage path escapes root") from exc
    return resolved_candidate


def _candidate_paths(storage_path: str, *, public: bool) -> Iterable[ResolvedUploadPath]:
    visibility, relative_path = split_storage_path(storage_path)
    expected_visibility = PUBLIC_STORAGE_PREFIX if public else PRIVATE_STORAGE_PREFIX

    if visibility and visibility != expected_visibility:
        raise UnsafeUploadPath("storage visibility mismatch")

    if visibility == PUBLIC_STORAGE_PREFIX:
        yield ResolvedUploadPath(
            path=_safe_candidate(get_public_upload_root(create=False), relative_path),
            relative_path=relative_path,
            visibility=visibility,
        )
        return

    if visibility == PRIVATE_STORAGE_PREFIX:
        yield ResolvedUploadPath(
            path=_safe_candidate(get_private_upload_root(create=False), relative_path),
            relative_path=relative_path,
            visibility=visibility,
        )
        return

    # Legacy records did not include a visibility prefix.  Prefer the new root,
    # but allow already-persisted local rows under the common upload root so
    # gated download can recover while public static serving remains public-only.
    primary_root = get_public_upload_root(create=False) if public else get_private_upload_root(create=False)
    yield ResolvedUploadPath(
        path=_safe_candidate(primary_root, relative_path),
        relative_path=relative_path,
        visibility=expected_visibility,
        legacy=True,
    )

    yield ResolvedUploadPath(
        path=_safe_candidate(get_upload_root(create=False), relative_path),
        relative_path=relative_path,
        visibility=expected_visibility,
        legacy=True,
    )


def resolve_local_upload_path(
    storage_path: str,
    *,
    public: bool,
    require_exists: bool = False,
) -> ResolvedUploadPath:
    """Resolve a persisted local storage path without allowing traversal.

    The returned file is guaranteed to remain inside one of the allowed roots.
    When multiple legacy candidates are safe, an existing path wins; otherwise
    the first safe candidate is returned unless ``require_exists`` is true.
    """

    candidates = list(_candidate_paths(storage_path, public=public))
    for candidate in candidates:
        if candidate.path.exists():
            return candidate

    if require_exists:
        raise FileNotFoundError("upload file not found")

    if candidates:
        return candidates[0]

    raise UnsafeUploadPath("unresolvable storage path")
