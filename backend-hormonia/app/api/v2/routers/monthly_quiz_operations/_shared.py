"""
Shared imports and utilities for monthly quiz operations.
"""

# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI OpenAPI issues

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import asc, desc, func, and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.quiz import QuizResponse, QuizSession, QuizTemplate
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.v2.quiz_extensions import (
    QuizResponseV2Detail,
    QuizResponseV2List,
    MonthlyQuizStatisticsV2,
    PublicQuizResponseV2,
    PublicSubmissionRequestV2,
    PublicQuizResultsV2,
    MonthlyQuizV2Detail,
    QuizReminderRequestV2,
    QuizScheduleV2,
    QuizGenerateRequestV2,
    QuizTemplateV2,
)
from app.utils.rate_limiter import limiter
from app.dependencies import get_current_user

# Logger
logger = logging.getLogger(__name__)

# Public patient ID constant
PUBLIC_PATIENT_ID = UUID("00000000-0000-0000-0000-000000000001")

# Cache TTLs
CACHE_TTL_STATISTICS = 300  # 5 minutes
CACHE_TTL_RESPONSES = 60  # 1 minute
CACHE_TTL_PUBLIC_QUIZ = 120  # 2 minutes
CACHE_TTL_TEMPLATES = 600  # 10 minutes


def get_pagination_params(cursor: str = None, limit: int = 20):
    """Get pagination parameters from request."""
    cursor_data = None
    if cursor:
        import base64
        import json
        try:
            cursor_data = json.loads(base64.b64decode(cursor).decode())
        except Exception as e:
            logger.warning(f"Invalid pagination cursor: {e}")
    return {"cursor_data": cursor_data, "limit": min(limit, 100)}


def create_cursor(item_id, created_at):
    """Create cursor for pagination."""
    import base64
    import json
    cursor_data = {"id": str(item_id), "created_at": created_at.isoformat()}
    return base64.b64encode(json.dumps(cursor_data).encode()).decode()


async def get_redis_cache():
    """Get Redis cache instance."""
    try:
        from app.core.redis_manager import get_redis_client
        return get_redis_client()
    except Exception:
        return None


async def _get_current_user_simple(
    db: Session = Depends(get_db),
) -> User:
    """Simple current user dependency that returns None if not authenticated."""
    try:
        return await get_current_user(db=db)
    except HTTPException:
        return None


__all__ = [
    # Types
    "UUID",
    "datetime",
    "timedelta",
    "defaultdict",
    "Dict",
    "Any",
    "Optional",
    "List",
    # FastAPI
    "Depends",
    "HTTPException",
    "status",
    # SQLAlchemy
    "Session",
    "asc",
    "desc",
    "func",
    "and_",
    "or_",
    # Database
    "get_db",
    # Rate limiting
    "limiter",
    # Pagination
    "get_pagination_params",
    "create_cursor",
    # Models
    "QuizResponse",
    "QuizSession",
    "QuizTemplate",
    "User",
    "UserRole",
    "Patient",
    # Schemas
    "QuizResponseV2Detail",
    "QuizResponseV2List",
    "MonthlyQuizStatisticsV2",
    "PublicQuizResponseV2",
    "PublicSubmissionRequestV2",
    "PublicQuizResultsV2",
    "MonthlyQuizV2Detail",
    "QuizReminderRequestV2",
    "QuizScheduleV2",
    "QuizGenerateRequestV2",
    "QuizTemplateV2",
    # Auth
    "_get_current_user_simple",
    # Cache
    "get_redis_cache",
    "CACHE_TTL_STATISTICS",
    "CACHE_TTL_RESPONSES",
    "CACHE_TTL_PUBLIC_QUIZ",
    "CACHE_TTL_TEMPLATES",
    # Constants
    "logger",
    "PUBLIC_PATIENT_ID",
]
