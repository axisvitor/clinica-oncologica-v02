"""
Advanced Monitoring Module

Provides health history, incidents, and alerts endpoints.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user
from app.models.user import User
from app.models.system_health import (
    SystemHealthSnapshot,
    SystemIncident,
    IncidentStatus as ModelIncidentStatus,
)
from app.schemas.v2.health import (
    HealthHistory,
    HealthHistoryEntry,
    HealthIncidentsResponse,
    HealthIncident,
    HealthAlertsResponse,
    HealthAlert,
    AlertLevel,
)


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/history", response_model=HealthHistory)
async def health_history_endpoint(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> HealthHistory:
    """
    Health check history for last 24 hours (Authenticated).

    Returns historical health data from database.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    snapshots = (
        db.query(SystemHealthSnapshot)
        .filter(SystemHealthSnapshot.created_at >= since)
        .order_by(SystemHealthSnapshot.created_at.asc())
        .all()
    )

    entries = []
    total_checks = len(snapshots)
    total_score = 0.0
    degraded = 0
    unhealthy = 0

    for s in snapshots:
        status_val = s.status.value if hasattr(s.status, "value") else s.status
        entries.append(
            HealthHistoryEntry(
                timestamp=s.created_at.isoformat(),
                status=status_val,
                health_score=s.health_score,
                services_status=s.services_status,
            )
        )
        total_score += s.health_score
        if status_val == "degraded":
            degraded += 1
        if status_val == "unhealthy":
            unhealthy += 1

    avg_score = (total_score / total_checks) if total_checks > 0 else 0.0

    return HealthHistory(
        entries=entries,
        period_hours=24,
        avg_health_score=round(avg_score, 1),
        total_checks=total_checks,
        degraded_periods=degraded,
        unhealthy_periods=unhealthy,
    )


@router.get("/incidents", response_model=HealthIncidentsResponse)
async def health_incidents_endpoint(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> HealthIncidentsResponse:
    """
    Health incidents log (Authenticated).

    Returns recent health incidents from database.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    incidents_db = (
        db.query(SystemIncident)
        .filter(SystemIncident.updated_at >= since)
        .order_by(SystemIncident.created_at.desc())
        .limit(50)
        .all()
    )

    incidents = []
    active_count = 0
    resolved_count = 0

    for i in incidents_db:
        status_val = i.status.value if hasattr(i.status, "value") else i.status
        severity_val = i.severity.value if hasattr(i.severity, "value") else i.severity

        incidents.append(
            HealthIncident(
                id=str(i.id),
                title=i.title,
                description=i.description,
                severity=severity_val,
                status=status_val,
                service=i.service_name,
                started_at=i.started_at.isoformat(),
                resolved_at=i.resolved_at.isoformat() if i.resolved_at else None,
                duration_minutes=int(
                    (i.resolved_at - i.started_at).total_seconds() / 60
                )
                if i.resolved_at
                else None,
            )
        )
        if status_val in ["active", "investigating"]:
            active_count += 1
        elif status_val == "resolved":
            resolved_count += 1

    return HealthIncidentsResponse(
        incidents=incidents,
        total_incidents=len(incidents),
        active_incidents=active_count,
        resolved_incidents=resolved_count,
        period_hours=24,
    )


@router.get("/alerts", response_model=HealthAlertsResponse)
async def health_alerts_endpoint(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> HealthAlertsResponse:
    """
    Active health alerts (Authenticated).

    Returns active incidents as alerts.
    """
    # Active or investigating
    active_incidents = (
        db.query(SystemIncident)
        .filter(
            SystemIncident.status.in_(
                [ModelIncidentStatus.ACTIVE, ModelIncidentStatus.INVESTIGATING]
            )
        )
        .all()
    )

    alerts = []
    critical = 0
    warning = 0
    info = 0

    for i in active_incidents:
        severity_val = i.severity.value if hasattr(i.severity, "value") else i.severity

        # Map severity to AlertLevel
        if severity_val in ["critical", "high"]:
            alert_level = AlertLevel.CRITICAL
            critical += 1
        elif severity_val == "medium":
            alert_level = AlertLevel.WARNING
            warning += 1
        else:
            alert_level = AlertLevel.INFO
            info += 1

        alerts.append(
            HealthAlert(
                id=str(i.id),
                component=i.service_name,
                message=i.title,
                level=alert_level,
                timestamp=i.started_at.isoformat(),
                details=i.description,
            )
        )

    return HealthAlertsResponse(
        alerts=alerts,
        total_alerts=len(alerts),
        critical_count=critical,
        warning_count=warning,
        info_count=info,
    )
