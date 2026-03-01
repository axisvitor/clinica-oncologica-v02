"""
Template Administration API v2
Provides administrative endpoints for template search and validation.
Supports full-text search across flow and quiz templates with validation capabilities.
"""

from typing import Optional, Dict, Any
import logging
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
    Request,
)
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.models.flow import FlowKind, FlowTemplateVersion
from app.models.quiz import QuizTemplate
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.schemas.v2.templates import (
    TemplateSearchResponse,
    TemplateValidationResponse,
)
from app.utils.rate_limiter import limiter

# Import shared helpers and constants from templates_shared module
from app.api.v2.templates_shared import (
    RATE_LIMIT_READ,
    RATE_LIMIT_SEARCH,
)
from app.monitoring.audit_logger import TemplateAuditLogger as AuditLogger, TemplateAuditAction as AuditAction

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== Template Search & Validation ====================


@router.get(
    "/search",
    response_model=TemplateSearchResponse,
    summary="Search templates",
    description="Full-text search across flow and quiz templates",
)
@limiter.limit(RATE_LIMIT_SEARCH)
async def search_templates(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    template_type: Optional[str] = Query(
        None, description="Filter by type (flow, quiz)"
    ),
    limit: int = Query(20, ge=1, le=100, description="Results limit"),
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    """
    Full-text search across templates.

    Searches in template names, descriptions, and metadata.
    """
    try:
        results = []

        # Search flow templates
        if not template_type or template_type == "flow":
            flow_result = await db.execute(
                select(FlowTemplateVersion)
                .join(FlowKind)
                .where(
                    or_(
                        FlowTemplateVersion.template_name.ilike(f"%{q}%"),
                        FlowTemplateVersion.description.ilike(f"%{q}%"),
                        FlowKind.display_name.ilike(f"%{q}%"),
                        FlowKind.kind_key.ilike(f"%{q}%"),
                    )
                )
                .limit(limit)
            )
            flow_templates = flow_result.scalars().all()

            for template in flow_templates:
                results.append(
                    {
                        "type": "flow",
                        "id": str(template.id),
                        "name": template.template_name,
                        "description": template.description,
                        "relevance_score": 1.0,  # Could implement proper scoring
                    }
                )

        # Search quiz templates
        if not template_type or template_type == "quiz":
            quiz_result = await db.execute(
                select(QuizTemplate).where(
                    or_(
                        QuizTemplate.name.ilike(f"%{q}%"),
                        QuizTemplate.description.ilike(f"%{q}%"),
                        QuizTemplate.category.ilike(f"%{q}%"),
                    )
                )
                .limit(limit)
            )
            quiz_templates = quiz_result.scalars().all()

            for quiz in quiz_templates:
                results.append(
                    {
                        "type": "quiz",
                        "id": str(quiz.id),
                        "name": quiz.name,
                        "description": quiz.description,
                        "relevance_score": 1.0,
                    }
                )

        # Audit log for search operations
        user_id = current_user.get("uid") or current_user.get("user_id") or "anonymous"
        user_role = current_user.get("role")
        AuditLogger.log(
            action=AuditAction.SEARCH,
            resource_type="template",
            resource_id="search",
            user_id=str(user_id),
            user_role=user_role,
            details={
                "query": q,
                "template_type": template_type,
                "results_count": len(results),
            },
            ip_address=request.client.host if request.client else None,
        )

        return {"query": q, "results": results[:limit], "total": len(results)}

    except Exception as e:
        logger.error(f"Error searching templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search templates",
        )


@router.post(
    "/validate",
    response_model=TemplateValidationResponse,
    summary="Validate template",
    description="Validate template structure and content",
)
@limiter.limit(RATE_LIMIT_READ)
async def validate_template(
    request: Request,
    template_data: Dict[str, Any],
    template_type: str = Query(..., description="Template type (flow, quiz)"),
    current_user: Dict = Depends(get_current_user_from_session),
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

        # Audit log for validation operations
        user_id = current_user.get("uid") or current_user.get("user_id") or "anonymous"
        user_role = current_user.get("role")
        AuditLogger.log(
            action=AuditAction.VALIDATE,
            resource_type=template_type,
            resource_id="validation",
            user_id=str(user_id),
            user_role=user_role,
            details={
                "template_type": template_type,
                "is_valid": is_valid,
                "errors_count": len(errors),
                "warnings_count": len(warnings),
            },
            ip_address=request.client.host if request.client else None,
        )

        return {"valid": is_valid, "errors": errors, "warnings": warnings}

    except Exception as e:
        logger.error(f"Error validating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate template",
        )
