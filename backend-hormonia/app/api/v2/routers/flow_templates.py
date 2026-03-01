from typing import Optional, Dict
from datetime import datetime, timezone
from uuid import UUID
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import contains_eager, selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, desc, func, or_, select, update

from app.core.database.async_engine import get_async_db
from app.models.flow import FlowKind, FlowTemplateVersion, PatientFlowState
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
from app.monitoring.audit_logger import TemplateAuditLogger as AuditLogger, TemplateAuditAction as AuditAction
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)


def _normalize_steps_payload(steps):
    if isinstance(steps, dict):
        return steps
    if isinstance(steps, list):
        for item in steps:
            if not isinstance(item, dict):
                raise HTTPException(status_code=400, detail="Invalid steps payload")
        return steps
    raise HTTPException(status_code=400, detail="Invalid steps payload")


def _is_content_update(payload: FlowTemplateV2Update) -> bool:
    return any(
        field is not None
        for field in (
            payload.template_name,
            payload.description,
            payload.steps,
            payload.metadata,
        )
    )


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
    db: AsyncSession = Depends(get_async_db),
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

        stmt = select(FlowTemplateVersion)
        if include and "kind" in include:
            stmt = stmt.options(selectinload(FlowTemplateVersion.kind))
        else:
            stmt = stmt.join(FlowKind).options(contains_eager(FlowTemplateVersion.kind))

        if is_active is not None:
            stmt = stmt.where(FlowTemplateVersion.is_active == is_active)
        if is_draft is not None:
            stmt = stmt.where(FlowTemplateVersion.is_draft == is_draft)
        if kind_key:
            stmt = stmt.where(FlowKind.kind_key == kind_key)

        if cursor:
            try:
                cursor_data = json.loads(cursor)
                cursor_id = UUID(cursor_data["id"])
                cursor_created = datetime.fromisoformat(cursor_data["created_at"])
                stmt = stmt.where(
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

        stmt = stmt.order_by(
            desc(FlowTemplateVersion.created_at), desc(FlowTemplateVersion.id)
        )
        result = await db.execute(stmt.limit(limit + 1))
        templates = result.unique().scalars().all()

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
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        cache_key = _get_cache_key(
            "flow_detail", template_id=str(template_id), include=include
        )
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        stmt = select(FlowTemplateVersion).where(FlowTemplateVersion.id == template_id)
        if include and "kind" in include:
            stmt = stmt.options(selectinload(FlowTemplateVersion.kind))
        else:
            stmt = stmt.join(FlowKind).options(contains_eager(FlowTemplateVersion.kind))

        result = await db.execute(stmt)
        template = result.unique().scalar_one_or_none()
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
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        flow_kind = None
        if template.flow_kind_id:
            result = await db.execute(
                select(FlowKind).where(FlowKind.id == template.flow_kind_id)
            )
            flow_kind = result.scalar_one_or_none()
            if not flow_kind:
                raise HTTPException(status_code=404, detail="Flow kind not found")
        elif template.kind_key:
            result = await db.execute(
                select(FlowKind).where(FlowKind.kind_key == template.kind_key)
            )
            flow_kind = result.scalar_one_or_none()
            if not flow_kind:
                flow_kind = FlowKind(
                    kind_key=template.kind_key,
                    display_name=template.display_name or template.kind_key,
                    description=template.description,
                    is_active=True,
                )
                db.add(flow_kind)
                await db.flush()
        else:
            raise HTTPException(
                status_code=400, detail="flow_kind_id or kind_key required"
            )

        result = await db.execute(
            select(FlowTemplateVersion).where(
                FlowTemplateVersion.flow_kind_id == flow_kind.id,
                FlowTemplateVersion.version_number == template.version_number,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Version exists")

        normalized_steps = _normalize_steps_payload(template.steps)
        is_active = template.is_active if template.is_active is not None else False
        is_draft = template.is_draft if template.is_draft is not None else True
        if is_active and is_draft:
            is_draft = False
        published_at = None if is_draft else now_sao_paulo()

        template_version = FlowTemplateVersion(
            flow_kind_id=flow_kind.id,
            version_number=template.version_number,
            template_name=template.template_name or template.display_name,
            description=template.description,
            steps=normalized_steps,
            metadata_json=template.metadata or {},
            is_active=is_active,
            is_draft=is_draft,
            published_at=published_at,
            created_by=user_uuid,
        )
        db.add(template_version)
        await db.flush()
        if is_active:
            await db.execute(
                update(FlowTemplateVersion)
                .where(
                    FlowTemplateVersion.flow_kind_id == flow_kind.id,
                    FlowTemplateVersion.id != template_version.id,
                )
                .values(is_active=False)
            )
        await db.commit()
        await db.refresh(template_version)
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

        result = await db.execute(
            select(FlowTemplateVersion)
            .options(selectinload(FlowTemplateVersion.kind))
            .where(FlowTemplateVersion.id == template_version.id)
        )
        template_version = result.scalar_one_or_none()

        return _serialize_flow_template(template_version)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating flow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create flow template")


@router.put("/flows/{template_id}", response_model=FlowTemplateV2Response)
@limiter.limit(RATE_LIMIT_WRITE)
async def update_flow_template(
    request: Request,
    template_id: UUID,
    updates: FlowTemplateV2Update,
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        _check_write_permission(current_user)
        result = await db.execute(
            select(FlowTemplateVersion).where(FlowTemplateVersion.id == template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=404)

        role, user_uuid = _extract_user_context(current_user)
        normalized_steps = (
            _normalize_steps_payload(updates.steps) if updates.steps is not None else None
        )
        if not template.is_draft and _is_content_update(updates):
            if updates.description is None:
                raise HTTPException(
                    status_code=400,
                    detail="Changelog (description) is required for new versions",
                )

            result = await db.execute(
                select(FlowTemplateVersion)
                .where(FlowTemplateVersion.flow_kind_id == template.flow_kind_id)
                .order_by(desc(FlowTemplateVersion.version_number))
            )
            latest_version = result.scalar_one_or_none()
            new_version_number = (
                latest_version.version_number + 1 if latest_version else template.version_number + 1
            )

            new_template = FlowTemplateVersion(
                flow_kind_id=template.flow_kind_id,
                version_number=new_version_number,
                template_name=updates.template_name or template.template_name,
                description=updates.description,
                steps=normalized_steps if normalized_steps is not None else template.steps,
                metadata_json=updates.metadata if updates.metadata is not None else template.metadata_json,
                is_active=updates.is_active if updates.is_active is not None else False,
                is_draft=True if updates.is_draft is None else updates.is_draft,
                published_at=None,
                created_by=user_uuid,
            )
            db.add(new_template)
            await db.flush()
            if new_template.is_active:
                new_template.is_draft = False
                new_template.published_at = now_sao_paulo()
                await db.execute(
                    update(FlowTemplateVersion)
                    .where(
                        FlowTemplateVersion.flow_kind_id == template.flow_kind_id,
                        FlowTemplateVersion.id != new_template.id,
                    )
                    .values(is_active=False)
                )
            await db.commit()
            await db.refresh(new_template)
            await _invalidate_template_cache("flow")

            AuditLogger.log(
                action=AuditAction.CREATE,
                resource_type="flow_template_version",
                resource_id=str(new_template.id),
                user_id=str(user_uuid),
                user_role=role,
                details={
                    "source_template_id": str(template_id),
                    "new_version_number": new_version_number,
                    "is_draft": new_template.is_draft,
                },
                ip_address=request.client.host if request.client else None,
            )

            result = await db.execute(
                select(FlowTemplateVersion)
                .options(selectinload(FlowTemplateVersion.kind))
                .where(FlowTemplateVersion.id == new_template.id)
            )
            new_template = result.scalar_one_or_none()
            return _serialize_flow_template(new_template)

        if updates.template_name is not None:
            template.template_name = updates.template_name
        if updates.description is not None:
            template.description = updates.description
        if normalized_steps is not None:
            template.steps = normalized_steps
        if updates.metadata is not None:
            template.metadata_json = updates.metadata
        if updates.is_active is not None:
            template.is_active = updates.is_active
            if updates.is_active:
                await db.execute(
                    update(FlowTemplateVersion)
                    .where(
                        FlowTemplateVersion.flow_kind_id == template.flow_kind_id,
                        FlowTemplateVersion.id != template.id,
                    )
                    .values(is_active=False)
                )
        if updates.is_draft is not None:
            if template.is_draft and not updates.is_draft:
                template.published_at = now_sao_paulo()
            template.is_draft = updates.is_draft
            if not template.is_draft and template.published_at is None:
                template.published_at = now_sao_paulo()
        if template.is_active and template.is_draft:
            template.is_draft = False
            template.published_at = template.published_at or now_sao_paulo()

        template.updated_at = now_sao_paulo()
        await db.commit()
        await db.refresh(template)
        await _invalidate_template_cache("flow", template_id)

        # Audit log
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

        result = await db.execute(
            select(FlowTemplateVersion)
            .options(selectinload(FlowTemplateVersion.kind))
            .where(FlowTemplateVersion.id == template_id)
        )
        template = result.scalar_one_or_none()
        return _serialize_flow_template(template)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating flow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update flow template")


@router.delete("/flows/{template_id}", status_code=204)
@limiter.limit(RATE_LIMIT_WRITE)
async def delete_flow_template(
    request: Request,
    template_id: UUID,
    soft_delete: bool = Query(True),
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        _check_write_permission(current_user)
        result = await db.execute(
            select(FlowTemplateVersion).where(FlowTemplateVersion.id == template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=404)

        result = await db.execute(
            select(func.count())
            .select_from(PatientFlowState)
            .where(
                PatientFlowState.flow_template_version_id == template.id,
                PatientFlowState.completed_at.is_(None),
            )
        )
        active_count = result.scalar_one()
        if active_count > 0:
            raise HTTPException(
                status_code=400, detail="Template has active patients and cannot be deleted"
            )

        if soft_delete:
            template.is_active = False
            template.updated_at = now_sao_paulo()
            await db.commit()
        else:
            await db.delete(template)
            await db.commit()

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
        await db.rollback()
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
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)
        result = await db.execute(
            select(FlowTemplateVersion).where(FlowTemplateVersion.id == template_id)
        )
        source = result.scalar_one_or_none()
        if not source:
            raise HTTPException(status_code=404)

        result = await db.execute(
            select(FlowTemplateVersion).where(
                FlowTemplateVersion.flow_kind_id == source.flow_kind_id,
                FlowTemplateVersion.version_number == duplicate_data.new_version_number,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Version exists")

        new_template = FlowTemplateVersion(
            flow_kind_id=source.flow_kind_id,
            version_number=duplicate_data.new_version_number,
            template_name=duplicate_data.new_template_name
            or f"{source.template_name} (Copy)",
            description=duplicate_data.description or source.description,
            steps=source.steps,
            metadata_json=source.metadata_json.copy()
            if source.metadata_json
            else {},
            is_active=False,
            is_draft=True,
            published_at=None,
            created_by=user_uuid,
        )
        db.add(new_template)
        await db.commit()
        await db.refresh(new_template)
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

        result = await db.execute(
            select(FlowTemplateVersion)
            .options(selectinload(FlowTemplateVersion.kind))
            .where(FlowTemplateVersion.id == new_template.id)
        )
        new_template = result.scalar_one_or_none()
        return _serialize_flow_template(new_template)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error duplicating flow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to duplicate flow template")


@router.get("/flow-kinds", response_model=FlowKindV2List)
@limiter.limit(RATE_LIMIT_READ)
async def list_flow_kinds(
    request: Request,
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        cache_key = _get_cache_key("flow_kinds", is_active=is_active)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        stmt = select(FlowKind)
        if is_active is not None:
            stmt = stmt.where(FlowKind.is_active == is_active)
        result = await db.execute(stmt)
        flow_kinds = result.scalars().all()

        data = []
        for kind in flow_kinds:
            stats = {
                "total": (
                    await db.execute(
                        select(func.count())
                        .select_from(FlowTemplateVersion)
                        .where(FlowTemplateVersion.flow_kind_id == kind.id)
                    )
                ).scalar_one(),
                "published": (
                    await db.execute(
                        select(func.count())
                        .select_from(FlowTemplateVersion)
                        .where(
                            FlowTemplateVersion.flow_kind_id == kind.id,
                            FlowTemplateVersion.is_draft.is_(False),
                            FlowTemplateVersion.is_active.is_(True),
                        )
                    )
                ).scalar_one(),
                "draft": (
                    await db.execute(
                        select(func.count())
                        .select_from(FlowTemplateVersion)
                        .where(
                            FlowTemplateVersion.flow_kind_id == kind.id,
                            FlowTemplateVersion.is_draft.is_(True),
                        )
                    )
                ).scalar_one(),
                "active_version": (
                    await db.execute(
                        select(FlowTemplateVersion.id).where(
                            FlowTemplateVersion.flow_kind_id == kind.id,
                            FlowTemplateVersion.is_active.is_(True),
                        )
                    )
                ).scalar_one_or_none(),
            }
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
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user_from_session),
):
    try:
        _check_write_permission(current_user)
        result = await db.execute(
            select(FlowKind).where(FlowKind.kind_key == kind_data.kind_key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Kind exists")

        flow_kind = FlowKind(
            kind_key=kind_data.kind_key,
            display_name=kind_data.display_name,
            description=kind_data.description,
            is_active=kind_data.is_active if kind_data.is_active is not None else True,
        )
        db.add(flow_kind)
        await db.commit()
        await db.refresh(flow_kind)
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
        await db.rollback()
        logger.error(f"Error creating flow kind: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create flow kind")
