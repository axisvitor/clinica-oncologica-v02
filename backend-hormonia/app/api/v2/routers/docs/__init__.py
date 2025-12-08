"""
Documentation API package.
Provides comprehensive API documentation with guides, examples, and search capabilities.

This package decomposes the large docs.py router into modular sub-routers:
- endpoints_router: API endpoint documentation
- guides_router: Documentation guides and tutorials
- examples_router: Code examples
- search_router: Full-text documentation search
- changelog_router: API version history

All sub-routers are combined into a single router for backward compatibility.
"""

from fastapi import APIRouter

from . import (
    endpoints_router,
    guides_router,
    examples_router,
    search_router,
    changelog_router,
)

# Create main router
router = APIRouter()

# Include all sub-routers with appropriate prefixes
router.include_router(
    endpoints_router.router,
    prefix="/endpoints",
    tags=["Documentation - Endpoints"]
)

router.include_router(
    guides_router.router,
    prefix="/guides",
    tags=["Documentation - Guides"]
)

router.include_router(
    examples_router.router,
    prefix="/examples",
    tags=["Documentation - Examples"]
)

router.include_router(
    search_router.router,
    prefix="/search",
    tags=["Documentation - Search"]
)

router.include_router(
    changelog_router.router,
    prefix="/changelog",
    tags=["Documentation - Changelog"]
)

# Re-export routers for direct access if needed
__all__ = [
    "router",
    "endpoints_router",
    "guides_router",
    "examples_router",
    "search_router",
    "changelog_router",
]
