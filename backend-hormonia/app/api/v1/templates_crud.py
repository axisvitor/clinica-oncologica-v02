"""
CRUD API endpoints for template management (flows and quizzes).
Provides full CRUD operations for database-backed templates.
"""
import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin_user
from app.models.user import User
from app.models.flow import FlowKind, FlowTemplateVersion
from app.models.quiz import QuizTemplate
from app.schemas.template import (
    # Flow schemas
    FlowTemplateCreate,
    FlowTemplateUpdate,
    FlowTemplateResponse,
    FlowTemplateListResponse,
    FlowKindCreate,
    FlowKindResponse,
    FlowKindListResponse,
    # Quiz schemas
    QuizTemplateCreate,
    QuizTemplateUpdate,
    QuizTemplateResponse,
    QuizTemplateListResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])


# ==================== Flow Template Endpoints ====================

@router.post("/flows", response_model=FlowTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_flow_template(
    template: FlowTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> FlowTemplateResponse:
    """
    Create a new flow template version.

    Creates a new template version for an existing flow kind or creates a new flow kind.
    """
    try:
        # Get or create flow kind
        if template.flow_kind_id:
            flow_kind = db.query(FlowKind).filter(FlowKind.id == template.flow_kind_id).first()
            if not flow_kind:
                raise HTTPException(status_code=404, detail="Flow kind not found")
        elif template.kind_key:
            # Try to find existing flow kind
            flow_kind = db.query(FlowKind).filter(FlowKind.kind_key == template.kind_key).first()

            if not flow_kind:
                # Create new flow kind
                flow_kind = FlowKind(
                    kind_key=template.kind_key,
                    display_name=template.display_name,
                    description=template.description,
                    is_active=True
                )
                db.add(flow_kind)
                db.flush()
        else:
            raise HTTPException(
                status_code=400,
                detail="Either flow_kind_id or kind_key must be provided"
            )

        # Create template version
        import json
        template_version = FlowTemplateVersion(
            flow_kind_id=flow_kind.id,
            version_number=template.version_number,
            template_name=template.display_name,
            description=template.description,
            steps=template.steps.model_dump() if hasattr(template.steps, 'model_dump') else template.steps,
            metadata=template.metadata.model_dump() if template.metadata and hasattr(template.metadata, 'model_dump') else (template.metadata or {}),
            is_active=template.is_active,
            is_draft=template.is_draft,
            published_at=None if template.is_draft else db.func.now(),
            created_by=current_user.id
        )

        db.add(template_version)
        db.commit()
        db.refresh(template_version)

        logger.info(f"Created flow template version: {flow_kind.kind_key} v{template.version_number}")

        # Build response
        return FlowTemplateResponse(
            id=template_version.id,
            flow_kind_id=template_version.flow_kind_id,
            kind_key=flow_kind.kind_key,
            display_name=flow_kind.display_name,
            version_number=template_version.version_number,
            template_name=template_version.template_name,
            description=template_version.description,
            steps=template_version.steps,
            metadata=template_version.metadata,
            is_active=template_version.is_active,
            is_draft=template_version.is_draft,
            published_at=template_version.published_at,
            created_at=template_version.created_at,
            updated_at=template_version.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating flow template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create flow template: {str(e)}")


@router.get("/flows", response_model=FlowTemplateListResponse)
async def list_flow_templates(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_draft: Optional[bool] = Query(None, description="Filter by draft status"),
    kind_key: Optional[str] = Query(None, description="Filter by flow kind"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> FlowTemplateListResponse:
    """
    List flow templates with pagination and filtering.
    """
    try:
        query = db.query(FlowTemplateVersion).join(FlowKind)

        # Apply filters
        if is_active is not None:
            query = query.filter(FlowTemplateVersion.is_active == is_active)
        if is_draft is not None:
            query = query.filter(FlowTemplateVersion.is_draft == is_draft)
        if kind_key:
            query = query.filter(FlowKind.kind_key == kind_key)

        # Get total count
        total = query.count()

        # Apply pagination
        query = query.order_by(FlowTemplateVersion.created_at.desc())
        query = query.offset((page - 1) * size).limit(size)

        templates = query.all()

        # Build response items
        items = []
        for template in templates:
            items.append(FlowTemplateResponse(
                id=template.id,
                flow_kind_id=template.flow_kind_id,
                kind_key=template.kind.kind_key,
                display_name=template.kind.display_name,
                version_number=template.version_number,
                template_name=template.template_name,
                description=template.description,
                steps=template.steps,
                metadata=template.metadata,
                is_active=template.is_active,
                is_draft=template.is_draft,
                published_at=template.published_at,
                created_at=template.created_at,
                updated_at=template.updated_at
            ))

        total_pages = (total + size - 1) // size

        return FlowTemplateListResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            total_pages=total_pages
        )

    except Exception as e:
        logger.error(f"Error listing flow templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to list flow templates")


@router.get("/flows/{template_id}", response_model=FlowTemplateResponse)
async def get_flow_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> FlowTemplateResponse:
    """
    Get specific flow template by ID.
    """
    template = db.query(FlowTemplateVersion).filter(FlowTemplateVersion.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Flow template not found")

    return FlowTemplateResponse(
        id=template.id,
        flow_kind_id=template.flow_kind_id,
        kind_key=template.kind.kind_key,
        display_name=template.kind.display_name,
        version_number=template.version_number,
        template_name=template.template_name,
        description=template.description,
        steps=template.steps,
        metadata=template.metadata,
        is_active=template.is_active,
        is_draft=template.is_draft,
        published_at=template.published_at,
        created_at=template.created_at,
        updated_at=template.updated_at
    )


@router.put("/flows/{template_id}", response_model=FlowTemplateResponse)
async def update_flow_template(
    template_id: UUID,
    updates: FlowTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> FlowTemplateResponse:
    """
    Update flow template.

    Note: For versioned templates, consider creating a new version instead of updating.
    """
    template = db.query(FlowTemplateVersion).filter(FlowTemplateVersion.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Flow template not found")

    try:
        # Apply updates
        if updates.template_name is not None:
            template.template_name = updates.template_name
        if updates.description is not None:
            template.description = updates.description
        if updates.steps is not None:
            template.steps = updates.steps.model_dump() if hasattr(updates.steps, 'model_dump') else updates.steps
        if updates.metadata is not None:
            template.metadata = updates.metadata.model_dump() if hasattr(updates.metadata, 'model_dump') else updates.metadata
        if updates.is_active is not None:
            template.is_active = updates.is_active
        if updates.is_draft is not None:
            template.is_draft = updates.is_draft

        template.updated_by = current_user.id

        db.commit()
        db.refresh(template)

        logger.info(f"Updated flow template: {template.id}")

        return FlowTemplateResponse(
            id=template.id,
            flow_kind_id=template.flow_kind_id,
            kind_key=template.kind.kind_key,
            display_name=template.kind.display_name,
            version_number=template.version_number,
            template_name=template.template_name,
            description=template.description,
            steps=template.steps,
            metadata=template.metadata,
            is_active=template.is_active,
            is_draft=template.is_draft,
            published_at=template.published_at,
            created_at=template.created_at,
            updated_at=template.updated_at
        )

    except Exception as e:
        logger.error(f"Error updating flow template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update flow template: {str(e)}")


@router.delete("/flows/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_template(
    template_id: UUID,
    soft_delete: bool = Query(True, description="Soft delete (deactivate) vs hard delete"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Delete flow template (soft or hard delete).

    Soft delete: Sets is_active = False (recommended)
    Hard delete: Permanently removes from database (use with caution)
    """
    template = db.query(FlowTemplateVersion).filter(FlowTemplateVersion.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Flow template not found")

    try:
        if soft_delete:
            # Soft delete: deactivate
            template.is_active = False
            template.updated_by = current_user.id
            db.commit()
            logger.info(f"Soft deleted flow template: {template.id}")
        else:
            # Hard delete: remove from database
            db.delete(template)
            db.commit()
            logger.warning(f"Hard deleted flow template: {template.id}")

        return None

    except Exception as e:
        logger.error(f"Error deleting flow template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete flow template")


# ==================== Quiz Template Endpoints ====================

@router.post("/quiz", response_model=QuizTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_quiz_template(
    quiz: QuizTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> QuizTemplateResponse:
    """
    Create a new quiz template.
    """
    try:
        # Check if quiz with same name already exists
        existing = db.query(QuizTemplate).filter(QuizTemplate.name == quiz.name).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Quiz template with name '{quiz.name}' already exists"
            )

        # Create quiz template
        quiz_template = QuizTemplate(
            name=quiz.name,
            version=quiz.version,
            description=quiz.description,
            questions=[ q.model_dump() for q in quiz.questions],
            category=quiz.category,
            tags=quiz.tags,
            passing_score=quiz.passing_score,
            time_limit_minutes=quiz.time_limit_minutes,
            randomize_questions=quiz.randomize_questions,
            is_active=quiz.is_active
        )

        db.add(quiz_template)
        db.commit()
        db.refresh(quiz_template)

        logger.info(f"Created quiz template: {quiz.name}")

        return QuizTemplateResponse(
            id=quiz_template.id,
            name=quiz_template.name,
            version=quiz_template.version,
            description=quiz_template.description,
            questions=quiz_template.questions,
            category=quiz_template.category,
            tags=quiz_template.tags,
            passing_score=quiz_template.passing_score,
            time_limit_minutes=quiz_template.time_limit_minutes,
            randomize_questions=quiz_template.randomize_questions,
            is_active=quiz_template.is_active,
            created_at=quiz_template.created_at,
            updated_at=quiz_template.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating quiz template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create quiz template: {str(e)}")


@router.get("/quiz", response_model=QuizTemplateListResponse)
async def list_quiz_templates(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> QuizTemplateListResponse:
    """
    List quiz templates with pagination and filtering.
    """
    try:
        query = db.query(QuizTemplate)

        # Apply filters
        if is_active is not None:
            query = query.filter(QuizTemplate.is_active == is_active)
        if category:
            query = query.filter(QuizTemplate.category == category)

        # Get total count
        total = query.count()

        # Apply pagination
        query = query.order_by(QuizTemplate.created_at.desc())
        query = query.offset((page - 1) * size).limit(size)

        quizzes = query.all()

        # Build response items
        items = [
            QuizTemplateResponse(
                id=quiz.id,
                name=quiz.name,
                version=quiz.version,
                description=quiz.description,
                questions=quiz.questions,
                category=quiz.category,
                tags=quiz.tags,
                passing_score=quiz.passing_score,
                time_limit_minutes=quiz.time_limit_minutes,
                randomize_questions=quiz.randomize_questions,
                is_active=quiz.is_active,
                created_at=quiz.created_at,
                updated_at=quiz.updated_at
            )
            for quiz in quizzes
        ]

        total_pages = (total + size - 1) // size

        return QuizTemplateListResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            total_pages=total_pages
        )

    except Exception as e:
        logger.error(f"Error listing quiz templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to list quiz templates")


@router.get("/quiz/{quiz_id}", response_model=QuizTemplateResponse)
async def get_quiz_template(
    quiz_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> QuizTemplateResponse:
    """
    Get specific quiz template by ID.
    """
    quiz = db.query(QuizTemplate).filter(QuizTemplate.id == quiz_id).first()

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz template not found")

    return QuizTemplateResponse(
        id=quiz.id,
        name=quiz.name,
        version=quiz.version,
        description=quiz.description,
        questions=quiz.questions,
        category=quiz.category,
        tags=quiz.tags,
        passing_score=quiz.passing_score,
        time_limit_minutes=quiz.time_limit_minutes,
        randomize_questions=quiz.randomize_questions,
        is_active=quiz.is_active,
        created_at=quiz.created_at,
        updated_at=quiz.updated_at
    )


@router.put("/quiz/{quiz_id}", response_model=QuizTemplateResponse)
async def update_quiz_template(
    quiz_id: UUID,
    updates: QuizTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> QuizTemplateResponse:
    """
    Update quiz template.
    """
    quiz = db.query(QuizTemplate).filter(QuizTemplate.id == quiz_id).first()

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz template not found")

    try:
        # Apply updates
        if updates.name is not None:
            quiz.name = updates.name
        if updates.version is not None:
            quiz.version = updates.version
        if updates.description is not None:
            quiz.description = updates.description
        if updates.questions is not None:
            quiz.questions = [q.model_dump() for q in updates.questions]
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

        db.commit()
        db.refresh(quiz)

        logger.info(f"Updated quiz template: {quiz.id}")

        return QuizTemplateResponse(
            id=quiz.id,
            name=quiz.name,
            version=quiz.version,
            description=quiz.description,
            questions=quiz.questions,
            category=quiz.category,
            tags=quiz.tags,
            passing_score=quiz.passing_score,
            time_limit_minutes=quiz.time_limit_minutes,
            randomize_questions=quiz.randomize_questions,
            is_active=quiz.is_active,
            created_at=quiz.created_at,
            updated_at=quiz.updated_at
        )

    except Exception as e:
        logger.error(f"Error updating quiz template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update quiz template: {str(e)}")


@router.delete("/quiz/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz_template(
    quiz_id: UUID,
    soft_delete: bool = Query(True, description="Soft delete (deactivate) vs hard delete"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Delete quiz template (soft or hard delete).

    Soft delete: Sets is_active = False (recommended)
    Hard delete: Permanently removes from database (use with caution)
    """
    quiz = db.query(QuizTemplate).filter(QuizTemplate.id == quiz_id).first()

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz template not found")

    try:
        if soft_delete:
            # Soft delete: deactivate
            quiz.is_active = False
            db.commit()
            logger.info(f"Soft deleted quiz template: {quiz.id}")
        else:
            # Hard delete: remove from database
            db.delete(quiz)
            db.commit()
            logger.warning(f"Hard deleted quiz template: {quiz.id}")

        return None

    except Exception as e:
        logger.error(f"Error deleting quiz template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete quiz template")


# ==================== Flow Kind Endpoints ====================

@router.get("/flow-kinds", response_model=FlowKindListResponse)
async def list_flow_kinds(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> FlowKindListResponse:
    """
    List all flow kinds (flow types).
    """
    try:
        query = db.query(FlowKind)

        if is_active is not None:
            query = query.filter(FlowKind.is_active == is_active)

        flow_kinds = query.all()

        items = [
            FlowKindResponse(
                id=fk.id,
                kind_key=fk.kind_key,
                display_name=fk.display_name,
                description=fk.description,
                is_active=fk.is_active,
                created_at=fk.created_at,
                updated_at=fk.updated_at
            )
            for fk in flow_kinds
        ]

        return FlowKindListResponse(
            items=items,
            total=len(items)
        )

    except Exception as e:
        logger.error(f"Error listing flow kinds: {e}")
        raise HTTPException(status_code=500, detail="Failed to list flow kinds")
