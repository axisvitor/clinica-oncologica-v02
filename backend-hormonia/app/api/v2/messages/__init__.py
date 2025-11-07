"""
Messages API v2 Package
Router aggregation for all message-related endpoints.

This package contains 4 focused router modules:
- core.py: Core CRUD operations (13 endpoints)
- conversations.py: Conversation management (6 endpoints)
- analytics.py: Analytics and reporting (2 endpoints)
- templates.py: Template management (5 endpoints)

Total: 26 endpoints

The main router aggregates all sub-routers and maintains backward compatibility
with the original messages.py monolithic module.
"""

from fastapi import APIRouter
from . import core, conversations, analytics, templates

# Create main router
router = APIRouter()

# Include all sub-routers with appropriate tags
router.include_router(core.router, tags=["messages-core"])
router.include_router(conversations.router, tags=["messages-conversations"])
router.include_router(analytics.router, tags=["messages-analytics"])
router.include_router(templates.router, tags=["messages-templates"])

# Export router for use in main application
__all__ = ["router"]
