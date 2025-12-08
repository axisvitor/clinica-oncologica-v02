"""
Upload module configuration and constants.

Contains:
- File size limits
- Cache TTL settings
- Rate limits
- Allowed MIME types
- Dangerous extensions
- Upload directory configuration
"""

from pathlib import Path
from app.config import settings

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
}

# ============================================================================
# Upload Directory
# ============================================================================

UPLOAD_DIR = Path(getattr(settings, "UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
