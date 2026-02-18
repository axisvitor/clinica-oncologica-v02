"""
API Versioning Infrastructure

Implements URL-based API versioning with deprecation support,
following ADR-007 API Versioning Strategy.

Features:
- URL path versioning (/api/v2/)
- Deprecation headers (Sunset, Deprecation, Link)
- Version-aware routing
- Deprecation tracking

Author: Backend API Developer
Created: 2025-01-16
"""

from fastapi import APIRouter, Request, Response
from typing import Optional, Dict, Callable
from datetime import datetime, timezone
import logging
from functools import wraps
from app.utils.timezone import SAO_PAULO_TZ, now_sao_paulo

logger = logging.getLogger(__name__)


class VersionInfo:
    """Information about an API version."""

    def __init__(
        self,
        version: str,
        router: APIRouter,
        sunset_date: Optional[datetime] = None,
        replacement_version: Optional[str] = None,
        is_deprecated: bool = False,
    ):
        self.version = version
        self.router = router
        self.sunset_date = sunset_date
        self.replacement_version = replacement_version
        self.is_deprecated = is_deprecated or sunset_date is not None

    def days_until_sunset(self) -> Optional[int]:
        """Calculate days until this version is sunset."""
        if not self.sunset_date:
            return None

        now = now_sao_paulo()
        delta = self.sunset_date - now
        return max(0, delta.days)

    def is_sunset(self) -> bool:
        """Check if this version is already sunset."""
        if not self.sunset_date:
            return False

        return now_sao_paulo() >= self.sunset_date


class VersionedRouter:
    """
    Router with API version awareness and deprecation support.

    Usage:
        versioned_router = VersionedRouter()

        # Register current version
        versioned_router.add_version("v2", router_v2, is_default=True)

        # Add middleware
        app.middleware("http")(versioned_router.get_version_middleware())
    """

    def __init__(self):
        self.versions: Dict[str, VersionInfo] = {}
        self._default_version: Optional[str] = None

    def add_version(
        self,
        version: str,
        router: APIRouter,
        sunset_date: Optional[datetime] = None,
        replacement_version: Optional[str] = None,
        is_default: bool = False,
    ) -> None:
        """
        Register a versioned router.

        Args:
            version: Version identifier (e.g., "v2")
            router: FastAPI router for this version
            sunset_date: When this version will be sunset (optional)
            replacement_version: Which version to migrate to (optional)
            is_default: Whether this is the default version
        """
        version_info = VersionInfo(
            version=version,
            router=router,
            sunset_date=sunset_date,
            replacement_version=replacement_version,
        )

        self.versions[version] = version_info

        if is_default or self._default_version is None:
            self._default_version = version

        logger.info(
            f"Registered API version {version} "
            f"(deprecated={version_info.is_deprecated}, "
            f"sunset={sunset_date})"
        )

    def get_version(self, version: str) -> Optional[VersionInfo]:
        """Get information about a specific version."""
        return self.versions.get(version)

    def get_default_version(self) -> str:
        """Get the default API version."""
        return self._default_version or "v2"

    def extract_version_from_path(self, path: str) -> Optional[str]:
        """
        Extract API version from URL path.

        Args:
            path: URL path (e.g., "/api/v2/patients")

        Returns:
            Version string (e.g., "v2") or None
        """
        parts = path.split("/")

        # Expected format: /api/v{X}/...
        if len(parts) >= 3 and parts[1] == "api":
            version_part = parts[2]
            if version_part.startswith("v") and version_part[1:].isdigit():
                return version_part

        return None

    def get_version_middleware(self) -> Callable:
        """
        Create middleware to add deprecation headers.

        Returns:
            Middleware function
        """

        async def version_middleware(request: Request, call_next):
            # Extract version from path
            version = self.extract_version_from_path(request.url.path)

            # Process request
            response: Response = await call_next(request)

            # Add version headers if version detected
            if version and version in self.versions:
                version_info = self.versions[version]

                # Add current version header
                response.headers["X-API-Version"] = version

                # Add deprecation headers if needed
                if version_info.is_deprecated:
                    self._add_deprecation_headers(response, version_info)

                # Check if version is sunset
                if version_info.is_sunset():
                    # Return 410 Gone for sunset versions
                    from fastapi.responses import JSONResponse

                    return JSONResponse(
                        status_code=410,
                        content={
                            "error": {
                                "code": "API_VERSION_SUNSET",
                                "message": f"API {version} was sunset on {version_info.sunset_date.isoformat()}",
                                "sunset_date": version_info.sunset_date.isoformat(),
                                "current_version": self.get_default_version(),
                                "migration_guide": f"/docs/api/{version}-to-{version_info.replacement_version}-migration",
                            }
                        },
                        headers={"X-API-Version": version, "X-API-Sunset": "true"},
                    )

            return response

        return version_middleware

    def _add_deprecation_headers(
        self, response: Response, version_info: VersionInfo
    ) -> None:
        """
        Add RFC 8594 deprecation headers to response.

        Args:
            response: FastAPI response object
            version_info: Version information
        """
        # Sunset header (RFC 8594)
        if version_info.sunset_date:
            # Use HTTP-date format: Wed, 21 Oct 2015 07:28:00 GMT
            sunset_str = version_info.sunset_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
            response.headers["Sunset"] = sunset_str

        # Deprecation header (RFC 8594)
        response.headers["Deprecation"] = "true"

        # Link to replacement version (RFC 8288)
        if version_info.replacement_version:
            response.headers["Link"] = (
                f'</api/{version_info.replacement_version}>; rel="successor-version"'
            )

        # Custom warning header with countdown
        days_remaining = version_info.days_until_sunset()
        if days_remaining is not None:
            replacement = version_info.replacement_version or "latest"
            response.headers["X-API-Warn"] = (
                f"API version {version_info.version} will be sunset in "
                f"{days_remaining} days. Please migrate to {replacement}."
            )
        else:
            response.headers["X-API-Warn"] = (
                f"API version {version_info.version} is deprecated. "
                f"Please migrate to {version_info.replacement_version or 'latest'}."
            )


def deprecated_endpoint(sunset_date: datetime, replacement: Optional[str] = None):
    """
    Decorator to mark individual endpoints as deprecated.

    Usage:
        @router.get("/old-endpoint")
        @deprecated_endpoint(
            sunset_date=datetime(2025, 7, 1, tzinfo=SAO_PAULO_TZ),
            replacement="/api/v2/new-endpoint"
        )
        async def old_endpoint():
            return {"message": "This endpoint is deprecated"}

    Args:
        sunset_date: When this endpoint will be removed
        replacement: URL of replacement endpoint (optional)
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute original function
            from fastapi import Response
            from starlette.responses import JSONResponse

            result = await func(*args, **kwargs)

            # If result is already a Response, add headers
            if isinstance(result, Response):
                response = result
            else:
                # Wrap result in JSONResponse
                response = JSONResponse(content=result)

            # Add deprecation headers
            sunset_str = sunset_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
            response.headers["Sunset"] = sunset_str
            response.headers["Deprecation"] = "true"

            if replacement:
                response.headers["Link"] = f'<{replacement}>; rel="successor-version"'

            # Calculate days remaining
            now = now_sao_paulo()
            days_remaining = max(0, (sunset_date - now).days)

            response.headers["X-API-Warn"] = (
                f"This endpoint will be removed in {days_remaining} days."
            )

            return response

        return wrapper

    return decorator


# Singleton instance for global use
versioned_router = VersionedRouter()


def get_versioned_router() -> VersionedRouter:
    """Get the global versioned router instance."""
    return versioned_router
