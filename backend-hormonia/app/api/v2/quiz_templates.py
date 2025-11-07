"""
Quiz Templates API v2
Quiz template management with version control, pagination, and caching.
Handles CRUD operations for quiz templates with validation and duplication support.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_

from app.database import get_db
from app.models.quiz import QuizTemplate
from app.dependencies.auth_dependencies import get_redis_cache
from app.schemas.v2.templates import (
    QuizTemplateV2Response,
    QuizTemplateV2List,
    QuizTemplateV2Create,
    QuizTemplateV2Update,
    QuizTemplateV2Duplicate,
)
from app.utils.rate_limiter import limiter

# Import shared helpers and constants from templates_shared module
from .templates_shared import (
    _get_current_user_simple,
    _check_write_permission,
    _extract_user_context,
    _get_cache_key,
    _get_cached_result,
    _set_cached_result,
    _invalidate_template_cache,
    _serialize_quiz_template,
    CACHE_TTL_ACTIVE_TEMPLATES,
    RATE_LIMIT_READ,
    RATE_LIMIT_WRITE,
)
from .dependencies import apply_field_selection

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== Quiz Template Endpoints ====================

@router.get(
    "/quiz",
    response_model=QuizTemplateV2List,
    summary="List quiz templates",
    description="List quiz templates with cursor pagination and filtering"
)
@limiter.limit(RATE_LIMIT_READ)
async def list_quiz_templates(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """List quiz templates with advanced filtering and pagination."""
    try:
        # Check cache
        cache_key = _get_cache_key("quiz_list", cursor=cursor, limit=limit,
                                   is_active=is_active, category=category)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        # Build query
        query = db.query(QuizTemplate)

        # Apply filters
        if is_active is not None:
            query = query.filter(QuizTemplate.is_active == is_active)
        if category:
            query = query.filter(QuizTemplate.category == category)

        # Apply cursor pagination
        if cursor:
            try:
                cursor_data = json.loads(cursor)
                cursor_id = UUID(cursor_data["id"])
                cursor_created = datetime.fromisoformat(cursor_data["created_at"])
                query = query.filter(
                    or_(
                        QuizTemplate.created_at < cursor_created,
                        and_(
                            QuizTemplate.created_at == cursor_created,
                            QuizTemplate.id < cursor_id
                        )
                    )
                )
            except (ValueError, KeyError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid cursor format: {str(e)}"
                )

        # Order and limit
        query = query.order_by(desc(QuizTemplate.created_at), desc(QuizTemplate.id))
        templates = query.limit(limit + 1).all()

        # Check if there are more items
        has_more = len(templates) > limit
        if has_more:
            templates = templates[:limit]

        # Generate next cursor
        next_cursor = None
        if has_more and templates:
            last_item = templates[-1]
            next_cursor = json.dumps({
                "id": str(last_item.id),
                "created_at": last_item.created_at.isoformat()
            })

        # Serialize templates
        data = [_serialize_quiz_template(t) for t in templates]

        # Apply field selection
        if fields:
            field_set = set(fields.split(","))
            data = [apply_field_selection(item, field_set) for item in data]

        result = {
            "data": data,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_ACTIVE_TEMPLATES)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing quiz templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list quiz templates"
        )


@router.get(
    "/quiz/{quiz_id}",
    response_model=QuizTemplateV2Response,
    summary="Get quiz template",
    description="Get specific quiz template by ID"
)
@limiter.limit(RATE_LIMIT_READ)
async def get_quiz_template(
    request: Request,
    quiz_id: UUID,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """Get specific quiz template by ID."""
    try:
        # Check cache
        cache_key = _get_cache_key("quiz_detail", quiz_id=str(quiz_id))
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        template = db.query(QuizTemplate).filter(QuizTemplate.id == quiz_id).first()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz template not found"
            )

        result = _serialize_quiz_template(template)

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_ACTIVE_TEMPLATES)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quiz template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get quiz template"
        )


@router.post(
    "/quiz",
    response_model=QuizTemplateV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create quiz template",
    description="Create a new quiz template"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def create_quiz_template(
    request: Request,
    quiz: QuizTemplateV2Create,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Create a new quiz template.

    Only administrators and doctors can create quiz templates.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        # Check if quiz with same name and version already exists
        existing = db.query(QuizTemplate).filter(
            QuizTemplate.name == quiz.name,
            QuizTemplate.version == quiz.version
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Quiz template '{quiz.name}' version '{quiz.version}' already exists"
            )

        # Create quiz template
        quiz_template = QuizTemplate(
            name=quiz.name,
            version=quiz.version,
            description=quiz.description,
            questions=quiz.questions,
            category=quiz.category,
            tags=quiz.tags or [],
            passing_score=quiz.passing_score,
            time_limit_minutes=quiz.time_limit_minutes,
            randomize_questions=quiz.randomize_questions,
            is_active=quiz.is_active if quiz.is_active is not None else True
        )

        db.add(quiz_template)
        db.commit()
        db.refresh(quiz_template)

        # Invalidate cache
        await _invalidate_template_cache("quiz")

        logger.info(f"Created quiz template: {quiz.name} v{quiz.version} by user {user_uuid}")

        return _serialize_quiz_template(quiz_template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating quiz template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create quiz template: {str(e)}"
        )


@router.put(
    "/quiz/{quiz_id}",
    response_model=QuizTemplateV2Response,
    summary="Update quiz template",
    description="Update an existing quiz template"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def update_quiz_template(
    request: Request,
    quiz_id: UUID,
    updates: QuizTemplateV2Update,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Update quiz template.

    Only administrators and doctors can update quiz templates.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        quiz = db.query(QuizTemplate).filter(QuizTemplate.id == quiz_id).first()

        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz template not found"
            )

        # Apply updates
        if updates.name is not None:
            quiz.name = updates.name
        if updates.version is not None:
            quiz.version = updates.version
        if updates.description is not None:
            quiz.description = updates.description
        if updates.questions is not None:
            quiz.questions = updates.questions
        if updates.category is not None:
            quiz.category = updates.category
        if updates.tags is not None:
            quiz.tags = updates.tags
        if updates.passing_score is not None:
            quiz.passing_score = updates.passing_score
        if updates.time_limit_minutes is not None:
            quiz.time_limit_minutes = updates.time_limit_minutes
        if updates.randomize_questions is not None:
            quiz.randomize_questions = updates.randomize_questions
        if updates.is_active is not None:
            quiz.is_active = updates.is_active

        quiz.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(quiz)

        # Invalidate cache
        await _invalidate_template_cache("quiz", quiz_id)

        logger.info(f"Updated quiz template: {quiz_id} by user {user_uuid}")

        return _serialize_quiz_template(quiz)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating quiz template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update quiz template: {str(e)}"
        )


@router.delete(
    "/quiz/{quiz_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete quiz template",
    description="Delete quiz template (soft or hard delete)"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def delete_quiz_template(
    request: Request,
    quiz_id: UUID,
    soft_delete: bool = Query(True, description="Soft delete (deactivate) vs hard delete"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Delete quiz template (soft or hard delete).

    - **soft_delete=true**: Sets is_active = False (recommended)
    - **soft_delete=false**: Permanently removes from database (use with caution)

    Only administrators and doctors can delete quiz templates.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        quiz = db.query(QuizTemplate).filter(QuizTemplate.id == quiz_id).first()

        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz template not found"
            )

        if soft_delete:
            # Soft delete: deactivate
            quiz.is_active = False
            quiz.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Soft deleted quiz template: {quiz_id} by user {user_uuid}")
        else:
            # Hard delete: remove from database
            db.delete(quiz)
            db.commit()
            logger.warning(f"Hard deleted quiz template: {quiz_id} by user {user_uuid}")

        # Invalidate cache
        await _invalidate_template_cache("quiz", quiz_id)

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting quiz template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete quiz template"
        )


@router.post(
    "/quiz/{quiz_id}/duplicate",
    response_model=QuizTemplateV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate quiz template",
    description="Create a copy of an existing quiz template"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def duplicate_quiz_template(
    request: Request,
    quiz_id: UUID,
    duplicate_data: QuizTemplateV2Duplicate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Duplicate an existing quiz template.

    Creates a new version based on an existing template.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        # Get source template
        source = db.query(QuizTemplate).filter(QuizTemplate.id == quiz_id).first()

        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source quiz template not found"
            )

        # Check if new version already exists
        existing = db.query(QuizTemplate).filter(
            QuizTemplate.name == (duplicate_data.new_name or source.name),
            QuizTemplate.version == duplicate_data.new_version
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Quiz '{duplicate_data.new_name or source.name}' version '{duplicate_data.new_version}' already exists"
            )

        # Create duplicate
        new_quiz = QuizTemplate(
            name=duplicate_data.new_name or source.name,
            version=duplicate_data.new_version,
            description=duplicate_data.description or source.description,
            questions=source.questions.copy() if isinstance(source.questions, list) else source.questions,
            category=source.category,
            tags=source.tags.copy() if source.tags else [],
            passing_score=source.passing_score,
            time_limit_minutes=source.time_limit_minutes,
            randomize_questions=source.randomize_questions,
            is_active=False  # New duplicates are inactive by default
        )

        db.add(new_quiz)
        db.commit()
        db.refresh(new_quiz)

        # Invalidate cache
        await _invalidate_template_cache("quiz")

        logger.info(f"Duplicated quiz template: {quiz_id} -> {new_quiz.id} by user {user_uuid}")

        return _serialize_quiz_template(new_quiz)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating quiz template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to duplicate quiz template: {str(e)}"
        )
