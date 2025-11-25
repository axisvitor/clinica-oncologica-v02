"""
API Changelog router.
Provides endpoints for viewing API version history and changelog.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query, Request

from app.schemas.v2.docs import APIChangelogResponse
from app.schemas.v2.common import ErrorResponse
from app.utils.rate_limiter import limiter

from .cache_utils import (
    get_cache_key,
    get_cached_result,
    set_cached_result,
    CACHE_TTL_API_DOCS,
)
from .data_providers import get_changelog_data

router = APIRouter()
logger = logging.getLogger(__name__)

# Rate limits
RATE_LIMIT_READ = "100/minute"


@router.get(
    "",
    response_model=APIChangelogResponse,
    summary="Get API changelog",
    description="Get complete API version history and changelog",
    responses={
        200: {"description": "API changelog"},
    }
)
@limiter.limit(RATE_LIMIT_READ)
async def get_api_changelog(
    request: Request,
    version: Optional[str] = Query(None, description="Filter by specific version"),
):
    """
    Get API changelog with version history.

    Returns:
    - All API versions
    - Changes for each version
    - Breaking changes
    - Release dates
    - Migration guides

    Public endpoint with 24-hour caching.
    """
    try:
        # Check cache
        cache_key = get_cache_key("changelog", version=version)
        cached = await get_cached_result(cache_key)
        if cached:
            return cached

        changelog = get_changelog_data()

        # Filter by version if specified
        if version:
            changelog = [c for c in changelog if c["version"] == version]
            if not changelog:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Version {version} not found"
                )

        result = {
            "versions": changelog,
            "current_version": "2.0.0",
            "latest_stable": "2.0.0",
            "deprecated_versions": ["1.0.0", "1.5.0"],
        }

        # Cache result
        await set_cached_result(cache_key, result, CACHE_TTL_API_DOCS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting changelog: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get changelog"
        )
