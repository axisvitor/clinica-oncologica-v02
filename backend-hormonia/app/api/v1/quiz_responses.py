"""
Quiz Response Viewer API Endpoints

Provides endpoints for doctors to view patient quiz responses, AI analysis, and risk scores.
"""
import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.quiz import QuizResponse, QuizSession, QuizTemplate
from app.models.patient import Patient
from app.schemas.quiz import QuizResponseResponse, QuizSessionResponse
from app.schemas.common import PaginationParams
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# Response Schemas
class QuizResponseWithContext(BaseModel):
    """Quiz response with additional context."""
    id: UUID
    patient_id: UUID
    quiz_template_id: UUID
    quiz_session_id: Optional[UUID]
    question_id: str
    question_text: str
    response_type: str
    response_value: str
    response_metadata: dict
    other_text: Optional[str]
    responded_at: datetime
    created_at: datetime
    
    # Additional context
    template_name: Optional[str] = None
    template_version: Optional[str] = None
    session_status: Optional[str] = None
    
    class Config:
        from_attributes = True


class PatientQuizResponsesResponse(BaseModel):
    """Paginated response for patient quiz responses."""
    items: List[QuizResponseWithContext]
    total: int
    page: int
    size: int
    pages: int
    
    class Config:
        from_attributes = True


class QuizSessionWithResponses(BaseModel):
    """Quiz session with all responses."""
    id: UUID
    patient_id: UUID
    quiz_template_id: UUID
    status: str
    current_question: int
    total_questions: Optional[int]
    answered_questions: Optional[int]
    score: Optional[float]
    max_score: Optional[float]
    passed: Optional[bool]
    started_at: datetime
    completed_at: Optional[datetime]
    time_spent_seconds: Optional[int]
    session_metadata: dict
    
    # Template info
    template_name: Optional[str] = None
    template_version: Optional[str] = None
    
    # Responses
    responses: List[QuizResponseWithContext] = []
    
    class Config:
        from_attributes = True


class QuizAnalysisResponse(BaseModel):
    """AI analysis and risk scores for a quiz session."""
    session_id: UUID
    patient_id: UUID
    template_name: str
    template_version: str
    completed_at: Optional[datetime]
    
    # AI Analysis from response_metadata
    risk_score: Optional[float] = Field(None, description="Overall risk score (0-100)")
    risk_level: Optional[str] = Field(None, description="Risk level: low, medium, high, critical")
    sentiment_score: Optional[float] = Field(None, description="Sentiment score (-1 to 1)")
    key_concerns: List[str] = Field(default_factory=list, description="Key concerns identified")
    recommendations: List[str] = Field(default_factory=list, description="AI recommendations")
    
    # Response summary
    total_responses: int
    flagged_responses: int = Field(0, description="Number of responses flagged for review")
    
    class Config:
        from_attributes = True


# Endpoint 1: Get patient quiz responses with pagination
@router.get(
    "/patients/{patient_id}/quiz-responses",
    response_model=PatientQuizResponsesResponse,
    summary="Get Patient Quiz Responses",
    description="Retrieve all quiz responses for a specific patient with pagination"
)
async def get_patient_quiz_responses(
    patient_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    session_id: Optional[UUID] = Query(None, description="Filter by quiz session ID"),
    template_id: Optional[UUID] = Query(None, description="Filter by quiz template ID"),
    start_date: Optional[datetime] = Query(None, description="Filter responses from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter responses until this date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all quiz responses for a patient with optional filtering.
    
    **Permissions**: Doctor must be assigned to the patient.
    **Performance**: Optimized with eager loading, target < 300ms.
    """
    # Verify patient exists and user has access
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    # Check authorization (doctor must be assigned to patient)
    if patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient's quiz responses"
        )
    
    # Build query with filters
    query = db.query(QuizResponse).filter(QuizResponse.patient_id == patient_id)
    
    if session_id:
        query = query.filter(QuizResponse.quiz_session_id == session_id)
    
    if template_id:
        query = query.filter(QuizResponse.quiz_template_id == template_id)
    
    if start_date:
        query = query.filter(QuizResponse.responded_at >= start_date)
    
    if end_date:
        query = query.filter(QuizResponse.responded_at <= end_date)
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    skip = (page - 1) * size
    pages = (total + size - 1) // size
    
    # Get paginated responses with eager loading
    responses = query.order_by(desc(QuizResponse.responded_at)).offset(skip).limit(size).all()
    
    # Enrich responses with template and session info
    enriched_responses = []
    for response in responses:
        # Get template info
        template = db.query(QuizTemplate).filter(QuizTemplate.id == response.quiz_template_id).first()
        
        # Get session info
        session = None
        if response.quiz_session_id:
            session = db.query(QuizSession).filter(QuizSession.id == response.quiz_session_id).first()
        
        enriched_response = QuizResponseWithContext(
            id=response.id,
            patient_id=response.patient_id,
            quiz_template_id=response.quiz_template_id,
            quiz_session_id=response.quiz_session_id,
            question_id=response.question_id,
            question_text=response.question_text,
            response_type=response.response_type,
            response_value=response.response_value,
            response_metadata=response.response_metadata or {},
            other_text=response.other_text,
            responded_at=response.responded_at,
            created_at=response.created_at,
            template_name=template.name if template else None,
            template_version=template.version if template else None,
            session_status=session.status if session else None
        )
        enriched_responses.append(enriched_response)
    
    logger.info(f"Retrieved {len(enriched_responses)} quiz responses for patient {patient_id}")
    
    return PatientQuizResponsesResponse(
        items=enriched_responses,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


# Endpoint 2: Get quiz session responses
@router.get(
    "/quiz/sessions/{session_id}/responses",
    response_model=QuizSessionWithResponses,
    summary="Get Quiz Session Responses",
    description="Retrieve a quiz session with all its responses"
)
async def get_quiz_session_responses(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a quiz session with all its responses.
    
    **Permissions**: Doctor must be assigned to the patient.
    **Performance**: Optimized with eager loading, target < 300ms.
    """
    # Get session
    session = db.query(QuizSession).filter(QuizSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz session not found"
        )
    
    # Verify patient access
    patient = db.query(Patient).filter(Patient.id == session.patient_id).first()
    if not patient or patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this quiz session"
        )
    
    # Get template info
    template = db.query(QuizTemplate).filter(QuizTemplate.id == session.quiz_template_id).first()
    
    # Get all responses for this session
    responses = db.query(QuizResponse).filter(
        QuizResponse.quiz_session_id == session_id
    ).order_by(QuizResponse.responded_at).all()
    
    # Enrich responses
    enriched_responses = [
        QuizResponseWithContext(
            id=r.id,
            patient_id=r.patient_id,
            quiz_template_id=r.quiz_template_id,
            quiz_session_id=r.quiz_session_id,
            question_id=r.question_id,
            question_text=r.question_text,
            response_type=r.response_type,
            response_value=r.response_value,
            response_metadata=r.response_metadata or {},
            other_text=r.other_text,
            responded_at=r.responded_at,
            created_at=r.created_at,
            template_name=template.name if template else None,
            template_version=template.version if template else None,
            session_status=session.status
        )
        for r in responses
    ]
    
    logger.info(f"Retrieved quiz session {session_id} with {len(enriched_responses)} responses")
    
    return QuizSessionWithResponses(
        id=session.id,
        patient_id=session.patient_id,
        quiz_template_id=session.quiz_template_id,
        status=session.status,
        current_question=session.current_question or 0,
        total_questions=session.total_questions,
        answered_questions=session.answered_questions,
        score=float(session.score) if session.score else None,
        max_score=float(session.max_score) if session.max_score else None,
        passed=session.passed,
        started_at=session.started_at,
        completed_at=session.completed_at,
        time_spent_seconds=session.time_spent_seconds,
        session_metadata=session.session_metadata or {},
        template_name=template.name if template else None,
        template_version=template.version if template else None,
        responses=enriched_responses
    )


# Endpoint 3: Get quiz session AI analysis
@router.get(
    "/quiz/sessions/{session_id}/analysis",
    response_model=QuizAnalysisResponse,
    summary="Get Quiz Session AI Analysis",
    description="Retrieve AI analysis and risk scores for a quiz session"
)
async def get_quiz_session_analysis(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get AI analysis and risk scores for a quiz session.

    Analyzes response_metadata from all responses to extract:
    - Risk scores and levels
    - Sentiment analysis
    - Key concerns
    - AI recommendations

    **Permissions**: Doctor must be assigned to the patient.
    **Performance**: Target < 300ms.
    """
    # Get session
    session = db.query(QuizSession).filter(QuizSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz session not found"
        )

    # Verify patient access
    patient = db.query(Patient).filter(Patient.id == session.patient_id).first()
    if not patient or patient.doctor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this quiz session"
        )

    # Get template info
    template = db.query(QuizTemplate).filter(QuizTemplate.id == session.quiz_template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz template not found"
        )

    # Get all responses for this session
    responses = db.query(QuizResponse).filter(
        QuizResponse.quiz_session_id == session_id
    ).all()

    # Aggregate AI analysis from response_metadata
    risk_scores = []
    sentiment_scores = []
    key_concerns = []
    recommendations = []
    flagged_count = 0

    for response in responses:
        metadata = response.response_metadata or {}

        # Extract risk score
        if 'risk_score' in metadata:
            risk_scores.append(float(metadata['risk_score']))

        # Extract sentiment
        if 'sentiment_score' in metadata:
            sentiment_scores.append(float(metadata['sentiment_score']))

        # Extract concerns
        if 'concerns' in metadata and isinstance(metadata['concerns'], list):
            key_concerns.extend(metadata['concerns'])

        # Extract recommendations
        if 'recommendations' in metadata and isinstance(metadata['recommendations'], list):
            recommendations.extend(metadata['recommendations'])

        # Check if flagged
        if metadata.get('flagged', False) or metadata.get('requires_review', False):
            flagged_count += 1

    # Calculate aggregate scores
    avg_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else None
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else None

    # Determine risk level
    risk_level = None
    if avg_risk_score is not None:
        if avg_risk_score >= 75:
            risk_level = "critical"
        elif avg_risk_score >= 50:
            risk_level = "high"
        elif avg_risk_score >= 25:
            risk_level = "medium"
        else:
            risk_level = "low"

    # Deduplicate concerns and recommendations
    unique_concerns = list(set(key_concerns))
    unique_recommendations = list(set(recommendations))

    logger.info(f"Generated AI analysis for quiz session {session_id}: risk_score={avg_risk_score}, risk_level={risk_level}")

    return QuizAnalysisResponse(
        session_id=session.id,
        patient_id=session.patient_id,
        template_name=template.name,
        template_version=template.version,
        completed_at=session.completed_at,
        risk_score=avg_risk_score,
        risk_level=risk_level,
        sentiment_score=avg_sentiment,
        key_concerns=unique_concerns[:10],  # Limit to top 10
        recommendations=unique_recommendations[:10],  # Limit to top 10
        total_responses=len(responses),
        flagged_responses=flagged_count
    )

