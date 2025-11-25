"""
Shared imports and utilities for monthly quiz operations.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import logging
from collections import defaultdict

from fastapi import Depends, HTTPException, status, Query, Request
from sqlalchemy import asc

from app.database import get_db
from app.models.quiz import QuizResponse, QuizSession, QuizTemplate
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.v2.quiz_extensions import (
    QuizResponseV2Detail,
    QuizResponseV2List,
    MonthlyQuizStatisticsV2,
    QuizReminderRequestV2,
    QuizScheduleV2,
    QuizGenerateRequestV2,
    MonthlyQuizV2Detail,
    QuizTemplateV2,
    PublicQuizResponseV2,
    PublicSubmissionRequestV2,
    PublicQuizResultsV2,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    create_cursor,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.utils.rate_limiter import limiter

# Import shared helpers and cache TTLs
from app.api.v2._quiz_shared import (
    _get_current_user_simple,
    CACHE_TTL_STATISTICS,
    CACHE_TTL_PUBLIC_QUIZ,
    CACHE_TTL_TEMPLATES,
)

# Logger
logger = logging.getLogger(__name__)

# Public patient ID constant
PUBLIC_PATIENT_ID = UUID("00000000-0000-0000-0000-000000000001")
