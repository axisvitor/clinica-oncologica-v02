"""
Admin Audit Log Endpoints.

Provides admin-only access to security audit logs for compliance,
security monitoring, and forensic analysis.

All endpoints require admin role.
"""
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_thread_safe_db as get_db, get_current_user
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog, AuditEventType
from app.services.audit_log import AuditLogService

router = APIRouter(prefix="/admin/audit", tags=["Admin - Audit Logs"])


# Response models

class AuditLogResponse(BaseModel):
    """Audit log entry response."""
    id: str
    event_type: str
    event_status: str
    user_id: Optional[str]
    user_email: Optional[str]
    firebase_uid: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource: Optional[str]
    action: Optional[str]
    message: Optional[str]
    error_details: Optional[str]
    metadata: dict
    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, audit_log: AuditLog):
        """Create from ORM model."""
        return cls(
            id=str(audit_log.id),
            event_type=audit_log.event_type.value,
            event_status=audit_log.event_status,
            user_id=audit_log.user_id,
            user_email=audit_log.user_email,
            firebase_uid=audit_log.firebase_uid,
            ip_address=str(audit_log.ip_address) if audit_log.ip_address else None,
            user_agent=audit_log.user_agent,
            resource=audit_log.resource,
            action=audit_log.action,
            message=audit_log.message,
            error_details=audit_log.error_details,
            metadata=audit_log.event_metadata or {},
            created_at=audit_log.created_at
        )


class AuditLogListResponse(BaseModel):
    """Paginated audit log list response."""
    items: List[AuditLogResponse]
    total: int
    limit: int
    offset: int


class AuditStatisticsResponse(BaseModel):
    """Audit log statistics response."""
    total_events: int
    failure_count: int
    unique_users: int
    events_by_type: dict
    period_start: Optional[datetime]
    period_end: Optional[datetime]


# Dependency for admin-only access

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to ensure only admin users can access endpoints.

    Args:
        current_user: Current authenticated user

    Returns:
        User if admin

    Raises:
        HTTPException 403: If user is not admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# Endpoints

@router.get(
    "/logs",
    response_model=AuditLogListResponse,
    summary="Get Audit Logs",
    description="Retrieve audit logs with filtering and pagination (admin only)"
)
async def get_audit_logs(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    event_status: Optional[str] = Query(None, description="Filter by event status (success, failure, error)"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Number of results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
) -> AuditLogListResponse:
    """
    Get audit logs with filtering and pagination.

    Requires admin role.
    """
    try:
        # Build query
        query = db.query(AuditLog)

        # Apply filters
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        if event_type:
            try:
                event_type_enum = AuditEventType(event_type)
                query = query.filter(AuditLog.event_type == event_type_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid event_type: {event_type}"
                )

        if event_status:
            query = query.filter(AuditLog.event_status == event_status)

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)

        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        # Get total count
        total = query.count()

        # Apply pagination
        logs = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset).all()

        # Convert to response models
        items = [AuditLogResponse.from_orm(log) for log in logs]

        return AuditLogListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve audit logs: {str(e)}"
        )


@router.get(
    "/logs/user/{user_id}",
    response_model=AuditLogListResponse,
    summary="Get User Audit Logs",
    description="Retrieve audit logs for a specific user (admin only)"
)
async def get_user_audit_logs(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
) -> AuditLogListResponse:
    """
    Get audit logs for a specific user.

    Requires admin role.
    """
    try:
        audit_service = AuditLogService(db)

        # Parse event types if provided
        event_types = None
        if event_type:
            try:
                event_types = [AuditEventType(event_type)]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid event_type: {event_type}"
                )

        # Get logs
        logs = audit_service.get_user_audit_logs(
            user_id=user_id,
            limit=limit,
            offset=offset,
            event_types=event_types,
            start_date=start_date,
            end_date=end_date
        )

        # Get total count
        query = db.query(AuditLog).filter(AuditLog.user_id == user_id)
        if event_types:
            query = query.filter(AuditLog.event_type.in_(event_types))
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        total = query.count()

        # Convert to response models
        items = [AuditLogResponse.from_orm(log) for log in logs]

        return AuditLogListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user audit logs: {str(e)}"
        )


@router.get(
    "/security-events",
    response_model=AuditLogListResponse,
    summary="Get Security Events",
    description="Retrieve security-related audit events (failures, suspicious activity) (admin only)"
)
async def get_security_events(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
) -> AuditLogListResponse:
    """
    Get security-related events (failures, suspicious activity).

    Requires admin role.
    """
    try:
        audit_service = AuditLogService(db)

        # Get security events
        logs = audit_service.get_security_events(
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date
        )

        # Get total count
        security_event_types = [
            AuditEventType.LOGIN_FAILURE,
            AuditEventType.ACCESS_DENIED,
            AuditEventType.SUSPICIOUS_ACTIVITY,
            AuditEventType.RATE_LIMIT_EXCEEDED,
            AuditEventType.INVALID_TOKEN,
            AuditEventType.CSRF_VIOLATION,
        ]
        query = db.query(AuditLog).filter(AuditLog.event_type.in_(security_event_types))
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        total = query.count()

        # Convert to response models
        items = [AuditLogResponse.from_orm(log) for log in logs]

        return AuditLogListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve security events: {str(e)}"
        )


@router.get(
    "/failed-logins",
    response_model=AuditLogListResponse,
    summary="Get Failed Login Attempts",
    description="Retrieve failed login attempts (admin only)"
)
async def get_failed_logins(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    email: Optional[str] = Query(None, description="Filter by email"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    hours: int = Query(24, ge=1, le=720, description="Time window in hours")
) -> AuditLogListResponse:
    """
    Get failed login attempts within time window.

    Requires admin role.
    """
    try:
        audit_service = AuditLogService(db)

        # Get failed login attempts
        logs = audit_service.get_failed_login_attempts(
            email=email,
            ip_address=ip_address,
            hours=hours
        )

        # Convert to response models
        items = [AuditLogResponse.from_orm(log) for log in logs]

        return AuditLogListResponse(
            items=items,
            total=len(items),
            limit=len(items),
            offset=0
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve failed login attempts: {str(e)}"
        )


@router.get(
    "/statistics",
    response_model=AuditStatisticsResponse,
    summary="Get Audit Statistics",
    description="Retrieve audit log statistics (admin only)"
)
async def get_audit_statistics(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date")
) -> AuditStatisticsResponse:
    """
    Get audit log statistics.

    Requires admin role.
    """
    try:
        audit_service = AuditLogService(db)

        # Get statistics
        stats = audit_service.get_audit_statistics(
            start_date=start_date,
            end_date=end_date
        )

        return AuditStatisticsResponse(
            total_events=stats["total_events"],
            failure_count=stats["failure_count"],
            unique_users=stats["unique_users"],
            events_by_type=stats["events_by_type"],
            period_start=start_date,
            period_end=end_date
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve audit statistics: {str(e)}"
        )


@router.get(
    "/event-types",
    response_model=List[str],
    summary="Get Available Event Types",
    description="Get list of available audit event types (admin only)"
)
async def get_event_types(
    current_user: User = Depends(require_admin)
) -> List[str]:
    """
    Get list of available audit event types.

    Requires admin role.
    """
    return [event_type.value for event_type in AuditEventType]
