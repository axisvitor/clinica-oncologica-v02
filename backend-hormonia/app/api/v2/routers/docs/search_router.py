"""
Documentation Search router.
Provides full-text search across all documentation.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query, Request

from app.schemas.v2.docs import DocumentationSearchResponse
from app.schemas.v2.common import ErrorResponse
from app.utils.rate_limiter import limiter

from .cache_utils import (
    get_cache_key,
    get_cached_result,
    set_cached_result,
    CACHE_TTL_SEARCH,
)
from .data_providers import (
    extract_openapi_endpoints,
    get_static_guides,
    get_static_examples,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Rate limits
RATE_LIMIT_SEARCH = "60/minute"


@router.get(
    "",
    response_model=DocumentationSearchResponse,
    summary="Search documentation",
    description="Full-text search across all documentation",
    responses={
        200: {"description": "Search results"},
        400: {"model": ErrorResponse, "description": "Invalid search query"},
    },
)
@limiter.limit(RATE_LIMIT_SEARCH)
async def search_documentation(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query"),
    type: Optional[str] = Query(
        None, description="Filter by type (endpoint, guide, example)"
    ),
    limit: int = Query(20, ge=1, le=100, description="Results limit"),
):
    """
    Full-text search across all documentation.

    Searches in:
    - API endpoints (path, summary, description)
    - Guides (title, content, tags)
    - Code examples (title, description, code)

    Returns ranked results with relevance scores.

    Public endpoint with 1-hour caching per unique query.
    """
    try:
        # Check cache
        cache_key = get_cache_key("search", q=q, type=type, limit=limit)
        cached = await get_cached_result(cache_key)
        if cached:
            return cached

        q_lower = q.lower()
        results = []

        # Search endpoints
        if not type or type == "endpoint":
            endpoints = extract_openapi_endpoints(request.app)
            for endpoint in endpoints:
                score = 0.0
                if q_lower in endpoint["path"].lower():
                    score += 1.0
                if q_lower in endpoint["summary"].lower():
                    score += 0.8
                if q_lower in endpoint["description"].lower():
                    score += 0.5

                if score > 0:
                    results.append(
                        {
                            "type": "endpoint",
                            "id": endpoint["id"],
                            "title": f"{endpoint['method']} {endpoint['path']}",
                            "description": endpoint["summary"],
                            "content_preview": endpoint["description"][:200],
                            "relevance_score": score,
                            "url": f"/api/v2/docs/endpoints/{endpoint['method']}/{endpoint['path']}",
                        }
                    )

        # Search guides
        if not type or type == "guide":
            guides = get_static_guides()
            for guide in guides:
                score = 0.0
                if q_lower in guide["title"].lower():
                    score += 1.0
                if q_lower in guide["description"].lower():
                    score += 0.8
                if q_lower in guide["content"].lower():
                    score += 0.5
                if any(q_lower in tag.lower() for tag in guide["tags"]):
                    score += 0.6

                if score > 0:
                    results.append(
                        {
                            "type": "guide",
                            "id": guide["id"],
                            "title": guide["title"],
                            "description": guide["description"],
                            "content_preview": guide["content"][:200],
                            "relevance_score": score,
                            "url": f"/api/v2/docs/guides/{guide['slug']}",
                        }
                    )

        # Search examples
        if not type or type == "example":
            examples = get_static_examples()
            for example in examples:
                score = 0.0
                if q_lower in example["title"].lower():
                    score += 1.0
                if q_lower in example["description"].lower():
                    score += 0.8
                if q_lower in example["code"].lower():
                    score += 0.4

                if score > 0:
                    results.append(
                        {
                            "type": "example",
                            "id": example["id"],
                            "title": example["title"],
                            "description": example["description"],
                            "content_preview": example["code"][:200],
                            "relevance_score": score,
                            "url": f"/api/v2/docs/examples/{example['id']}",
                        }
                    )

        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)

        # Limit results
        total = len(results)
        results = results[:limit]

        result = {
            "query": q,
            "results": results,
            "total": total,
            "types": list(set(r["type"] for r in results)),
        }

        # Cache result
        await set_cached_result(cache_key, result, CACHE_TTL_SEARCH)

        return result

    except Exception as e:
        logger.error(f"Error searching documentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search documentation",
        )
