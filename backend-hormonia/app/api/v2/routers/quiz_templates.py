from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import and_, desc, or_

from app.database import get_db
from app.models.quiz import QuizTemplate
from app.schemas.v2.templates import (
    QuizTemplateV2Response,
    QuizTemplateV2List,
    QuizTemplateV2Create,
    QuizTemplateV2Update,
    QuizTemplateV2Duplicate,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.api.v2.dependencies import apply_field_selection
from app.utils.rate_limiter import limiter

from app.api.v2.templates_shared import (
    _get_current_user_simple,
    _extract_user_context,
    _check_write_permission,
    _get_cache_key,
    _get_cached_result,
    _set_cached_result,
    _invalidate_template_cache,
    CACHE_TTL_ACTIVE_TEMPLATES,
    RATE_LIMIT_READ,
    RATE_LIMIT_WRITE,
)

router = APIRouter()
logger = logging.getLogger(__name__)

def _serialize_quiz_template(template) -> dict:
    return {
        "id": str(template.id),
        "name": template.name,
        "version": template.version,
        "description": template.description,
        "questions": template.questions,
        "is_active": template.is_active,
        "category": template.category,
        "tags": template.tags,
        "passing_score": template.passing_score,
        "time_limit_minutes": template.time_limit_minutes,
        "randomize_questions": template.randomize_questions,
        "created_at": template.created_at,
        "updated_at": template.updated_at
    }

@router.get("/quizzes", response_model=QuizTemplateV2List)
@limiter.limit(RATE_LIMIT_READ)
async def list_quiz_templates(
    request: Request,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    category: Optional[str] = Query(None),
    fields: Optional[str] = Query(None),
    db = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
):
    try:
        cache_key = _get_cache_key("quiz_list", cursor=cursor, limit=limit, is_active=is_active, category=category)
        cached = await _get_cached_result(cache_key)
        if cached: return cached

        query = db.query(QuizTemplate)
        if is_active is not None: query = query.filter(QuizTemplate.is_active == is_active)
        if category: query = query.filter(QuizTemplate.category == category)

        if cursor:
            try:
                cursor_data = json.loads(cursor)
                cursor_id = UUID(cursor_data["id"])
                cursor_created = datetime.fromisoformat(cursor_data["created_at"])
                query = query.filter(or_(
                    QuizTemplate.created_at < cursor_created,
                    and_(QuizTemplate.created_at == cursor_created, QuizTemplate.id < cursor_id)
                ))
            except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                raise HTTPException(status_code=400, detail="Invalid cursor")

        query = query.order_by(desc(QuizTemplate.created_at), desc(QuizTemplate.id))
        templates = query.limit(limit + 1).all()

        has_more = len(templates) > limit
        if has_more: templates = templates[:limit]

        next_cursor = None
        if has_more and templates:
            last = templates[-1]
            next_cursor = json.dumps({"id": str(last.id), "created_at": last.created_at.isoformat()})

        data = [_serialize_quiz_template(t) for t in templates]
        if fields:
            field_set = set(fields.split(","))
            data = [apply_field_selection(item, field_set) for item in data]

        result = {"data": data, "next_cursor": next_cursor, "has_more": has_more, "total": None}
        await _set_cached_result(cache_key, result, CACHE_TTL_ACTIVE_TEMPLATES)
        return result
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list")

@router.get("/quizzes/{template_id}", response_model=QuizTemplateV2Response)
@limiter.limit(RATE_LIMIT_READ)
async def get_quiz_template(
    request: Request,
    template_id: UUID,
    db = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
):
    try:
        query = db.query(QuizTemplate).filter(QuizTemplate.id == template_id)
        template = query.first()
        if not template: raise HTTPException(status_code=404)
        return _serialize_quiz_template(template)
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quizzes", response_model=QuizTemplateV2Response, status_code=201)
@limiter.limit(RATE_LIMIT_WRITE)
async def create_quiz_template(
    request: Request,
    template: QuizTemplateV2Create,
    db = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
):
    try:
        _check_write_permission(current_user)
        new_template = QuizTemplate(
            name=template.name,
            version=template.version,
            description=template.description,
            questions=template.questions,
            is_active=template.is_active if template.is_active is not None else True,
            category=template.category,
            tags=template.tags,
            passing_score=template.passing_score,
            time_limit_minutes=template.time_limit_minutes,
            randomize_questions=template.randomize_questions if template.randomize_questions is not None else False
        )
        db.add(new_template)
        db.commit()
        db.refresh(new_template)
        await _invalidate_template_cache("quiz")
        return _serialize_quiz_template(new_template)
    except HTTPException: raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/quizzes/{template_id}", response_model=QuizTemplateV2Response)
@limiter.limit(RATE_LIMIT_WRITE)
async def update_quiz_template(
    request: Request,
    template_id: UUID,
    updates: QuizTemplateV2Update,
    db = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
):
    try:
        _check_write_permission(current_user)
        template = db.query(QuizTemplate).get(template_id)
        if not template: raise HTTPException(status_code=404)

        if updates.name: template.name = updates.name
        if updates.version: template.version = updates.version
        if updates.description: template.description = updates.description
        if updates.questions: template.questions = updates.questions
        if updates.is_active is not None: template.is_active = updates.is_active
        if updates.category: template.category = updates.category
        if updates.tags: template.tags = updates.tags
        if updates.passing_score: template.passing_score = updates.passing_score
        if updates.time_limit_minutes: template.time_limit_minutes = updates.time_limit_minutes
        if updates.randomize_questions is not None: template.randomize_questions = updates.randomize_questions
        
        template.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(template)
        await _invalidate_template_cache("quiz", template_id)
        return _serialize_quiz_template(template)
    except HTTPException: raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/quizzes/{template_id}", status_code=204)
async def delete_quiz_template(
    request: Request,
    template_id: UUID,
    db = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
):
    try:
        _check_write_permission(current_user)
        template = db.query(QuizTemplate).get(template_id)
        if not template: raise HTTPException(status_code=404)
        db.delete(template)
        db.commit()
        await _invalidate_template_cache("quiz", template_id)
        return None
    except HTTPException: raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quizzes/{template_id}/duplicate", response_model=QuizTemplateV2Response, status_code=201)
async def duplicate_quiz_template(
    request: Request,
    template_id: UUID,
    duplicate_data: QuizTemplateV2Duplicate,
    db = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
):
    try:
        _check_write_permission(current_user)
        source = db.query(QuizTemplate).get(template_id)
        if not source: raise HTTPException(status_code=404)

        new_template = QuizTemplate(
            name=duplicate_data.new_name or f"{source.name} (Copy)",
            version=duplicate_data.new_version or source.version,
            description=source.description,
            questions=source.questions,
            is_active=False,
            category=source.category,
            tags=source.tags,
            passing_score=source.passing_score,
            time_limit_minutes=source.time_limit_minutes,
            randomize_questions=source.randomize_questions
        )
        db.add(new_template)
        db.commit()
        db.refresh(new_template)
        await _invalidate_template_cache("quiz")
        return _serialize_quiz_template(new_template)
    except HTTPException: raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
