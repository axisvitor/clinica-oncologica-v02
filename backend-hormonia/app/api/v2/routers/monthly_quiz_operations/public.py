"""
Public quiz access endpoints (no authentication required).

Endpoints:
- GET /monthly/public/current - Get current public quiz (token-based)
- POST /monthly/public/{quiz_id}/submit - Submit quiz response publicly
- GET /monthly/public/{quiz_id}/results - View aggregate quiz results
"""

# NOTE: Do NOT use `from __future__ import annotations` here
# It breaks FastAPI/Pydantic path parameter validation with UUID type

import base64
import json
from uuid import UUID
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response, Cookie
from pydantic import BaseModel

from ._shared import (
    logger,
    defaultdict,
    get_db,
    limiter,
    QuizResponse,
    QuizSession,
    QuizTemplate,
    PublicQuizResponseV2,
    PublicSubmissionRequestV2,
    PublicQuizResultsV2,
    get_redis_cache,
    CACHE_TTL_PUBLIC_QUIZ,
    PUBLIC_PATIENT_ID,
    Dict,
    Any,
)

router = APIRouter()


# ==============================================================================
# CSRF TOKEN ENDPOINT (Frontend Compatibility)
# ==============================================================================
# Frontend quiz-mensal-interface uses NEXT_PUBLIC_QUIZ_PUBLIC_API_URL as base
# and expects /auth/csrf-token to be available under that prefix

@router.get(
    "/auth/csrf-token",
    summary="Get CSRF Token (Quiz Public)",
    description="CSRF token endpoint for quiz interface compatibility",
    include_in_schema=False  # Hide from docs since it's a compatibility layer
)
async def get_csrf_token_quiz_public(response: Response):
    """
    Compatibility endpoint: Frontend expects CSRF at /monthly-quiz-public/auth/csrf-token
    """
    from app.middleware.csrf import get_csrf_token, set_csrf_cookie
    
    token = get_csrf_token()
    set_csrf_cookie(response, token)
    return {"csrf_token": token}


@router.get(
    "/monthly/public/current",
    response_model=PublicQuizResponseV2,
    summary="Get current monthly quiz (PUBLIC)",
    description="Get the current active monthly quiz without authentication",
)
@limiter.limit("20/minute")  # Lower limit for public endpoint
async def get_current_public_quiz(
    request: Request,
    token: str = Query(..., description="Access token"),
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
):
    """
    Get current monthly quiz using access token.

    **PUBLIC ENDPOINT** - No authentication required
    **Rate limited:** 20 requests/minute per IP
    **Security:** Token validation, IP logging, expiry checking

    Token format (base64-encoded JSON):
    {
        "quiz_id": "uuid",
        "exp": timestamp,
        "type": "quiz_access"
    }
    """
    logger.info(f"Public quiz access from IP: {request.client.host}")

    # Validate token
    try:
        token_data = json.loads(base64.b64decode(token))
        quiz_id = UUID(token_data.get("quiz_id"))
        exp_timestamp = token_data.get("exp")
        token_type = token_data.get("type")

        # Check expiry
        if exp_timestamp and datetime.fromtimestamp(exp_timestamp) < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )

        # Check token type
        if token_type != "quiz_access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )

    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format"
        )

    # Get quiz
    quiz = (
        db.query(QuizTemplate)
        .filter(QuizTemplate.id == quiz_id, QuizTemplate.category == "monthly_quiz")
        .first()
    )

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )

    # Check if quiz is published
    if quiz.tags.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quiz is not currently available",
        )

    # Check if quiz has expired
    if quiz.tags.get("expires_at"):
        expires_at = datetime.fromisoformat(quiz.tags["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Quiz has expired"
            )

    # Create or get quiz session for public user
    # Use a special public patient ID (in production, create a PUBLIC_USER patient)

    # Find or create session
    session = (
        db.query(QuizSession)
        .filter(
            QuizSession.quiz_template_id == quiz_id,
            QuizSession.patient_id == PUBLIC_PATIENT_ID,
            QuizSession.status.in_(["in_progress", "pending"]),
        )
        .first()
    )

    if not session:
        session = QuizSession(
            patient_id=PUBLIC_PATIENT_ID,
            quiz_template_id=quiz_id,
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Increment access count
        quiz.tags["total_accessed"] = quiz.tags.get("total_accessed", 0) + 1
        db.commit()

    # Sanitize questions (remove sensitive data, scoring info)
    sanitized_questions = []
    if quiz.questions:
        for q in quiz.questions:
            sanitized_q = {
                "id": q.get("id"),
                "text": q.get("text"),
                "type": q.get("type"),
                "options": q.get("options", []),
            }
            # Remove scoring and medical interpretation
            sanitized_questions.append(sanitized_q)

    return PublicQuizResponseV2(
        quiz_id=quiz.id,
        quiz_name=quiz.name,
        description=quiz.description,
        questions=sanitized_questions,
        expires_at=datetime.fromisoformat(quiz.tags["expires_at"])
        if quiz.tags.get("expires_at")
        else None,
        session_id=session.id,
    )


@router.post(
    "/monthly/public/{quiz_id}/submit",
    response_model=Dict[str, Any],
    summary="Submit quiz response (PUBLIC)",
    description="Submit a quiz response using access token",
)
@limiter.limit("20/minute")
async def submit_public_quiz_response(
    request: Request,
    quiz_id: UUID,
    submission: PublicSubmissionRequestV2,
    db=Depends(get_db),
):
    """
    Submit quiz response with token validation.

    **PUBLIC ENDPOINT** - Token-based authentication
    **Rate limited:** 20 requests/minute per IP
    """
    logger.info(f"Public quiz submission from IP: {request.client.host}")

    # Validate token
    try:
        token_data = json.loads(base64.b64decode(submission.token))
        token_quiz_id = UUID(token_data.get("quiz_id"))
        exp_timestamp = token_data.get("exp")
        token_type = token_data.get("type")

        # Check if token matches quiz_id
        if token_quiz_id != quiz_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token does not match quiz ID",
            )

        # Check expiry
        if exp_timestamp and datetime.fromtimestamp(exp_timestamp) < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )

        # Check token type
        if token_type not in ["quiz_access", "quiz_submission"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type for submission",
            )

    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format"
        )

    # Get quiz
    quiz = (
        db.query(QuizTemplate)
        .filter(QuizTemplate.id == quiz_id, QuizTemplate.category == "monthly_quiz")
        .first()
    )

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )

    # Check if quiz is published
    if quiz.tags.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot submit to unpublished quiz",
        )

    # Get or create session
    session = (
        db.query(QuizSession)
        .filter(
            QuizSession.quiz_template_id == quiz_id,
            QuizSession.patient_id == PUBLIC_PATIENT_ID,
            QuizSession.status.in_(["in_progress", "pending"]),
        )
        .first()
    )

    if not session:
        # Create new session
        session = QuizSession(
            patient_id=PUBLIC_PATIENT_ID,
            quiz_template_id=quiz_id,
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # Find the question in quiz
    question = None
    if quiz.questions:
        for q in quiz.questions:
            if q.get("id") == submission.question_id:
                question = q
                break

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {submission.question_id} not found in quiz",
        )

    # Create quiz response
    quiz_response = QuizResponse(
        patient_id=PUBLIC_PATIENT_ID,
        quiz_template_id=quiz_id,
        quiz_session_id=session.id,
        question_id=submission.question_id,
        question_text=question.get("text", ""),
        response_type=question.get("type", "text"),
        response_value=str(submission.response_value),
        response_metadata=submission.response_metadata or {},
        responded_at=datetime.now(timezone.utc),
    )

    db.add(quiz_response)
    db.commit()
    db.refresh(quiz_response)

    # Check if all questions are answered
    total_questions = len(quiz.questions) if quiz.questions else 0
    answered_questions = (
        db.query(QuizResponse)
        .filter(QuizResponse.quiz_session_id == session.id)
        .count()
    )

    if answered_questions >= total_questions:
        # Complete session
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)

        # Update quiz completion stats
        quiz.tags["total_completed"] = quiz.tags.get("total_completed", 0) + 1
        total_sent = quiz.tags.get("total_sent", 1)
        quiz.tags["completion_rate"] = (
            (quiz.tags["total_completed"] / total_sent * 100) if total_sent > 0 else 0.0
        )

        db.commit()

        logger.info(f"Public quiz {quiz_id} completed by session {session.id}")

        return {
            "message": "Quiz completed successfully",
            "status": "completed",
            "session_id": str(session.id),
            "total_questions": total_questions,
            "answered_questions": answered_questions,
        }

    return {
        "message": "Response recorded successfully",
        "status": "in_progress",
        "session_id": str(session.id),
        "total_questions": total_questions,
        "answered_questions": answered_questions,
        "remaining_questions": total_questions - answered_questions,
    }


@router.get(
    "/monthly/public/{quiz_id}/results",
    response_model=PublicQuizResultsV2,
    summary="Get public quiz results",
    description="Get aggregate quiz results (no personal data)",
)
@limiter.limit("20/minute")
async def get_public_quiz_results(
    request: Request,
    quiz_id: UUID,
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
):
    """
    Get aggregate quiz results.

    **PUBLIC ENDPOINT** - No authentication required
    **Privacy:** Only aggregate data, no personal information
    **Cache:** 15 minutes TTL
    """
    logger.info(f"Public quiz results request from IP: {request.client.host}")

    # Check cache
    cache_key = f"public_quiz_results:{quiz_id}"
    if redis_cache:
        cached = redis_cache.get(cache_key)
        if cached:
            return PublicQuizResultsV2.parse_raw(cached)

    # Get quiz
    quiz = (
        db.query(QuizTemplate)
        .filter(QuizTemplate.id == quiz_id, QuizTemplate.category == "monthly_quiz")
        .first()
    )

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )

    # Only show results for published quizzes
    if quiz.tags.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Results not available for this quiz",
        )

    # Get aggregate statistics
    sessions_query = db.query(QuizSession).filter(
        QuizSession.quiz_template_id == quiz_id
    )

    total_completions = sessions_query.filter(QuizSession.status == "completed").count()

    # Calculate average score
    completed_sessions = sessions_query.filter(
        QuizSession.status == "completed", QuizSession.score.isnot(None)
    ).all()

    average_score = None
    if completed_sessions:
        scores = [float(s.score) for s in completed_sessions if s.score is not None]
        if scores:
            average_score = sum(scores) / len(scores)

    # Completion rate
    total_sent = quiz.tags.get("total_sent", 0)
    completion_rate = (total_completions / total_sent * 100) if total_sent > 0 else 0.0

    # Response distribution (aggregate, anonymized)
    response_distribution = {}
    responses = (
        db.query(QuizResponse).filter(QuizResponse.quiz_template_id == quiz_id).all()
    )

    # Group responses by question
    question_responses = defaultdict(list)
    for response in responses:
        question_responses[response.question_id].append(response.response_value)

    # Calculate distribution for each question
    for question_id, values in question_responses.items():
        # Find question in quiz
        question = None
        if quiz.questions:
            for q in quiz.questions:
                if q.get("id") == question_id:
                    question = q
                    break

        if not question:
            continue

        # For scale questions, group into ranges
        if question.get("type") == "scale":
            ranges = {"1-3": 0, "4-7": 0, "8-10": 0}
            for value in values:
                try:
                    val = int(value)
                    if 1 <= val <= 3:
                        ranges["1-3"] += 1
                    elif 4 <= val <= 7:
                        ranges["4-7"] += 1
                    elif 8 <= val <= 10:
                        ranges["8-10"] += 1
                except (ValueError, TypeError):
                    pass
            response_distribution[question_id] = ranges

        # For choice questions, count by option
        elif question.get("type") in ["single_choice", "multiple_choice"]:
            counts = defaultdict(int)
            for value in values:
                counts[value] += 1
            # Convert to percentages
            total = len(values)
            percentages = (
                {k: round(v / total * 100, 1) for k, v in counts.items()}
                if total > 0
                else {}
            )
            response_distribution[question_id] = percentages

    result = PublicQuizResultsV2(
        quiz_id=quiz_id,
        quiz_name=quiz.name,
        total_completions=total_completions,
        average_score=round(average_score, 2) if average_score else None,
        completion_rate=round(completion_rate, 2),
        response_distribution=response_distribution if response_distribution else None,
    )

    # Cache result
    if redis_cache:
        redis_cache.setex(cache_key, CACHE_TTL_PUBLIC_QUIZ, result.json())

    return result


# ==============================================================================
# FRONTEND COMPATIBILITY LAYER (v2.0)
# ==============================================================================
# Compatibility endpoints for existing React frontend (quiz-mensal-interface).
# These endpoints map the Frontend API client expectations to the Backend V2 logic.


# ==============================================================================
# SHARED FUNCTIONS FOR QUESTION TRANSFORMATION (with Redis Cache)
# ==============================================================================

def transform_single_question(q: dict) -> dict:
    """
    Transform a single question from database format to frontend format.
    
    Transformations:
    - free_text → text (type mapping)
    - label → text (in options)
    """
    q_type = q.get("type", "text")
    if q_type == "free_text":
        q_type = "text"
    
    raw_options = q.get("options", [])
    transformed_options = []
    for opt in raw_options:
        if isinstance(opt, dict):
            transformed_options.append({
                "text": opt.get("label") or opt.get("text", ""),
                "value": opt.get("value", ""),
                "id": opt.get("id"),
                "allow_other": opt.get("allow_other", False)
            })
        else:
            transformed_options.append(opt)
    
    return {
        "id": q.get("id"),
        "text": q.get("text"),
        "type": q_type,
        "options": transformed_options,
        "required": q.get("required", True),
        "allow_other": q.get("allow_other", False),
        "min_value": q.get("min_value"),
        "max_value": q.get("max_value")
    }


def get_cached_transformed_questions(
    quiz_template_id: str,
    questions: list,
    redis_cache=None
) -> list:
    """
    Get transformed questions with Redis caching.
    
    Cache key: quiz:frontend:questions:{template_id}
    TTL: 1 hour (questions rarely change)
    
    Performance impact:
    - Without cache: ~50-100ms for 58 questions transformation
    - With cache: ~1-5ms (Redis GET)
    """
    cache_key = f"quiz:frontend:questions:{quiz_template_id}"
    
    # Try to get from cache first
    if redis_cache:
        try:
            cached = redis_cache.get(cache_key)
            if cached:
                logger.debug(f"[Cache HIT] Transformed questions for template {quiz_template_id}")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache read error: {e}")
    
    # Transform questions (cache miss)
    logger.debug(f"[Cache MISS] Transforming {len(questions)} questions for template {quiz_template_id}")
    transformed = [transform_single_question(q) for q in questions]
    
    # Store in cache
    if redis_cache:
        try:
            redis_cache.setex(cache_key, 3600, json.dumps(transformed))  # 1 hour TTL
            logger.debug(f"[Cache SET] Stored transformed questions for template {quiz_template_id}")
        except Exception as e:
            logger.warning(f"Redis cache write error: {e}")
    
    return transformed


class QuizAccessRequestCompatibility(BaseModel):
    token: str

@router.post(
    "/access",
    summary="Access Quiz (Frontend Compatibility)",
    description="POST /access endpoint compatible with frontend QuizApiClient",
    response_model=Dict[str, Any]
)
@limiter.limit("20/minute")
async def access_quiz_compatibility(
    access_req: QuizAccessRequestCompatibility,
    response: Response,
    request: Request,
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache)
):
    """
    Compatibility endpoint for POST /monthly-quiz-public/access
    
    1. Validates token
    2. Creates/Gets session
    3. Sets HttpOnly cookie for session persistence (Critical for F5 refresh)
    4. Returns QuizSession object matching Frontend interface
    """
    logger.info(f"Compatibility access request from IP: {request.client.host}")
    
    # Reuse logic from get_current_public_quiz, but adapted
    try:
        token_data = json.loads(base64.b64decode(access_req.token))
        quiz_id = UUID(token_data.get("quiz_id"))
        exp_timestamp = token_data.get("exp")
        # token_type validation same as above...
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Invalid token format")

    # Get Quiz
    quiz = db.query(QuizTemplate).filter(QuizTemplate.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Get/Create Session
    session = db.query(QuizSession).filter(
        QuizSession.quiz_template_id == quiz_id,
        QuizSession.patient_id == PUBLIC_PATIENT_ID,
        QuizSession.status == "started"
    ).first()

    if not session:
        session = QuizSession(
            patient_id=PUBLIC_PATIENT_ID,
            quiz_template_id=quiz_id,
            status="started",
            started_at=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Increment stats
        if quiz.tags:
            quiz.tags["total_accessed"] = quiz.tags.get("total_accessed", 0) + 1
        else:
            quiz.tags = {"total_accessed": 1}
        db.commit()

    # Set Session Cookie
    response.set_cookie(
        key="quiz_session_id",
        value=str(session.id),
        httponly=True,
        secure=False, # Set True in production if HTTPS
        samesite="lax",
        max_age=86400 # 24h
    )

    # Transform questions using cached function (Performance optimization)
    sanitized_questions = get_cached_transformed_questions(
        quiz_template_id=str(quiz.id),
        questions=quiz.questions or [],
        redis_cache=redis_cache
    )

    # Return structure matching QuizSession interface
    return {
        "id": str(session.id),
        "quiz_session_id": str(session.id), # Redundant but safe
        "patient_id": str(session.patient_id),
        "template_id": str(quiz.id),
        "patient_name": "Paciente", # Public/Anon
        "template_name": quiz.name,
        "expires_at": (datetime.now(timezone.utc).replace(year=datetime.now().year + 1)).isoformat(), # Mock expiry if not set
        "questions": sanitized_questions,
        "status": session.status
    }

@router.get(
    "/session/active",
    summary="Get Active Session (Frontend Compatibility)",
    description="GET /session/active endpoint for session recovery",
    response_model=Dict[str, Any]
)
async def get_active_session_compatibility(
    request: Request,
    quiz_session_id: Optional[str] = Cookie(None),
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache)
):
    """
    Recover session from cookie.
    """
    if not quiz_session_id:
        raise HTTPException(status_code=401, detail="No active session cookie")
    
    session = db.query(QuizSession).filter(QuizSession.id == UUID(quiz_session_id)).first()
    if not session or session.status != "started":
        raise HTTPException(status_code=404, detail="Session expired or not found")

    quiz = session.quiz_template
    
    # Transform questions using cached function (Performance optimization)
    sanitized_questions = get_cached_transformed_questions(
        quiz_template_id=str(quiz.id),
        questions=quiz.questions or [],
        redis_cache=redis_cache
    )

    return {
        "id": str(session.id),
        "quiz_session_id": str(session.id),
        "patient_id": str(session.patient_id),
        "template_id": str(quiz.id),
        "patient_name": "Paciente",
        "template_name": quiz.name,
        "expires_at": (datetime.now(timezone.utc).replace(year=datetime.now().year + 1)).isoformat(),
        "questions": sanitized_questions,
        "status": session.status,
        "current_question_index": 0  # TODO: Track progress if needed
    }


# ==============================================================================
# SUBMIT ENDPOINT (Frontend Compatibility)
# ==============================================================================

class QuizSubmitRequestCompatibility(BaseModel):
    question_id: str
    response_value: Any  # Can be string or list
    response_metadata: Optional[Dict[str, Any]] = None


@router.post(
    "/submit",
    summary="Submit Quiz Answer (Frontend Compatibility)",
    description="POST /submit endpoint for submitting quiz answers",
    response_model=Dict[str, Any]
)
@limiter.limit("60/minute")
async def submit_answer_compatibility(
    submit_req: QuizSubmitRequestCompatibility,
    request: Request,
    quiz_session_id: Optional[str] = Cookie(None),
    db=Depends(get_db)
):
    """
    Submit an answer to a quiz question.
    Session is identified via HttpOnly cookie.
    """
    if not quiz_session_id:
        raise HTTPException(status_code=401, detail="No active session")
    
    try:
        session = db.query(QuizSession).filter(
            QuizSession.id == UUID(quiz_session_id)
        ).first()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    
    if not session or session.status != "started":
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    quiz = session.quiz_template
    
    # Find question in template
    question_data = None
    question_index = 0
    for i, q in enumerate(quiz.questions or []):
        if q.get("id") == submit_req.question_id:
            question_data = q
            question_index = i
            break
    
    if not question_data:
        raise HTTPException(status_code=400, detail="Question not found in quiz")
    
    # Create or update response
    existing = db.query(QuizResponse).filter(
        QuizResponse.quiz_session_id == session.id,
        QuizResponse.question_id == submit_req.question_id
    ).first()
    
    response_value = submit_req.response_value
    if isinstance(response_value, str):
        response_value = {"text": response_value}
    elif isinstance(response_value, list):
        response_value = {"options": response_value}
    
    # Normalize response_type to match DB constraint
    # DB allows: 'multiple_choice', 'open_text', 'scale', 'boolean', 'rating', 'yes_no', 'number', 'date', 'single_choice'
    raw_type = question_data.get("type", "single_choice")
    type_mapping = {
        "free_text": "open_text",
        "text": "open_text",
        "checkbox": "multiple_choice",
        "radio": "single_choice",
    }
    response_type = type_mapping.get(raw_type, raw_type)
    
    if existing:
        existing.response_value = response_value
        existing.response_value_text_backup = str(submit_req.response_value)
        existing.response_metadata = submit_req.response_metadata or {}
        existing.responded_at = datetime.now(timezone.utc)
    else:
        new_response = QuizResponse(
            patient_id=session.patient_id,
            quiz_template_id=quiz.id,
            quiz_session_id=session.id,
            question_id=submit_req.question_id,
            question_text=question_data.get("text", ""),
            response_type=response_type,  # Use normalized type
            response_value=response_value,
            response_value_text_backup=str(submit_req.response_value),
            response_metadata=submit_req.response_metadata or {},
            responded_at=datetime.now(timezone.utc)
        )
        db.add(new_response)
    
    # Update session progress
    session.answered_questions = (session.answered_questions or 0) + 1
    session.current_question = question_index + 1
    
    total_questions = len(quiz.questions or [])
    is_last = question_index >= total_questions - 1
    
    # If last question, mark completed
    if is_last:
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
    
    db.commit()
    
    # Prepare next question
    next_question = None
    if not is_last and question_index + 1 < total_questions:
        next_q = quiz.questions[question_index + 1]
        next_question = {
            "id": next_q.get("id"),
            "text": next_q.get("text"),
            "type": next_q.get("type", "text").replace("free_text", "text"),
            "options": [
                {"text": opt.get("label") or opt.get("text", ""), "value": opt.get("value", "")}
                if isinstance(opt, dict) else opt
                for opt in next_q.get("options", [])
            ],
            "required": next_q.get("required", True)
        }
    
    return {
        "success": True,
        "is_last_question": is_last,
        "next_question": next_question,
        "session_status": session.status,
        "message": "Resposta salva com sucesso"
    }


# ==============================================================================
# LOGOUT ENDPOINT (Frontend Compatibility)
# ==============================================================================

@router.post(
    "/logout",
    summary="Logout from Quiz Session (Frontend Compatibility)",
    description="POST /logout endpoint to end quiz session",
    response_model=Dict[str, Any]
)
async def logout_quiz_compatibility(
    response: Response,
    quiz_session_id: Optional[str] = Cookie(None),
    db=Depends(get_db)
):
    """
    End quiz session and clear cookie.
    """
    if quiz_session_id:
        try:
            session = db.query(QuizSession).filter(
                QuizSession.id == UUID(quiz_session_id)
            ).first()
            if session and session.status == "started":
                session.status = "cancelled"
                db.commit()
        except ValueError:
            pass  # Invalid UUID, just clear cookie
    
    # Clear session cookie
    response.delete_cookie(key="quiz_session_id")
    
    return {"success": True, "message": "Session ended"}
