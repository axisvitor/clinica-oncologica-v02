"""
Version Utility Functions for Template Management.

Provides standardized version handling across template loaders and validators.
Supports both legacy integer versions and semantic versioning (x.y.z).
"""

from typing import Union, Tuple, Optional, Dict
import re
import logging

logger = logging.getLogger(__name__)

# Semantic version pattern (x.y.z where x, y, z are integers)
VERSION_PATTERN = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')


class VersionError(ValueError):
    """Raised when version format is invalid."""
    pass


def parse_version(version: Union[str, int, None]) -> Tuple[int, int, int]:
    """
    Parse version string or int to tuple.

    Supports:
    - Semantic versioning: "1.2.3" -> (1, 2, 3)
    - Legacy integer: 1 -> (1, 0, 0)
    - String integer: "1" -> (1, 0, 0)

    Args:
        version: Version as string, int, or None

    Returns:
        Tuple of (major, minor, patch) version numbers

    Raises:
        VersionError: If version format is invalid

    Examples:
        >>> parse_version("1.2.3")
        (1, 2, 3)
        >>> parse_version(1)
        (1, 0, 0)
        >>> parse_version("2")
        (2, 0, 0)
    """
    if version is None:
        return (1, 0, 0)  # Default version

    # Handle integer versions (legacy format)
    if isinstance(version, int):
        return (version, 0, 0)

    # Convert to string for pattern matching
    version_str = str(version).strip()

    # Try semantic versioning pattern first
    match = VERSION_PATTERN.match(version_str)
    if match:
        return tuple(int(x) for x in match.groups())

    # Try to parse as simple integer (legacy format)
    try:
        v = int(version_str)
        return (v, 0, 0)
    except ValueError:
        raise VersionError(
            f"Invalid version format: {version}. "
            f"Expected semantic version (x.y.z) or integer."
        )


def normalize_version(version: Union[str, int, None]) -> str:
    """
    Convert any version to standard semantic version string format.

    Args:
        version: Version as string, int, or None

    Returns:
        Normalized version string in format "x.y.z"

    Examples:
        >>> normalize_version(1)
        '1.0.0'
        >>> normalize_version("2")
        '2.0.0'
        >>> normalize_version("1.2.3")
        '1.2.3'
    """
    major, minor, patch = parse_version(version)
    return f"{major}.{minor}.{patch}"


def to_int_version(version: Union[str, int, None]) -> int:
    """
    Convert version to integer (major version only).

    Used for backward compatibility with systems that only support integer versions.

    Args:
        version: Version as string, int, or None

    Returns:
        Integer representing major version number

    Examples:
        >>> to_int_version("1.2.3")
        1
        >>> to_int_version(2)
        2
    """
    major, _, _ = parse_version(version)
    return major


def compare_versions(v1: Union[str, int, None], v2: Union[str, int, None]) -> int:
    """
    Compare two versions.

    Args:
        v1: First version
        v2: Second version

    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2

    Examples:
        >>> compare_versions("1.0.0", "2.0.0")
        -1
        >>> compare_versions("2.1.0", "2.0.5")
        1
        >>> compare_versions(1, "1.0.0")
        0
    """
    t1 = parse_version(v1)
    t2 = parse_version(v2)

    # Compare tuples lexicographically
    if t1 < t2:
        return -1
    elif t1 > t2:
        return 1
    else:
        return 0


def is_valid_version(version: Union[str, int, None]) -> bool:
    """
    Check if version is valid.

    Args:
        version: Version to validate

    Returns:
        True if valid, False otherwise

    Examples:
        >>> is_valid_version("1.2.3")
        True
        >>> is_valid_version(1)
        True
        >>> is_valid_version("invalid")
        False
    """
    try:
        parse_version(version)
        return True
    except (VersionError, ValueError, TypeError):
        return False


def is_semantic_version(version_str: str) -> bool:
    """
    Check if string follows semantic versioning format (x.y.z).

    Args:
        version_str: Version string to check

    Returns:
        True if semantic version, False otherwise

    Examples:
        >>> is_semantic_version("1.2.3")
        True
        >>> is_semantic_version("1")
        False
    """
    return VERSION_PATTERN.match(str(version_str)) is not None


def get_major_version(version: Union[str, int, None]) -> int:
    """Get major version number from version.

    Args:
        version: Version as string, int, or None

    Returns:
        Major version number (first component)

    Example:
        >>> get_major_version("2.5.1")
        2
        >>> get_major_version(3)
        3
    """
    major, _, _ = parse_version(version)
    return major


def get_minor_version(version: Union[str, int, None]) -> int:
    """Get minor version number from version.

    Args:
        version: Version as string, int, or None

    Returns:
        Minor version number (second component)

    Example:
        >>> get_minor_version("2.5.1")
        5
        >>> get_minor_version(3)
        0
    """
    _, minor, _ = parse_version(version)
    return minor


def get_patch_version(version: Union[str, int, None]) -> int:
    """Get patch version number from version.

    Args:
        version: Version as string, int, or None

    Returns:
        Patch version number (third component)

    Example:
        >>> get_patch_version("2.5.1")
        1
        >>> get_patch_version(3)
        0
    """
    _, _, patch = parse_version(version)
    return patch


def increment_major(version: Union[str, int, None]) -> str:
    """Increment major version (reset minor and patch to 0).

    Args:
        version: Version to increment

    Returns:
        New version string with incremented major version

    Example:
        >>> increment_major("1.2.3")
        '2.0.0'
        >>> increment_major(1)
        '2.0.0'
    """
    major, _, _ = parse_version(version)
    return f"{major + 1}.0.0"


def increment_minor(version: Union[str, int, None]) -> str:
    """Increment minor version (reset patch to 0).

    Args:
        version: Version to increment

    Returns:
        New version string with incremented minor version

    Example:
        >>> increment_minor("1.2.3")
        '1.3.0'
        >>> increment_minor(1)
        '1.1.0'
    """
    major, minor, _ = parse_version(version)
    return f"{major}.{minor + 1}.0"


def increment_patch(version: Union[str, int, None]) -> str:
    """Increment patch version.

    Args:
        version: Version to increment

    Returns:
        New version string with incremented patch version

    Example:
        >>> increment_patch("1.2.3")
        '1.2.4'
        >>> increment_patch(1)
        '1.0.1'
    """
    major, minor, patch = parse_version(version)
    return f"{major}.{minor}.{patch + 1}"


def version_to_dict(version: Union[str, int, None]) -> Dict[str, Union[int, str]]:
    """Convert version to dictionary with all components.

    Args:
        version: Version to convert

    Returns:
        Dictionary with major, minor, patch, string, and integer keys

    Example:
        >>> version_to_dict("1.2.3")
        {'major': 1, 'minor': 2, 'patch': 3, 'string': '1.2.3', 'integer': 1}
        >>> version_to_dict(2)
        {'major': 2, 'minor': 0, 'patch': 0, 'string': '2.0.0', 'integer': 2}
    """
    major, minor, patch = parse_version(version)
    return {
        'major': major,
        'minor': minor,
        'patch': patch,
        'string': f"{major}.{minor}.{patch}",
        'integer': major
    }


# Convenience constants
DEFAULT_VERSION = "1.0.0"
INITIAL_VERSION = "0.1.0"


__all__ = [
    'parse_version',
    'normalize_version',
    'to_int_version',
    'compare_versions',
    'is_valid_version',
    'is_semantic_version',
    'get_major_version',
    'get_minor_version',
    'get_patch_version',
    'increment_major',
    'increment_minor',
    'increment_patch',
    'version_to_dict',
    'VersionError',
    'DEFAULT_VERSION',
    'INITIAL_VERSION',
]
