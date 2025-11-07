"""
Quiz Responses API v2
Endpoints for submitting and analyzing quiz responses.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.database import get_db
from app.models.quiz import QuizSession, QuizResponse, QuizTemplate
from app.models.patient import Patient
from app.models.user import UserRole
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.utils.rate_limiter import limiter
from .dependencies import get_pagination_params, get_field_selection, apply_field_selection
from .quiz import _extract_user_context, _ensure_uuid, _ensure_patient_owner

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class QuizResponseItemV2(BaseModel):
    """Individual quiz response for submission"""
    question_id: str = Field(..., description="Question ID")
    answer: str = Field(..., description="Answer value")
    points: Optional[float] = Field(None, ge=0, description="Points earned")


class QuizSubmitRequestV2(BaseModel):
    """Request schema for submitting quiz responses"""
    responses: List[QuizResponseItemV2] = Field(..., min_length=1, description="List of responses")


class QuizSubmitResponseV2(BaseModel):
    """Response schema for quiz submission"""
    session_id: str = Field(..., description="Quiz session ID")
    score: float = Field(..., description="Total score")
    max_score: float = Field(..., description="Maximum possible score")
    percentage: float = Field(..., description="Score percentage")
    completion_time: int = Field(..., description="Completion time in seconds")
    analysis: Dict[str, Any] = Field(..., description="Quiz analysis and recommendations")


class QuizSessionResponseItemV2(BaseModel):
    """Individual response within a session"""
    id: str = Field(..., description="Response ID")
    question_id: str = Field(..., description="Question ID")
    question_text: str = Field(..., description="Question text")
    response_type: str = Field(..., description="Response type")
    response_value: str = Field(..., description="Response value")
    points: Optional[float] = Field(None, description="Points earned")
    responded_at: datetime = Field(..., description="Response timestamp")

    class Config:
        from_attributes = True


class QuizSessionResponsesV2(BaseModel):
    """All responses for a quiz session"""
    session_id: str = Field(..., description="Quiz session ID")
    patient_id: str = Field(..., description="Patient ID")
    template_id: str = Field(..., description="Template ID")
    status: str = Field(..., description="Session status")
    responses: List[QuizSessionResponseItemV2] = Field(..., description="List of responses")
    total_responses: int = Field(..., description="Total number of responses")


class QuizSessionAnalysisV2(BaseModel):
    """Detailed analysis of quiz session"""
    session_id: str = Field(..., description="Quiz session ID")
    score: float = Field(..., description="Total score")
    max_score: float = Field(..., description="Maximum possible score")
    percentage: float = Field(..., description="Score percentage")
    passed: bool = Field(..., description="Whether quiz was passed")
    strengths: List[str] = Field(default_factory=list, description="Areas of strength")
    weaknesses: List[str] = Field(default_factory=list, description="Areas needing improvement")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    question_breakdown: List[Dict[str, Any]] = Field(default_factory=list, description="Per-question analysis")


class TemplateAnalyticsV2(BaseModel):
    """Analytics for a quiz template"""
    template_id: str = Field(..., description="Template ID")
    template_name: str = Field(..., description="Template name")
    total_sessions: int = Field(..., description="Total number of sessions")
    completed_sessions: int = Field(..., description="Number of completed sessions")
    completion_rate: float = Field(..., description="Completion rate percentage")
    average_score: Optional[float] = Field(None, description="Average score")
    average_completion_time: Optional[int] = Field(None, description="Average completion time in seconds")
    pass_rate: Optional[float] = Field(None, description="Pass rate percentage")
    question_stats: List[Dict[str, Any]] = Field(default_factory=list, description="Per-question statistics")


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/{session_id}/submit",
    response_model=QuizSubmitResponseV2,
    summary="Submit quiz responses",
    description="Submit responses for a quiz session and calculate score"
)
@limiter.limit("30/minute")
async def submit_quiz_responses(
    request: Request,
    session_id: str,
    submission_data: QuizSubmitRequestV2,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """Submit quiz responses and calculate final score."""
    # Validate session UUID
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session UUID format"
        )

    # Get quiz session
    query = db.query(QuizSession)
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        query = query.join(Patient).filter(Patient.doctor_id == current_user_uuid)

    quiz_session = query.filter(QuizSession.id == session_uuid).first()

    if not quiz_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz session with id {session_id} not found"
        )

    # Check if already completed
    if quiz_session.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Quiz session already completed"
        )

    # Calculate score
    total_score = sum(r.points for r in submission_data.responses if r.points is not None)
    max_score = len(submission_data.responses) * 10.0  # Assuming 10 points per question
    percentage = (total_score / max_score * 100) if max_score > 0 else 0

    # Calculate completion time
    completion_time = 0
    if quiz_session.started_at:
        completion_time = int((datetime.utcnow() - quiz_session.started_at).total_seconds())

    # Generate analysis
    passed = percentage >= 70.0
    analysis = {
        "passed": passed,
        "recommendations": [],
        "areas_for_improvement": [],
        "strengths": []
    }

    if passed:
        analysis["recommendations"].append("Excellent work! You've demonstrated strong understanding.")
        analysis["strengths"].append("Met all learning objectives")
    else:
        analysis["recommendations"].append("Review the material and try again.")
        analysis["areas_for_improvement"].append("Needs improvement in core concepts")

    # Update session
    quiz_session.status = "completed"
    quiz_session.completed_at = datetime.utcnow()
    quiz_session.score = total_score
    quiz_session.max_score = max_score
    quiz_session.passed = passed
    quiz_session.time_spent_seconds = completion_time
    quiz_session.answered_questions = len(submission_data.responses)

    # Store responses in database
    for response_data in submission_data.responses:
        existing_response = db.query(QuizResponse).filter(
            and_(
                QuizResponse.quiz_session_id == session_uuid,
                QuizResponse.question_id == response_data.question_id
            )
        ).first()

        if not existing_response:
            new_response = QuizResponse(
                patient_id=quiz_session.patient_id,
                quiz_template_id=quiz_session.quiz_template_id,
                quiz_session_id=session_uuid,
                question_id=response_data.question_id,
                question_text=f"Question {response_data.question_id}",
                response_type="single_choice",
                response_value=response_data.answer,
                response_metadata={"points": response_data.points},
                responded_at=datetime.utcnow()
            )
            db.add(new_response)

    db.commit()
    db.refresh(quiz_session)

    # Invalidate cache
    cache_key_pattern = f"quiz:session:{session_id}:*"
    try:
        keys_to_delete = [
            f"quiz:session:{session_id}:responses",
            f"quiz:session:{session_id}:analysis"
        ]
        for key in keys_to_delete:
            await redis_cache.delete(key)
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")

    return {
        "session_id": str(quiz_session.id),
        "score": float(quiz_session.score) if quiz_session.score else 0.0,
        "max_score": float(quiz_session.max_score) if quiz_session.max_score else 0.0,
        "percentage": percentage,
        "completion_time": completion_time,
        "analysis": analysis
    }


@router.get(
    "/{session_id}/responses",
    response_model=QuizSessionResponsesV2,
    summary="Get session responses",
    description="Get all responses for a quiz session"
)
@limiter.limit("50/minute")
async def get_session_responses(
    request: Request,
    session_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """Get all responses for a quiz session."""
    # Check cache first
    cache_key = f"quiz:session:{session_id}:responses"
    try:
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for session responses: {cache_key}")
            return cached_data
    except Exception as e:
        logger.warning(f"Cache retrieval failed: {e}")

    # Validate session UUID
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session UUID format"
        )

    # Get quiz session
    query = db.query(QuizSession)
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        query = query.join(Patient).filter(Patient.doctor_id == current_user_uuid)

    quiz_session = query.filter(QuizSession.id == session_uuid).first()

    if not quiz_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz session with id {session_id} not found"
        )

    # Get all responses for this session
    responses = db.query(QuizResponse).filter(
        QuizResponse.quiz_session_id == session_uuid
    ).order_by(QuizResponse.responded_at).all()

    # Build response
    response_items = []
    for resp in responses:
        points = None
        if resp.response_metadata and isinstance(resp.response_metadata, dict):
            points = resp.response_metadata.get("points")

        response_items.append({
            "id": str(resp.id),
            "question_id": resp.question_id,
            "question_text": resp.question_text,
            "response_type": resp.response_type,
            "response_value": resp.response_value,
            "points": points,
            "responded_at": resp.responded_at
        })

    result = {
        "session_id": str(quiz_session.id),
        "patient_id": str(quiz_session.patient_id),
        "template_id": str(quiz_session.quiz_template_id),
        "status": quiz_session.status,
        "responses": response_items,
        "total_responses": len(response_items)
    }

    # Cache the result (10 minutes)
    try:
        await redis_cache.set(cache_key, result, ttl=600)
    except Exception as e:
        logger.warning(f"Cache storage failed: {e}")

    return result


@router.get(
    "/{session_id}/analysis",
    response_model=QuizSessionAnalysisV2,
    summary="Get session analysis",
    description="Get detailed analysis of quiz session responses"
)
@limiter.limit("50/minute")
async def get_session_analysis(
    request: Request,
    session_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """Get detailed analysis of quiz session."""
    # Check cache first
    cache_key = f"quiz:session:{session_id}:analysis"
    try:
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for session analysis: {cache_key}")
            return cached_data
    except Exception as e:
        logger.warning(f"Cache retrieval failed: {e}")

    # Validate session UUID
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session UUID format"
        )

    # Get quiz session
    query = db.query(QuizSession)
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        query = query.join(Patient).filter(Patient.doctor_id == current_user_uuid)

    quiz_session = query.filter(QuizSession.id == session_uuid).first()

    if not quiz_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz session with id {session_id} not found"
        )

    # Check if session is completed
    if quiz_session.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session must be completed to generate analysis"
        )

    # Get responses for analysis
    responses = db.query(QuizResponse).filter(
        QuizResponse.quiz_session_id == session_uuid
    ).all()

    # Calculate metrics
    score = float(quiz_session.score) if quiz_session.score else 0.0
    max_score = float(quiz_session.max_score) if quiz_session.max_score else 100.0
    percentage = (score / max_score * 100) if max_score > 0 else 0
    passed = quiz_session.passed or percentage >= 70.0

    # Generate analysis
    strengths = []
    weaknesses = []
    recommendations = []
    question_breakdown = []

    if passed:
        strengths.append("Strong overall performance")
        if percentage >= 90:
            strengths.append("Exceptional understanding of all concepts")
            recommendations.append("Continue with advanced topics")
        else:
            recommendations.append("Good progress, keep up the work")
    else:
        weaknesses.append("Overall score below passing threshold")
        recommendations.append("Review core concepts and retake quiz")

    # Analyze individual responses
    for resp in responses:
        points = 0
        if resp.response_metadata and isinstance(resp.response_metadata, dict):
            points = resp.response_metadata.get("points", 0)

        question_breakdown.append({
            "question_id": resp.question_id,
            "question_text": resp.question_text,
            "response": resp.response_value,
            "points": points,
            "correct": points > 0
        })

    result = {
        "session_id": str(quiz_session.id),
        "score": score,
        "max_score": max_score,
        "percentage": percentage,
        "passed": passed,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "question_breakdown": question_breakdown
    }

    # Cache the result (15 minutes)
    try:
        await redis_cache.set(cache_key, result, ttl=900)
    except Exception as e:
        logger.warning(f"Cache storage failed: {e}")

    return result


@router.get(
    "/templates/{template_id}/analytics",
    response_model=TemplateAnalyticsV2,
    summary="Get template analytics",
    description="Get analytics for a quiz template"
)
@limiter.limit("50/minute")
async def get_template_analytics(
    request: Request,
    template_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """Get analytics for a quiz template."""
    # Check cache first
    cache_key = f"quiz:template:{template_id}:analytics"
    try:
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for template analytics: {cache_key}")
            return cached_data
    except Exception as e:
        logger.warning(f"Cache retrieval failed: {e}")

    # Validate template UUID
    try:
        template_uuid = UUID(template_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template UUID format"
        )

    # Get template
    template = db.query(QuizTemplate).filter(QuizTemplate.id == template_uuid).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz template with id {template_id} not found"
        )

    # Get all sessions for this template
    query = db.query(QuizSession).filter(QuizSession.quiz_template_id == template_uuid)

    # Check role-based access
    role_enum, user_id = _extract_user_context(current_user)
    current_user_uuid = _ensure_uuid(user_id)

    if role_enum != UserRole.ADMIN:
        if current_user_uuid is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions",
            )
        # Filter by doctor's patients
        query = query.join(Patient).filter(Patient.doctor_id == current_user_uuid)

    all_sessions = query.all()
    total_sessions = len(all_sessions)

    # Calculate metrics
    completed_sessions = [s for s in all_sessions if s.status == "completed"]
    completed_count = len(completed_sessions)
    completion_rate = (completed_count / total_sessions * 100) if total_sessions > 0 else 0.0

    # Calculate average score
    average_score = None
    if completed_sessions:
        scores = [float(s.score) for s in completed_sessions if s.score is not None]
        if scores:
            average_score = sum(scores) / len(scores)

    # Calculate average completion time
    average_completion_time = None
    if completed_sessions:
        times = [s.time_spent_seconds for s in completed_sessions if s.time_spent_seconds is not None]
        if times:
            average_completion_time = sum(times) // len(times)

    # Calculate pass rate
    pass_rate = None
    if completed_sessions:
        passed = [s for s in completed_sessions if s.passed]
        pass_rate = (len(passed) / len(completed_sessions) * 100)

    # Get question statistics
    question_stats = []
    responses = db.query(QuizResponse).filter(
        QuizResponse.quiz_template_id == template_uuid
    ).all()

    # Group responses by question
    question_groups = {}
    for resp in responses:
        if resp.question_id not in question_groups:
            question_groups[resp.question_id] = []
        question_groups[resp.question_id].append(resp)

    # Calculate stats per question
    for question_id, question_responses in question_groups.items():
        total_answers = len(question_responses)
        if total_answers > 0:
            question_stats.append({
                "question_id": question_id,
                "total_responses": total_answers,
                "most_common_answer": question_responses[0].response_value if question_responses else None
            })

    result = {
        "template_id": str(template.id),
        "template_name": template.name,
        "total_sessions": total_sessions,
        "completed_sessions": completed_count,
        "completion_rate": round(completion_rate, 2),
        "average_score": round(average_score, 2) if average_score is not None else None,
        "average_completion_time": average_completion_time,
        "pass_rate": round(pass_rate, 2) if pass_rate is not None else None,
        "question_stats": question_stats
    }

    # Cache the result (15 minutes)
    try:
        await redis_cache.set(cache_key, result, ttl=900)
    except Exception as e:
        logger.warning(f"Cache storage failed: {e}")

    return result
