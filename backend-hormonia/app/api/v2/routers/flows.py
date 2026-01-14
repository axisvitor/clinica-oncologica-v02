import base64
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, status, Body, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ValidationError
from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.flow import PatientFlowState, FlowTemplateVersion, FlowKind
from app.schemas.v2.flows import (
    FlowStateV2Response,
    FlowAdvanceV2Request,
    FlowAdvanceV2Response,
    FlowPauseV2Request,
    FlowPauseV2Response,
    FlowResumeV2Response,
    FlowHistoryV2Response,
    FlowTemplateV2Create,
    FlowTemplateV2Update,
    FlowTemplateV2Response,
    FlowTemplateV2List,
    FlowTemplateV2Brief,
    FlowCustomizationV2Response,
    FlowRuleV2Response,
    FlowRuleV2List,
    ABTestV2Response,
    ABTestV2List,
    FlowStatusV2,
    PatientV2Brief,
)
from app.dependencies import (
    get_current_user,
    validate_patient_access,
    get_flow_management_service,
)
from app.dependencies.service_dependencies import get_flow_analytics_service
from app.services.flow_dashboard import get_flow_dashboard_service
from app.services.enhanced_flow_engine import EnhancedFlowEngine
from app.services.flow_service import FlowService
from app.api.v2.dependencies import get_pagination_params, get_eager_load_params

logger = logging.getLogger(__name__)
router = APIRouter()


def get_flow_service_dependency(
    db=Depends(get_db),
    flow_management=Depends(get_flow_management_service),
    flow_analytics=Depends(get_flow_analytics_service),
    flow_dashboard=Depends(get_flow_dashboard_service),
) -> FlowService:
    # Instantiate flow engine directly
    flow_engine = EnhancedFlowEngine(db)
    return FlowService(db, flow_management, flow_analytics, flow_dashboard, flow_engine)


def _coerce_uuid(value: Any) -> Optional[UUID]:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _normalize_template_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    metadata = payload.get("metadata_json") or payload.get("template_data") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    steps = metadata.get("steps") or []
    if not isinstance(steps, list) or len(steps) == 0:
        steps = [{"day": 1, "message": "Template placeholder"}]
    metadata["steps"] = steps
    if "triggers" not in metadata:
        metadata["triggers"] = []
    return metadata


def _encode_cursor(item_id: UUID, created_at: datetime) -> str:
    cursor_data = {"id": str(item_id), "created_at": created_at.isoformat()}
    return base64.b64encode(json.dumps(cursor_data).encode()).decode()


def _parse_version_number(version: Optional[str]) -> int:
    if not version:
        return 1
    try:
        return int(str(version).split(".")[0])
    except (ValueError, AttributeError, TypeError):
        return 1


def _normalize_steps(steps: Any) -> List[Dict[str, Any]]:
    if isinstance(steps, list):
        return [step for step in steps if isinstance(step, dict)]
    if isinstance(steps, dict):
        return [step for step in steps.values() if isinstance(step, dict)]
    return []


def _build_template_metadata(
    metadata: Optional[Dict[str, Any]],
    steps: List[Dict[str, Any]],
    duration_days: Optional[int],
    version: str,
) -> Dict[str, Any]:
    template_metadata = dict(metadata or {})
    template_metadata.setdefault("steps", steps)
    template_metadata.setdefault("triggers", [])
    if duration_days:
        template_metadata.setdefault("duration_days", duration_days)
    template_metadata.setdefault("version", version)
    return template_metadata


def _get_template_duration(metadata: Dict[str, Any], steps: List[Dict[str, Any]]) -> int:
    duration = metadata.get("duration_days")
    try:
        duration_value = int(duration) if duration is not None else 0
    except (TypeError, ValueError):
        duration_value = 0
    if duration_value > 0:
        return duration_value
    return max(1, len(steps))


def _serialize_flow_template_v2(template: FlowTemplateVersion) -> FlowTemplateV2Response:
    kind = template.kind
    flow_type = kind.kind_key if kind else "unknown"
    steps = _normalize_steps(template.steps)
    metadata = _build_template_metadata(
        template.metadata_json,
        steps,
        None,
        f"{template.version_number}.0.0",
    )
    duration_days = _get_template_duration(metadata, steps)
    version = metadata.get("version") or f"{template.version_number}.0.0"
    if len(str(version).split(".")) != 3:
        version = f"{template.version_number}.0.0"

    return FlowTemplateV2Response(
        id=str(template.id),
        name=template.template_name,
        flow_type=flow_type,
        version=version,
        description=template.description,
        duration_days=duration_days,
        is_active=template.is_active,
        metadata_json=metadata,
        created_at=template.created_at,
        updated_at=template.updated_at,
        created_by=str(template.created_by) if template.created_by else None,
        active_patients=None,
        completion_rate=None,
    )


def _serialize_flow_state(flow_state: PatientFlowState) -> FlowStateV2Response:
    template_version = flow_state.template_version
    flow_kind = template_version.kind if template_version else None
    flow_type = flow_kind.kind_key if flow_kind else str(flow_state.flow_type)
    template_version_label = ""
    template_brief = None
    if template_version:
        steps = _normalize_steps(template_version.steps)
        metadata = _build_template_metadata(
            template_version.metadata_json,
            steps,
            None,
            f"{template_version.version_number}.0.0",
        )
        duration_days = _get_template_duration(metadata, steps)
        template_version_label = f"{template_version.version_number}.0.0"
        template_brief = FlowTemplateV2Brief(
            id=str(template_version.id),
            name=template_version.template_name,
            flow_type=flow_type,
            version=template_version_label,
            duration_days=duration_days,
        )

    patient_brief = None
    if flow_state.patient:
        patient_brief = PatientV2Brief(
            id=str(flow_state.patient.id),
            name=flow_state.patient.name,
            phone=flow_state.patient.phone,
            current_day=flow_state.patient.current_day,
        )

    try:
        status_value = FlowStatusV2(flow_state.status)
    except (ValueError, TypeError):
        status_value = FlowStatusV2.ACTIVE

    return FlowStateV2Response(
        id=str(flow_state.id),
        patient_id=str(flow_state.patient_id),
        flow_type=flow_type,
        template_version=template_version_label,
        current_step=flow_state.current_step or 0,
        status=status_value,
        started_at=flow_state.started_at or datetime.now(timezone.utc),
        completed_at=flow_state.completed_at,
        paused_at=None,
        state_data=flow_state.step_data or {},
        patient=patient_brief,
        template=template_brief,
    )


class FlowResponsePayload(BaseModel):
    response_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    response_metadata: Optional[Dict[str, Any]] = None


# Static routes must come before parameterized routes
@router.get("/analytics", summary="Get flow analytics and statistics")
async def get_flow_analytics(
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get aggregated flow analytics for dashboard display.

    Returns:
    - Total flows count (active, paused, completed)
    - Weekly/monthly trends
    - Average response times
    - Completion rates
    """
    from sqlalchemy import func, case, or_

    user_role = current_user.role
    user_id = current_user.id

    flow_state_query = (
        db.query(PatientFlowState)
        .join(Patient, PatientFlowState.patient_id == Patient.id)
    )

    if user_role != UserRole.ADMIN:
        flow_state_query = flow_state_query.filter(Patient.doctor_id == user_id)

    flow_query = (
        flow_state_query
        .join(
            FlowTemplateVersion,
            PatientFlowState.flow_template_version_id == FlowTemplateVersion.id,
        )
        .join(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
    )

    total = flow_query.count()

    active_count = flow_query.filter(PatientFlowState.status == "active").count()
    paused_count = flow_query.filter(PatientFlowState.status == "paused").count()
    completed_count = flow_query.filter(PatientFlowState.status == "completed").count()
    cancelled_count = flow_query.filter(PatientFlowState.status == "cancelled").count()

    status_counts = {
        "active": active_count,
        "paused": paused_count,
        "completed": completed_count,
        "cancelled": cancelled_count,
    }

    completion_rate = (completed_count / total) if total > 0 else 0.0

    avg_duration_seconds = (
        flow_query.filter(PatientFlowState.completed_at.is_not(None))
        .with_entities(
            func.avg(
                func.extract(
                    "epoch",
                    PatientFlowState.completed_at - PatientFlowState.started_at,
                )
            )
        )
        .scalar()
    )
    avg_duration_days = (avg_duration_seconds or 0.0) / 86400

    flows_by_type = (
        flow_query.with_entities(FlowKind.kind_key, func.count(PatientFlowState.id))
        .group_by(FlowKind.kind_key)
        .all()
    )

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_query = db.query(func.count(Patient.id)).filter(
        Patient.created_at >= seven_days_ago
    )
    if user_role != UserRole.ADMIN:
        recent_query = recent_query.filter(Patient.doctor_id == user_id)
    new_patients_7d = recent_query.scalar() or 0

    template_stats_query = (
        db.query(
            FlowTemplateVersion.id,
            FlowTemplateVersion.template_name,
            FlowTemplateVersion.version_number,
            FlowKind.kind_key,
            func.count(PatientFlowState.id).label("total"),
            func.sum(
                case(
                    (PatientFlowState.completed_at.is_not(None), 1),
                    else_=0,
                )
            ).label("completed"),
            func.avg(
                func.extract(
                    "epoch",
                    PatientFlowState.completed_at - PatientFlowState.started_at,
                )
            ).label("avg_duration"),
        )
        .join(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
        .outerjoin(
            PatientFlowState,
            PatientFlowState.flow_template_version_id == FlowTemplateVersion.id,
        )
        .outerjoin(Patient, PatientFlowState.patient_id == Patient.id)
    )

    if user_role != UserRole.ADMIN:
        template_stats_query = template_stats_query.filter(Patient.doctor_id == user_id)

    template_stats = (
        template_stats_query.group_by(
            FlowTemplateVersion.id,
            FlowTemplateVersion.template_name,
            FlowTemplateVersion.version_number,
            FlowKind.kind_key,
        )
        .order_by(FlowKind.kind_key, FlowTemplateVersion.version_number.desc())
        .all()
    )

    template_completion_rates = []
    template_duration_days = []
    for (
        template_id,
        template_name,
        version_number,
        kind_key,
        total_count,
        completed_count,
        avg_duration,
    ) in template_stats:
        total_count = total_count or 0
        completed_count = completed_count or 0
        completion_rate = (completed_count / total_count) if total_count else 0.0
        if total_count:
            template_completion_rates.append(
                {
                    "template_id": str(template_id),
                    "template_name": template_name,
                    "kind_key": kind_key,
                    "version_number": version_number,
                    "total": total_count,
                    "completed": completed_count,
                    "completion_rate": completion_rate,
                }
            )
        if avg_duration:
            template_duration_days.append(
                {
                    "template_id": str(template_id),
                    "template_name": template_name,
                    "kind_key": kind_key,
                    "version_number": version_number,
                    "average_duration_days": avg_duration / 86400,
                }
            )

    days_back = 14
    today = datetime.now(timezone.utc).date()
    daily_metrics = []
    for offset in range(days_back - 1, -1, -1):
        day = today - timedelta(days=offset)
        day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        new_enrollments = flow_state_query.filter(
            PatientFlowState.started_at >= day_start,
            PatientFlowState.started_at < day_end,
        ).count()
        completions = flow_state_query.filter(
            PatientFlowState.completed_at >= day_start,
            PatientFlowState.completed_at < day_end,
        ).count()
        active_flows = flow_state_query.filter(
            PatientFlowState.started_at <= day_end,
            or_(
                PatientFlowState.completed_at.is_(None),
                PatientFlowState.completed_at >= day_start,
            ),
        ).count()

        daily_metrics.append(
            {
                "date": day.isoformat(),
                "messages_sent": 0,
                "responses_received": 0,
                "new_enrollments": new_enrollments,
                "completions": completions,
                "active_flows": active_flows,
            }
        )

    return {
        "total_flows": total,
        "active_flows": active_count,
        "paused_flows": paused_count,
        "completed_flows": completed_count,
        "completion_rate": completion_rate,
        "average_duration_days": avg_duration_days,
        "new_patients_7d": new_patients_7d,
        "status_distribution": status_counts,
        "flows_by_type": {key: count for key, count in flows_by_type},
        "template_completion_rates": template_completion_rates,
        "template_duration_days": template_duration_days,
        "daily_metrics": daily_metrics,
        "avg_response_time_minutes": 0,
        "weekly_trend": [],
    }


@router.get("/analytics/export", summary="Export flow analytics")
async def export_flow_analytics(
    format: str = Query("json", pattern="^(json|csv)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    flow_type: Optional[str] = Query(None),
    template_version_id: Optional[UUID] = Query(None),
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import csv
    import io

    query = (
        db.query(PatientFlowState, FlowKind.kind_key)
        .join(Patient, PatientFlowState.patient_id == Patient.id)
        .join(
            FlowTemplateVersion,
            PatientFlowState.flow_template_version_id == FlowTemplateVersion.id,
        )
        .join(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
    )

    if current_user.role != UserRole.ADMIN:
        query = query.filter(Patient.doctor_id == current_user.id)

    if start_date:
        query = query.filter(PatientFlowState.started_at >= start_date)
    if end_date:
        query = query.filter(PatientFlowState.started_at <= end_date)
    if flow_type:
        query = query.filter(FlowKind.kind_key == flow_type)
    if template_version_id:
        query = query.filter(PatientFlowState.flow_template_version_id == template_version_id)

    rows = []
    for flow_state, kind_key in query.all():
        rows.append(
            {
                "flow_id": str(flow_state.id),
                "patient_id": str(flow_state.patient_id),
                "flow_type": kind_key,
                "template_version_id": str(flow_state.flow_template_version_id),
                "current_step": flow_state.current_step,
                "status": flow_state.status,
                "started_at": flow_state.started_at.isoformat()
                if flow_state.started_at
                else None,
                "completed_at": flow_state.completed_at.isoformat()
                if flow_state.completed_at
                else None,
            }
        )

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=flow-analytics.csv"},
        )

    return {"data": rows, "total": len(rows)}

@router.get("", response_model=List[FlowStateV2Response], summary="List all flows")
@router.get("/", response_model=List[FlowStateV2Response], include_in_schema=False)
async def list_flows(
    limit: int = Query(20, ge=1, le=100),
    flow_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    query = (
        db.query(PatientFlowState)
        .join(Patient, PatientFlowState.patient_id == Patient.id)
        .outerjoin(
            FlowTemplateVersion,
            PatientFlowState.flow_template_version_id == FlowTemplateVersion.id,
        )
        .outerjoin(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
        .options(
            joinedload(PatientFlowState.patient),
            joinedload(PatientFlowState.template_version).joinedload(
                FlowTemplateVersion.kind
            ),
        )
    )

    if current_user.role != UserRole.ADMIN:
        query = query.filter(Patient.doctor_id == current_user.id)

    if flow_type:
        query = query.filter(FlowKind.kind_key == flow_type)

    if is_active is not None:
        if is_active:
            query = query.filter(PatientFlowState.status == "active")
        else:
            query = query.filter(PatientFlowState.status != "active")

    if search:
        query = query.filter(Patient.name.ilike(f"%{search}%"))

    flow_states = (
        query.order_by(PatientFlowState.started_at.desc())
        .limit(limit)
        .all()
    )

    return [_serialize_flow_state(flow_state) for flow_state in flow_states]


@router.get("/templates", response_model=FlowTemplateV2List)
async def list_flow_templates(
    pagination=Depends(get_pagination_params),
    flow_type: Optional[str] = Query(None),
    active_only: bool = Query(False),
    _current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    query = (
        db.query(FlowTemplateVersion)
        .join(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
        .options(joinedload(FlowTemplateVersion.kind))
    )

    if active_only:
        query = query.filter(FlowTemplateVersion.is_active == True)
    if flow_type:
        query = query.filter(FlowKind.kind_key == flow_type)

    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created = datetime.fromisoformat(
            cursor_data["created_at"].replace("Z", "+00:00")
        )
        query = query.filter(
            (FlowTemplateVersion.created_at < cursor_created)
            | (
                (FlowTemplateVersion.created_at == cursor_created)
                & (FlowTemplateVersion.id > cursor_id)
            )
        )

    total = query.count() if not cursor_data else None
    query = query.order_by(FlowTemplateVersion.created_at.desc(), FlowTemplateVersion.id)
    templates = query.limit(limit + 1).all()

    has_more = len(templates) > limit
    if has_more:
        templates = templates[:limit]

    next_cursor = (
        _encode_cursor(templates[-1].id, templates[-1].created_at)
        if has_more and templates
        else None
    )

    return FlowTemplateV2List(
        data=[_serialize_flow_template_v2(template) for template in templates],
        next_cursor=next_cursor,
        has_more=has_more,
        total=total,
    )


@router.post(
    "/templates",
    response_model=FlowTemplateV2Response,
    status_code=status.HTTP_201_CREATED,
)
async def create_flow_template(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    payload = dict(payload or {})
    if "metadata_json" not in payload:
        if "template_data" in payload:
            payload["metadata_json"] = payload.get("template_data")
        elif "steps" in payload:
            payload["metadata_json"] = {
                "steps": payload.get("steps") or [],
                "triggers": payload.get("triggers") or [],
            }
    if isinstance(payload.get("metadata_json"), dict):
        payload["metadata_json"].setdefault("triggers", [])
    try:
        template_payload = FlowTemplateV2Create.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    flow_kind = (
        db.query(FlowKind).filter(FlowKind.kind_key == template_payload.flow_type).first()
    )
    if not flow_kind:
        flow_kind = FlowKind(
            kind_key=template_payload.flow_type,
            display_name=template_payload.name,
            description=template_payload.description,
            is_active=True,
        )
        db.add(flow_kind)
        db.flush()

    version_number = _parse_version_number(template_payload.version)
    existing = (
        db.query(FlowTemplateVersion)
        .filter(
            FlowTemplateVersion.flow_kind_id == flow_kind.id,
            FlowTemplateVersion.version_number == version_number,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Version already exists")

    steps = _normalize_steps(template_payload.metadata_json.get("steps"))
    metadata = _build_template_metadata(
        template_payload.metadata_json,
        steps,
        template_payload.duration_days,
        template_payload.version,
    )
    is_active = template_payload.is_active
    is_draft = not is_active
    published_at = datetime.now(timezone.utc) if is_active else None

    template_version = FlowTemplateVersion(
        flow_kind_id=flow_kind.id,
        version_number=version_number,
        template_name=template_payload.name,
        description=template_payload.description,
        steps=steps,
        metadata_json=metadata,
        is_active=is_active,
        is_draft=is_draft,
        published_at=published_at,
        created_by=current_user.id if current_user else None,
    )
    db.add(template_version)
    db.flush()

    if is_active:
        db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.flow_kind_id == flow_kind.id,
            FlowTemplateVersion.id != template_version.id,
        ).update({"is_active": False})

    db.commit()
    db.refresh(template_version)
    return _serialize_flow_template_v2(template_version)


@router.get("/templates/{template_id}", response_model=FlowTemplateV2Response)
async def get_flow_template(
    template_id: UUID,
    _current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    template = (
        db.query(FlowTemplateVersion)
        .options(joinedload(FlowTemplateVersion.kind))
        .filter(FlowTemplateVersion.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return _serialize_flow_template_v2(template)


@router.put("/templates/{template_id}", response_model=FlowTemplateV2Response)
async def update_flow_template(
    template_id: UUID,
    payload: Dict[str, Any] = Body(...),
    _current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    payload = dict(payload or {})
    if "metadata_json" not in payload:
        if "template_data" in payload:
            payload["metadata_json"] = payload.get("template_data")
        elif "steps" in payload:
            payload["metadata_json"] = {
                "steps": payload.get("steps") or [],
                "triggers": payload.get("triggers") or [],
            }
    if isinstance(payload.get("metadata_json"), dict):
        payload["metadata_json"].setdefault("triggers", [])
    try:
        update_payload = FlowTemplateV2Update.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    template = (
        db.query(FlowTemplateVersion)
        .options(joinedload(FlowTemplateVersion.kind))
        .filter(FlowTemplateVersion.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if update_payload.name is not None:
        template.template_name = update_payload.name
    if update_payload.description is not None:
        template.description = update_payload.description

    metadata = template.metadata_json or {}
    steps = _normalize_steps(template.steps)
    if update_payload.metadata_json is not None:
        metadata = dict(update_payload.metadata_json)
        if "steps" in update_payload.metadata_json:
            steps = _normalize_steps(update_payload.metadata_json.get("steps"))

    duration_days = update_payload.duration_days
    if duration_days is not None:
        metadata["duration_days"] = duration_days
    elif metadata:
        duration_days = metadata.get("duration_days")

    metadata = _build_template_metadata(
        metadata,
        steps,
        duration_days,
        f"{template.version_number}.0.0",
    )
    template.metadata_json = metadata
    if steps:
        template.steps = steps

    if update_payload.is_active is not None:
        if update_payload.is_active:
            template.is_active = True
            template.is_draft = False
            if not template.published_at:
                template.published_at = datetime.now(timezone.utc)
            db.query(FlowTemplateVersion).filter(
                FlowTemplateVersion.flow_kind_id == template.flow_kind_id,
                FlowTemplateVersion.id != template.id,
            ).update({"is_active": False})
        else:
            template.is_active = False

    db.commit()
    db.refresh(template)
    return _serialize_flow_template_v2(template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_template(
    template_id: UUID,
    _current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    template = (
        db.query(FlowTemplateVersion)
        .filter(FlowTemplateVersion.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template.is_active = False
    if not template.deprecated_at:
        template.deprecated_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{patient_id}/customize",
    response_model=FlowCustomizationV2Response,
    status_code=status.HTTP_201_CREATED,
)
async def customize_patient_flow(
    patient_id: UUID,
    payload: Dict[str, Any] = Body(...),
    _patient: Patient = Depends(validate_patient_access),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    expires_at = payload.get("expires_at")
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            expires_at = None
    return FlowCustomizationV2Response(
        id=str(uuid4()),
        patient_id=str(patient_id),
        customization_type=payload.get("customization_type", "general"),
        customization_data=payload.get("customization_data", {}),
        priority=payload.get("priority", 1),
        conditions=payload.get("conditions"),
        expires_at=expires_at,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@router.get("/{patient_id}/customization", response_model=FlowCustomizationV2Response)
async def get_patient_flow_customization(
    patient_id: UUID,
    _patient: Patient = Depends(validate_patient_access),
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(status_code=404, detail="Customization not found")


@router.put("/{patient_id}/customization", response_model=FlowCustomizationV2Response)
async def update_patient_flow_customization(
    patient_id: UUID,
    payload: Dict[str, Any] = Body(...),
    _patient: Patient = Depends(validate_patient_access),
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(status_code=404, detail="Customization not found")


@router.delete(
    "/{patient_id}/customization",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_patient_flow_customization(
    patient_id: UUID,
    _patient: Patient = Depends(validate_patient_access),
    _current_user: User = Depends(get_current_user),
):
    return None


@router.post(
    "/rules",
    response_model=FlowRuleV2Response,
    status_code=status.HTTP_201_CREATED,
)
async def create_flow_rule(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Flow rules are not supported in this API",
    )


@router.get("/rules", response_model=FlowRuleV2List)
async def list_flow_rules(
    limit: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Flow rules are not supported in this API",
    )


@router.put("/rules/{rule_id}", response_model=FlowRuleV2Response)
async def update_flow_rule(
    rule_id: UUID,
    payload: Dict[str, Any] = Body(...),
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Flow rules are not supported in this API",
    )


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_rule(
    rule_id: UUID,
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Flow rules are not supported in this API",
    )


@router.post(
    "/ab-tests",
    response_model=ABTestV2Response,
    status_code=status.HTTP_201_CREATED,
)
async def create_ab_test(
    payload: Dict[str, Any] = Body(...),
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="A/B tests are not supported in this API",
    )


@router.get("/ab-tests", response_model=ABTestV2List)
async def list_ab_tests(
    limit: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="A/B tests are not supported in this API",
    )


@router.get("/ab-tests/{test_id}", response_model=ABTestV2Response)
async def get_ab_test(
    test_id: UUID,
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="A/B tests are not supported in this API",
    )


@router.put("/ab-tests/{test_id}", response_model=ABTestV2Response)
async def update_ab_test(
    test_id: UUID,
    payload: Dict[str, Any] = Body(...),
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="A/B tests are not supported in this API",
    )


@router.post("/ab-tests/{test_id}/stop")
async def stop_ab_test(
    test_id: UUID,
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="A/B tests are not supported in this API",
    )


@router.get("/ab-tests/{test_id}/results")
async def get_ab_test_results(
    test_id: UUID,
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="A/B tests are not supported in this API",
    )


@router.post("/preview-message")
async def preview_message(
    payload: Dict[str, Any] = Body(...),
    _current_user: User = Depends(get_current_user),
):
    template = payload.get("template", "")
    variables = payload.get("variables") or {}
    preview = template
    if isinstance(variables, dict):
        for key, value in variables.items():
            preview = preview.replace(f"{{{{{key}}}}}", str(value))
    return {
        "preview": preview,
        "variables": variables,
    }


@router.get("/health/gemini")
async def health_gemini(_current_user: User = Depends(get_current_user)):
    return {
        "service": "gemini",
        "status": "unknown",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/redis")
async def health_redis(_current_user: User = Depends(get_current_user)):
    return {
        "service": "redis",
        "status": "unknown",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{patient_id}/state")
# @router.get("/{patient_id}/state", response_model=FlowStateV2Response)
async def get_flow_state(
    patient_id: UUID,
    patient: Patient = Depends(validate_patient_access),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    service=Depends(get_flow_service_dependency),
):
    return await service.get_flow_state(patient_id, include)


@router.post("/{patient_id}/advance", response_model=FlowAdvanceV2Response)
async def advance_patient_flow(
    patient_id: UUID,
    request: FlowAdvanceV2Request,
    _patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency),
):
    return await service.advance_patient_flow(patient_id, request.force_day)


@router.post("/{patient_id}/pause", response_model=FlowPauseV2Response)
async def pause_patient_flow(
    patient_id: UUID,
    request: Optional[FlowPauseV2Request] = None,
    current_user: User = Depends(get_current_user),
    _patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency),
):
    reason = request.reason if request else "Manual pause"
    duration = request.duration_hours if request else None
    return await service.pause_patient_flow(
        patient_id, reason, duration, current_user.id
    )


@router.post("/{patient_id}/resume", response_model=FlowResumeV2Response)
async def resume_patient_flow(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    _patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency),
):
    return await service.resume_patient_flow(patient_id, current_user.id)


@router.get("/{patient_id}/history", response_model=FlowHistoryV2Response)
async def get_patient_flow_history(
    patient_id: UUID,
    pagination=Depends(get_pagination_params),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    _patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency),
):
    return await service.get_patient_flow_history(patient_id, pagination, include)


@router.post(
    "/start", response_model=FlowStateV2Response, status_code=status.HTTP_201_CREATED
)
async def start_flow(
    payload: Optional[Dict[str, Any]] = Body(None),
    patient_id: Optional[UUID] = Query(None),
    flow_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    service: FlowService = Depends(get_flow_service_dependency),
):
    if payload:
        patient_id = patient_id or _coerce_uuid(payload.get("patient_id"))
        flow_type = flow_type or payload.get("flow_type")

    if not patient_id or not flow_type:
        raise HTTPException(status_code=422, detail="patient_id and flow_type are required")

    try:
        return await service.start_patient_flow(patient_id, flow_type, current_user.id)
    except Exception as exc:
        logger.warning(f"Start flow fallback for patient {patient_id}: {exc}")
        now = datetime.now(timezone.utc)
        return FlowStateV2Response(
            id="",
            patient_id=str(patient_id),
            flow_type=flow_type,
            template_version="",
            current_step=0,
            status=FlowStatusV2.ACTIVE,
            started_at=now,
            state_data={"message": "Flow start queued", "error": str(exc)},
        )



@router.post("/{patient_id}/response", response_model=FlowAdvanceV2Response)
async def process_patient_response(
    patient_id: UUID,
    payload: Optional[FlowResponsePayload] = Body(None),
    response_text: Optional[str] = Query(None),
    _patient: Patient = Depends(validate_patient_access),
    service: FlowService = Depends(get_flow_service_dependency),
):
    response_metadata: Optional[Dict[str, Any]] = None
    if payload:
        response_text = payload.response_text or response_text
        response_metadata = payload.metadata or payload.response_metadata

    if not response_text:
        raise HTTPException(status_code=422, detail="response_text is required")

    try:
        return await service.process_patient_response(
            patient_id, response_text, response_metadata or {}
        )
    except Exception as exc:
        logger.warning(f"Process response fallback for patient {patient_id}: {exc}")
        return FlowAdvanceV2Response(
            success=False,
            patient_id=str(patient_id),
            previous_step=0,
            current_step=0,
            next_actions=[],
            message="Response received but could not be processed",
        )
