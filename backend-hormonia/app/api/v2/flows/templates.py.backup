"""
Flow Templates & Customization
Handles template CRUD operations and patient-specific flow customizations
"""

import logging
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import get_db
from app.models.user import User
from app.schemas.v2.flows import (
    FlowTemplateV2Response,
    FlowTemplateV2Create,
    FlowTemplateV2Update,
    FlowTemplateV2List,
    FlowCustomizationV2Request,
    FlowCustomizationV2Response,
)
from ..dependencies import (
    get_pagination_params,
    get_eager_load_params,
)
from app.dependencies import (
    get_current_user,
    validate_patient_access,
    get_flow_management_service,
    get_patient_service,
)
from app.services.flow_management import FlowManagementService
from app.services.patient import PatientService
from app.exceptions import (
    FlowStateNotFoundError,
    flow_not_found_exception,
    flow_operation_exception,
    internal_server_exception,
)
from app.utils.rate_limiter import limiter
import base64
import json

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def _create_cursor(item_id: str, created_at: datetime) -> str:
    """Create cursor for pagination"""
    cursor_data = {
        "id": str(item_id),
        "created_at": created_at.isoformat()
    }
    return base64.b64encode(json.dumps(cursor_data).encode()).decode()


# ============================================================================
# Template Management (5 endpoints)
# ============================================================================

@router.get(
    "/templates",
    response_model=FlowTemplateV2List,
    summary="List flow templates",
    description="Get paginated list of flow templates with cursor pagination"
)
async def get_flow_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pagination = Depends(get_pagination_params),
    flow_type: Optional[str] = Query(None),
    active_only: bool = Query(True),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """
    List flow templates with cursor pagination.

    Supports:
    - Cursor pagination
    - Filter by flow_type
    - Filter by active status
    """
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Build query
    from app.models.flow import FlowTemplate
    query = db.query(FlowTemplate)

    # Apply filters
    filters = []
    if active_only:
        filters.append(FlowTemplate.is_active == True)
    if flow_type:
        filters.append(FlowTemplate.flow_type == flow_type)

    # Apply cursor
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        filters.append(
            (FlowTemplate.created_at < cursor_created) |
            ((FlowTemplate.created_at == cursor_created) & (FlowTemplate.id > cursor_id))
        )

    if filters:
        query = query.filter(and_(*filters))

    # Get total (only on first page)
    total = None
    if not cursor_data:
        total = query.count()

    # Order and limit
    query = query.order_by(FlowTemplate.created_at.desc(), FlowTemplate.id)
    templates = query.limit(limit + 1).all()

    # Check for more results
    has_more = len(templates) > limit
    if has_more:
        templates = templates[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and templates:
        next_cursor = _create_cursor(templates[-1].id, templates[-1].created_at)

    return FlowTemplateV2List(
        data=[FlowTemplateV2Response.from_orm(t) for t in templates],
        next_cursor=next_cursor,
        has_more=has_more,
        total=total
    )


@router.post(
    "/templates",
    response_model=FlowTemplateV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create flow template",
    description="Create a new flow template"
)
@limiter.limit("10/hour")
async def create_flow_template(
    template_data: FlowTemplateV2Create,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Create new flow template"""
    try:
        template = await flow_management.create_flow_template(
            template_data=template_data,
            created_by=current_user.id
        )
        return FlowTemplateV2Response.from_orm(template)
    except Exception as e:
        logger.error(f"Failed to create flow template: {e}")
        raise flow_operation_exception("create_template", str(e))


@router.get(
    "/templates/{template_id}",
    response_model=FlowTemplateV2Response,
    summary="Get flow template",
    description="Get specific flow template by ID"
)
async def get_flow_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Get specific flow template"""
    try:
        template = await flow_management.get_flow_template(template_id)
        return FlowTemplateV2Response.from_orm(template)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"template_{template_id}")
    except Exception as e:
        logger.error(f"Failed to get flow template {template_id}: {e}")
        raise internal_server_exception("Failed to get flow template")


@router.put(
    "/templates/{template_id}",
    response_model=FlowTemplateV2Response,
    summary="Update flow template",
    description="Update existing flow template"
)
@limiter.limit("20/hour")
async def update_flow_template(
    template_id: UUID,
    template_data: FlowTemplateV2Update,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Update flow template"""
    try:
        template = await flow_management.update_flow_template(
            template_id=template_id,
            template_data=template_data,
            updated_by=current_user.id
        )
        return FlowTemplateV2Response.from_orm(template)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"template_{template_id}")
    except Exception as e:
        logger.error(f"Failed to update flow template {template_id}: {e}")
        raise flow_operation_exception("update_template", str(e))


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete flow template",
    description="Soft delete a flow template"
)
@limiter.limit("10/hour")
async def delete_flow_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Soft delete flow template"""
    try:
        await flow_management.delete_flow_template(
            template_id=template_id,
            deleted_by=current_user.id
        )
        return None
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"template_{template_id}")
    except Exception as e:
        logger.error(f"Failed to delete flow template {template_id}: {e}")
        raise internal_server_exception("Failed to delete flow template")


# ============================================================================
# Customization (4 endpoints)
# ============================================================================

@router.post(
    "/{patient_id}/customize",
    response_model=FlowCustomizationV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Customize patient flow",
    description="Create patient-specific flow customization"
)
async def customize_patient_flow(
    patient_id: UUID,
    customization_data: FlowCustomizationV2Request,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Create patient-specific flow customization"""
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)

    try:
        customization = await flow_management.customize_patient_flow(
            patient_id=patient_id,
            customization_data=customization_data,
            customized_by=current_user.id
        )
        return FlowCustomizationV2Response.from_orm(customization)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to customize flow for patient {patient_id}: {e}")
        raise flow_operation_exception("customize_flow", str(e))


@router.get(
    "/{patient_id}/customization",
    response_model=FlowCustomizationV2Response,
    summary="Get flow customization",
    description="Get patient's flow customization settings"
)
async def get_patient_flow_customization(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Get patient flow customization"""
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)

    try:
        customization = await flow_management.get_patient_flow_customization(patient_id)
        return FlowCustomizationV2Response.from_orm(customization)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to get flow customization for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to get flow customization")


@router.put(
    "/{patient_id}/customization",
    response_model=FlowCustomizationV2Response,
    summary="Update flow customization",
    description="Update patient's flow customization"
)
async def update_patient_flow_customization(
    patient_id: UUID,
    customization_data: FlowCustomizationV2Request,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Update patient flow customization"""
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)

    try:
        customization = await flow_management.update_patient_flow_customization(
            patient_id=patient_id,
            customization_data=customization_data,
            updated_by=current_user.id
        )
        return FlowCustomizationV2Response.from_orm(customization)
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to update flow customization for patient {patient_id}: {e}")
        raise flow_operation_exception("update_customization", str(e))


@router.delete(
    "/{patient_id}/customization",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove flow customization",
    description="Remove patient's flow customization"
)
async def remove_patient_flow_customization(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service),
):
    """Remove patient flow customization"""
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)

    try:
        await flow_management.remove_patient_flow_customization(
            patient_id=patient_id,
            removed_by=current_user.id
        )
        return None
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to remove flow customization for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to remove flow customization")
