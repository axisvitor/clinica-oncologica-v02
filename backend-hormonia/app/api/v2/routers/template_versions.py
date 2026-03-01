"""
Template Version Management API
Provides version control operations for flow templates including:
- Version listing and history tracking
- Version comparison and diff generation
- Version rollback capabilities
- Draft publication workflow
"""

from typing import Dict
from datetime import datetime, timezone
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import func, desc, select, update as sql_update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.models.flow import FlowTemplateVersion
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.schemas.v2.templates import (
    FlowTemplateV2Response,
    TemplateVersionV2List,
    TemplateVersionCompareResponse,
    TemplateVersionRollbackRequest,
)
from app.utils.rate_limiter import limiter

# Import shared helpers and constants from templates_shared module
from app.api.v2.templates_shared import (
    _extract_user_context,
    _check_write_permission,
    _get_cache_key,
    _get_cached_result,
    _set_cached_result,
    _invalidate_template_cache,
    _serialize_flow_template,
    _compare_templates,
    CACHE_TTL_VERSIONS,
    RATE_LIMIT_READ,
    RATE_LIMIT_WRITE,
)
from app.monitoring.audit_logger import TemplateAuditLogger as AuditLogger, TemplateAuditAction as AuditAction
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== Version Management Endpoints ====================


@router.get(
    "/flows/{template_id}/versions",
    response_model=TemplateVersionV2List,
    summary="List template versions",
    description="List all versions for a specific flow template",
)
@limiter.limit(RATE_LIMIT_READ)
async def list_template_versions(
    request: Request,
    template_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    """
    List all versions for a specific flow template.

    Returns version history with metadata, timestamps, and status information.
    """
    try:
        # Check cache
        cache_key = _get_cache_key("template_versions", template_id=str(template_id))
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        # Get the template to find its kind
        template_result = await db.execute(
            select(FlowTemplateVersion).where(FlowTemplateVersion.id == template_id)
        )
        template = template_result.scalar_one_or_none()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        # Get all versions for this kind (with eager loading to prevent N+1)
        versions_result = await db.execute(
            select(FlowTemplateVersion)
            .options(selectinload(FlowTemplateVersion.kind))
            .where(FlowTemplateVersion.flow_kind_id == template.flow_kind_id)
            .order_by(desc(FlowTemplateVersion.version_number))
        )
        versions = list(versions_result.scalars().all())

        data = [_serialize_flow_template(v) for v in versions]

        result = {
            "data": data,
            "kind_key": template.kind.kind_key if template.kind else None,
            "total": len(data),
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_VERSIONS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing template versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list template versions",
        )


@router.post(
    "/flows/{template_id}/versions/compare",
    response_model=TemplateVersionCompareResponse,
    summary="Compare template versions",
    description="Compare two template versions and show differences",
)
@limiter.limit(RATE_LIMIT_READ)
async def compare_template_versions(
    request: Request,
    template_id: UUID,
    compare_with_id: UUID = Query(..., description="Version ID to compare with"),
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    """
    Compare two template versions and generate a diff.

    Shows structural differences between versions to help understand what changed.
    """
    try:
        # Get both templates
        t1_result = await db.execute(
            select(FlowTemplateVersion).where(FlowTemplateVersion.id == template_id)
        )
        template1 = t1_result.scalar_one_or_none()
        t2_result = await db.execute(
            select(FlowTemplateVersion).where(FlowTemplateVersion.id == compare_with_id)
        )
        template2 = t2_result.scalar_one_or_none()

        if not template1 or not template2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both templates not found",
            )

        # Compare templates
        diff_result = _compare_templates(
            _serialize_flow_template(template1), _serialize_flow_template(template2)
        )

        return {
            "version1": _serialize_flow_template(template1),
            "version2": _serialize_flow_template(template2),
            "diff": diff_result["diff"],
            "changes": diff_result["changes"],
            "total_changes": diff_result["total_changes"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing template versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare template versions",
        )


@router.post(
    "/flows/{template_id}/rollback",
    response_model=FlowTemplateV2Response,
    summary="Rollback to template version",
    description="Rollback to a previous template version",
)
@limiter.limit(RATE_LIMIT_WRITE)
async def rollback_template_version(
    request: Request,
    template_id: UUID,
    rollback_data: TemplateVersionRollbackRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    """
    Rollback to a previous template version.

    Creates a new version based on a previous version's configuration.
    This maintains version history while reverting to known-good state.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        # Get source version to rollback to
        source_result = await db.execute(
            select(FlowTemplateVersion).where(FlowTemplateVersion.id == template_id)
        )
        source_version = source_result.scalar_one_or_none()

        if not source_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Source version not found"
            )

        # Get latest version number for this kind
        latest_result = await db.execute(
            select(func.max(FlowTemplateVersion.version_number)).where(
                FlowTemplateVersion.flow_kind_id == source_version.flow_kind_id
            )
        )
        latest = latest_result.scalar()

        new_version_number = (latest or 0) + 1

        # Create rollback version
        rollback_version = FlowTemplateVersion(
            flow_kind_id=source_version.flow_kind_id,
            version_number=new_version_number,
            template_name=f"{source_version.template_name} (Rollback)",
            description=rollback_data.reason
            or f"Rollback to version {source_version.version_number}",
            steps=source_version.steps,
            metadata_json=source_version.metadata_json.copy()
            if source_version.metadata_json
            else {},
            is_active=rollback_data.set_as_active
            if rollback_data.set_as_active is not None
            else False,
            is_draft=False,
            # Rollbacks are published by default
            published_at=now_sao_paulo(),
            created_by=user_uuid,
        )

        db.add(rollback_version)

        # If set_as_active, deactivate other versions
        if rollback_data.set_as_active:
            await db.execute(
                sql_update(FlowTemplateVersion)
                .where(
                    FlowTemplateVersion.flow_kind_id == source_version.flow_kind_id,
                    FlowTemplateVersion.id != rollback_version.id,
                )
                .values(is_active=False)
            )

        await db.commit()
        await db.refresh(rollback_version)

        # Invalidate cache
        await _invalidate_template_cache("flow")

        # Audit log
        AuditLogger.log(
            action=AuditAction.ROLLBACK,
            resource_type="flow_template",
            resource_id=str(rollback_version.id),
            user_id=str(user_uuid),
            user_role=role,
            details={
                "source_version_id": str(template_id),
                "source_version_number": source_version.version_number,
                "new_version_number": new_version_number,
                "reason": rollback_data.reason,
                "set_as_active": rollback_data.set_as_active,
            },
            ip_address=request.client.host if request.client else None,
        )

        logger.info(
            f"Rolled back to template version: {template_id} -> {rollback_version.id} by user {user_uuid}"
        )

        # Reload with kind relationship
        reload_result = await db.execute(
            select(FlowTemplateVersion)
            .options(selectinload(FlowTemplateVersion.kind))
            .where(FlowTemplateVersion.id == rollback_version.id)
        )
        rollback_version = reload_result.scalar_one_or_none()

        return _serialize_flow_template(rollback_version)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rolling back template version: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback template version: {str(e)}",
        )


@router.post(
    "/flows/{template_id}/publish",
    response_model=FlowTemplateV2Response,
    summary="Publish template version",
    description="Publish a draft template version",
)
@limiter.limit(RATE_LIMIT_WRITE)
async def publish_template_version(
    request: Request,
    template_id: UUID,
    set_as_active: bool = Query(False, description="Set this version as active"),
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    """
    Publish a draft template version.

    Moves a template from draft to published state, optionally setting it as the active version.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        template_result = await db.execute(
            select(FlowTemplateVersion).where(FlowTemplateVersion.id == template_id)
        )
        template = template_result.scalar_one_or_none()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        if not template.is_draft:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template is already published",
            )

        # Publish template
        template.is_draft = False
        template.published_at = now_sao_paulo()

        if set_as_active:
            # Deactivate other versions
            await db.execute(
                sql_update(FlowTemplateVersion)
                .where(
                    FlowTemplateVersion.flow_kind_id == template.flow_kind_id,
                    FlowTemplateVersion.id != template.id,
                )
                .values(is_active=False)
            )
            template.is_active = True

        template.updated_at = now_sao_paulo()

        await db.commit()
        await db.refresh(template)

        # Invalidate cache
        await _invalidate_template_cache("flow", template_id)

        # Audit log
        AuditLogger.log(
            action=AuditAction.PUBLISH,
            resource_type="flow_template",
            resource_id=str(template_id),
            user_id=str(user_uuid),
            user_role=role,
            details={
                "template_name": template.template_name,
                "version_number": template.version_number,
                "set_as_active": set_as_active,
            },
            ip_address=request.client.host if request.client else None,
        )

        logger.info(f"Published template: {template_id} by user {user_uuid}")

        # Reload with kind relationship
        reload_result = await db.execute(
            select(FlowTemplateVersion)
            .options(selectinload(FlowTemplateVersion.kind))
            .where(FlowTemplateVersion.id == template_id)
        )
        template = reload_result.scalar_one_or_none()

        return _serialize_flow_template(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing template: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish template",
        )
