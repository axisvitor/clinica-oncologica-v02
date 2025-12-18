"""
Audit Log Management Endpoints
Comprehensive audit log management for compliance (HIPAA, LGPD).
"""

import logging
import csv
import io
import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from app.database import get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.services.audit import AuditService
from app.utils.rate_limiter import limiter
from app.infrastructure.cache import cache_response
from app.dependencies import get_request_context, RequestContext
from app.schemas.v2.admin_extensions import (
    AuditLogResponse,
    AuditLogListResponse,
    AuditLogExportRequest,
    AuditLogExportFormat,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    get_field_selection,
    create_cursor,
)

from .constants import CACHE_TTL_AUDIT_LOGS, CACHE_TTL_AUDIT_SINGLE
from .dependencies import get_admin_user, log_admin_extension_action
from .utils import serialize_audit_log

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    response_model=AuditLogListResponse,
    summary="List Audit Logs",
    description="Retrieve paginated list of audit logs with cursor-based pagination and comprehensive filters.",
)
@limiter.limit("60/minute")
@cache_response(ttl=CACHE_TTL_AUDIT_LOGS, key_prefix="admin_ext:audit:list")
async def list_audit_logs(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    fields: Optional[str] = Query(
        None, description="Comma-separated fields to include"
    ),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    event_status: Optional[str] = Query(
        None, description="Filter by status (success/failure)"
    ),
    user_id: Optional[UUID] = Query(None, description="Filter by user"),
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    search: Optional[str] = Query(None, description="Search in messages"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    List audit logs with cursor pagination and comprehensive filters.

    Supports filtering by:
    - Event type (login, logout, access_denied, etc.)
    - Event status (success, failure, error)
    - User ID or email
    - IP address
    - Date range
    - Search in messages

    Returns:
        Paginated list of audit logs with cursor for next page
    """
    try:
        # Parse pagination params
        pagination = get_pagination_params(cursor, limit)
        cursor_data = pagination["cursor_data"]

        # Parse field selection
        field_list = get_field_selection(fields) if fields else None

        # Build base query
        query = db.query(AuditLog)

        # Apply cursor pagination
        if cursor_data:
            query = query.filter(AuditLog.id > cursor_data.get("id", 0))

        # Apply filters
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)

        if event_status:
            query = query.filter(AuditLog.event_status == event_status)

        if user_id:
            query = query.filter(AuditLog.user_id == str(user_id))

        if user_email:
            query = query.filter(AuditLog.user_email.ilike(f"%{user_email}%"))

        if ip_address:
            query = query.filter(AuditLog.ip_address == ip_address)

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)

        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    AuditLog.message.ilike(search_pattern),
                    AuditLog.action.ilike(search_pattern),
                    AuditLog.resource.ilike(search_pattern),
                )
            )

        # Order by created_at DESC (most recent first)
        query = query.order_by(desc(AuditLog.created_at))

        # Fetch limit + 1 to check if there's more
        logs = query.limit(limit + 1).all()

        # Check if there are more results
        has_more = len(logs) > limit
        if has_more:
            logs = logs[:limit]

        # Create next cursor
        next_cursor = None
        if has_more and logs:
            next_cursor = create_cursor(logs[-1].id)

        # Serialize logs
        serialized_logs = [serialize_audit_log(log, field_list) for log in logs]

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service,
            "audit_list",
            admin_user,
            context,
            additional_data={
                "count": len(logs),
                "filters": {
                    "event_type": event_type,
                    "user_email": user_email,
                    "ip_address": ip_address,
                },
            },
        )

        return {
            "data": serialized_logs,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None,  # Cursor pagination doesn't include total for performance
        }

    except Exception as e:
        logger.error(f"Error listing audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving audit logs",
        )


@router.get(
    "/{log_id}",
    response_model=AuditLogResponse,
    summary="Get Audit Log",
    description="Retrieve detailed information about a specific audit log. Cached for 15 minutes.",
)
@cache_response(ttl=CACHE_TTL_AUDIT_SINGLE, key_prefix="admin_ext:audit:item")
async def get_audit_log(
    log_id: UUID,
    fields: Optional[str] = Query(
        None, description="Comma-separated fields to include"
    ),
    redact_sensitive: bool = Query(True, description="Redact sensitive data"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Get detailed information about a specific audit log.

    Includes:
    - Full event details
    - User information
    - Network information (IP, user agent)
    - Event metadata
    - Sensitive data redaction (configurable)

    Args:
        log_id: Audit log UUID
        fields: Optional field selection
        redact_sensitive: Whether to redact sensitive data (default: True)

    Returns:
        Detailed audit log information
    """
    try:
        log = db.query(AuditLog).filter(AuditLog.id == log_id).first()

        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Audit log not found"
            )

        # Parse field selection
        field_list = get_field_selection(fields) if fields else None

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service,
            "audit_view",
            admin_user,
            context,
            additional_data={"log_id": str(log_id)},
        )

        return serialize_audit_log(log, field_list, redact_sensitive)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving audit log {log_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving audit log",
        )


@router.post(
    "/export",
    summary="Export Audit Logs",
    description="Export audit logs to CSV or JSON format with filters.",
)
@limiter.limit("10/hour")
async def export_audit_logs(
    request: Request,
    export_request: AuditLogExportRequest,
    event_type: Optional[str] = Query(None),
    event_status: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Export audit logs to CSV or JSON format.

    CRITICAL: This exports sensitive compliance data. All exports are logged.

    Supports:
    - CSV or JSON format
    - Field selection
    - Comprehensive filters
    - Automatic sensitive data redaction
    - HIPAA/LGPD compliance

    Args:
        export_request: Export configuration (format, fields)
        event_type: Filter by event type
        event_status: Filter by status
        user_email: Filter by user email
        start_date: Filter from date
        end_date: Filter to date

    Returns:
        Streaming response with exported data
    """
    try:
        # Build query with filters
        query = db.query(AuditLog)

        if event_type:
            query = query.filter(AuditLog.event_type == event_type)

        if event_status:
            query = query.filter(AuditLog.event_status == event_status)

        if user_email:
            query = query.filter(AuditLog.user_email.ilike(f"%{user_email}%"))

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)

        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        # Order by created_at
        query = query.order_by(desc(AuditLog.created_at))

        # Fetch logs (limit to 10000 for safety)
        logs = query.limit(10000).all()

        # Determine fields
        all_fields = [
            "id",
            "event_type",
            "event_status",
            "user_id",
            "user_email",
            "firebase_uid",
            "ip_address",
            "user_agent",
            "resource",
            "action",
            "event_metadata",
            "message",
            "error_details",
            "created_at",
        ]
        fields_to_export = (
            export_request.fields if export_request.fields else all_fields
        )

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service,
            "audit_export",
            admin_user,
            context,
            additional_data={
                "format": export_request.format,
                "count": len(logs),
                "fields": fields_to_export,
                "filters": {
                    "event_type": event_type,
                    "user_email": user_email,
                    "date_range": f"{start_date} to {end_date}"
                    if start_date or end_date
                    else None,
                },
            },
        )

        logger.warning(
            f"Admin {admin_user.email} exported {len(logs)} audit logs in {export_request.format} format"
        )

        if export_request.format == AuditLogExportFormat.CSV:
            # Generate CSV
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields_to_export)
            writer.writeheader()

            for log in logs:
                row_data = serialize_audit_log(
                    log, redact_sensitive=export_request.redact_sensitive
                )
                row = {}
                for field in fields_to_export:
                    value = row_data.get(field)
                    if isinstance(value, (datetime)):
                        value = value.isoformat()
                    elif isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    elif isinstance(value, UUID):
                        value = str(value)
                    row[field] = value
                writer.writerow(row)

            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=audit_logs_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                },
            )

        else:  # JSON
            data = []
            for log in logs:
                row_data = serialize_audit_log(
                    log, redact_sensitive=export_request.redact_sensitive
                )
                # Filter fields
                filtered_data = {
                    k: v for k, v in row_data.items() if k in fields_to_export
                }
                # Convert datetime to ISO format
                for k, v in filtered_data.items():
                    if isinstance(v, datetime):
                        filtered_data[k] = v.isoformat()
                    elif isinstance(v, UUID):
                        filtered_data[k] = str(v)
                data.append(filtered_data)

            return Response(
                content=json.dumps(data, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=audit_logs_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                },
            )

    except Exception as e:
        logger.error(f"Error exporting audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting audit logs: {str(e)}",
        )
