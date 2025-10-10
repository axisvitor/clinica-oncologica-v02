"""
Admin API endpoints for Dead Letter Queue (DLQ) management.
Provides manual review, retry, and monitoring capabilities.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.dependencies.auth_dependencies import require_admin
from app.dependencies.database import get_db
from app.integrations.whatsapp.queue.dlq import DLQHandler
from app.models.failed_message import FailureReason, DLQStatus
from app.exceptions import NotFoundError, ValidationError
import logging


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/dlq", tags=["Admin - Dead Letter Queue"])


# Pydantic schemas
class DLQMessageResponse(BaseModel):
    """DLQ message response schema."""
    id: str
    patient_id: str
    whatsapp_phone: str
    content: str
    failure_reason: str
    retry_count: int
    failed_at: str
    dlq_status: str
    requeue_count: int
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: str
    updated_at: str


class DLQReviewRequest(BaseModel):
    """Request schema for reviewing DLQ message."""
    approve_retry: bool = Field(..., description="Whether to approve message for retry")
    notes: Optional[str] = Field(None, description="Review notes")


class DLQRequeueRequest(BaseModel):
    """Request schema for re-queuing DLQ message."""
    immediate: bool = Field(default=False, description="Retry immediately vs scheduled")


class DLQMetricsResponse(BaseModel):
    """DLQ metrics response schema."""
    total_failures: int
    failure_by_reason: dict
    status_distribution: dict
    avg_retry_count: float
    requeue_rate: float
    period_days: int


@router.get("/pending", response_model=List[DLQMessageResponse])
async def get_pending_messages(
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    failure_reason: Optional[FailureReason] = Query(None, description="Filter by failure reason"),
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get messages pending review in DLQ.

    **Admin only** - Requires admin role.

    Returns paginated list of failed messages awaiting manual review.
    """
    try:
        dlq_handler = DLQHandler(db)
        messages = await dlq_handler.get_pending_review(
            limit=limit,
            offset=offset,
            failure_reason=failure_reason
        )

        return [
            DLQMessageResponse(**msg.to_dict())
            for msg in messages
        ]

    except Exception as e:
        logger.error(f"Failed to get pending DLQ messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve DLQ messages: {str(e)}"
        )


@router.get("/critical", response_model=List[DLQMessageResponse])
async def get_critical_failures(
    hours_back: int = Query(24, ge=1, le=168, description="Hours to look back"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get critical failures requiring immediate attention.

    **Admin only** - Returns high-priority failures with multiple retry attempts.

    Criteria:
    - Retry count >= 3
    - Failed within specified hours
    - Pending review status
    """
    try:
        dlq_handler = DLQHandler(db)
        messages = await dlq_handler.get_critical_failures(
            hours_back=hours_back,
            limit=limit
        )

        return [
            DLQMessageResponse(**msg.to_dict())
            for msg in messages
        ]

    except Exception as e:
        logger.error(f"Failed to get critical DLQ failures: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve critical failures: {str(e)}"
        )


@router.get("/{dlq_id}", response_model=DLQMessageResponse)
async def get_dlq_message(
    dlq_id: UUID,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get specific DLQ message by ID.

    **Admin only** - Retrieve detailed information about a failed message.
    """
    try:
        dlq_handler = DLQHandler(db)
        message = dlq_handler.repository.get(dlq_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DLQ message {dlq_id} not found"
            )

        return DLQMessageResponse(**message.to_dict(include_sensitive=True))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get DLQ message {dlq_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve DLQ message: {str(e)}"
        )


@router.post("/{dlq_id}/review", response_model=DLQMessageResponse)
async def review_dlq_message(
    dlq_id: UUID,
    request: DLQReviewRequest,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Review a failed message and approve/reject retry.

    **Admin only** - Manually review failed messages and decide on retry.

    Use this endpoint to:
    - Investigate failure cause
    - Approve messages for retry
    - Add review notes for audit trail
    """
    try:
        dlq_handler = DLQHandler(db)

        reviewed_message = await dlq_handler.review_message(
            dlq_id=dlq_id,
            reviewer_id=current_user["uid"],
            approve_retry=request.approve_retry,
            notes=request.notes
        )

        return DLQMessageResponse(**reviewed_message.to_dict())

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to review DLQ message {dlq_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to review message: {str(e)}"
        )


@router.post("/{dlq_id}/requeue")
async def requeue_dlq_message(
    dlq_id: UUID,
    request: DLQRequeueRequest = DLQRequeueRequest(),
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Re-queue a failed message for retry delivery.

    **Admin only** - Send failed message back to delivery queue.

    Message must be in PENDING_REVIEW or APPROVED_FOR_RETRY status.

    Options:
    - immediate: Retry within 1 minute (use for urgent messages)
    - scheduled: Retry in next business hours (default, safer)
    """
    try:
        dlq_handler = DLQHandler(db)

        result = await dlq_handler.requeue_for_retry(
            dlq_id=dlq_id,
            immediate=request.immediate
        )

        return {
            "success": True,
            "message": "Message re-queued successfully",
            **result
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to re-queue DLQ message {dlq_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to re-queue message: {str(e)}"
        )


@router.get("/metrics/overview", response_model=DLQMetricsResponse)
async def get_dlq_metrics(
    days_back: int = Query(7, ge=1, le=90, description="Days to analyze"),
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get DLQ metrics and analytics.

    **Admin only** - View failure trends, reasons, and re-queue statistics.

    Provides:
    - Total failures in period
    - Breakdown by failure reason
    - Status distribution
    - Average retry count
    - Re-queue success rate
    """
    try:
        dlq_handler = DLQHandler(db)
        metrics = await dlq_handler.get_dlq_metrics(days_back=days_back)

        return DLQMetricsResponse(**metrics)

    except Exception as e:
        logger.error(f"Failed to get DLQ metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve DLQ metrics: {str(e)}"
        )
