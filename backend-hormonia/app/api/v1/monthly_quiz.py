"""
Monthly Quiz API endpoints for Hormonia Backend System.

Endpoints for creating and managing monthly quiz via link.
"""
import logging
from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.dependencies import (
    get_db, get_current_user, get_monthly_quiz_service,
    verify_monthly_quiz_token, get_request_context, RequestContext
)
from app.models.user import User, UserRole
from app.services.monthly_quiz_service import MonthlyQuizService
from app.schemas.monthly_quiz import (
    MonthlyQuizLinkCreate, MonthlyQuizLinkResponse,
    MonthlyQuizAccessRequest, MonthlyQuizAccessResponse,
    MonthlyQuizSubmitResponse, MonthlyQuizStats,
    BulkQuizLinkCreate, BulkQuizLinkResponse,
    DeliveryMethod
)
from typing import List
from app.utils.api_decorators import handle_service_exceptions
from app.core.error_handler import error_handler
from app.core.monitoring_logging import monitoring_logger

router = APIRouter()
logger = logging.getLogger(__name__)


# Admin endpoints (require authentication)
@router.post("/links", response_model=MonthlyQuizLinkResponse, status_code=status.HTTP_201_CREATED)
@handle_service_exceptions
async def create_monthly_quiz_link(
    link_data: MonthlyQuizLinkCreate,
    service: MonthlyQuizService = Depends(get_monthly_quiz_service),
    current_user: User = Depends(get_current_user),
    context: RequestContext = Depends(get_request_context)
) -> MonthlyQuizLinkResponse:
    """
    Create a monthly quiz link for a patient.

    This endpoint creates a secure tokenized link that allows a patient
    to access their monthly quiz without authentication.

    **Required permissions**: Authenticated user (doctor, admin)

    **Parameters**:
    - patient_id: UUID of the patient
    - quiz_template_id: UUID of the quiz template
    - delivery_method: How the link will be delivered (whatsapp, email, sms)
    - expiry_hours: Link validity in hours (default: 72)
    - custom_message: Optional custom message to send with link

    **Returns**:
    - Link details including token and full URL
    """
    try:
        return await service.create_quiz_link(
            link_data,
            actor_id=current_user.id,
            ip_address=context.ip_address,
            user_agent=context.user_agent
        )
    except Exception as e:
        logger.error(f"Error creating monthly quiz link: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create quiz link: {str(e)}"
        )


@router.post("/links/bulk", response_model=BulkQuizLinkResponse, status_code=status.HTTP_201_CREATED)
@handle_service_exceptions
async def create_bulk_monthly_quiz_links(
    bulk_data: BulkQuizLinkCreate,
    service: MonthlyQuizService = Depends(get_monthly_quiz_service),
    current_user: User = Depends(get_current_user),
    context: RequestContext = Depends(get_request_context)
) -> BulkQuizLinkResponse:
    """
    Create monthly quiz links for multiple patients at once.

    **Required permissions**: Authenticated user (doctor, admin)

    **Parameters**:
    - patient_ids: List of patient UUIDs
    - quiz_template_id: UUID of the quiz template
    - delivery_method: How links will be delivered
    - expiry_hours: Link validity in hours
    - custom_message: Optional custom message

    **Returns**:
    - Summary of created links and any failures
    """
    try:
        return await service.create_bulk_quiz_links(
            bulk_data,
            actor_id=current_user.id,
            ip_address=context.ip_address,
            user_agent=context.user_agent
        )
    except Exception as e:
        logger.error(f"Error creating bulk quiz links: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bulk quiz links: {str(e)}"
        )


@router.get("/links/{session_id}/status", response_model=MonthlyQuizLinkResponse)
@handle_service_exceptions
async def get_quiz_link_status(
    session_id: UUID,
    service: MonthlyQuizService = Depends(get_monthly_quiz_service),
    current_user: User = Depends(get_current_user)
) -> MonthlyQuizLinkResponse:
    """
    Get status of a monthly quiz link.

    **Required permissions**: Authenticated user

    **Returns**:
    - Link status, access count, expiration, completion status
    """
    try:
        return await service.get_quiz_link_status(session_id)
    except Exception as e:
        logger.error(f"Error getting quiz link status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get quiz link status: {str(e)}"
        )


@router.get("/stats", response_model=MonthlyQuizStats)
@handle_service_exceptions
async def get_monthly_quiz_statistics(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    service: MonthlyQuizService = Depends(get_monthly_quiz_service),
    current_user: User = Depends(get_current_user)
) -> MonthlyQuizStats:
    """
    Get statistics for monthly quizzes.

    **Required permissions**: Authenticated user

    **Parameters**:
    - start_date: Optional start date filter (ISO format)
    - end_date: Optional end date filter (ISO format)

    **Returns**:
    - Comprehensive statistics about quiz links and completions
    """
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None

        return await service.get_monthly_quiz_stats(start, end)
    except Exception as e:
        logger.error(f"Error getting quiz statistics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get quiz statistics: {str(e)}"
        )


# DEPRECATED: Public endpoints moved to monthly_quiz_public.py for security
# DEPRECATED: Use /api/v1/monthly-quiz-public/access instead
@router.post("/access", response_model=MonthlyQuizAccessResponse, deprecated=True)
@handle_service_exceptions
async def access_monthly_quiz(
    access_data: MonthlyQuizAccessRequest,
    request: Request,
    service: MonthlyQuizService = Depends(get_monthly_quiz_service)
) -> MonthlyQuizAccessResponse:
    """
    Access a monthly quiz using a token.

    **Public endpoint** - No authentication required

    This endpoint allows patients to access their quiz using the
    tokenized link sent to them via WhatsApp, email, or SMS.

    **Parameters**:
    - token: The access token from the quiz link

    **Returns**:
    - Quiz session details and questions

    **Security**:
    - Token is validated and checked for expiration
    - Access is logged and rate-limited
    """
    try:
        # Extract request context for public endpoint
        ip_address = None
        if "x-forwarded-for" in request.headers:
            ip_address = request.headers["x-forwarded-for"].split(",")[0].strip()
        elif "x-real-ip" in request.headers:
            ip_address = request.headers["x-real-ip"]
        else:
            ip_address = request.client.host if request.client else "unknown"

        user_agent = request.headers.get("user-agent", "unknown")

        # Log public access with metrics
        logger.info(
            f"Monthly quiz public access attempt",
            extra={
                'event_type': 'monthly_quiz_access',
                'token_prefix': access_data.token[:10] if access_data.token else 'none',
                'ip_address': ip_address
            }
        )

        response = await service.access_quiz_via_token(
            access_data.token,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Log successful access
        logger.info(
            f"Monthly quiz accessed successfully",
            extra={
                'event_type': 'monthly_quiz_access_success',
                'session_id': str(response.quiz_session_id),
                'patient_name': response.patient_name,
                'ip_address': ip_address
            }
        )

        return response
    except Exception as e:
        logger.error(
            f"Error accessing quiz via token: {str(e)}",
            extra={'event_type': 'monthly_quiz_access_error'},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to access quiz: {str(e)}"
        )


# DEPRECATED: Use /api/v1/monthly-quiz-public/submit instead
@router.post("/submit", response_model=dict, deprecated=True)
@handle_service_exceptions
async def submit_monthly_quiz_response(
    submit_data: MonthlyQuizSubmitResponse,
    request: Request,
    service: MonthlyQuizService = Depends(get_monthly_quiz_service)
) -> dict:
    """
    Submit a quiz response via token.

    **Public endpoint** - No authentication required

    Allows patients to submit quiz responses using their access token.

    **Parameters**:
    - token: The access token
    - question_id: ID of the question being answered
    - response_value: The patient's response
    - response_metadata: Optional additional metadata

    **Returns**:
    - Confirmation of submission

    **Security**:
    - Token is validated for each submission
    - Responses are validated against question type
    """
    try:
        # Extract request context for public endpoint
        ip_address = None
        if "x-forwarded-for" in request.headers:
            ip_address = request.headers["x-forwarded-for"].split(",")[0].strip()
        elif "x-real-ip" in request.headers:
            ip_address = request.headers["x-real-ip"]
        else:
            ip_address = request.client.host if request.client else "unknown"

        user_agent = request.headers.get("user-agent", "unknown")

        # Log submission attempt
        logger.info(
            f"Monthly quiz response submission",
            extra={
                'event_type': 'monthly_quiz_submit',
                'question_id': submit_data.question_id,
                'token_prefix': submit_data.token[:10] if submit_data.token else 'none',
                'ip_address': ip_address
            }
        )

        result = await service.submit_quiz_response(
            submit_data,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Log successful submission
        logger.info(
            f"Monthly quiz response submitted successfully",
            extra={
                'event_type': 'monthly_quiz_submit_success',
                'response_id': result.get('response_id'),
                'question_id': submit_data.question_id,
                'ip_address': ip_address
            }
        )

        return result
    except Exception as e:
        logger.error(
            f"Error submitting quiz response: {str(e)}",
            extra={
                'event_type': 'monthly_quiz_submit_error',
                'question_id': submit_data.question_id
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to submit response: {str(e)}"
        )


@router.post("/links/{session_id}/resend", response_model=MonthlyQuizLinkResponse)
@handle_service_exceptions
async def resend_monthly_quiz_link(
    session_id: UUID,
    delivery_method: DeliveryMethod = Query(..., description="Delivery method for resend"),
    service: MonthlyQuizService = Depends(get_monthly_quiz_service),
    current_user: User = Depends(get_current_user),
    context: RequestContext = Depends(get_request_context)
) -> MonthlyQuizLinkResponse:
    """
    Resend an existing quiz link via a new delivery method.

    **Required permissions**: Authenticated user (doctor, admin)

    **Parameters**:
    - session_id: UUID of the quiz session
    - delivery_method: New delivery method (whatsapp, email, sms)

    **Returns**:
    - Link details with new token and URL
    """
    try:
        return await service.resend_quiz_link(
            session_id,
            delivery_method,
            actor_id=current_user.id,
            ip_address=context.ip_address,
            user_agent=context.user_agent
        )
    except Exception as e:
        logger.error(f"Error resending quiz link: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resend quiz link: {str(e)}"
        )


@router.get("/patients/{patient_id}/status", response_model=MonthlyQuizLinkResponse)
@handle_service_exceptions
async def get_patient_latest_quiz_status(
    patient_id: UUID,
    service: MonthlyQuizService = Depends(get_monthly_quiz_service),
    current_user: User = Depends(get_current_user)
) -> MonthlyQuizLinkResponse:
    """
    Get the latest quiz link status for a specific patient.

    **Required permissions**: Authenticated user

    **Parameters**:
    - patient_id: UUID of the patient

    **Returns**:
    - Latest quiz link status for the patient
    """
    return await service.get_patient_latest_status(patient_id)


@router.get("/patients/{patient_id}/history", response_model=List[MonthlyQuizLinkResponse])
@handle_service_exceptions
async def get_patient_quiz_history(
    patient_id: UUID,
    limit: Optional[int] = Query(10, description="Maximum number of records to return"),
    offset: Optional[int] = Query(0, description="Number of records to skip"),
    service: MonthlyQuizService = Depends(get_monthly_quiz_service),
    current_user: User = Depends(get_current_user)
) -> List[MonthlyQuizLinkResponse]:
    """
    Get quiz session history for a specific patient.

    **Required permissions**: Authenticated user

    **Parameters**:
    - patient_id: UUID of the patient
    - limit: Maximum number of records to return (default: 10)
    - offset: Number of records to skip (default: 0)

    **Returns**:
    - List of all quiz sessions for the patient
    """
    try:
        return await service.get_patient_history(patient_id, limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"Error getting patient quiz history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get patient quiz history: {str(e)}"
        )


@router.get("/links/active", response_model=List[dict])
@handle_service_exceptions
async def get_active_quiz_links_with_details(
    service: MonthlyQuizService = Depends(get_monthly_quiz_service),
    current_user: User = Depends(get_current_user)
) -> List[dict]:
    """
    Get active quiz links with patient and template details.
    Returns enriched data for dashboard display.

    **Required permissions**: Authenticated user

    **Returns**:
    - List of active quiz links with patient names, template details, and access URLs
    """
    try:
        with monitoring_logger.context(operation="get_active_quiz_links", user_id=str(current_user.id)):
            # Pass user_id for filtering if needed (can be enhanced based on role)
            user_id = None if current_user.role == UserRole.ADMIN else current_user.id
            return await service.get_active_links_with_details(user_id=user_id)
    except AttributeError as e:
        # Handle role enum errors
        if "UserRole" in str(e) or "role" in str(e).lower():
            await error_handler.handle_role_enum_error(
                e,
                user_role=str(current_user.role) if hasattr(current_user, 'role') else None,
                endpoint="monthly_quiz.get_active_quiz_links_with_details"
            )
        else:
            await error_handler.handle_dependency_injection_error(
                e,
                {
                    "operation": "get_active_quiz_links",
                    "endpoint": "monthly_quiz.get_active_quiz_links_with_details",
                    "user_id": str(current_user.id)
                }
            )
    except Exception as e:
        await error_handler.handle_generic_error(
            e,
            error_type="MONTHLY_QUIZ_LINKS_ERROR",
            context={
                "operation": "get_active_quiz_links",
                "user_id": str(current_user.id)
            },
            user_message="Failed to get active quiz links. Please try again."
        )


@router.get("/stats/dashboard", response_model=dict)
@handle_service_exceptions
async def get_dashboard_quiz_stats(
    service: MonthlyQuizService = Depends(get_monthly_quiz_service),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Get quiz statistics with both new and old field names for compatibility.
    Optimized for dashboard display.

    **Required permissions**: Authenticated user

    **Returns**:
    - Comprehensive statistics with backward-compatible field names
    """
    try:
        with monitoring_logger.context(operation="get_dashboard_quiz_stats", user_id=str(current_user.id)):
            # Pass user_id for filtering if needed (can be enhanced based on role)
            user_id = None if current_user.role == UserRole.ADMIN else current_user.id
            return await service.get_quiz_stats(user_id=user_id)
    except AttributeError as e:
        # Handle role enum errors
        if "UserRole" in str(e) or "role" in str(e).lower():
            await error_handler.handle_role_enum_error(
                e,
                user_role=str(current_user.role) if hasattr(current_user, 'role') else None,
                endpoint="monthly_quiz.get_dashboard_quiz_stats"
            )
        else:
            await error_handler.handle_dependency_injection_error(
                e,
                {
                    "operation": "get_dashboard_quiz_stats",
                    "endpoint": "monthly_quiz.get_dashboard_quiz_stats",
                    "user_id": str(current_user.id)
                }
            )
    except Exception as e:
        await error_handler.handle_generic_error(
            e,
            error_type="MONTHLY_QUIZ_STATS_ERROR",
            context={
                "operation": "get_dashboard_quiz_stats",
                "user_id": str(current_user.id)
            },
            user_message="Failed to get dashboard statistics. Please try again."
        )


@router.post("/links/{session_id}/cancel", response_model=MonthlyQuizLinkResponse)
@handle_service_exceptions
async def cancel_quiz_link(
    session_id: UUID,
    service: MonthlyQuizService = Depends(get_monthly_quiz_service),
    current_user: User = Depends(get_current_user),
    context: RequestContext = Depends(get_request_context)
) -> MonthlyQuizLinkResponse:
    """
    Cancel a quiz link (update status to cancelled).

    **Required permissions**: Authenticated user (doctor, admin)

    **Parameters**:
    - session_id: UUID of the quiz session to cancel

    **Returns**:
    - Updated quiz link details with cancelled status
    """
    try:
        return await service.cancel_quiz_link(
            session_id,
            actor_id=current_user.id,
            ip_address=context.ip_address,
            user_agent=context.user_agent
        )
    except Exception as e:
        logger.error(f"Error cancelling quiz link: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel quiz link: {str(e)}"
        )


@router.get("/health", response_model=dict)
async def monthly_quiz_health() -> dict:
    """Health check endpoint for monthly quiz API."""
    return {
        "status": "healthy",
        "service": "monthly-quiz-api",
        "version": "1.0.0",
        "features": {
            "token_generation": "JWT with HMAC",
            "delivery_methods": ["whatsapp", "email", "sms"],
            "security": "Rate-limited, token-based access",
            "audit_logging": "Comprehensive with actor/subject tracking"
        }
    }