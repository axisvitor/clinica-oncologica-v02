"""
API Endpoints documentation router.
Provides endpoints for listing and viewing API endpoint documentation.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query, Request

from app.schemas.v2.docs import APIEndpointList, APIEndpointDetail
from app.schemas.v2.common import ErrorResponse
from app.utils.rate_limiter import limiter

from .cache_utils import (
    get_cache_key,
    get_cached_result,
    set_cached_result,
    CACHE_TTL_API_DOCS,
)
from .data_providers import extract_openapi_endpoints

router = APIRouter()
logger = logging.getLogger(__name__)

# Rate limits
RATE_LIMIT_READ = "100/minute"


@router.get(
    "",
    response_model=APIEndpointList,
    summary="List API endpoints",
    description="Get comprehensive list of all API endpoints with filtering and search",
    responses={
        200: {"description": "List of API endpoints"},
        400: {"model": ErrorResponse, "description": "Invalid parameters"},
    },
)
@limiter.limit(RATE_LIMIT_READ)
async def list_api_endpoints(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category/tag"),
    method: Optional[str] = Query(None, description="Filter by HTTP method"),
    search: Optional[str] = Query(None, description="Search in path or description"),
    deprecated: Optional[bool] = Query(None, description="Filter by deprecated status"),
    requires_auth: Optional[bool] = Query(
        None, description="Filter by authentication requirement"
    ),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List all available API endpoints.

    Returns comprehensive information about each endpoint including:
    - HTTP method and path
    - Summary and description
    - Parameters and request body
    - Response schemas
    - Authentication requirements
    - Tags and categories

    Public endpoint with 24-hour caching.
    """
    try:
        # Check cache
        cache_key = get_cache_key(
            "endpoints",
            category=category,
            method=method,
            search=search,
            deprecated=deprecated,
            requires_auth=requires_auth,
            limit=limit,
        )
        cached = await get_cached_result(cache_key)
        if cached:
            return cached

        # Extract endpoints from OpenAPI spec
        endpoints = extract_openapi_endpoints(request.app)

        # Apply filters
        filtered = endpoints

        if category:
            filtered = [
                e
                for e in filtered
                if category.lower() in [t.lower() for t in e["tags"]]
            ]

        if method:
            filtered = [e for e in filtered if e["method"].lower() == method.lower()]

        if search:
            search_lower = search.lower()
            filtered = [
                e
                for e in filtered
                if search_lower in e["path"].lower()
                or search_lower in e["summary"].lower()
                or search_lower in e["description"].lower()
            ]

        if deprecated is not None:
            filtered = [e for e in filtered if e["deprecated"] == deprecated]

        if requires_auth is not None:
            filtered = [e for e in filtered if e["requires_auth"] == requires_auth]

        # Limit results
        total = len(filtered)
        filtered = filtered[:limit]

        # Group by category
        by_category = {}
        for endpoint in filtered:
            cat = endpoint["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(endpoint)

        result = {
            "data": filtered,
            "by_category": by_category,
            "total": total,
            "categories": list(by_category.keys()),
        }

        # Cache result
        await set_cached_result(cache_key, result, CACHE_TTL_API_DOCS)

        return result

    except Exception as e:
        logger.error(f"Error listing endpoints: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API endpoints",
        )


@router.get(
    "/{method}/{path:path}",
    response_model=APIEndpointDetail,
    summary="Get endpoint documentation",
    description="Get detailed documentation for a specific endpoint",
    responses={
        200: {"description": "Endpoint documentation"},
        404: {"model": ErrorResponse, "description": "Endpoint not found"},
    },
)
@limiter.limit(RATE_LIMIT_READ)
async def get_endpoint_documentation(
    request: Request,
    method: str,
    path: str,
):
    """
    Get detailed documentation for a specific API endpoint.

    Returns complete information including:
    - Full description and usage notes
    - Request/response schemas
    - Example requests and responses
    - Error codes and handling
    - Related endpoints

    Public endpoint with 24-hour caching.
    """
    try:
        # Check cache
        cache_key = get_cache_key("endpoint_detail", method=method, path=path)
        cached = await get_cached_result(cache_key)
        if cached:
            return cached

        # Normalize path (add leading slash if missing)
        if not path.startswith("/"):
            path = f"/{path}"

        # Extract endpoints from OpenAPI spec
        endpoints = extract_openapi_endpoints(request.app)

        # Find matching endpoint
        endpoint = None
        for e in endpoints:
            if e["method"].lower() == method.lower() and e["path"] == path:
                endpoint = e
                break

        if not endpoint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Endpoint {method.upper()} {path} not found",
            )

        # Find related endpoints (same category)
        related = [
            {"method": e["method"], "path": e["path"], "summary": e["summary"]}
            for e in endpoints
            if e["category"] == endpoint["category"] and e["id"] != endpoint["id"]
        ][:5]

        result = {
            **endpoint,
            "related_endpoints": related,
        }

        # Cache result
        await set_cached_result(cache_key, result, CACHE_TTL_API_DOCS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting endpoint documentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get endpoint documentation",
        )
