"""
Public quiz access endpoints (no authentication required).

Endpoints:
- GET /monthly/public/current - Get current public quiz (token-based)
- POST /monthly/public/{quiz_id}/submit - Submit quiz response publicly
- GET /monthly/public/{quiz_id}/results - View aggregate quiz results
"""

import base64
import json
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request

from ._shared import (
    UUID, datetime, logger, defaultdict,
    get_db, limiter, QuizResponse, QuizSession, QuizTemplate,
    PublicQuizResponseV2, PublicSubmissionRequestV2, PublicQuizResultsV2,
    get_redis_cache, CACHE_TTL_PUBLIC_QUIZ, PUBLIC_PATIENT_ID,
    Dict, Any
)

router = APIRouter()


@router.get(
    "/monthly/public/current",
    response_model=PublicQuizResponseV2,
    summary="Get current monthly quiz (PUBLIC)",
    description="Get the current active monthly quiz without authentication"
)
@limiter.limit("20/minute")  # Lower limit for public endpoint
async def get_current_public_quiz(
    request: Request,
    token: str = Query(..., description="Access token"),
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
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
        if exp_timestamp and datetime.fromtimestamp(exp_timestamp) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )

        # Check token type
        if token_type != "quiz_access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format"
        )

    # Get quiz
    quiz = db.query(QuizTemplate).filter(
        QuizTemplate.id == quiz_id,
        QuizTemplate.category == "monthly_quiz"
    ).first()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )

    # Check if quiz is published
    if quiz.tags.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quiz is not currently available"
        )

    # Check if quiz has expired
    if quiz.tags.get("expires_at"):
        expires_at = datetime.fromisoformat(quiz.tags["expires_at"])
        if expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Quiz has expired"
            )

    # Create or get quiz session for public user
    # Use a special public patient ID (in production, create a PUBLIC_USER patient)

    # Find or create session
    session = db.query(QuizSession).filter(
        QuizSession.quiz_template_id == quiz_id,
        QuizSession.patient_id == PUBLIC_PATIENT_ID,
        QuizSession.status.in_(["in_progress", "pending"])
    ).first()

    if not session:
        session = QuizSession(
            patient_id=PUBLIC_PATIENT_ID,
            quiz_template_id=quiz_id,
            status="in_progress",
            started_at=datetime.utcnow()
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
                "options": q.get("options", [])
            }
            # Remove scoring and medical interpretation
            sanitized_questions.append(sanitized_q)

    return PublicQuizResponseV2(
        quiz_id=quiz.id,
        quiz_name=quiz.name,
        description=quiz.description,
        questions=sanitized_questions,
        expires_at=datetime.fromisoformat(quiz.tags["expires_at"]) if quiz.tags.get("expires_at") else None,
        session_id=session.id
    )


@router.post(
    "/monthly/public/{quiz_id}/submit",
    response_model=Dict[str, Any],
    summary="Submit quiz response (PUBLIC)",
    description="Submit a quiz response using access token"
)
@limiter.limit("20/minute")
async def submit_public_quiz_response(
    request: Request,
    quiz_id: UUID,
    submission: PublicSubmissionRequestV2,
    db = Depends(get_db)
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
                detail="Token does not match quiz ID"
            )

        # Check expiry
        if exp_timestamp and datetime.fromtimestamp(exp_timestamp) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )

        # Check token type
        if token_type not in ["quiz_access", "quiz_submission"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type for submission"
            )

    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format"
        )

    # Get quiz
    quiz = db.query(QuizTemplate).filter(
        QuizTemplate.id == quiz_id,
        QuizTemplate.category == "monthly_quiz"
    ).first()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )

    # Check if quiz is published
    if quiz.tags.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot submit to unpublished quiz"
        )

    # Get or create session
    session = db.query(QuizSession).filter(
        QuizSession.quiz_template_id == quiz_id,
        QuizSession.patient_id == PUBLIC_PATIENT_ID,
        QuizSession.status.in_(["in_progress", "pending"])
    ).first()

    if not session:
        # Create new session
        session = QuizSession(
            patient_id=PUBLIC_PATIENT_ID,
            quiz_template_id=quiz_id,
            status="in_progress",
            started_at=datetime.utcnow()
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
            detail=f"Question {submission.question_id} not found in quiz"
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
        responded_at=datetime.utcnow()
    )

    db.add(quiz_response)
    db.commit()
    db.refresh(quiz_response)

    # Check if all questions are answered
    total_questions = len(quiz.questions) if quiz.questions else 0
    answered_questions = db.query(QuizResponse).filter(
        QuizResponse.quiz_session_id == session.id
    ).count()

    if answered_questions >= total_questions:
        # Complete session
        session.status = "completed"
        session.completed_at = datetime.utcnow()

        # Update quiz completion stats
        quiz.tags["total_completed"] = quiz.tags.get("total_completed", 0) + 1
        total_sent = quiz.tags.get("total_sent", 1)
        quiz.tags["completion_rate"] = (quiz.tags["total_completed"] / total_sent * 100) if total_sent > 0 else 0.0

        db.commit()

        logger.info(f"Public quiz {quiz_id} completed by session {session.id}")

        return {
            "message": "Quiz completed successfully",
            "status": "completed",
            "session_id": str(session.id),
            "total_questions": total_questions,
            "answered_questions": answered_questions
        }

    return {
        "message": "Response recorded successfully",
        "status": "in_progress",
        "session_id": str(session.id),
        "total_questions": total_questions,
        "answered_questions": answered_questions,
        "remaining_questions": total_questions - answered_questions
    }


@router.get(
    "/monthly/public/{quiz_id}/results",
    response_model=PublicQuizResultsV2,
    summary="Get public quiz results",
    description="Get aggregate quiz results (no personal data)"
)
@limiter.limit("20/minute")
async def get_public_quiz_results(
    request: Request,
    quiz_id: UUID,
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
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
    quiz = db.query(QuizTemplate).filter(
        QuizTemplate.id == quiz_id,
        QuizTemplate.category == "monthly_quiz"
    ).first()

    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )

    # Only show results for published quizzes
    if quiz.tags.get("status") != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Results not available for this quiz"
        )

    # Get aggregate statistics
    sessions_query = db.query(QuizSession).filter(
        QuizSession.quiz_template_id == quiz_id
    )

    total_completions = sessions_query.filter(
        QuizSession.status == "completed"
    ).count()

    # Calculate average score
    completed_sessions = sessions_query.filter(
        QuizSession.status == "completed",
        QuizSession.score.isnot(None)
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
    responses = db.query(QuizResponse).filter(
        QuizResponse.quiz_template_id == quiz_id
    ).all()

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
            percentages = {k: round(v/total*100, 1) for k, v in counts.items()} if total > 0 else {}
            response_distribution[question_id] = percentages

    result = PublicQuizResultsV2(
        quiz_id=quiz_id,
        quiz_name=quiz.name,
        total_completions=total_completions,
        average_score=round(average_score, 2) if average_score else None,
        completion_rate=round(completion_rate, 2),
        response_distribution=response_distribution if response_distribution else None
    )

    # Cache result
    if redis_cache:
        redis_cache.setex(cache_key, CACHE_TTL_PUBLIC_QUIZ, result.json())

    return result
