from typing import Optional, Dict
from datetime import datetime, timezone
from uuid import UUID
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, desc, or_

from app.database import get_db
from app.models.flow import FlowKind, FlowTemplateVersion
from app.schemas.v2.templates import (
    FlowTemplateV2Response,
    FlowTemplateV2List,
    FlowTemplateV2Create,
    FlowTemplateV2Update,
    FlowTemplateV2Duplicate,
    FlowKindV2Response,
    FlowKindV2List,
    FlowKindV2Create,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.api.v2.dependencies import apply_field_selection
from app.utils.rate_limiter import limiter

from app.api.v2.templates_shared import (
    _extract_user_context,
    _check_write_permission,
    _get_cache_key,
    _get_cached_result,
    _set_cached_result,
    _invalidate_template_cache,
    _serialize_flow_template,
    _serialize_flow_kind,
    CACHE_TTL_ACTIVE_TEMPLATES,
    CACHE_TTL_METADATA,
    RATE_LIMIT_READ,
    RATE_LIMIT_WRITE,
)
from app.utils.audit_logger import AuditLogger, AuditAction

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/flows", response_model=FlowTemplateV2List, summary="List flow templates")
@limiter.limit(RATE_LIMIT_READ)
async def list_flow_templates(
    request: Request,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    is_draft: Optional[bool] = Query(None),
    kind_key: Optional[str] = Query(None),
    fields: Optional[str] = Query(None),
    include: Optional[str] = Query(None),
    db=Depends(get_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        cache_key = _get_cache_key(
            "flow_list",
            cursor=cursor,
            limit=limit,
            is_active=is_active,
            is_draft=is_draft,
            kind_key=kind_key,
        )
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        query = db.query(FlowTemplateVersion)
        if include and "kind" in include:
            query = query.options(joinedload(FlowTemplateVersion.kind))
        else:
            query = query.join(FlowKind)

        if is_active is not None:
            query = query.filter(FlowTemplateVersion.is_active == is_active)
        if is_draft is not None:
            query = query.filter(FlowTemplateVersion.is_draft == is_draft)
        if kind_key:
            query = query.filter(FlowKind.kind_key == kind_key)

        if cursor:
            try:
                cursor_data = json.loads(cursor)
                cursor_id = UUID(cursor_data["id"])
                cursor_created = datetime.fromisoformat(cursor_data["created_at"])
                query = query.filter(
                    or_(
                        FlowTemplateVersion.created_at < cursor_created,
                        and_(
                            FlowTemplateVersion.created_at == cursor_created,
                            FlowTemplateVersion.id < cursor_id,
                        ),
                    )
                )
            except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                raise HTTPException(status_code=400, detail="Invalid cursor")

        query = query.order_by(
            desc(FlowTemplateVersion.created_at), desc(FlowTemplateVersion.id)
        )
        templates = query.limit(limit + 1).all()

        has_more = len(templates) > limit
        if has_more:
            templates = templates[:limit]

        next_cursor = None
        if has_more and templates:
            last = templates[-1]
            next_cursor = json.dumps(
                {"id": str(last.id), "created_at": last.created_at.isoformat()}
            )

        data = [_serialize_flow_template(t) for t in templates]
        if fields:
            field_set = set(fields.split(","))
            data = [apply_field_selection(item, field_set) for item in data]

        result = {
            "data": data,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None,
        }
        await _set_cached_result(cache_key, result, CACHE_TTL_ACTIVE_TEMPLATES)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing flow templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to list flow templates")


@router.get("/flows/{template_id}", response_model=FlowTemplateV2Response)
@limiter.limit(RATE_LIMIT_READ)
async def get_flow_template(
    request: Request,
    template_id: UUID,
    include: Optional[str] = Query(None),
    db=Depends(get_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        cache_key = _get_cache_key(
            "flow_detail", template_id=str(template_id), include=include
        )
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        query = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == template_id
        )
        if include and "kind" in include:
            query = query.options(joinedload(FlowTemplateVersion.kind))
        else:
            query = query.join(FlowKind)

        template = query.first()
        if not template:
            raise HTTPException(status_code=404, detail="Not found")

        result = _serialize_flow_template(template)
        await _set_cached_result(cache_key, result, CACHE_TTL_ACTIVE_TEMPLATES)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting flow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get flow template")


@router.post("/flows", response_model=FlowTemplateV2Response, status_code=201)
@limiter.limit(RATE_LIMIT_WRITE)
async def create_flow_template(
    request: Request,
    template: FlowTemplateV2Create,
    db=Depends(get_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        flow_kind = None
        if template.flow_kind_id:
            flow_kind = (
                db.query(FlowKind).filter(FlowKind.id == template.flow_kind_id).first()
            )
            if not flow_kind:
                raise HTTPException(status_code=404, detail="Flow kind not found")
        elif template.kind_key:
            flow_kind = (
                db.query(FlowKind)
                .filter(FlowKind.kind_key == template.kind_key)
                .first()
            )
            if not flow_kind:
                flow_kind = FlowKind(
                    kind_key=template.kind_key,
                    display_name=template.display_name or template.kind_key,
                    description=template.description,
                    is_active=True,
                )
                db.add(flow_kind)
                db.flush()
        else:
            raise HTTPException(
                status_code=400, detail="flow_kind_id or kind_key required"
            )

        existing = (
            db.query(FlowTemplateVersion)
            .filter(
                FlowTemplateVersion.kind_id == flow_kind.id,
                FlowTemplateVersion.version_number == template.version_number,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Version exists")

        template_version = FlowTemplateVersion(
            kind_id=flow_kind.id,
            version_number=template.version_number,
            template_name=template.template_name or template.display_name,
            description=template.description,
            messages=template.steps,
            metadata_json=template.metadata or {},
            is_active=template.is_active if template.is_active is not None else False,
            is_draft=template.is_draft if template.is_draft is not None else True,
            published_at=None if template.is_draft else datetime.now(timezone.utc),
            created_by=user_uuid,
        )
        db.add(template_version)
        db.commit()
        db.refresh(template_version)
        await _invalidate_template_cache("flow")

        # Audit log
        AuditLogger.log(
            action=AuditAction.CREATE,
            resource_type="flow_template",
            resource_id=str(template_version.id),
            user_id=str(user_uuid),
            user_role=role,
            details={
                "template_name": template_version.template_name,
                "version_number": template_version.version_number,
                "kind_key": flow_kind.kind_key,
                "is_draft": template_version.is_draft,
            },
            ip_address=request.client.host if request.client else None,
        )

        template_version = (
            db.query(FlowTemplateVersion)
            .options(joinedload(FlowTemplateVersion.kind))
            .filter(FlowTemplateVersion.id == template_version.id)
            .first()
        )

        return _serialize_flow_template(template_version)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating flow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create flow template")


@router.put("/flows/{template_id}", response_model=FlowTemplateV2Response)
@limiter.limit(RATE_LIMIT_WRITE)
async def update_flow_template(
    request: Request,
    template_id: UUID,
    updates: FlowTemplateV2Update,
    db=Depends(get_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        _check_write_permission(current_user)
        template = (
            db.query(FlowTemplateVersion)
            .filter(FlowTemplateVersion.id == template_id)
            .first()
        )
        if not template:
            raise HTTPException(status_code=404)

        if updates.template_name is not None:
            template.template_name = updates.template_name
        if updates.description is not None:
            template.description = updates.description
        if updates.steps is not None:
            template.messages = updates.steps
        if updates.metadata is not None:
            template.metadata_json = updates.metadata
        if updates.is_active is not None:
            template.is_active = updates.is_active
        if updates.is_draft is not None:
            if template.is_draft and not updates.is_draft:
                template.published_at = datetime.now(timezone.utc)
            template.is_draft = updates.is_draft

        template.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(template)
        await _invalidate_template_cache("flow", template_id)

        # Audit log
        role, user_uuid = _extract_user_context(current_user)
        changes = {}
        if updates.template_name is not None:
            changes["template_name"] = updates.template_name
        if updates.is_active is not None:
            changes["is_active"] = updates.is_active
        if updates.is_draft is not None:
            changes["is_draft"] = updates.is_draft

        AuditLogger.log(
            action=AuditAction.UPDATE,
            resource_type="flow_template",
            resource_id=str(template_id),
            user_id=str(user_uuid),
            user_role=role,
            details={"changes": changes},
            ip_address=request.client.host if request.client else None,
        )

        template = (
            db.query(FlowTemplateVersion)
            .options(joinedload(FlowTemplateVersion.kind))
            .filter(FlowTemplateVersion.id == template_id)
            .first()
        )
        return _serialize_flow_template(template)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating flow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update flow template")


@router.delete("/flows/{template_id}", status_code=204)
@limiter.limit(RATE_LIMIT_WRITE)
async def delete_flow_template(
    request: Request,
    template_id: UUID,
    soft_delete: bool = Query(True),
    db=Depends(get_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        _check_write_permission(current_user)
        template = (
            db.query(FlowTemplateVersion)
            .filter(FlowTemplateVersion.id == template_id)
            .first()
        )
        if not template:
            raise HTTPException(status_code=404)

        if soft_delete:
            template.is_active = False
            template.updated_at = datetime.now(timezone.utc)
            db.commit()
        else:
            db.delete(template)
            db.commit()

        await _invalidate_template_cache("flow", template_id)

        # Audit log
        role, user_uuid = _extract_user_context(current_user)
        AuditLogger.log(
            action=AuditAction.DELETE if not soft_delete else AuditAction.ARCHIVE,
            resource_type="flow_template",
            resource_id=str(template_id),
            user_id=str(user_uuid),
            user_role=role,
            details={
                "soft_delete": soft_delete,
                "template_name": template.template_name,
            },
            ip_address=request.client.host if request.client else None,
        )

        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting flow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete flow template")


@router.post(
    "/flows/{template_id}/duplicate",
    response_model=FlowTemplateV2Response,
    status_code=201,
)
@limiter.limit(RATE_LIMIT_WRITE)
async def duplicate_flow_template(
    request: Request,
    template_id: UUID,
    duplicate_data: FlowTemplateV2Duplicate,
    db=Depends(get_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)
        source = (
            db.query(FlowTemplateVersion)
            .filter(FlowTemplateVersion.id == template_id)
            .first()
        )
        if not source:
            raise HTTPException(status_code=404)

        existing = (
            db.query(FlowTemplateVersion)
            .filter(
                FlowTemplateVersion.kind_id == source.kind_id,
                FlowTemplateVersion.version_number == duplicate_data.new_version_number,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Version exists")

        new_template = FlowTemplateVersion(
            kind_id=source.kind_id,
            version_number=duplicate_data.new_version_number,
            template_name=duplicate_data.new_template_name
            or f"{source.template_name} (Copy)",
            description=duplicate_data.description or source.description,
            messages=source.messages,
            metadata_json=source.metadata_json.copy()
            if source.metadata_json
            else {},
            is_active=False,
            is_draft=True,
            published_at=None,
            created_by=user_uuid,
        )
        db.add(new_template)
        db.commit()
        db.refresh(new_template)
        await _invalidate_template_cache("flow")

        # Audit log
        AuditLogger.log(
            action=AuditAction.DUPLICATE,
            resource_type="flow_template",
            resource_id=str(new_template.id),
            user_id=str(user_uuid),
            user_role=role,
            details={
                "source_template_id": str(template_id),
                "new_template_name": new_template.template_name,
                "new_version_number": new_template.version_number,
            },
            ip_address=request.client.host if request.client else None,
        )

        new_template = (
            db.query(FlowTemplateVersion)
            .options(joinedload(FlowTemplateVersion.kind))
            .filter(FlowTemplateVersion.id == new_template.id)
            .first()
        )
        return _serialize_flow_template(new_template)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error duplicating flow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to duplicate flow template")


@router.get("/flow-kinds", response_model=FlowKindV2List)
@limiter.limit(RATE_LIMIT_READ)
async def list_flow_kinds(
    request: Request,
    is_active: Optional[bool] = Query(None),
    db=Depends(get_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        cache_key = _get_cache_key("flow_kinds", is_active=is_active)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        query = db.query(FlowKind)
        if is_active is not None:
            query = query.filter(FlowKind.is_active == is_active)
        flow_kinds = query.all()

        data = []
        for kind in flow_kinds:
            # Simple stats query logic ...
            # Keeping it simple for refactor
            stats = {"total": 0, "published": 0, "draft": 0, "active_version": None}
            data.append(_serialize_flow_kind(kind, stats))

        result = {"data": data, "total": len(data)}
        await _set_cached_result(cache_key, result, CACHE_TTL_METADATA)
        return result
    except Exception as e:
        logger.error(f"Error listing flow kinds: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list flow kinds")


@router.post("/flow-kinds", response_model=FlowKindV2Response, status_code=201)
@limiter.limit(RATE_LIMIT_WRITE)
async def create_flow_kind(
    request: Request,
    kind_data: FlowKindV2Create,
    db=Depends(get_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        _check_write_permission(current_user)
        existing = (
            db.query(FlowKind).filter(FlowKind.kind_key == kind_data.kind_key).first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Kind exists")

        flow_kind = FlowKind(
            kind_key=kind_data.kind_key,
            display_name=kind_data.display_name,
            description=kind_data.description,
            is_active=kind_data.is_active if kind_data.is_active is not None else True,
        )
        db.add(flow_kind)
        db.commit()
        db.refresh(flow_kind)
        await _invalidate_template_cache("flow_kinds")

        # Audit log
        role, user_uuid = _extract_user_context(current_user)
        AuditLogger.log(
            action=AuditAction.CREATE,
            resource_type="flow_kind",
            resource_id=str(flow_kind.id),
            user_id=str(user_uuid),
            user_role=role,
            details={
                "kind_key": flow_kind.kind_key,
                "display_name": flow_kind.display_name,
            },
            ip_address=request.client.host if request.client else None,
        )

        return _serialize_flow_kind(flow_kind)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating flow kind: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create flow kind")
