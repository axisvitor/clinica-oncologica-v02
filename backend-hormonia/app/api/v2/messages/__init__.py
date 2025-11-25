"""
Messages API v2 Package
Router aggregation for all message-related endpoints.

This package contains 7 focused router modules:
- crud.py: Basic CRUD operations (list, get, filter by status)
- send.py: Message sending operations (send, schedule, cancel, get status)
- retry.py: Retry and resend operations (retry, retry all failed, list failed)
- bulk.py: Bulk operations (bulk send)
- stats.py: Statistics and analytics (patient stats, overall stats)
- conversations.py: Conversation management (6 endpoints)
- analytics.py: Analytics and reporting (2 endpoints)
- templates.py: Template management (5 endpoints)

Total: 26 endpoints

The main router aggregates all sub-routers and maintains backward compatibility
with the original core.py monolithic module.
"""

from fastapi import APIRouter
from . import crud, send, retry, bulk, stats, conversations, analytics, templates

# Create main router
router = APIRouter()

# Include all sub-routers with appropriate tags
router.include_router(crud.router, tags=["messages-crud"])
router.include_router(send.router, tags=["messages-send"])
router.include_router(retry.router, tags=["messages-retry"])
router.include_router(bulk.router, tags=["messages-bulk"])
router.include_router(stats.router, tags=["messages-stats"])
router.include_router(conversations.router, tags=["messages-conversations"])
router.include_router(analytics.router, tags=["messages-analytics"])
router.include_router(templates.router, tags=["messages-templates"])

# Export router for use in main application
__all__ = ["router"]
