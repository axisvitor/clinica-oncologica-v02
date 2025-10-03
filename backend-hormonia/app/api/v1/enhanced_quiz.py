"""
Enhanced Quiz/Questionnaire System API with comprehensive session management.
Implements medical questionnaire functionality with advanced analytics and real-time features.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
import logging
from uuid import UUID, uuid4
import json

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from pydantic import BaseModel, validator, Field
from enum import Enum

from app.dependencies import get_db, get_current_user, get_quiz_service
from app.models.user import User
from app.models.quiz import QuizTemplate, QuizSession, QuizResponse
from app.schemas.quiz import QuestionType
from app.services.quiz import QuizService
from app.services.websocket_events import websocket_events
from app.schemas.quiz import (
    QuizTemplateCreate, QuizTemplateUpdate, QuizTemplateResponse,
    QuizSessionCreate, QuizSessionResponse, QuizResponseCreate
)
from app.utils.logging import get_logger
from app.utils.pagination import paginate_query

logger = get_logger(__name__)
router = APIRouter()

class QuizCategory(str, Enum):
    """Quiz category types."""
    SYMPTOMS = "symptoms"
    SIDE_EFFECTS = "side_effects"
    QUALITY_OF_LIFE = "quality_of_life"
    MEDICATION_ADHERENCE = "medication_adherence"
    PSYCHOLOGICAL = "psychological"
    NUTRITION = "nutrition"
    EXERCISE = "exercise"
    PAIN_ASSESSMENT = "pain_assessment"
    GENERAL_HEALTH = "general_health"

class QuizStatus(str, Enum):
    """Quiz session status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class QuizDifficulty(str, Enum):
    """Quiz difficulty levels."""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    COMPREHENSIVE = "comprehensive"

class QuizQuestion(BaseModel):
    """Quiz question model."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    question_text: str
    question_type: QuestionType
    options: Optional[List[str]] = None
    required: bool = True
    validation_rules: Optional[Dict[str, Any]] = None
    scoring_weight: float = 1.0
    category: Optional[str] = None
    help_text: Optional[str] = None

    @validator('options')
    def validate_options(cls, v, values):
        question_type = values.get('question_type')
        if question_type in [QuestionType.MULTIPLE_CHOICE, QuestionType.SINGLE_CHOICE] and not v:
            raise ValueError('Options required for choice questions')
        return v

class EnhancedQuizTemplate(BaseModel):
    """Enhanced quiz template with advanced features."""
    title: str
    description: Optional[str] = None
    category: QuizCategory
    difficulty: QuizDifficulty = QuizDifficulty.BASIC
    questions: List[QuizQuestion]
    time_limit_minutes: Optional[int] = None
    max_attempts: int = 1
    randomize_questions: bool = False
    show_results_immediately: bool = True
    passing_score: Optional[float] = None
    tags: List[str] = []
    is_active: bool = True
    scheduling_rules: Optional[Dict[str, Any]] = None

class QuizSessionAnalytics(BaseModel):
    """Quiz session analytics."""
    session_id: UUID
    completion_rate: float
    average_time_per_question: float
    skipped_questions: int
    revised_answers: int
    difficulty_score: float
    engagement_score: float
    completion_time_minutes: float

class QuizReportData(BaseModel):
    """Quiz report generation data."""
    patient_id: UUID
    template_id: UUID
    session_ids: List[UUID]
    report_type: str = "detailed"
    include_trends: bool = True
    include_recommendations: bool = True

class BulkQuizAssignment(BaseModel):
    """Bulk quiz assignment to patients."""
    patient_ids: List[UUID]
    template_id: UUID
    scheduled_for: Optional[datetime] = None
    deadline: Optional[datetime] = None
    priority: str = "normal"
    auto_remind: bool = True

@router.post(
    "/templates",
    response_model=QuizTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Quiz Template",
    description="""
    Create a new quiz template with advanced configuration options.

    This endpoint supports:
    - Multiple question types (text, choice, scale, date, etc.)
    - Advanced validation rules
    - Scoring and weighting systems
    - Time limits and attempt restrictions
    - Scheduling and automation rules
    - Accessibility features

    **Rate Limit**: 10 requests per minute per user.
    """,
    responses={
        201: {
            "description": "Quiz template created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "title": "Weekly Symptom Assessment",
                        "category": "symptoms",
                        "difficulty": "basic",
                        "questions": [
                            {
                                "id": "q1",
                                "question_text": "How are you feeling today?",
                                "question_type": "scale",
                                "required": True
                            }
                        ],
                        "created_at": "2024-01-01T00:00:00Z"
                    }
                }
            }
        }
    }
)
async def create_quiz_template(
    template_data: EnhancedQuizTemplate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service)
) -> QuizTemplateResponse:
    """Create a new quiz template."""
    try:
        # Create template
        template = await quiz_service.create_template(template_data, current_user.id)

        # Background tasks for template processing
        background_tasks.add_task(
            _validate_template_questions,
            template.id
        )
        background_tasks.add_task(
            _generate_template_preview,
            template.id
        )

        logger.info(
            f"Quiz template created: {template.title}",
            extra={
                "event_type": "quiz_template_created",
                "template_id": str(template.id),
                "category": template_data.category,
                "question_count": len(template_data.questions),
                "user_id": str(current_user.id)
            }
        )

        return QuizTemplateResponse.from_orm(template)

    except ValueError as e:
        logger.warning(f"Quiz template validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating quiz template: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create quiz template"
        )

@router.get(
    "/templates",
    response_model=List[QuizTemplateResponse],
    summary="List Quiz Templates",
    description="""
    Retrieve quiz templates with filtering and search capabilities.

    Supports filtering by:
    - Category and difficulty
    - Active/inactive status
    - Creation date range
    - Text search in title/description
    - Tags
    """,
    responses={
        200: {
            "description": "Templates retrieved successfully"
        }
    }
)
async def list_quiz_templates(
    category: Optional[QuizCategory] = Query(None, description="Filter by category"),
    difficulty: Optional[QuizDifficulty] = Query(None, description="Filter by difficulty"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in title/description"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum templates to return"),
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service)
) -> List[QuizTemplateResponse]:
    """List quiz templates with filtering."""
    try:
        # Parse tags
        tag_list = tags.split(',') if tags else None

        # Get templates
        templates = await quiz_service.list_templates(
            category=category,
            difficulty=difficulty,
            is_active=is_active,
            search=search,
            tags=tag_list,
            limit=limit,
            current_user=current_user
        )

        logger.info(
            f"Quiz templates listed: {len(templates)}",
            extra={
                "event_type": "quiz_templates_listed",
                "count": len(templates),
                "user_id": str(current_user.id),
                "filters": {
                    "category": category,
                    "difficulty": difficulty,
                    "is_active": is_active,
                    "search": search,
                    "tags": tag_list
                }
            }
        )

        return [QuizTemplateResponse.from_orm(t) for t in templates]

    except Exception as e:
        logger.error(f"Error listing quiz templates: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve quiz templates"
        )

@router.post(
    "/sessions",
    response_model=QuizSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Quiz Session",
    description="""
    Create a new quiz session for a patient with advanced session management.

    Features:
    - Automatic session initialization
    - Progress tracking
    - Time management
    - Auto-save functionality
    - Resume capability
    - Real-time notifications
    """,
    responses={
        201: {
            "description": "Quiz session created successfully"
        },
        400: {
            "description": "Invalid session parameters"
        }
    }
)
async def create_quiz_session(
    session_data: QuizSessionCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service)
) -> QuizSessionResponse:
    """Create a new quiz session."""
    try:
        # Create session
        session = await quiz_service.create_session(session_data, current_user.id)

        # Background tasks for session setup
        background_tasks.add_task(
            _initialize_session_tracking,
            session.id
        )
        background_tasks.add_task(
            _send_session_notification,
            session.patient_id, session.id
        )

        # Real-time notification
        if websocket_events:
            await websocket_events.notify_quiz_session_created(
                session.patient_id, session.dict()
            )

        logger.info(
            f"Quiz session created for patient {session.patient_id}",
            extra={
                "event_type": "quiz_session_created",
                "session_id": str(session.id),
                "patient_id": str(session.patient_id),
                "template_id": str(session.template_id),
                "user_id": str(current_user.id)
            }
        )

        return QuizSessionResponse.from_orm(session)

    except ValueError as e:
        logger.warning(f"Quiz session validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating quiz session: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create quiz session"
        )

@router.get(
    "/sessions/{session_id}",
    response_model=QuizSessionResponse,
    summary="Get Quiz Session",
    description="""
    Retrieve detailed quiz session information including progress and analytics.

    Returns comprehensive session data with:
    - Current progress and completion status
    - Response history and timestamps
    - Performance analytics
    - Time tracking information
    """,
    responses={
        200: {
            "description": "Session retrieved successfully"
        },
        404: {
            "description": "Session not found"
        }
    }
)
async def get_quiz_session(
    session_id: UUID,
    include_analytics: bool = Query(True, description="Include session analytics"),
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service)
) -> QuizSessionResponse:
    """Get detailed quiz session information."""
    try:
        session = await quiz_service.get_session(
            session_id, current_user, include_analytics=include_analytics
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz session not found"
            )

        logger.info(
            f"Quiz session retrieved: {session_id}",
            extra={
                "event_type": "quiz_session_viewed",
                "session_id": str(session_id),
                "user_id": str(current_user.id)
            }
        )

        return QuizSessionResponse.from_orm(session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving quiz session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve quiz session"
        )

@router.post(
    "/sessions/{session_id}/responses",
    response_model=Dict[str, Any],
    summary="Submit Quiz Responses",
    description="""
    Submit responses for a quiz session with validation and auto-save.

    Features:
    - Real-time validation
    - Automatic progress tracking
    - Response versioning
    - Partial submission support
    - Auto-completion detection
    """,
    responses={
        200: {
            "description": "Responses submitted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "123e4567-e89b-12d3-a456-426614174000",
                        "responses_saved": 5,
                        "completion_percentage": 83.3,
                        "is_completed": False,
                        "next_question": "q6"
                    }
                }
            }
        }
    }
)
async def submit_quiz_responses(
    session_id: UUID,
    responses: List[QuizResponseCreate],
    background_tasks: BackgroundTasks,
    auto_advance: bool = Query(True, description="Auto-advance to next question"),
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service)
) -> Dict[str, Any]:
    """Submit responses for a quiz session."""
    try:
        # Submit responses
        result = await quiz_service.submit_responses(
            session_id, responses, current_user, auto_advance=auto_advance
        )

        # Background tasks for response processing
        background_tasks.add_task(
            _process_response_analytics,
            session_id, len(responses)
        )

        if result.get('is_completed'):
            background_tasks.add_task(
                _process_completed_session,
                session_id
            )

        # Real-time notification
        if websocket_events:
            await websocket_events.notify_quiz_progress_updated(
                result['patient_id'], result
            )

        logger.info(
            f"Quiz responses submitted: {len(responses)} responses for session {session_id}",
            extra={
                "event_type": "quiz_responses_submitted",
                "session_id": str(session_id),
                "response_count": len(responses),
                "completion_percentage": result.get('completion_percentage', 0),
                "user_id": str(current_user.id)
            }
        )

        return result

    except ValueError as e:
        logger.warning(f"Quiz response validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error submitting quiz responses: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit responses"
        )

@router.get(
    "/sessions/{session_id}/analytics",
    response_model=QuizSessionAnalytics,
    summary="Get Session Analytics",
    description="""
    Retrieve comprehensive analytics for a quiz session.

    Provides detailed insights including:
    - Completion metrics
    - Time analysis
    - Engagement scores
    - Difficulty assessment
    - Performance indicators
    """,
    responses={
        200: {
            "description": "Analytics retrieved successfully"
        }
    }
)
async def get_session_analytics(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service)
) -> QuizSessionAnalytics:
    """Get detailed analytics for a quiz session."""
    try:
        analytics = await quiz_service.get_session_analytics(session_id, current_user)

        if not analytics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session analytics not found"
            )

        logger.info(
            f"Quiz session analytics retrieved: {session_id}",
            extra={
                "event_type": "quiz_analytics_viewed",
                "session_id": str(session_id),
                "user_id": str(current_user.id)
            }
        )

        return analytics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics"
        )

@router.post(
    "/bulk-assign",
    response_model=Dict[str, Any],
    summary="Bulk Assign Quizzes",
    description="""
    Assign quiz templates to multiple patients efficiently.

    Features:
    - Batch assignment processing
    - Scheduling support
    - Automatic reminders
    - Progress tracking
    - Error handling
    """,
    responses={
        200: {
            "description": "Bulk assignment completed",
            "content": {
                "application/json": {
                    "example": {
                        "total_patients": 50,
                        "sessions_created": 48,
                        "failed": 2,
                        "job_id": "bulk-quiz-123e4567"
                    }
                }
            }
        }
    }
)
async def bulk_assign_quizzes(
    assignment: BulkQuizAssignment,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service)
) -> Dict[str, Any]:
    """Assign quizzes to multiple patients."""
    try:
        # Validate patient access
        accessible_patients = await quiz_service.validate_patient_access(
            assignment.patient_ids, current_user
        )

        if len(accessible_patients) != len(assignment.patient_ids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to some patients"
            )

        # Start bulk assignment
        job_id = await quiz_service.start_bulk_assignment(assignment, current_user.id)

        # Process in background
        background_tasks.add_task(
            _process_bulk_quiz_assignment,
            job_id, assignment, current_user.id
        )

        logger.info(
            f"Bulk quiz assignment started: {len(assignment.patient_ids)} patients",
            extra={
                "event_type": "bulk_quiz_assignment_started",
                "job_id": job_id,
                "patient_count": len(assignment.patient_ids),
                "template_id": str(assignment.template_id),
                "user_id": str(current_user.id)
            }
        )

        return {
            "job_id": job_id,
            "total_patients": len(assignment.patient_ids),
            "status": "processing",
            "estimated_completion": (
                datetime.utcnow() + timedelta(minutes=len(assignment.patient_ids) // 20)
            ).isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting bulk quiz assignment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start bulk assignment"
        )

@router.post(
    "/reports/generate",
    response_model=Dict[str, Any],
    summary="Generate Quiz Report",
    description="""
    Generate comprehensive quiz reports with analytics and insights.

    Report types:
    - Individual patient reports
    - Comparative analysis
    - Trend reports
    - Performance summaries
    - Outcome predictions
    """,
    responses={
        200: {
            "description": "Report generation started",
            "content": {
                "application/json": {
                    "example": {
                        "report_id": "report-123e4567",
                        "status": "generating",
                        "estimated_completion": "2024-01-01T12:05:00Z"
                    }
                }
            }
        }
    }
)
async def generate_quiz_report(
    report_data: QuizReportData,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service)
) -> Dict[str, Any]:
    """Generate comprehensive quiz report."""
    try:
        # Start report generation
        report_id = await quiz_service.start_report_generation(report_data, current_user.id)

        # Process in background
        background_tasks.add_task(
            _generate_quiz_report,
            report_id, report_data, current_user.id
        )

        logger.info(
            f"Quiz report generation started for patient {report_data.patient_id}",
            extra={
                "event_type": "quiz_report_generation_started",
                "report_id": report_id,
                "patient_id": str(report_data.patient_id),
                "template_id": str(report_data.template_id),
                "user_id": str(current_user.id)
            }
        )

        return {
            "report_id": report_id,
            "status": "generating",
            "estimated_completion": (
                datetime.utcnow() + timedelta(minutes=5)
            ).isoformat()
        }

    except Exception as e:
        logger.error(f"Error starting quiz report generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start report generation"
        )

# Background task functions
async def _validate_template_questions(template_id: UUID):
    """Validate template questions after creation."""
    # Implementation for question validation
    pass

async def _generate_template_preview(template_id: UUID):
    """Generate template preview after creation."""
    # Implementation for preview generation
    pass

async def _initialize_session_tracking(session_id: UUID):
    """Initialize session tracking after creation."""
    # Implementation for session tracking
    pass

async def _send_session_notification(patient_id: UUID, session_id: UUID):
    """Send notification about new quiz session."""
    # Implementation for notification service
    pass

async def _process_response_analytics(session_id: UUID, response_count: int):
    """Process response analytics after submission."""
    # Implementation for analytics processing
    pass

async def _process_completed_session(session_id: UUID):
    """Process completed session analytics and notifications."""
    # Implementation for completion processing
    pass

async def _process_bulk_quiz_assignment(job_id: str, assignment: BulkQuizAssignment, user_id: UUID):
    """Process bulk quiz assignment in background."""
    # Implementation for bulk processing
    pass

async def _generate_quiz_report(report_id: str, report_data: QuizReportData, user_id: UUID):
    """Generate quiz report in background."""
    # Implementation for report generation
    pass