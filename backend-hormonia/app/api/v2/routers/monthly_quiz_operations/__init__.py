"""
Monthly Quiz Operations and Public Access API v2 - Modular Package

This package handles monthly quiz operations, scheduling, and public access.

**Package Structure:**
- crud.py - CRUD operations (responses, statistics)
- scheduling.py - Scheduling operations (reminders, schedule, generation, templates)
- public.py - Public access endpoints (current quiz, submit, results)
- health.py - Health check endpoint

**Monthly Quiz Operations (6 endpoints):**
- Get quiz responses with analytics
- View comprehensive statistics
- Send reminders to non-completers
- View quiz schedule
- Auto-generate monthly quizzes
- List available quiz templates

**Public Access Endpoints (3 endpoints):**
- Get current public quiz (token-based)
- Submit quiz response publicly
- View aggregate quiz results

**Health Check (1 endpoint):**
- Service health monitoring

**Features:**
- Token-based public access security
- Cursor-based pagination
- Redis caching with appropriate TTLs
- Rate limiting to prevent abuse
- RBAC: Admin/Doctors (operations), Public (access endpoints)
- Comprehensive audit trail

**Security:**
- Public endpoints use base64-encoded JWT-like tokens
- Token expiration validation
- IP logging for public access
- Personal data sanitization in public responses
"""

# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI OpenAPI issues

from fastapi import APIRouter

# Import sub-routers
from .crud import router as crud_router
from .scheduling import router as scheduling_router
from .public import router as public_router
from .health import router as health_router

# Create main router
router = APIRouter()

# Include all sub-routers
router.include_router(crud_router, tags=["Monthly Quiz - CRUD"])
router.include_router(scheduling_router, tags=["Monthly Quiz - Scheduling"])
router.include_router(public_router, tags=["Monthly Quiz - Public Access"])
router.include_router(health_router, tags=["Monthly Quiz - Health"])

# Export for backward compatibility
__all__ = ["router"]
