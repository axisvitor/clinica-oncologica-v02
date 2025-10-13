"""
Alert management endpoints for Hormonia Backend System.
"""
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.alert import AlertSeverity, AlertStatus
from app.schemas.alert import (
    AlertResponse, AlertListResponse, AlertAcknowledge, AlertStatistics,
    PatientAlertSummary, AlertRuleConfig
)
from app.schemas.common import PaginationParams
from app.services.alert import AlertService
from app.services.alert_processor import AlertProcessor
from app.utils.api_decorators import handle_service_exceptions, validate_pagination
from app.core.error_handler import error_handler
from app.core.monitoring_logging import monitoring_logger


def _convert_pagination(pagination: PaginationParams) -> dict:
    """Convert PaginationParams to page/size format for compatibility."""
    skip = max(pagination.skip, 0)
    limit = pagination.limit if pagination.limit > 0 else 1
    page = (skip // limit) + 1
    return {
        "page": page,
        "size": limit,
        "skip": skip,
        "limit": limit
    }

router = APIRouter()


@router.get("", response_model=AlertListResponse)
@handle_service_exceptions
@validate_pagination()
async def list_alerts(
    pagination: PaginationParams = Depends(),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    status: Optional[AlertStatus] = Query(None, description="Filter by status"),
    patient_id: Optional[UUID] = Query(None, description="Filter by patient ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AlertListResponse:
    """List system alerts with filtering and pagination."""
    try:
        with monitoring_logger.context(
            operation="list_alerts",
            user_id=str(current_user.id),
            filters={"severity": severity, "status": status, "patient_id": str(patient_id) if patient_id else None}
        ):
            alert_system = AlertService(db)
            
            if patient_id:
                alerts = alert_system.alert_repo.get_by_patient(patient_id, _convert_pagination(pagination)["skip"], _convert_pagination(pagination)["limit"])
                total = len(alert_system.alert_repo.get_by_patient(patient_id, 0, 10000))  # Get total count
            elif severity:
                alerts = alert_system.alert_repo.get_by_severity(severity, _convert_pagination(pagination)["skip"], _convert_pagination(pagination)["limit"])
                total = alert_system.alert_repo.count_by_severity(severity)
            elif status == AlertStatus.PENDING:
                alerts = alert_system.alert_repo.get_unacknowledged(_convert_pagination(pagination)["skip"], _convert_pagination(pagination)["limit"])
                total = alert_system.alert_repo.count_unacknowledged()
            else:
                alerts = alert_system.alert_repo.get_active_alerts(_convert_pagination(pagination)["skip"], _convert_pagination(pagination)["limit"])
                total = len(alert_system.alert_repo.get_active_alerts(0, 10000))  # Get total count
            
            return AlertListResponse(
                items=[AlertResponse.from_orm(alert) for alert in alerts],
                total=total,
                page=pagination.page,
                size=_convert_pagination(pagination)["limit"],
                pages=(total + _convert_pagination(pagination)["limit"] - 1) // _convert_pagination(pagination)["limit"]
            )
    except Exception as e:
        # Check if it's a schema compatibility error
        if "column" in str(e).lower() or "table" in str(e).lower():
            await error_handler.handle_schema_mismatch_error(
                e,
                table_name="alerts",
                operation="list_alerts",
                context={
                    "filters": {"severity": severity, "status": status, "patient_id": str(patient_id) if patient_id else None},
                    "pagination": {"skip": _convert_pagination(pagination)["skip"], "limit": _convert_pagination(pagination)["limit"]}
                }
            )
        else:
            await error_handler.handle_generic_error(
                e,
                error_type="ALERTS_LIST_ERROR",
                context={
                    "operation": "list_alerts",
                    "user_id": str(current_user.id),
                    "filters": {"severity": severity, "status": status, "patient_id": str(patient_id) if patient_id else None}
                },
                user_message="Failed to retrieve alerts. Please try again."
            )


@router.get("/patient/{patient_id}", response_model=AlertListResponse)
@handle_service_exceptions
@validate_pagination()
async def get_patient_alerts(
    patient_id: UUID,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AlertListResponse:
    """Get alerts for specific patient."""
    try:
        with monitoring_logger.context(
            operation="get_patient_alerts",
            user_id=str(current_user.id),
            patient_id=str(patient_id)
        ):
            alert_system = AlertService(db)
            
            alerts = alert_system.alert_repo.get_by_patient(patient_id, _convert_pagination(pagination)["skip"], _convert_pagination(pagination)["limit"])
            total = len(alert_system.alert_repo.get_by_patient(patient_id, 0, 10000))
            
            return AlertListResponse(
                items=[AlertResponse.from_orm(alert) for alert in alerts],
                total=total,
                page=pagination.page,
                size=_convert_pagination(pagination)["limit"],
                pages=(total + _convert_pagination(pagination)["limit"] - 1) // _convert_pagination(pagination)["limit"]
            )
    except Exception as e:
        # Check if it's a schema compatibility error
        if "column" in str(e).lower() or "table" in str(e).lower():
            await error_handler.handle_schema_mismatch_error(
                e,
                table_name="alerts",
                operation="get_patient_alerts",
                context={
                    "patient_id": str(patient_id),
                    "pagination": {"skip": _convert_pagination(pagination)["skip"], "limit": _convert_pagination(pagination)["limit"]}
                }
            )
        else:
            await error_handler.handle_generic_error(
                e,
                error_type="PATIENT_ALERTS_ERROR",
                context={
                    "operation": "get_patient_alerts",
                    "user_id": str(current_user.id),
                    "patient_id": str(patient_id)
                },
                user_message="Failed to retrieve patient alerts. Please try again."
            )


@router.get("/patient/{patient_id}/summary", response_model=PatientAlertSummary)
@handle_service_exceptions
async def get_patient_alert_summary(
    patient_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PatientAlertSummary:
    """Get alert summary for a specific patient."""
    alert_system = AlertService(db)
    
    all_alerts = alert_system.alert_repo.get_by_patient(patient_id, 0, 1000)
    pending_alerts = [alert for alert in all_alerts if alert.status == AlertStatus.PENDING]
    critical_alerts = [alert for alert in all_alerts if alert.severity == AlertSeverity.CRITICAL]
    
    last_alert = all_alerts[0] if all_alerts else None
    
    return PatientAlertSummary(
        patient_id=patient_id,
        total_alerts=len(all_alerts),
        pending_alerts=len(pending_alerts),
        critical_alerts=len(critical_alerts),
        last_alert_at=last_alert.created_at if last_alert else None
    )


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
@handle_service_exceptions
async def acknowledge_alert(
    alert_id: UUID,
    request: AlertAcknowledge,
    notes: Optional[str] = Query(None, description="Acknowledgment notes"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AlertResponse:
    """Acknowledge alert."""
    alert_processor = AlertProcessor(db)
    
    alert = await alert_processor.acknowledge_alert(alert_id, request.user_id, notes)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    return AlertResponse.from_orm(alert)


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
@handle_service_exceptions
async def resolve_alert(
    alert_id: UUID,
    resolution_notes: Optional[str] = Query(None, description="Resolution notes"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AlertResponse:
    """Resolve alert."""
    alert_processor = AlertProcessor(db)
    
    alert = await alert_processor.resolve_alert(alert_id, current_user.id, resolution_notes)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    return AlertResponse.from_orm(alert)


@router.get("/{alert_id}", response_model=AlertResponse)
@handle_service_exceptions
async def get_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AlertResponse:
    """Get specific alert by ID."""
    alert_system = AlertService(db)
    
    alert = alert_system.alert_repo.get(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    return AlertResponse.from_orm(alert)


@router.get("/dashboard/data", response_model=None)
@handle_service_exceptions
async def get_alert_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get alert dashboard metrics and data."""
    alert_processor = AlertProcessor(db)
    
    dashboard_data = alert_processor.get_alert_dashboard_data()
    return dashboard_data


@router.get("/statistics", response_model=AlertStatistics)
@handle_service_exceptions
async def get_alert_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AlertStatistics:
    """Get alert system statistics."""
    alert_system = AlertService(db)
    
    stats = alert_system.get_alert_statistics()
    return AlertStatistics(**stats)


@router.post("/{alert_id}/escalate", response_model=None)
@handle_service_exceptions
async def escalate_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Manually escalate an alert."""
    alert_processor = AlertProcessor(db)
    
    result = alert_processor.process_escalation(alert_id)
    return result


@router.put("/rules/{severity}", response_model=None)
@handle_service_exceptions
async def update_alert_rule(
    severity: AlertSeverity,
    rule_config: AlertRuleConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """Update alert rule configuration."""
    alert_system = AlertService(db)
    
    success = alert_system.update_alert_rule(
        rule_config.rule_type,
        severity=rule_config.severity,
        threshold=rule_config.threshold,
        time_window_hours=rule_config.time_window_hours,
        description_template=rule_config.description_template,
        enabled=rule_config.enabled
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert rule not found"
        )
    
    return {"status": "updated", "rule_type": rule_config.rule_type}


@router.put("/notifications/{channel_name}", response_model=None)
@handle_service_exceptions
async def update_notification_channel(
    channel_name: str,
    enabled: bool = Query(..., description="Enable or disable the channel"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Update notification channel configuration."""
    alert_processor = AlertProcessor(db)
    
    success = alert_processor.update_notification_channel(channel_name, enabled)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification channel not found"
        )
    
    return {"status": "updated", "channel": channel_name, "enabled": enabled}
