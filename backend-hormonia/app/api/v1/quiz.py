"""
Quiz and assessment endpoints for Hormonia Backend System.
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.dependencies import (
    get_quiz_template_service,
    get_quiz_response_service,
    get_quiz_session_service,
    get_quiz_analytics_service,
    get_current_user,
    get_pagination_params,
    validate_patient_access,
    get_patient_service
)
from app.models.user import User
from app.models.patient import Patient
from app.services.quiz import QuizTemplateService, QuizResponseService, QuizSessionService, QuizAnalyticsService
from app.services.patient import PatientService
from app.schemas.quiz import (
    QuizTemplateCreate, QuizTemplateUpdate, QuizTemplateResponse,
    QuizResponseCreate, QuizResponseResponse,
    QuizSessionCreate, QuizSessionResponse,
    QuizAnalytics, QuizTemplateListResponse, QuizResponseListResponse,
    QuizSessionListResponse, PatientQuizAnalytics
)
from app.schemas.common import PaginationParams
from app.utils.api_decorators import handle_service_exceptions

router = APIRouter()


# Quiz Template Endpoints
@router.post("/templates", response_model=QuizTemplateResponse, status_code=status.HTTP_201_CREATED)
@handle_service_exceptions
async def create_quiz_template(
    template_data: QuizTemplateCreate,
    service: QuizTemplateService = Depends(get_quiz_template_service),
    current_user: User = Depends(get_current_user)
) -> QuizTemplateResponse:
    """Create a new quiz template."""
    try:
        # Validate template data before creation
        if not template_data.name or not template_data.name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template name cannot be empty"
            )

        if not template_data.version or not template_data.version.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template version cannot be empty"
            )

        if not template_data.questions or len(template_data.questions) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template must contain at least one question"
            )

        return service.create_template(template_data)

    except IntegrityError as e:
        if "uq_quiz_template_name_version" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Template with name '{template_data.name}' and version '{template_data.version}' already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity error occurred"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/templates", response_model=QuizTemplateListResponse)
async def get_quiz_templates(
    pagination: PaginationParams = Depends(get_pagination_params),
    active_only: bool = Query(True),
    service: QuizTemplateService = Depends(get_quiz_template_service),
    current_user: User = Depends(get_current_user)
) -> QuizTemplateListResponse:
    """Get available quiz templates."""
    templates, total = service.get_templates(
        skip=pagination.skip,
        limit=pagination.limit,
        active_only=active_only
    )
    return QuizTemplateListResponse(
        items=templates,
        total=total,
        page=pagination.skip // pagination.limit + 1 if pagination.limit > 0 else 1,
        size=pagination.limit
    )


@router.get("/templates/{template_id}", response_model=QuizTemplateResponse)
@handle_service_exceptions
async def get_quiz_template(
    template_id: UUID,
    service: QuizTemplateService = Depends(get_quiz_template_service),
    current_user: User = Depends(get_current_user)
) -> QuizTemplateResponse:
    """Get quiz template by ID."""
    try:
        template = service.get_template(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz template with ID {template_id} not found"
            )
        return template
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while retrieving template"
        )


@router.put("/templates/{template_id}", response_model=QuizTemplateResponse)
@handle_service_exceptions
async def update_quiz_template(
    template_id: UUID,
    template_data: QuizTemplateUpdate,
    service: QuizTemplateService = Depends(get_quiz_template_service),
    current_user: User = Depends(get_current_user)
) -> QuizTemplateResponse:
    """Update quiz template."""
    try:
        # Validate template exists
        existing_template = service.get_template(template_id)
        if not existing_template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz template with ID {template_id} not found"
            )

        # Validate update data
        if template_data.questions and len(template_data.questions) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template must contain at least one question"
            )

        return service.update_template(template_id, template_data)

    except HTTPException:
        raise
    except IntegrityError as e:
        if "uq_quiz_template_name_version" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Template with this name and version already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity error occurred"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while updating template"
        )


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_service_exceptions
async def delete_quiz_template(
    template_id: UUID,
    service: QuizTemplateService = Depends(get_quiz_template_service),
    current_user: User = Depends(get_current_user)
) -> None:
    """Delete (deactivate) quiz template."""
    try:
        # Check if template exists
        template = service.get_template(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz template with ID {template_id} not found"
            )

        service.delete_template(template_id)

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while deleting template"
        )


@router.get("/templates/name/{template_name}", response_model=QuizTemplateResponse)
@handle_service_exceptions
async def get_quiz_template_by_name(
    template_name: str,
    version: Optional[str] = Query(None),
    service: QuizTemplateService = Depends(get_quiz_template_service),
    current_user: User = Depends(get_current_user)
) -> QuizTemplateResponse:
    """Get quiz template by name and optionally version."""
    try:
        template = service.get_template_by_name(template_name, version)
        if not template:
            version_text = f" version '{version}'" if version else ""
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz template '{template_name}'{version_text} not found"
            )
        return template
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while retrieving template"
        )


# New endpoints for template management
@router.post("/templates/{template_id}/versions", response_model=QuizTemplateResponse, status_code=status.HTTP_201_CREATED)
@handle_service_exceptions
async def create_template_version(
    template_id: UUID,
    new_version: str = Query(..., description="New version identifier"),
    service: QuizTemplateService = Depends(get_quiz_template_service),
    current_user: User = Depends(get_current_user)
) -> QuizTemplateResponse:
    """Create a new version of an existing template."""
    try:
        if not new_version or not new_version.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New version cannot be empty"
            )

        return service.create_template_version(template_id, new_version)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while creating template version"
        )


@router.get("/templates/name/{template_name}/versions", response_model=List[QuizTemplateResponse])
@handle_service_exceptions
async def get_template_versions(
    template_name: str,
    service: QuizTemplateService = Depends(get_quiz_template_service),
    current_user: User = Depends(get_current_user)
) -> List[QuizTemplateResponse]:
    """Get all versions of a template."""
    try:
        versions = service.get_template_versions(template_name)
        if not versions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No versions found for template '{template_name}'"
            )
        return versions
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while retrieving template versions"
        )


@router.post("/templates/validate", response_model=dict)
@handle_service_exceptions
async def validate_quiz_template(
    questions: List[dict],
    service: QuizTemplateService = Depends(get_quiz_template_service),
    current_user: User = Depends(get_current_user)
) -> dict:
    """Validate quiz template questions before creating/updating."""
    try:
        # Convert dict to QuizQuestion objects for validation
        from app.schemas.quiz import QuizQuestion
        quiz_questions = [QuizQuestion(**q) for q in questions]

        validation_result = service.validate_template(quiz_questions)

        return {
            "is_valid": validation_result.is_valid,
            "errors": validation_result.errors,
            "warnings": validation_result.warnings
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid question format: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation error: {str(e)}"
        )


# Quiz Session Endpoints
@router.post("/sessions", response_model=QuizSessionResponse, status_code=status.HTTP_201_CREATED)
@handle_service_exceptions
async def start_quiz_session(
    session_data: QuizSessionCreate,
    service: QuizSessionService = Depends(get_quiz_session_service),
    current_user: User = Depends(get_current_user)
) -> QuizSessionResponse:
    """Start a new quiz session for a patient."""
    try:
        # Validate session data
        if not session_data.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient ID is required"
            )

        if not session_data.quiz_template_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quiz template ID is required"
            )

        # Check for existing active session
        existing_session = service.get_active_session(session_data.patient_id)
        if existing_session and existing_session.quiz_template_id == session_data.quiz_template_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient already has an active session for this quiz template. Session ID: {existing_session.id}"
            )

        return await service.start_quiz_session(session_data)

    except IntegrityError as e:
        if "uq_active_quiz_session_per_patient" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Patient already has an active quiz session for this template"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity error occurred"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/sessions/active/{patient_id}", response_model=Optional[QuizSessionResponse])
@handle_service_exceptions
async def get_active_quiz_session(
    patient_id: UUID,
    service: QuizSessionService = Depends(get_quiz_session_service),
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service)
) -> Optional[QuizSessionResponse]:
    """Get patient's active quiz session."""
    try:
        # Validate patient access
        await validate_patient_access(patient_id, current_user, patient_service)

        return service.get_active_session(patient_id)

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while retrieving active session"
        )


@router.get("/sessions/{session_id}", response_model=QuizSessionResponse)
@handle_service_exceptions
async def get_quiz_session(
    session_id: UUID,
    service: QuizSessionService = Depends(get_quiz_session_service),
    current_user: User = Depends(get_current_user)
) -> QuizSessionResponse:
    """Get quiz session by ID."""
    return service.get_session(session_id)


@router.put("/sessions/{session_id}/advance", response_model=QuizSessionResponse)
@handle_service_exceptions
async def advance_quiz_session(
    session_id: UUID,
    service: QuizSessionService = Depends(get_quiz_session_service),
    current_user: User = Depends(get_current_user)
) -> QuizSessionResponse:
    """Advance quiz session to next question."""
    try:
        # Validate session exists and is active
        session = service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz session with ID {session_id} not found"
            )

        if session.status != 'in_progress':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot advance session with status '{session.status}'. Only 'in_progress' sessions can be advanced."
            )

        return service.advance_session(session_id)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while advancing session"
        )


@router.put("/sessions/{session_id}/complete", response_model=QuizSessionResponse)
@handle_service_exceptions
async def complete_quiz_session(
    session_id: UUID,
    service: QuizSessionService = Depends(get_quiz_session_service),
    current_user: User = Depends(get_current_user)
) -> QuizSessionResponse:
    """Complete a quiz session."""
    try:
        # Validate session exists and is active
        session = service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz session with ID {session_id} not found"
            )

        if session.status != 'in_progress':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot complete session with status '{session.status}'. Only 'in_progress' sessions can be completed."
            )

        return await service.complete_session(session_id)

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while completing session"
        )


@router.put("/sessions/{session_id}/cancel", response_model=QuizSessionResponse)
@handle_service_exceptions
async def cancel_quiz_session(
    session_id: UUID,
    service: QuizSessionService = Depends(get_quiz_session_service),
    current_user: User = Depends(get_current_user)
) -> QuizSessionResponse:
    """Cancel an active quiz session."""
    try:
        # Validate session exists and is active
        session = service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz session with ID {session_id} not found"
            )

        if session.is_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel completed session"
            )

        # Cancel session logic (mark as cancelled or completed)
        return await service.complete_session(session_id)  # Reuse complete logic

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while cancelling session"
        )


@router.get("/sessions", response_model=QuizSessionListResponse)
@handle_service_exceptions
async def get_all_quiz_sessions(
    pagination: PaginationParams = Depends(get_pagination_params),
    patient_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    service: QuizSessionService = Depends(get_quiz_session_service),
    current_user: User = Depends(get_current_user)
) -> QuizSessionListResponse:
    """Get all quiz sessions with optional filtering."""
    if patient_id:
        sessions, total = service.get_patient_sessions(patient_id, pagination.skip, pagination.limit)
    else:
        sessions, total = service.get_all_sessions(pagination.skip, pagination.limit, status)

    return QuizSessionListResponse(
        items=sessions,
        total=total,
        page=pagination.skip // pagination.limit + 1 if pagination.limit > 0 else 1,
        size=pagination.limit
    )


@router.get("/sessions/patient/{patient_id}", response_model=QuizSessionListResponse)
@handle_service_exceptions
async def get_patient_quiz_sessions(
    patient_id: UUID,
    pagination: PaginationParams = Depends(get_pagination_params),
    # patient: Patient = Depends(validate_patient_access),
    service: QuizSessionService = Depends(get_quiz_session_service),
    current_user: User = Depends(get_current_user)
) -> QuizSessionListResponse:
    """Get all quiz sessions for a patient."""
    sessions, total = service.get_patient_sessions(patient_id, pagination.skip, pagination.limit)
    return QuizSessionListResponse(
        items=sessions,
        total=total,
        page=pagination.skip // pagination.limit + 1 if pagination.limit > 0 else 1,
        size=pagination.limit
    )


# Quiz Response Endpoints
@router.post("/responses", response_model=QuizResponseResponse, status_code=status.HTTP_201_CREATED)
@handle_service_exceptions
async def create_quiz_response(
    response_data: QuizResponseCreate,
    service: QuizResponseService = Depends(get_quiz_response_service),
    current_user: User = Depends(get_current_user)
) -> QuizResponseResponse:
    """Submit a quiz response."""
    try:
        # Validate response data
        if not response_data.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient ID is required"
            )

        if not response_data.quiz_template_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quiz template ID is required"
            )

        if not response_data.question_id or not response_data.question_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question ID cannot be empty"
            )

        if not response_data.response_value or not str(response_data.response_value).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Response value cannot be empty"
            )

        # Validate response_type against QuestionType enum
        from app.schemas.quiz import QuestionType
        valid_types = [qt.value for qt in QuestionType]
        if response_data.response_type.value not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid response type. Must be one of: {', '.join(valid_types)}"
            )

        return await service.create_response(response_data)

    except IntegrityError as e:
        if "uq_quiz_response_per_question_session" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Response for this question in this session already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity error occurred"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/responses/patient/{patient_id}", response_model=QuizResponseListResponse)
@handle_service_exceptions
async def get_patient_quiz_responses(
    patient_id: UUID,
    pagination: PaginationParams = Depends(get_pagination_params),
    service: QuizResponseService = Depends(get_quiz_response_service),
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service)
) -> QuizResponseListResponse:
    """Get quiz responses for a patient."""
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)
    
    responses, total = service.get_patient_responses(
        patient_id,
        skip=pagination.skip,
        limit=pagination.limit
    )
    return QuizResponseListResponse(
        items=responses,
        total=total,
        page=pagination.skip // pagination.limit + 1 if pagination.limit > 0 else 1,
        size=pagination.limit
    )


@router.get("/responses/template/{template_id}", response_model=QuizResponseListResponse)
@handle_service_exceptions
async def get_template_quiz_responses(
    template_id: UUID,
    pagination: PaginationParams = Depends(get_pagination_params),
    service: QuizResponseService = Depends(get_quiz_response_service),
    current_user: User = Depends(get_current_user)
) -> QuizResponseListResponse:
    """Get responses for a quiz template."""
    responses, total = service.get_template_responses(
        template_id,
        skip=pagination.skip,
        limit=pagination.limit
    )
    return QuizResponseListResponse(
        items=responses,
        total=total,
        page=pagination.skip // pagination.limit + 1 if pagination.limit > 0 else 1,
        size=pagination.limit
    )


@router.get("/responses/patient/{patient_id}/template/{template_id}", response_model=List[QuizResponseResponse])
@handle_service_exceptions
async def get_patient_template_responses(
    patient_id: UUID,
    template_id: UUID,
    service: QuizResponseService = Depends(get_quiz_response_service),
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service)
) -> List[QuizResponseResponse]:
    """Get all responses from a patient for a specific quiz template."""
    try:
        # Validate patient access
        patient = await validate_patient_access(patient_id, current_user, patient_service)

        responses = service.get_patient_quiz_responses(patient_id, template_id)
        if not responses:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No responses found for patient {patient_id} and template {template_id}"
            )

        return responses

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while retrieving responses"
        )


# Analytics Endpoints
@router.get("/analytics/patient/{patient_id}", response_model=PatientQuizAnalytics)
@handle_service_exceptions
async def get_patient_quiz_analytics(
    patient_id: UUID,
    template_id: Optional[UUID] = Query(None),
    service: QuizAnalyticsService = Depends(get_quiz_analytics_service),
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service)
) -> PatientQuizAnalytics:
    """Get quiz analytics for a patient."""
    try:
        # Validate patient access
        patient = await validate_patient_access(patient_id, current_user, patient_service)

        analytics = service.get_patient_analytics(patient_id, template_id)
        return analytics

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while retrieving patient analytics"
        )


@router.get("/analytics/template/{template_id}", response_model=QuizAnalytics)
@handle_service_exceptions
async def get_template_quiz_analytics(
    template_id: UUID,
    service: QuizAnalyticsService = Depends(get_quiz_analytics_service),
    current_user: User = Depends(get_current_user)
) -> QuizAnalytics:
    """Get analytics for a quiz template."""
    try:
        analytics = service.get_template_analytics(template_id)
        return analytics

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while retrieving template analytics"
        )


# Additional analytics endpoints
@router.get("/analytics/summary", response_model=dict)
@handle_service_exceptions
async def get_quiz_summary_analytics(
    date_from: Optional[str] = Query(None, description="Start date (ISO format)"),
    date_to: Optional[str] = Query(None, description="End date (ISO format)"),
    service: QuizAnalyticsService = Depends(get_quiz_analytics_service),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Get quiz analytics summary.

    ⚠️ PLACEHOLDER IMPLEMENTATION
    This endpoint currently returns mock data for development purposes.

    TODO: Implement real analytics aggregation:
    - Total quizzes created (from quiz_templates table)
    - Total quiz responses (from quiz_responses table)
    - Total quiz sessions (from quiz_sessions table)
    - Average completion rate (calculated from sessions)
    - Response time metrics (from session durations)
    - User engagement scores (from response patterns)
    - Template popularity metrics (usage counts)
    - Temporal analysis (trends over date range)

    Args:
        date_from: Start date for analytics period (ISO format)
        date_to: End date for analytics period (ISO format)
        service: QuizAnalyticsService dependency
        current_user: Authenticated user

    Returns:
        dict: Mock analytics summary with the following structure:
            - message: Placeholder notification
            - date_from: Requested start date
            - date_to: Requested end date
            - total_templates: Count of quiz templates (placeholder: 0)
            - total_responses: Count of quiz responses (placeholder: 0)
            - total_sessions: Count of quiz sessions (placeholder: 0)
            - completion_rate: Average completion rate (placeholder: 0.0)

    Note:
        Production implementation pending. Will aggregate real-time
        metrics from quiz_sessions and quiz_responses tables with:
        - Time-series data for trend analysis
        - Engagement metrics per patient/template
        - Performance benchmarks and SLAs
        - Cached results for optimization
    """
    logger = logging.getLogger(__name__)
    logger.warning(
        "Analytics summary endpoint called - returning placeholder data. "
        f"date_from={date_from}, date_to={date_to}, user_id={current_user.id}"
    )

    try:
        # TODO: Replace with actual service implementation
        # Example implementation would be:
        # return service.get_summary_analytics(
        #     date_from=datetime.fromisoformat(date_from) if date_from else None,
        #     date_to=datetime.fromisoformat(date_to) if date_to else None
        # )

        return {
            "message": "Summary analytics endpoint - implementation needed in service layer",
            "date_from": date_from,
            "date_to": date_to,
            "total_templates": 0,  # TODO: Query COUNT(*) FROM quiz_templates
            "total_responses": 0,  # TODO: Query COUNT(*) FROM quiz_responses WHERE date BETWEEN date_from AND date_to
            "total_sessions": 0,   # TODO: Query COUNT(*) FROM quiz_sessions WHERE date BETWEEN date_from AND date_to
            "completion_rate": 0.0  # TODO: Calculate (completed_sessions / total_sessions) * 100
        }
    except Exception as e:
        logger.error(f"Error in analytics summary endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving summary analytics: {str(e)}"
        )


@router.get("/responses/{response_id}", response_model=QuizResponseResponse)
@handle_service_exceptions
async def get_quiz_response(
    response_id: UUID,
    service: QuizResponseService = Depends(get_quiz_response_service),
    current_user: User = Depends(get_current_user)
) -> QuizResponseResponse:
    """Get a specific quiz response by ID."""
    try:
        response = service.response_repository.get(response_id)
        if not response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz response with ID {response_id} not found"
            )

        return QuizResponseResponse.from_orm(response)

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while retrieving response"
        )


@router.put("/responses/{response_id}", response_model=QuizResponseResponse)
@handle_service_exceptions
async def update_quiz_response(
    response_id: UUID,
    response_value: str,
    response_metadata: Optional[dict] = None,
    service: QuizResponseService = Depends(get_quiz_response_service),
    current_user: User = Depends(get_current_user)
) -> QuizResponseResponse:
    """Update a quiz response."""
    try:
        # Get existing response
        response = service.response_repository.get(response_id)
        if not response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz response with ID {response_id} not found"
            )

        # Validate new response value
        if not response_value or not response_value.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Response value cannot be empty"
            )

        # Update response
        update_data = {
            "response_value": response_value,
            "response_metadata": response_metadata or response.response_metadata
        }

        updated_response = service.response_repository.update(response, update_data)
        service.db.commit()

        return QuizResponseResponse.from_orm(updated_response)

    except HTTPException:
        raise
    except SQLAlchemyError:
        service.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while updating response"
        )


@router.delete("/responses/{response_id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_service_exceptions
async def delete_quiz_response(
    response_id: UUID,
    service: QuizResponseService = Depends(get_quiz_response_service),
    current_user: User = Depends(get_current_user)
) -> None:
    """Delete a quiz response."""
    try:
        # Get existing response
        response = service.response_repository.get(response_id)
        if not response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz response with ID {response_id} not found"
            )

        # Delete response
        service.response_repository.delete(response)
        service.db.commit()

    except HTTPException:
        raise
    except SQLAlchemyError:
        service.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while deleting response"
        )


# Additional endpoints for comprehensive quiz management
@router.get("/sessions/{session_id}/responses", response_model=List[QuizResponseResponse])
@handle_service_exceptions
async def get_session_responses(
    session_id: UUID,
    session_service: QuizSessionService = Depends(get_quiz_session_service),
    response_service: QuizResponseService = Depends(get_quiz_response_service),
    current_user: User = Depends(get_current_user)
) -> List[QuizResponseResponse]:
    """Get all responses for a specific quiz session."""
    try:
        # Get session to validate it exists
        session = session_service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz session with ID {session_id} not found"
            )

        # Get responses for this session's patient and template
        responses = response_service.get_patient_quiz_responses(
            session.patient_id,
            session.quiz_template_id
        )

        return responses

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while retrieving session responses"
        )


@router.get("/sessions/{session_id}/current-question", response_model=dict)
@handle_service_exceptions
async def get_current_question(
    session_id: UUID,
    service: QuizSessionService = Depends(get_quiz_session_service),
    template_service: QuizTemplateService = Depends(get_quiz_template_service),
    current_user: User = Depends(get_current_user)
) -> dict:
    """Get the current question for a quiz session."""
    try:
        # Get session
        session = service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz session with ID {session_id} not found"
            )

        if session.is_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quiz session is already completed"
            )

        # Get template
        template = template_service.get_template(session.quiz_template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz template not found"
            )

        # Get current question
        questions = template.questions
        if session.current_question_index >= len(questions):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session has reached the end of questions"
            )

        current_question = questions[session.current_question_index]

        return {
            "session_id": str(session.id),
            "current_question_index": session.current_question_index,
            "total_questions": len(questions),
            "question": current_question,
            "progress_percentage": round((session.current_question_index / len(questions)) * 100, 2)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving current question: {str(e)}"
        )


@router.get("/templates/search", response_model=QuizTemplateListResponse)
@handle_service_exceptions
async def search_quiz_templates(
    q: str = Query(..., description="Search query"),
    pagination: PaginationParams = Depends(get_pagination_params),
    active_only: bool = Query(True),
    service: QuizTemplateService = Depends(get_quiz_template_service),
    current_user: User = Depends(get_current_user)
) -> QuizTemplateListResponse:
    """Search quiz templates by name or content."""
    try:
        # This would need to be implemented in the service layer
        # For now, return basic templates with a filter
        templates, total = service.get_templates(
            skip=pagination.skip,
            limit=pagination.limit,
            active_only=active_only
        )

        # Simple search filter
        filtered_templates = [
            template for template in templates
            if q.lower() in template.name.lower()
        ]

        return QuizTemplateListResponse(
            items=filtered_templates,
            total=len(filtered_templates),
            page=pagination.skip // pagination.limit + 1 if pagination.limit > 0 else 1,
            size=pagination.limit
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching templates: {str(e)}"
        )


@router.post("/sessions/{session_id}/submit", response_model=QuizResponseResponse, status_code=status.HTTP_201_CREATED)
@handle_service_exceptions
async def submit_quiz_response(
    session_id: UUID,
    question_id: str,
    answer: str,
    response_metadata: Optional[dict] = None,
    service: QuizResponseService = Depends(get_quiz_response_service),
    session_service: QuizSessionService = Depends(get_quiz_session_service),
    current_user: User = Depends(get_current_user)
) -> QuizResponseResponse:
    """Submit a response for a specific quiz session (convenience endpoint)."""
    try:
        # Get session to validate it exists and get patient/template info
        session = session_service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz session with ID {session_id} not found"
            )

        if session.is_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot submit response to completed session"
            )

        # Create response using existing endpoint logic
        response_data = QuizResponseCreate(
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            session_id=session_id,
            question_id=question_id,
            answer=answer,
            response_metadata=response_metadata or {}
        )

        # Validate response data
        if not response_data.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient ID is required"
            )

        if not response_data.quiz_template_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quiz template ID is required"
            )

        if not response_data.answer or not response_data.answer.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Answer cannot be empty"
            )

        response = service.create_response(response_data)

        # Automatically advance session if configured to do so
        try:
            session_service.advance_session(session_id)
        except Exception as e:
            logging.warning(f"Could not auto-advance session {session_id}: {e}")

        return response

    except HTTPException:
        raise
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A response for this question already exists"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting quiz response: {str(e)}"
        )


@router.get("/health", response_model=dict)
async def quiz_api_health() -> dict:
    """Health check endpoint for quiz API."""
    return {
        "status": "healthy",
        "service": "quiz-api",
        "version": "1.0.0",
        "endpoints": {
            "templates": "CRUD operations for quiz templates",
            "sessions": "Quiz session management",
            "responses": "Quiz response handling",
            "analytics": "Quiz analytics and reporting"
        }
    }