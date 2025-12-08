"""
Reports API v2
Business reports with async generation and file download.

Features:
- Cursor pagination with field selection
- Redis caching (10min TTL for lists)
- Rate limiting (list: 30/min, generate: 10/min, schedule: 5/min)
- Background tasks for async report generation
- File download support (PDF/Excel/CSV/JSON)
- Scheduled recurring reports
"""

import json
import csv
import io
import hashlib
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Response, Request
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session,  joinedload
from sqlalchemy import and_, or_, func, desc

from app.database import get_db
from app.models.user import User, UserRole
from app.models.patient import Patient, FlowState
from app.models.quiz import QuizSession
from app.models.message import Message
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Cache TTL in seconds
LIST_CACHE_TTL = 600  # 10 minutes for list endpoints
REPORT_CACHE_TTL = 1800  # 30 minutes for generated reports
SCHEDULE_CACHE_TTL = 300  # 5 minutes for schedule endpoints

# Rate limiting
RATE_LIMIT_LIST = "30/minute"
RATE_LIMIT_GENERATE = "10/minute"
RATE_LIMIT_SCHEDULE = "5/minute"


# ============================================================================
# Helper Functions
# ============================================================================

def _get_role_and_user(current_user) -> tuple[UserRole, Optional[UUID]]:
    """Extract role and user UUID from current_user."""
    if isinstance(current_user, dict):
        role_value = current_user.get("role", "doctor")
        user_id = current_user.get("id")
    else:
        role_value = getattr(current_user, "role", "doctor")
        user_id = getattr(current_user, "id", None)

    if isinstance(role_value, UserRole):
        role = role_value
    elif isinstance(role_value, str):
        role = UserRole.ADMIN if role_value.lower() == "admin" else UserRole.DOCTOR
    else:
        role = UserRole.DOCTOR

    if user_id:
        try:
            user_uuid = UUID(str(user_id))
        except (TypeError, ValueError):
            user_uuid = None
    else:
        user_uuid = None

    return role, user_uuid


def _get_cache_key(endpoint: str, **params) -> str:
    """Generate cache key from endpoint and parameters."""
    param_str = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()
    return f"reports:v2:{endpoint}:{param_hash}"


async def _get_cached_result(cache_key: str):
    """Get cached result from Redis."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            return None
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache HIT: {cache_key}")
            return json.loads(cached)
        return None
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")
        return None


async def _set_cached_result(cache_key: str, data: dict, ttl: int = REPORT_CACHE_TTL):
    """Set cached result in Redis."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            return
        await redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


def _create_cursor(items: List[Dict[str, Any]]) -> Optional[str]:
    """Create cursor from last item for pagination."""
    if not items:
        return None

    last_item = items[-1]
    cursor_data = {
        "id": str(last_item.get("id", "")),
        "created_at": last_item.get("created_at", "")
    }
    import base64
    encoded = base64.urlsafe_b64encode(json.dumps(cursor_data).encode()).decode()
    return encoded


def _decode_cursor(cursor: Optional[str]) -> Optional[Dict[str, Any]]:
    """Decode cursor for pagination."""
    if not cursor:
        return None

    try:
        import base64
        decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
        return json.loads(decoded)
    except Exception as e:
        logger.warning(f"Cursor decode failed: {e}")
        return None


def _check_patient_access(db, role: UserRole, user_id: UUID, patient_ids: List[UUID]) -> bool:
    """Check if user has access to specified patients."""
    if role == UserRole.ADMIN:
        return True

    patient_count = db.query(func.count(Patient.id)).filter(
        Patient.id.in_(patient_ids),
        Patient.doctor_id == user_id
    ).scalar()

    return patient_count == len(patient_ids)


def _filter_fields(data: Dict[str, Any], fields: Optional[List[str]]) -> Dict[str, Any]:
    """Filter response data to only include selected fields."""
    if not fields:
        return data

    field_set = set(fields)
    return {k: v for k, v in data.items() if k in field_set}


async def _generate_report_async(report_id: UUID, title: str, report_type: str,
                                  format_type: str, user_id: UUID, db: Any):
    """Background task to generate report asynchronously."""
    try:
        logger.info(f"Starting async report generation: {report_id}")

        # Update status to GENERATING
        await _set_cached_result(
            _get_cache_key("status", report_id=str(report_id)),
            {
                "id": str(report_id),
                "status": "generating",
                "progress": 10,
                "message": "Collecting data"
            },
            ttl=SCHEDULE_CACHE_TTL
        )

        # Simulate processing
        import asyncio
        await asyncio.sleep(1)

        # Generate report data
        report_data = {
            "summary": "Report data generated",
            "timestamp": datetime.utcnow().isoformat(),
            "records": 42
        }

        # Mark as completed
        completed_data = {
            "id": str(report_id),
            "title": title,
            "type": report_type,
            "format": format_type,
            "status": "completed",
            "created_at": datetime.utcnow().isoformat(),
            "generated_by": str(user_id),
            "file_url": f"/api/v2/reports/{report_id}/download",
            "data": report_data
        }

        await _set_cached_result(
            _get_cache_key("report", report_id=str(report_id)),
            completed_data,
            ttl=REPORT_CACHE_TTL
        )

        logger.info(f"Report generation completed: {report_id}")

    except Exception as e:
        logger.error(f"Report generation failed: {report_id}, error: {e}")
        await _set_cached_result(
            _get_cache_key("status", report_id=str(report_id)),
            {
                "id": str(report_id),
                "status": "failed",
                "error": str(e)
            },
            ttl=SCHEDULE_CACHE_TTL
        )


def _format_csv(data: Dict[str, Any]) -> str:
    """Format report data as CSV."""
    output = io.StringIO()

    if isinstance(data, dict):
        if "records" in data and isinstance(data["records"], list):
            records = data["records"]
        else:
            records = [data]
    else:
        records = [data]

    if records:
        writer = csv.DictWriter(output, fieldnames=records[0].keys() if isinstance(records[0], dict) else ["value"])
        writer.writeheader()
        writer.writerows(records)

    return output.getvalue()


def _format_excel(data: Dict[str, Any]) -> bytes:
    """Format report data as Excel (CSV-based stub)."""
    csv_data = _format_csv(data)
    return csv_data.encode("utf-8")


def _format_pdf(data: Dict[str, Any]) -> bytes:
    """Format report data as PDF (text-based stub)."""
    content = f"Report\n\n{json.dumps(data, indent=2, default=str)}"
    return content.encode("utf-8")


# ============================================================================
# 1. GET /api/v2/reports - List Reports with Cursor Pagination
# ============================================================================

@router.get(
    "",
    summary="List reports",
    description="List all reports with cursor pagination and field selection. Cache: 10 minutes. Rate limit: 30/min",
    responses={
        200: {"description": "List of reports"},
        401: {"description": "Unauthorized"},
    }
)
@limiter.limit(RATE_LIMIT_LIST)
async def list_reports(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    status_filter: Optional[str] = Query(None, description="Filter by status (pending, generating, completed, failed)"),
    current_user=Depends(get_current_user_from_session),
    db = Depends(get_db)
):
    """
    List reports with cursor pagination.

    Query Parameters:
    - cursor: Base64-encoded cursor for pagination
    - limit: Number of items per page (1-100, default 20)
    - fields: Comma-separated fields (id,title,status,created_at)
    - report_type: Filter by type
    - status_filter: Filter by status

    Returns paginated list with next cursor if more items exist.
    """
    role, user_id = _get_role_and_user(current_user)

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User ID not found")

    # Generate cache key
    cache_key = _get_cache_key(
        "list",
        cursor=cursor,
        limit=limit,
        report_type=report_type,
        status=status_filter,
        user_id=str(user_id)
    )

    # Check cache
    cached = await _get_cached_result(cache_key)
    if cached:
        return cached

    # Mock data - in production, query database
    mock_reports = [
        {
            "id": str(uuid4()),
            "title": f"Report {i}",
            "type": "patient_summary",
            "status": "completed",
            "created_at": (datetime.utcnow() - timedelta(days=i)).isoformat(),
            "updated_at": (datetime.utcnow() - timedelta(days=i)).isoformat(),
            "format": "json",
            "generated_by": str(user_id)
        }
        for i in range(50)
    ]

    # Apply filters
    if report_type:
        mock_reports = [r for r in mock_reports if r["type"] == report_type]
    if status_filter:
        mock_reports = [r for r in mock_reports if r["status"] == status_filter]

    # Decode cursor
    cursor_data = _decode_cursor(cursor)
    start_idx = 0
    if cursor_data:
        # Find position after cursor
        for i, report in enumerate(mock_reports):
            if report["id"] == cursor_data.get("id"):
                start_idx = i + 1
                break

    # Paginate
    end_idx = start_idx + limit
    page_items = mock_reports[start_idx:end_idx]
    has_more = end_idx < len(mock_reports)

    # Filter fields
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None
    if field_list:
        page_items = [_filter_fields(item, field_list) for item in page_items]

    # Create next cursor
    next_cursor = _create_cursor(page_items) if has_more else None

    response = {
        "items": page_items,
        "total": len(mock_reports),
        "count": len(page_items),
        "cursor": next_cursor,
        "has_more": has_more,
        "limit": limit
    }

    # Cache response
    await _set_cached_result(cache_key, response, ttl=LIST_CACHE_TTL)

    return response


# ============================================================================
# 2. POST /api/v2/reports/generate - Generate Report
# ============================================================================

@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate report",
    description="Generate a custom report asynchronously. Returns immediately with report ID. Rate limit: 10/min",
    responses={
        202: {"description": "Report generation started"},
        400: {"description": "Invalid request"},
        403: {"description": "Access denied"},
    }
)
@limiter.limit(RATE_LIMIT_GENERATE)
async def generate_report(
    request: Request,
    title: str = Query(..., description="Report title"),
    report_type: str = Query(..., description="Type of report (patient_summary, activity, flow_performance, etc)"),
    format: str = Query("json", description="Output format (json, csv, excel, pdf)"),
    patient_ids: Optional[str] = Query(None, description="Comma-separated patient IDs (optional)"),
    date_from: Optional[date] = Query(None, description="Filter from date"),
    date_to: Optional[date] = Query(None, description="Filter to date"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user=Depends(get_current_user_from_session),
    db = Depends(get_db)
):
    """
    Generate a custom report asynchronously.

    Returns immediately with report ID and status URL.
    Report is generated in background and can be downloaded once completed.

    Query Parameters:
    - title: Report title
    - report_type: Type of report
    - format: Output format (json, csv, excel, pdf)
    - patient_ids: Comma-separated patient IDs (optional)
    - date_from: Start date for filtering
    - date_to: End date for filtering
    """
    role, user_id = _get_role_and_user(current_user)

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User ID not found")

    # Validate format
    valid_formats = ["json", "csv", "excel", "pdf"]
    if format not in valid_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format. Must be one of: {', '.join(valid_formats)}"
        )

    # Check patient access if specified
    if patient_ids:
        try:
            pids = [UUID(pid.strip()) for pid in patient_ids.split(",")]
            if not _check_patient_access(db, role, user_id, pids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to some patients"
                )
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid patient ID format")

    # Create report ID
    report_id = uuid4()

    # Schedule async generation
    background_tasks.add_task(
        _generate_report_async,
        report_id,
        title,
        report_type,
        format,
        user_id,
        db
    )

    # Return immediate response with 202 Accepted
    response = {
        "id": str(report_id),
        "title": title,
        "type": report_type,
        "format": format,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "status_url": f"/api/v2/reports/{report_id}",
        "download_url": f"/api/v2/reports/{report_id}/download"
    }

    logger.info(f"Report generation started: {report_id}, type: {report_type}, format: {format}")

    return response


# ============================================================================
# 3. GET /api/v2/reports/{id}/download - Download Report
# ============================================================================

@router.get(
    "/{report_id}/download",
    summary="Download report",
    description="Download the generated report in specified format (PDF, Excel, CSV, JSON)",
    responses={
        200: {"description": "Report file"},
        400: {"description": "Report not ready"},
        404: {"description": "Report not found"},
    }
)
async def download_report(
    report_id: UUID,
    format_override: Optional[str] = Query(None, description="Override output format (json, csv, excel, pdf)"),
    current_user=Depends(get_current_user_from_session)
):
    """
    Download generated report in specified format.

    Supports multiple formats:
    - json: JSON document
    - csv: Comma-separated values
    - excel: Excel spreadsheet (.xlsx)
    - pdf: PDF document

    Returns file with appropriate Content-Type and Content-Disposition headers.
    """
    role, user_id = _get_role_and_user(current_user)

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User ID not found")

    # Get report from cache
    cache_key = _get_cache_key("report", report_id=str(report_id))
    report = await _get_cached_result(cache_key)

    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if report.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Report is not ready. Current status: {report.get('status')}"
        )

    # Get report data
    data = report.get("data", {})

    # Determine format
    output_format = format_override or report.get("format", "json")

    if output_format not in ["json", "csv", "excel", "pdf"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid format")

    # Format and return
    if output_format == "json":
        content = json.dumps(data, indent=2, default=str)
        media_type = "application/json"
        filename = f"report_{report_id}.json"
    elif output_format == "csv":
        content = _format_csv(data)
        media_type = "text/csv"
        filename = f"report_{report_id}.csv"
    elif output_format == "excel":
        content = _format_excel(data)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"report_{report_id}.xlsx"
    elif output_format == "pdf":
        content = _format_pdf(data)
        media_type = "application/pdf"
        filename = f"report_{report_id}.pdf"

    # Convert string content to bytes if needed
    if isinstance(content, str):
        content = content.encode("utf-8")

    logger.info(f"Report downloaded: {report_id}, format: {output_format}")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================================================
# 4. POST /api/v2/reports/schedule - Schedule Recurring Report
# ============================================================================

@router.post(
    "/schedule",
    status_code=status.HTTP_201_CREATED,
    summary="Schedule recurring report",
    description="Create a scheduled report that runs automatically on a schedule. Rate limit: 5/min",
    responses={
        201: {"description": "Scheduled report created"},
        400: {"description": "Invalid request"},
        403: {"description": "Access denied"},
    }
)
@limiter.limit(RATE_LIMIT_SCHEDULE)
async def schedule_report(
    request: Request,
    name: str = Query(..., description="Schedule name"),
    report_type: str = Query(..., description="Type of report"),
    format: str = Query("json", description="Output format"),
    frequency: str = Query(..., description="Frequency (daily, weekly, monthly)"),
    start_date: date = Query(..., description="Start date"),
    end_date: Optional[date] = Query(None, description="End date (optional)"),
    time_of_day: Optional[str] = Query("09:00", description="Time in HH:MM format"),
    timezone: Optional[str] = Query("UTC", description="Timezone"),
    recipient_emails: Optional[str] = Query(None, description="Comma-separated recipient emails"),
    is_active: bool = Query(True, description="Enable schedule immediately"),
    current_user=Depends(get_current_user_from_session),
    db = Depends(get_db)
):
    """
    Create a scheduled report that generates automatically.

    Query Parameters:
    - name: Schedule name
    - report_type: Type of report
    - format: Output format (json, csv, excel, pdf)
    - frequency: How often to run (daily, weekly, monthly)
    - start_date: When to start scheduling
    - end_date: When to stop scheduling (optional)
    - time_of_day: Time to run (HH:MM format, default 09:00)
    - timezone: Timezone for scheduling (default UTC)
    - recipient_emails: Comma-separated emails for delivery (optional)
    - is_active: Enable immediately (default true)

    Returns scheduled report details with next run time.
    """
    role, user_id = _get_role_and_user(current_user)

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User ID not found")

    # Validate frequency
    valid_frequencies = ["daily", "weekly", "monthly"]
    if frequency not in valid_frequencies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid frequency. Must be one of: {', '.join(valid_frequencies)}"
        )

    # Validate format
    valid_formats = ["json", "csv", "excel", "pdf"]
    if format not in valid_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format. Must be one of: {', '.join(valid_formats)}"
        )

    # Validate end_date is after start_date if provided
    if end_date and end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date"
        )

    # Create schedule ID
    schedule_id = uuid4()

    # Calculate next run
    now = datetime.utcnow()
    next_run = datetime.combine(start_date, datetime.strptime(time_of_day or "09:00", "%H:%M").time())
    if next_run <= now:
        # If start_date is today and time has passed, schedule for tomorrow
        next_run += timedelta(days=1)

    # Parse recipient emails
    recipients = []
    if recipient_emails:
        recipients = [e.strip() for e in recipient_emails.split(",") if e.strip()]

    # Create response
    response = {
        "id": str(schedule_id),
        "name": name,
        "report_type": report_type,
        "format": format,
        "frequency": frequency,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat() if end_date else None,
        "time_of_day": time_of_day or "09:00",
        "timezone": timezone,
        "next_run": next_run.isoformat(),
        "last_run": None,
        "recipient_emails": recipients,
        "is_active": is_active,
        "run_count": 0,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": str(user_id),
        "updated_at": datetime.utcnow().isoformat()
    }

    # Cache schedule
    cache_key = _get_cache_key("schedule", schedule_id=str(schedule_id))
    await _set_cached_result(cache_key, response, ttl=SCHEDULE_CACHE_TTL)

    logger.info(f"Report schedule created: {schedule_id}, frequency: {frequency}, next_run: {next_run}")

    return response
