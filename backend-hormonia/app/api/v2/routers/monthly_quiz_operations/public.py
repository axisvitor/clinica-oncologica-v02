"""
Public quiz access endpoints (no authentication required).

Endpoints:
- GET /monthly/public/current - Get current public quiz (token-based)
- POST /monthly/public/{quiz_id}/submit - Submit quiz response publicly
- GET /monthly/public/{quiz_id}/results - View aggregate quiz results
"""

# NOTE: Do NOT use `from __future__ import annotations` here
# It breaks FastAPI/Pydantic path parameter validation with UUID type

import asyncio
import inspect
import json
import jwt
from uuid import UUID
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response, Cookie
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.domain.quizzes.session import TokenManager
from ._shared import (
    logger,
    defaultdict,
    get_async_db,
    limiter,
    QuizResponse,
    QuizSession,
    QuizTemplate,
    PublicQuizResponseV2,
    PublicSubmissionRequestV2,
    PublicQuizResultsV2,
    get_redis_cache,
    CACHE_TTL_PUBLIC_QUIZ,
)
from app.utils.timezone import now_sao_paulo

router = APIRouter()


async def _maybe_await(value):
    """Await cache operations when providers expose async methods."""
    if inspect.isawaitable(value):
        return await value
    return value


async def _cache_get(redis_cache, key: str):
    if not redis_cache:
        return None
    getter = getattr(redis_cache, "get", None)
    if not callable(getter):
        return None
    try:
        return await asyncio.wait_for(_maybe_await(getter(key)), timeout=1.0)
    except Exception:
        return None


async def _cache_set(redis_cache, key: str, value: str, ttl: int) -> None:
    if not redis_cache:
        return

    setex = getattr(redis_cache, "setex", None)
    if callable(setex):
        try:
            await asyncio.wait_for(_maybe_await(setex(key, ttl, value)), timeout=1.0)
        except Exception:
            pass
        return

    setter = getattr(redis_cache, "set", None)
    if not callable(setter):
        return

    try:
        await asyncio.wait_for(_maybe_await(setter(key, value, ttl)), timeout=1.0)
    except TypeError:
        try:
            await asyncio.wait_for(_maybe_await(setter(key, value)), timeout=1.0)
        except Exception:
            pass
    except Exception:
        pass


def _decode_quiz_token(token: str) -> Dict[str, Any]:
    """
    Decode quiz access token.

    Supports signed JWT tokens only.
    """
    token = token.strip()

    if token.count(".") != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format"
        )

    try:
        payload = TokenManager().verify_token(token)
        return {
            "quiz_id": payload.get("quiz_template_id"),
            "patient_id": payload.get("patient_id"),
            "session_id": payload.get("session_id"),
            "exp": payload.get("exp"),
            "type": payload.get("type", "quiz_access"),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format"
        )


# ==============================================================================
# CSRF TOKEN ENDPOINT
# ==============================================================================

@router.get(
    "/auth/csrf-token",
    summary="Get CSRF Token (Quiz Public)",
    description="CSRF token endpoint for quiz interface",
    include_in_schema=False
)
async def get_csrf_token_quiz_public(response: Response):
    """Return CSRF token for quiz public flows."""
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
    db: AsyncSession = Depends(get_async_db),
    redis_cache=Depends(get_redis_cache),
):
    """
    Get current monthly quiz using access token.

    **PUBLIC ENDPOINT** - No authentication required
    **Rate limited:** 20 requests/minute per IP
    **Security:** Token validation, IP logging, expiry checking

    Token format:
    - Signed JWT with quiz_template_id/patient_id/session_id/exp
    """
    logger.info(f"Public quiz access from IP: {request.client.host}")

    # Validate token
    try:
        token_data = _decode_quiz_token(token)
        quiz_id = UUID(token_data.get("quiz_id"))
        token_type = token_data.get("type")

        # Check token type
        if token_type != "quiz_access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )

    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format"
        )

    # Get quiz
    quiz_result = await db.execute(
        select(QuizTemplate).where(
            QuizTemplate.id == quiz_id, QuizTemplate.category == "monthly_quiz"
        )
    )
    quiz = quiz_result.scalar_one_or_none()

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
        if expires_at < now_sao_paulo():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Quiz has expired"
            )

    # Resolve patient and session from token
    patient_id = token_data.get("patient_id")
    if not patient_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    patient_uuid = UUID(patient_id)
    session_id = token_data.get("session_id")

    # Find or create session
    session = None
    if session_id:
        try:
            session_result = await db.execute(
                select(QuizSession).where(QuizSession.id == UUID(session_id))
            )
            session = session_result.scalar_one_or_none()
        except ValueError:
            session = None

    if not session:
        session_result = await db.execute(
            select(QuizSession).where(
                QuizSession.quiz_template_id == quiz_id,
                QuizSession.patient_id == patient_uuid,
                QuizSession.status.in_(["in_progress", "pending"]),
            )
        )
        session = session_result.scalar_one_or_none()

    if not session:
        session = QuizSession(
            patient_id=patient_uuid,
            quiz_template_id=quiz_id,
            status="in_progress",
            started_at=now_sao_paulo(),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        # Increment access count
        quiz.tags["total_accessed"] = quiz.tags.get("total_accessed", 0) + 1
        await db.commit()

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
    db: AsyncSession = Depends(get_async_db),
):
    """
    Submit quiz response with token validation.

    **PUBLIC ENDPOINT** - Token-based authentication
    **Rate limited:** 20 requests/minute per IP
    """
    logger.info(f"Public quiz submission from IP: {request.client.host}")

    # Validate token
    try:
        token_data = _decode_quiz_token(submission.token)
        token_quiz_id = UUID(token_data.get("quiz_id"))
        token_type = token_data.get("type")

        # Check if token matches quiz_id
        if token_quiz_id != quiz_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token does not match quiz ID",
            )

        # Check token type
        if token_type not in ["quiz_access", "quiz_submission"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type for submission",
            )

    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format"
        )

    # Get quiz
    quiz_result = await db.execute(
        select(QuizTemplate).where(
            QuizTemplate.id == quiz_id, QuizTemplate.category == "monthly_quiz"
        )
    )
    quiz = quiz_result.scalar_one_or_none()

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

    # Resolve patient and session from token
    patient_id = token_data.get("patient_id")
    if not patient_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    patient_uuid = UUID(patient_id)
    session_id = token_data.get("session_id")

    # Get or create session
    session = None
    if session_id:
        try:
            session_result = await db.execute(
                select(QuizSession).where(QuizSession.id == UUID(session_id))
            )
            session = session_result.scalar_one_or_none()
        except ValueError:
            session = None

    if not session:
        session_result = await db.execute(
            select(QuizSession).where(
                QuizSession.quiz_template_id == quiz_id,
                QuizSession.patient_id == patient_uuid,
                QuizSession.status.in_(["in_progress", "pending"]),
            )
        )
        session = session_result.scalar_one_or_none()

    if not session:
        # Create new session
        session = QuizSession(
            patient_id=patient_uuid,
            quiz_template_id=quiz_id,
            status="in_progress",
            started_at=now_sao_paulo(),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

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
        patient_id=patient_uuid,
        quiz_template_id=quiz_id,
        quiz_session_id=session.id,
        question_id=submission.question_id,
        question_text=question.get("text", ""),
        response_type=question.get("type", "text"),
        response_value=str(submission.response_value),
        response_metadata=submission.response_metadata or {},
        responded_at=now_sao_paulo(),
    )

    db.add(quiz_response)
    await db.commit()
    await db.refresh(quiz_response)

    # Check if all questions are answered
    total_questions = len(quiz.questions) if quiz.questions else 0
    answered_questions = (
        await db.execute(
            select(func.count(QuizResponse.id)).where(QuizResponse.quiz_session_id == session.id)
        )
    )
    answered_questions = answered_questions.scalar_one()

    if answered_questions >= total_questions:
        # Complete session
        session.status = "completed"
        session.completed_at = now_sao_paulo()

        # Update quiz completion stats
        quiz.tags["total_completed"] = quiz.tags.get("total_completed", 0) + 1
        total_sent = quiz.tags.get("total_sent", 1)
        quiz.tags["completion_rate"] = (
            (quiz.tags["total_completed"] / total_sent * 100) if total_sent > 0 else 0.0
        )

        await db.commit()

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
    db: AsyncSession = Depends(get_async_db),
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
        cached = await _cache_get(redis_cache, cache_key)
        if cached:
            return PublicQuizResultsV2.parse_raw(cached)

    # Get quiz
    quiz_result = await db.execute(
        select(QuizTemplate).where(
            QuizTemplate.id == quiz_id, QuizTemplate.category == "monthly_quiz"
        )
    )
    quiz = quiz_result.scalar_one_or_none()

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
    total_completions = (
        await db.execute(
            select(func.count(QuizSession.id)).where(
                QuizSession.quiz_template_id == quiz_id,
                QuizSession.status == "completed",
            )
        )
    ).scalar_one()

    # Calculate average score
    completed_sessions = (
        await db.execute(
            select(QuizSession).where(
                QuizSession.quiz_template_id == quiz_id,
                QuizSession.status == "completed",
                QuizSession.score.isnot(None),
            )
        )
    ).scalars().all()

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
        await db.execute(
            select(QuizResponse).where(QuizResponse.quiz_template_id == quiz_id)
        )
    ).scalars().all()

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
        await _cache_set(redis_cache, cache_key, result.json(), CACHE_TTL_PUBLIC_QUIZ)

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


async def get_cached_transformed_questions(
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
            cached = await _cache_get(redis_cache, cache_key)
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
            await _cache_set(redis_cache, cache_key, json.dumps(transformed), 3600)  # 1 hour TTL
            logger.debug(f"[Cache SET] Stored transformed questions for template {quiz_template_id}")
        except Exception as e:
            logger.warning(f"Redis cache write error: {e}")
    
    return transformed


class QuizAccessRequest(BaseModel):
    token: str

@router.post(
    "/access",
    summary="Access Quiz",
    description="POST /access endpoint for QuizApiClient",
    response_model=Dict[str, Any]
)
@limiter.limit("20/minute")
async def access_quiz(
    access_req: QuizAccessRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    redis_cache=Depends(get_redis_cache)
):
    """
    Access endpoint for POST /quiz-extensions/access
    
    1. Validates token
    2. Creates/Gets session
    3. Sets HttpOnly cookie for session persistence (Critical for F5 refresh)
    4. Returns QuizSession object matching Frontend interface
    """
    logger.info(f"Compatibility access request from IP: {request.client.host}")
    
    # Reuse logic from get_current_public_quiz, but adapted
    try:
        token_data = _decode_quiz_token(access_req.token)
        quiz_id = UUID(token_data.get("quiz_id"))
        token_type = token_data.get("type")

        # Validate token type
        if token_type != "quiz_access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token format")

    # Get Quiz
    quiz_result = await db.execute(select(QuizTemplate).where(QuizTemplate.id == quiz_id))
    quiz = quiz_result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Resolve patient and session from token
    patient_id = token_data.get("patient_id")
    if not patient_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    patient_uuid = UUID(patient_id)
    session_id = token_data.get("session_id")

    # Get/Create Session
    session = None
    if session_id:
        try:
            session_result = await db.execute(
                select(QuizSession).where(QuizSession.id == UUID(session_id))
            )
            session = session_result.scalar_one_or_none()
        except ValueError:
            session = None

    if not session:
        session_result = await db.execute(
            select(QuizSession).where(
                QuizSession.quiz_template_id == quiz_id,
                QuizSession.patient_id == patient_uuid,
                QuizSession.status == "started",
            )
        )
        session = session_result.scalar_one_or_none()

    if not session:
        session = QuizSession(
            patient_id=patient_uuid,
            quiz_template_id=quiz_id,
            status="started",
            started_at=now_sao_paulo()
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        # Increment stats
        if quiz.tags:
            quiz.tags["total_accessed"] = quiz.tags.get("total_accessed", 0) + 1
        else:
            quiz.tags = {"total_accessed": 1}
        await db.commit()

    # Set Session Cookie (SameSite=None for cross-site fetch from quiz domain)
    cookie_secure = settings.SESSION_ENABLE_COOKIE_SECURE
    cookie_samesite = "none" if cookie_secure else "lax"
    response.set_cookie(
        key="quiz_session_id",
        value=str(session.id),
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        max_age=86400  # 24h
    )

    # Transform questions using cached function (Performance optimization)
    sanitized_questions = await get_cached_transformed_questions(
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
        "expires_at": (now_sao_paulo().replace(year=datetime.now().year + 1)).isoformat(), # Mock expiry if not set
        "questions": sanitized_questions,
        "status": session.status
    }

@router.get(
    "/session/active",
    summary="Get Active Session",
    description="GET /session/active endpoint for session recovery",
    response_model=Dict[str, Any]
)
async def get_active_session(
    request: Request,
    quiz_session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_async_db),
    redis_cache=Depends(get_redis_cache)
):
    """
    Recover session from cookie.
    """
    if not quiz_session_id:
        raise HTTPException(status_code=401, detail="No active session cookie")
    
    session_result = await db.execute(
        select(QuizSession).where(QuizSession.id == UUID(quiz_session_id))
    )
    session = session_result.scalar_one_or_none()
    if not session or session.status != "started":
        raise HTTPException(status_code=404, detail="Session expired or not found")

    quiz_result = await db.execute(
        select(QuizTemplate).where(QuizTemplate.id == session.quiz_template_id)
    )
    quiz = quiz_result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    # Transform questions using cached function (Performance optimization)
    sanitized_questions = await get_cached_transformed_questions(
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
        "expires_at": (now_sao_paulo().replace(year=datetime.now().year + 1)).isoformat(),
        "questions": sanitized_questions,
        "status": session.status,
        "current_question_index": 0  # TODO: Track progress if needed
    }


# ==============================================================================
# SUBMIT ENDPOINT
# ==============================================================================

class QuizSubmitRequest(BaseModel):
    question_id: str
    response_value: Any  # Can be string or list
    response_metadata: Optional[Dict[str, Any]] = None


@router.post(
    "/submit",
    summary="Submit Quiz Answer",
    description="POST /submit endpoint for submitting quiz answers",
    response_model=Dict[str, Any]
)
@limiter.limit("60/minute")
async def submit_answer(
    submit_req: QuizSubmitRequest,
    request: Request,
    quiz_session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Submit an answer to a quiz question.
    Session is identified via HttpOnly cookie.
    """
    if not quiz_session_id:
        raise HTTPException(status_code=401, detail="No active session")
    
    try:
        session_result = await db.execute(
            select(QuizSession).where(QuizSession.id == UUID(quiz_session_id))
        )
        session = session_result.scalar_one_or_none()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    
    if not session or session.status != "started":
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    quiz_result = await db.execute(
        select(QuizTemplate).where(QuizTemplate.id == session.quiz_template_id)
    )
    quiz = quiz_result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
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
    existing_result = await db.execute(
        select(QuizResponse).where(
            QuizResponse.quiz_session_id == session.id,
            QuizResponse.question_id == submit_req.question_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    
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
        existing.responded_at = now_sao_paulo()
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
            responded_at=now_sao_paulo()
        )
        db.add(new_response)
    
    # Update session progress (only increment for new responses, not updates)
    if not existing:
        session.answered_questions = (session.answered_questions or 0) + 1
    session.current_question = question_index + 1
    
    total_questions = len(quiz.questions or [])
    is_last = question_index >= total_questions - 1
    
    # If last question, mark completed
    if is_last:
        session.status = "completed"
        session.completed_at = now_sao_paulo()
    
    await db.commit()
    
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
# LOGOUT ENDPOINT
# ==============================================================================

@router.post(
    "/logout",
    summary="Logout from Quiz Session",
    description="POST /logout endpoint to end quiz session",
    response_model=Dict[str, Any]
)
async def logout_quiz(
    response: Response,
    quiz_session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_async_db)
):
    """
    End quiz session and clear cookie.
    """
    if quiz_session_id:
        try:
            session_result = await db.execute(
                select(QuizSession).where(QuizSession.id == UUID(quiz_session_id))
            )
            session = session_result.scalar_one_or_none()
            if session and session.status == "started":
                session.status = "cancelled"
                await db.commit()
        except ValueError:
            pass  # Invalid UUID, just clear cookie
    
    # Clear session cookie
    cookie_secure = settings.SESSION_ENABLE_COOKIE_SECURE
    cookie_samesite = "none" if cookie_secure else "lax"
    response.delete_cookie(
        key="quiz_session_id",
        secure=cookie_secure,
        samesite=cookie_samesite,
    )
    
    return {"success": True, "message": "Session ended"}
