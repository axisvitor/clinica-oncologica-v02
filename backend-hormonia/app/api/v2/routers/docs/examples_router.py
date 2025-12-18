"""
Code Examples router.
Provides endpoints for listing and viewing code examples.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query, Request

from app.schemas.v2.docs import CodeExampleList, CodeExampleDetail
from app.schemas.v2.common import ErrorResponse
from app.utils.rate_limiter import limiter

from .cache_utils import (
    get_cache_key,
    get_cached_result,
    set_cached_result,
    CACHE_TTL_EXAMPLES,
)
from .data_providers import get_static_examples

router = APIRouter()
logger = logging.getLogger(__name__)

# Rate limits
RATE_LIMIT_READ = "100/minute"


@router.get(
    "",
    response_model=CodeExampleList,
    summary="List code examples",
    description="Get list of code examples for various API operations",
    responses={
        200: {"description": "List of code examples"},
    },
)
@limiter.limit(RATE_LIMIT_READ)
async def list_code_examples(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    language: Optional[str] = Query(None, description="Filter by programming language"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint"),
):
    """
    List all code examples.

    Examples available for:
    - Python
    - JavaScript/Node.js
    - cURL
    - Multiple API operations

    Public endpoint with 6-hour caching.
    """
    try:
        # Check cache
        cache_key = get_cache_key(
            "examples_list", category=category, language=language, endpoint=endpoint
        )
        cached = await get_cached_result(cache_key)
        if cached:
            return cached

        examples = get_static_examples()

        # Apply filters
        if category:
            examples = [
                e for e in examples if e["category"].lower() == category.lower()
            ]

        if language:
            examples = [
                e for e in examples if e["language"].lower() == language.lower()
            ]

        if endpoint:
            examples = [e for e in examples if e.get("endpoint") == endpoint]

        result = {
            "data": examples,
            "total": len(examples),
            "languages": list(set(e["language"] for e in examples)),
            "categories": list(set(e["category"] for e in examples)),
        }

        # Cache result
        await set_cached_result(cache_key, result, CACHE_TTL_EXAMPLES)

        return result

    except Exception as e:
        logger.error(f"Error listing examples: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list code examples",
        )


@router.get(
    "/{example_id}",
    response_model=CodeExampleDetail,
    summary="Get code example by ID",
    description="Get detailed code example by ID",
    responses={
        200: {"description": "Code example details"},
        404: {"model": ErrorResponse, "description": "Example not found"},
    },
)
@limiter.limit(RATE_LIMIT_READ)
async def get_code_example(
    request: Request,
    example_id: str,
):
    """
    Get detailed code example by ID.

    Returns complete code with:
    - Full source code
    - Explanation and usage notes
    - Related examples
    - Endpoint reference

    Public endpoint with 6-hour caching.
    """
    try:
        # Check cache
        cache_key = get_cache_key("example_detail", example_id=example_id)
        cached = await get_cached_result(cache_key)
        if cached:
            return cached

        examples = get_static_examples()

        # Find example by ID
        example = None
        for e in examples:
            if e["id"] == example_id:
                example = e
                break

        if not example:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Example '{example_id}' not found",
            )

        # Find related examples (same category or language)
        related = [
            {"id": e["id"], "title": e["title"], "language": e["language"]}
            for e in examples
            if (
                e["category"] == example["category"]
                or e["language"] == example["language"]
            )
            and e["id"] != example["id"]
        ][:5]

        result = {
            **example,
            "related_examples": related,
        }

        # Cache result
        await set_cached_result(cache_key, result, CACHE_TTL_EXAMPLES)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting example: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get code example",
        )
