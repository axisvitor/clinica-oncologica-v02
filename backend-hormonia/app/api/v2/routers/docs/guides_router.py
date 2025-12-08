"""
Documentation Guides router.
Provides endpoints for listing and viewing documentation guides and tutorials.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query, Request

from app.schemas.v2.docs import GuideList, GuideDetail
from app.schemas.v2.common import ErrorResponse
from app.utils.rate_limiter import limiter

from .cache_utils import (
    get_cache_key,
    get_cached_result,
    set_cached_result,
    CACHE_TTL_GUIDES,
)
from .data_providers import get_static_guides

router = APIRouter()
logger = logging.getLogger(__name__)

# Rate limits
RATE_LIMIT_READ = "100/minute"


@router.get(
    "",
    response_model=GuideList,
    summary="List documentation guides",
    description="Get list of documentation guides and tutorials",
    responses={
        200: {"description": "List of guides"},
    }
)
@limiter.limit(RATE_LIMIT_READ)
async def list_guides(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
):
    """
    List all documentation guides and tutorials.

    Guides include:
    - Getting started guides
    - Authentication tutorials
    - Best practices
    - Integration guides
    - Performance optimization tips

    Public endpoint with 12-hour caching.
    """
    try:
        # Check cache
        cache_key = get_cache_key("guides_list", category=category, tags=tags)
        cached = await get_cached_result(cache_key)
        if cached:
            return cached

        guides = get_static_guides()

        # Apply filters
        if category:
            guides = [g for g in guides if g["category"].lower() == category.lower()]

        if tags:
            tag_list = [t.strip().lower() for t in tags.split(",")]
            guides = [
                g for g in guides
                if any(tag in [t.lower() for t in g["tags"]] for tag in tag_list)
            ]

        # Sort by order
        guides.sort(key=lambda x: x.get("order", 999))

        result = {
            "data": guides,
            "total": len(guides),
            "categories": list(set(g["category"] for g in guides)),
        }

        # Cache result
        await set_cached_result(cache_key, result, CACHE_TTL_GUIDES)

        return result

    except Exception as e:
        logger.error(f"Error listing guides: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list guides"
        )


@router.get(
    "/{slug}",
    response_model=GuideDetail,
    summary="Get guide by slug",
    description="Get detailed guide content by slug",
    responses={
        200: {"description": "Guide details"},
        404: {"model": ErrorResponse, "description": "Guide not found"},
    }
)
@limiter.limit(RATE_LIMIT_READ)
async def get_guide_by_slug(
    request: Request,
    slug: str,
):
    """
    Get detailed guide content by slug.

    Returns guide with full markdown content, metadata, and related guides.

    Public endpoint with 12-hour caching.
    """
    try:
        # Check cache
        cache_key = get_cache_key("guide_detail", slug=slug)
        cached = await get_cached_result(cache_key)
        if cached:
            return cached

        guides = get_static_guides()

        # Find guide by slug
        guide = None
        for g in guides:
            if g["slug"] == slug:
                guide = g
                break

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Guide '{slug}' not found"
            )

        # Find related guides (same category)
        related = [
            {"id": g["id"], "slug": g["slug"], "title": g["title"]}
            for g in guides
            if g["category"] == guide["category"] and g["id"] != guide["id"]
        ]

        result = {
            **guide,
            "related_guides": related,
        }

        # Cache result
        await set_cached_result(cache_key, result, CACHE_TTL_GUIDES)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting guide: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get guide"
        )
