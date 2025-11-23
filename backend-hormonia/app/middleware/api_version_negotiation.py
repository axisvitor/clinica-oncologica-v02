"""
API Version Negotiation Middleware

Implements content negotiation for API versions, supporting:
1. URL path (/api/v2/...)
2. Accept header (Accept: application/vnd.clinica.v2+json)
3. Custom header (X-API-Version: 2)
4. Default to latest version

Author: Backend API Developer
Created: 2025-01-16
"""

from fastapi import Request, HTTPException
from typing import Optional
import re
import logging

logger = logging.getLogger(__name__)


class APIVersionNegotiation:
    """
    Content negotiation for API versions.

    Supports multiple methods of specifying API version with fallback order:
    1. URL path (most explicit, highest priority)
    2. Accept header (standard content negotiation)
    3. Custom X-API-Version header
    4. Default to latest stable version
    """

    # Regex pattern for Accept header: application/vnd.clinica.v2+json
    ACCEPT_PATTERN = re.compile(
        r'application/vnd\.clinica\.(v\d+)\+json'
    )

    def __init__(self, default_version: str = "v2"):
        """
        Initialize version negotiation.

        Args:
            default_version: Default version when none specified (e.g., "v2")
        """
        self.default_version = default_version
        self.supported_versions = {"v2"}  # Update as new versions added

    async def negotiate_version(self, request: Request) -> str:
        """
        Determine API version from request.

        Priority order:
        1. URL path (/api/v2/...)
        2. Accept header (Accept: application/vnd.clinica.v2+json)
        3. Custom header (X-API-Version: 2)
        4. Default to latest

        Args:
            request: FastAPI request object

        Returns:
            Version string (e.g., "v2")

        Raises:
            HTTPException: If unsupported version requested
        """
        # 1. Check URL path (highest priority)
        version = self._extract_from_url(request.url.path)
        if version:
            logger.debug(f"Version from URL path: {version}")
            return self._validate_version(version)

        # 2. Check Accept header
        version = self._extract_from_accept_header(request)
        if version:
            logger.debug(f"Version from Accept header: {version}")
            return self._validate_version(version)

        # 3. Check custom X-API-Version header
        version = self._extract_from_custom_header(request)
        if version:
            logger.debug(f"Version from X-API-Version header: {version}")
            return self._validate_version(version)

        # 4. Default to latest version
        logger.debug(f"Using default version: {self.default_version}")
        return self.default_version

    def _extract_from_url(self, path: str) -> Optional[str]:
        """
        Extract version from URL path.

        Examples:
            /api/v2/patients -> "v2"
            /health -> None

        Args:
            path: URL path

        Returns:
            Version string or None
        """
        parts = path.split('/')

        # Expected format: /api/v{X}/...
        if len(parts) >= 3 and parts[1] == 'api':
            version_part = parts[2]
            if version_part.startswith('v') and version_part[1:].isdigit():
                return version_part

        return None

    def _extract_from_accept_header(self, request: Request) -> Optional[str]:
        """
        Extract version from Accept header.

        Examples:
            Accept: application/vnd.clinica.v2+json -> "v2"
            Accept: application/json -> None

        Args:
            request: FastAPI request

        Returns:
            Version string or None
        """
        accept_header = request.headers.get('Accept', '')

        match = self.ACCEPT_PATTERN.search(accept_header)
        if match:
            return match.group(1)  # Extract version from pattern (e.g., "v2")

        return None

    def _extract_from_custom_header(self, request: Request) -> Optional[str]:
        """
        Extract version from custom X-API-Version header.

        Examples:
            X-API-Version: 2 -> "v2"
            X-API-Version: v2 -> "v2"

        Args:
            request: FastAPI request

        Returns:
            Version string or None
        """
        custom_version = request.headers.get('X-API-Version')

        if custom_version:
            # Normalize: "2" -> "v2", "v2" -> "v2"
            if custom_version.isdigit():
                return f"v{custom_version}"
            elif custom_version.startswith('v') and custom_version[1:].isdigit():
                return custom_version

        return None

    def _validate_version(self, version: str) -> str:
        """
        Validate that requested version is supported.

        Args:
            version: Version string (e.g., "v2")

        Returns:
            Validated version string

        Raises:
            HTTPException: If version not supported
        """
        if version not in self.supported_versions:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "UNSUPPORTED_API_VERSION",
                        "message": f"API version '{version}' is not supported",
                        "supported_versions": sorted(self.supported_versions),
                        "default_version": self.default_version
                    }
                }
            )

        return version

    def add_supported_version(self, version: str) -> None:
        """
        Add a new supported version.

        Args:
            version: Version to add (e.g., "v4")
        """
        self.supported_versions.add(version)
        logger.info(f"Added supported API version: {version}")

    def remove_supported_version(self, version: str) -> None:
        """
        Remove a supported version (e.g., after sunset).

        Args:
            version: Version to remove (e.g., "v1")
        """
        if version in self.supported_versions:
            self.supported_versions.remove(version)
            logger.info(f"Removed API version: {version}")


# Singleton instance
api_version_negotiation = APIVersionNegotiation(default_version="v2")


async def get_api_version(request: Request) -> str:
    """
    Dependency function to get API version from request.

    Usage:
        @router.get("/patients")
        async def get_patients(version: str = Depends(get_api_version)):
            if version == "v2":
                # v2 logic

    Args:
        request: FastAPI request

    Returns:
        API version string
    """
    return await api_version_negotiation.negotiate_version(request)
