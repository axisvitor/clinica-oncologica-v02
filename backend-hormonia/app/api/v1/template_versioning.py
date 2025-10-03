"""
API endpoints for template versioning management.
Handles flow kinds, template versions, publishing, and lifecycle management.
"""
import logging
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import datetime
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.repositories.flow_kind import FlowKindRepository
from app.repositories.flow_template_version import FlowTemplateVersionRepository
from app.services.versioned_template_loader import VersionedTemplateLoader
from app.exceptions import internal_server_exception, flow_operation_exception

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models for request/response
from pydantic import BaseModel, Field
from typing import Union


class FlowKindCreateRequest(BaseModel):
    flow_type: str = Field(..., min_length=1, max_length=50, description="Unique flow type identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable name")
    description: Optional[str] = Field(None, description="Flow kind description")


class FlowKindResponse(BaseModel):
    id: str
    flow_type: str
    name: str
    description: Optional[str]
    current_version_id: Optional[str]
    total_versions: int
    published_versions: int
    draft_versions: int
    latest_version_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateVersionCreateRequest(BaseModel):
    version: str = Field(..., min_length=1, max_length=20, description="Version string (e.g., '2.1.0')")
    description: Optional[str] = Field(None, description="Version description")
    template_data: Dict[str, Any] = Field(..., description="Template data (messages, metadata, etc.)")
    duration_days: int = Field(..., ge=1, le=365, description="Flow duration in days")


class TemplateVersionResponse(BaseModel):
    id: str
    version: str
    description: Optional[str]
    status: str
    duration_days: int
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    updated_by: Optional[str]

    class Config:
        from_attributes = True


class TemplateVersionPublishRequest(BaseModel):
    set_as_current: bool = Field(True, description="Set this version as current for the flow kind")


class FlowKindListResponse(BaseModel):
    kinds: List[FlowKindResponse]
    total: int


class TemplateVersionListResponse(BaseModel):
    versions: List[TemplateVersionResponse]
    flow_type: str
    kind_name: str
    total: int


@router.get("/kinds", response_model=FlowKindListResponse)
async def list_flow_kinds(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all flow kinds with version statistics."""
    try:
        flow_kind_repo = FlowKindRepository(db)
        kinds_with_stats = flow_kind_repo.list_kinds_with_stats()

        kinds = []
        for kind_data in kinds_with_stats:
            kinds.append(FlowKindResponse(
                id=str(kind_data.id),
                flow_type=kind_data.flow_type,
                name=kind_data.name,
                description=kind_data.description,
                current_version_id=str(kind_data.current_version_id) if kind_data.current_version_id else None,
                total_versions=kind_data.total_versions or 0,
                published_versions=kind_data.published_versions or 0,
                draft_versions=kind_data.draft_versions or 0,
                latest_version_date=kind_data.latest_version_date,
                created_at=datetime.now(),  # Would come from actual DB
                updated_at=datetime.now()   # Would come from actual DB
            ))

        return FlowKindListResponse(kinds=kinds, total=len(kinds))

    except Exception as e:
        logger.error(f"Error listing flow kinds: {e}")
        raise internal_server_exception("Failed to list flow kinds")


@router.post("/kinds", response_model=FlowKindResponse, status_code=status.HTTP_201_CREATED)
async def create_flow_kind(
    request: FlowKindCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new flow kind."""
    try:
        flow_kind_repo = FlowKindRepository(db)

        # Check if flow_type already exists
        existing = flow_kind_repo.get_by_flow_type(request.flow_type)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Flow kind with type '{request.flow_type}' already exists"
            )

        # Create new flow kind
        kind = flow_kind_repo.create_kind(
            flow_type=request.flow_type,
            name=request.name,
            description=request.description
        )
        db.commit()

        return FlowKindResponse(
            id=str(kind.id),
            flow_type=kind.flow_type,
            name=kind.name,
            description=kind.description,
            current_version_id=None,
            total_versions=0,
            published_versions=0,
            draft_versions=0,
            latest_version_date=None,
            created_at=kind.created_at,
            updated_at=kind.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating flow kind: {e}")
        db.rollback()
        raise internal_server_exception("Failed to create flow kind")


@router.get("/kinds/{flow_type}/versions", response_model=TemplateVersionListResponse)
async def list_template_versions(
    flow_type: str,
    status: Optional[str] = Query(None, description="Filter by status (draft, published, archived)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all versions for a specific flow kind."""
    try:
        flow_kind_repo = FlowKindRepository(db)
        template_version_repo = FlowTemplateVersionRepository(db)

        # Get flow kind
        kind = flow_kind_repo.get_by_flow_type(flow_type)
        if not kind:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Flow kind '{flow_type}' not found"
            )

        # Get versions
        versions = template_version_repo.list_versions_by_kind(kind.id, status)

        version_responses = []
        for version in versions:
            version_responses.append(TemplateVersionResponse(
                id=str(version.id),
                version=version.version,
                description=version.description,
                status=version.status,
                duration_days=version.duration_days,
                published_at=version.published_at,
                created_at=version.created_at,
                updated_at=version.updated_at,
                created_by=str(version.created_by) if version.created_by else None,
                updated_by=str(version.updated_by) if version.updated_by else None
            ))

        return TemplateVersionListResponse(
            versions=version_responses,
            flow_type=flow_type,
            kind_name=kind.name,
            total=len(version_responses)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing template versions: {e}")
        raise internal_server_exception("Failed to list template versions")


@router.post("/kinds/{flow_type}/versions", response_model=TemplateVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_template_version(
    flow_type: str,
    request: TemplateVersionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new template version for a flow kind."""
    try:
        flow_kind_repo = FlowKindRepository(db)
        template_version_repo = FlowTemplateVersionRepository(db)

        # Get flow kind
        kind = flow_kind_repo.get_by_flow_type(flow_type)
        if not kind:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Flow kind '{flow_type}' not found"
            )

        # Check if version already exists
        existing = template_version_repo.get_by_kind_and_version(kind.id, request.version)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version '{request.version}' already exists for flow kind '{flow_type}'"
            )

        # Create template version
        version = template_version_repo.create_version(
            kind_id=kind.id,
            version=request.version,
            template_data=request.template_data,
            duration_days=request.duration_days,
            description=request.description,
            created_by=current_user.id
        )
        db.commit()

        return TemplateVersionResponse(
            id=str(version.id),
            version=version.version,
            description=version.description,
            status=version.status,
            duration_days=version.duration_days,
            published_at=version.published_at,
            created_at=version.created_at,
            updated_at=version.updated_at,
            created_by=str(version.created_by) if version.created_by else None,
            updated_by=str(version.updated_by) if version.updated_by else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating template version: {e}")
        db.rollback()
        raise internal_server_exception("Failed to create template version")


@router.post("/versions/{version_id}/publish", response_model=TemplateVersionResponse)
async def publish_template_version(
    version_id: UUID,
    request: TemplateVersionPublishRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Publish a draft template version."""
    try:
        flow_kind_repo = FlowKindRepository(db)
        template_version_repo = FlowTemplateVersionRepository(db)

        # Get template version
        version = template_version_repo.get_by_id(version_id)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template version not found"
            )

        if version.status != 'draft':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot publish version with status '{version.status}'. Only draft versions can be published."
            )

        # Publish version
        success = template_version_repo.publish_version(version_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to publish template version"
            )

        # Set as current version if requested
        if request.set_as_current:
            flow_kind_repo.update_current_version(version.kind_id, version_id)

        db.commit()

        # Return updated version
        updated_version = template_version_repo.get_by_id(version_id)
        return TemplateVersionResponse(
            id=str(updated_version.id),
            version=updated_version.version,
            description=updated_version.description,
            status=updated_version.status,
            duration_days=updated_version.duration_days,
            published_at=updated_version.published_at,
            created_at=updated_version.created_at,
            updated_at=updated_version.updated_at,
            created_by=str(updated_version.created_by) if updated_version.created_by else None,
            updated_by=str(updated_version.updated_by) if updated_version.updated_by else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing template version: {e}")
        db.rollback()
        raise internal_server_exception("Failed to publish template version")


@router.post("/versions/{version_id}/archive", response_model=TemplateVersionResponse)
async def archive_template_version(
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Archive a published template version."""
    try:
        template_version_repo = FlowTemplateVersionRepository(db)

        # Get template version
        version = template_version_repo.get_by_id(version_id)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template version not found"
            )

        if version.status != 'published':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot archive version with status '{version.status}'. Only published versions can be archived."
            )

        # Archive version
        success = template_version_repo.archive_version(version_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to archive template version"
            )

        db.commit()

        # Return updated version
        updated_version = template_version_repo.get_by_id(version_id)
        return TemplateVersionResponse(
            id=str(updated_version.id),
            version=updated_version.version,
            description=updated_version.description,
            status=updated_version.status,
            duration_days=updated_version.duration_days,
            published_at=updated_version.published_at,
            created_at=updated_version.created_at,
            updated_at=updated_version.updated_at,
            created_by=str(updated_version.created_by) if updated_version.created_by else None,
            updated_by=str(updated_version.updated_by) if updated_version.updated_by else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving template version: {e}")
        db.rollback()
        raise internal_server_exception("Failed to archive template version")


@router.get("/preview")
async def preview_template_message(
    flow_type: str = Query(..., description="Flow type"),
    day: int = Query(..., ge=1, description="Day number"),
    version: Optional[str] = Query(None, description="Template version (defaults to current)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Preview a message template for a specific day."""
    try:
        loader = VersionedTemplateLoader(db, enable_yaml_fallback=True)

        message_template = loader.get_message_for_day(flow_type, day, version)
        if not message_template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message template not found for {flow_type} day {day}"
            )

        return {
            "flow_type": flow_type,
            "day": day,
            "version": version or "current",
            "message": {
                "intent": message_template.intent,
                "base_content": message_template.base_content,
                "message_type": message_template.message_type.value,
                "core_elements": message_template.core_elements,
                "personalization_hints": message_template.personalization_hints,
                "ai_instructions": message_template.ai_instructions,
                "interactive_elements": message_template.interactive_elements.__dict__ if message_template.interactive_elements else None,
                "conditions": [
                    {
                        "type": c.type,
                        "field": c.field,
                        "operator": c.operator,
                        "value": c.value,
                        "logical_operator": c.logical_operator
                    } for c in message_template.conditions
                ],
                "follow_up": message_template.follow_up,
                "variations": message_template.variations
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing template message: {e}")
        raise internal_server_exception("Failed to preview template message")


@router.get("/analytics/{version_id}")
async def get_version_analytics(
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get analytics for a specific template version."""
    try:
        template_version_repo = FlowTemplateVersionRepository(db)

        # Check if version exists
        version = template_version_repo.get_by_id(version_id)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template version not found"
            )

        # Get analytics
        analytics = template_version_repo.get_version_analytics(version_id)

        return {
            "version_id": str(version_id),
            "version": version.version,
            "status": version.status,
            "analytics": analytics
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting version analytics: {e}")
        raise internal_server_exception("Failed to get version analytics")