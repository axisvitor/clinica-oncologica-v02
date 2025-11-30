"""
Template Administration API v2
Provides administrative endpoints for template search and validation.
Supports full-text search across flow and quiz templates with validation capabilities.
"""

from typing import Optional, Dict, Any
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Cookie, Header
from sqlalchemy import or_

from app.database import get_db
from app.models.flow import FlowKind, FlowTemplateVersion
from app.models.quiz import QuizTemplate
from app.models.user import User
from app.dependencies.auth_dependencies import get_redis_cache
from app.schemas.v2.templates import (
    TemplateSearchResponse,
    TemplateValidationResponse,
)
from app.utils.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

# Rate limits (requests per minute)
RATE_LIMIT_READ = "60/minute"
RATE_LIMIT_SEARCH = "30/minute"


# ==================== Helper Functions ====================

async def _get_current_user_simple(
    session_cookie_id: str = Cookie(None, alias="session_id"),
    x_session_id: str = Header(None, alias="X-Session-ID"),
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
) -> Dict[str, Any]:
    """Simplified session validation for template operations."""
    final_session_id = session_cookie_id or x_session_id
    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided"
        )

    session_data = await redis_cache.get_session(final_session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data"
        )

    # Get user from cache or DB
    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)

    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user_data


# ==================== Template Search & Validation ====================

@router.get(
    "/search",
    response_model=TemplateSearchResponse,
    summary="Search templates",
    description="Full-text search across flow and quiz templates"
)
@limiter.limit(RATE_LIMIT_SEARCH)
async def search_templates(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    template_type: Optional[str] = Query(None, description="Filter by type (flow, quiz)"),
    limit: int = Query(20, ge=1, le=100, description="Results limit"),
    db = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple)
):
    """
    Full-text search across templates.

    Searches in template names, descriptions, and metadata.
    """
    try:
        results = []

        # Search flow templates
        if not template_type or template_type == "flow":
            flow_query = db.query(FlowTemplateVersion).join(FlowKind).filter(
                or_(
                    FlowTemplateVersion.template_name.ilike(f"%{q}%"),
                    FlowTemplateVersion.description.ilike(f"%{q}%"),
                    FlowKind.display_name.ilike(f"%{q}%"),
                    FlowKind.kind_key.ilike(f"%{q}%")
                )
            ).limit(limit)

            for template in flow_query:
                results.append({
                    "type": "flow",
                    "id": str(template.id),
                    "name": template.template_name,
                    "description": template.description,
                    "relevance_score": 1.0  # Could implement proper scoring
                })

        # Search quiz templates
        if not template_type or template_type == "quiz":
            quiz_query = db.query(QuizTemplate).filter(
                or_(
                    QuizTemplate.name.ilike(f"%{q}%"),
                    QuizTemplate.description.ilike(f"%{q}%"),
                    QuizTemplate.category.ilike(f"%{q}%")
                )
            ).limit(limit)

            for quiz in quiz_query:
                results.append({
                    "type": "quiz",
                    "id": str(quiz.id),
                    "name": quiz.name,
                    "description": quiz.description,
                    "relevance_score": 1.0
                })

        return {
            "query": q,
            "results": results[:limit],
            "total": len(results)
        }

    except Exception as e:
        logger.error(f"Error searching templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search templates"
        )


@router.post(
    "/validate",
    response_model=TemplateValidationResponse,
    summary="Validate template",
    description="Validate template structure and content"
)
@limiter.limit(RATE_LIMIT_READ)
async def validate_template(
    request: Request,
    template_data: Dict[str, Any],
    template_type: str = Query(..., description="Template type (flow, quiz)"),
    current_user: Dict = Depends(_get_current_user_simple)
):
    """
    Validate template structure and content.

    Checks for required fields, data types, and business rules.
    """
    try:
        errors = []
        warnings = []

        if template_type == "flow":
            # Validate flow template
            if "steps" not in template_data:
                errors.append("Missing required field: steps")
            elif not isinstance(template_data["steps"], (list, dict)):
                errors.append("Field 'steps' must be array or object")

            if "version_number" not in template_data:
                errors.append("Missing required field: version_number")

            if "template_name" not in template_data:
                warnings.append("Missing recommended field: template_name")

        elif template_type == "quiz":
            # Validate quiz template
            if "questions" not in template_data:
                errors.append("Missing required field: questions")
            elif not isinstance(template_data["questions"], list):
                errors.append("Field 'questions' must be array")
            elif len(template_data["questions"]) == 0:
                errors.append("Quiz must have at least one question")

            if "name" not in template_data:
                errors.append("Missing required field: name")

            if "version" not in template_data:
                errors.append("Missing required field: version")
        else:
            errors.append(f"Invalid template type: {template_type}")

        is_valid = len(errors) == 0

        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings
        }

    except Exception as e:
        logger.error(f"Error validating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate template"
        )
