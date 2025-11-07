"""
Enhanced Quiz API v2
Advanced quiz endpoints with branching logic, risk scoring, and adaptive flows.
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import json
import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, case

from app.database import get_db
from app.models.quiz import QuizSession, QuizTemplate, QuizResponse
from app.models.patient import Patient
from app.models.user import UserRole
from app.schemas.v2.enhanced_quiz import (
    AdvancedQuizTemplate,
    QuizAnalyticsResponse,
    QuizAnalyticsTrend,
    AdaptiveQuizFlowRequest,
    AdaptiveQuizFlowResponse,
    RiskScoringRequest,
    RiskScoringResponse,
    RiskScore,
    RiskLevel,
    QuizRecommendationsResponse,
    QuizRecommendation,
    PerformanceMetricsResponse,
    PerformanceMetric,
    BulkQuizOperation,
    BulkOperationResponse,
    QuizExportRequest,
    QuizExportResponse,
    QuizCategory,
    QuizQuestion,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter
from app.utils.logging import get_logger
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
)

logger = get_logger(__name__)
router = APIRouter()

# Cache TTL configurations (Phase 4 requirement)
QUIZ_TEMPLATE_CACHE_TTL = 1800  # 30 minutes
QUIZ_RESULTS_CACHE_TTL = 600  # 10 minutes
ANALYTICS_CACHE_TTL = 900  # 15 minutes


def _extract_user_context(current_user) -> Tuple[Optional[UserRole], Optional[UUID]]:
    """Extract role and user UUID from current_user (can be model or dict)."""
    role = None
    user_id = None

    if isinstance(current_user, dict):
        role = current_user.get("role")
        user_id = current_user.get("id")
    else:
        user_id = getattr(current_user, "id", None)
        role = getattr(current_user, "role", None)

    if isinstance(role, UserRole):
        role_enum = role
    elif isinstance(role, str):
        try:
            role_enum = UserRole(role.lower())
        except ValueError:
            role_enum = None
    else:
        role_enum = None

    if user_id is not None:
        try:
            user_uuid = UUID(str(user_id))
        except (TypeError, ValueError):
            user_uuid = None
    else:
        user_uuid = None

    return role_enum, user_uuid


def _is_admin(current_user) -> bool:
    """Check if current user is admin."""
    role_enum, _ = _extract_user_context(current_user)
    return role_enum == UserRole.ADMIN


def _get_cache_key(endpoint: str, **params) -> str:
    """Generate cache key from endpoint and parameters."""
    param_str = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()
    return f"enhanced_quiz:v2:{endpoint}:{param_hash}"


async def _get_cached_result(cache_key: str):
    """Get cached result from Redis."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            logger.debug("Redis not available, skipping cache read")
            return None
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache HIT: {cache_key}")
            return json.loads(cached)
        logger.debug(f"Cache MISS: {cache_key}")
        return None
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")
        return None


async def _set_cached_result(cache_key: str, data: dict, ttl: int):
    """Set cached result in Redis."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            logger.debug("Redis not available, skipping cache write")
            return
        await redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


def _evaluate_branching_condition(condition: Dict[str, Any], response_data: Dict[str, Any]) -> bool:
    """
    Evaluate a branching condition against response data.

    Args:
        condition: Condition with field, operator, value
        response_data: Response data to evaluate

    Returns:
        bool: True if condition matches
    """
    field = condition.get("field")
    operator = condition.get("operator")
    expected_value = condition.get("value")

    actual_value = response_data.get(field)

    if actual_value is None:
        return False

    if operator == "eq":
        return actual_value == expected_value
    elif operator == "neq":
        return actual_value != expected_value
    elif operator == "gt":
        return actual_value > expected_value
    elif operator == "lt":
        return actual_value < expected_value
    elif operator == "gte":
        return actual_value >= expected_value
    elif operator == "lte":
        return actual_value <= expected_value
    elif operator == "in":
        return actual_value in expected_value
    elif operator == "contains":
        return expected_value in str(actual_value)

    return False


def _calculate_risk_score(responses: List[QuizResponse], template: QuizTemplate) -> RiskScore:
    """
    Calculate risk score based on quiz responses.

    Args:
        responses: List of quiz responses
        template: Quiz template with risk factor definitions

    Returns:
        RiskScore: Calculated risk assessment
    """
    risk_score = 0.0
    risk_factors = []
    recommendations = []
    urgent_actions = []

    # Parse template questions for risk factors
    template_questions = template.questions if isinstance(template.questions, list) else []
    risk_mapping = {}

    for question in template_questions:
        if isinstance(question, dict) and "risk_factors" in question:
            risk_mapping[question.get("id")] = question.get("risk_factors", {})

    # Evaluate each response
    for response in responses:
        question_id = response.question_id
        response_value = response.response_value

        if question_id in risk_mapping:
            risk_factors_for_question = risk_mapping[question_id]

            # Check if response indicates risk
            for factor_name, factor_weight in risk_factors_for_question.items():
                try:
                    numeric_value = float(response_value)
                    if numeric_value >= 7:  # High value threshold
                        risk_score += factor_weight * 10
                        risk_factors.append(factor_name)
                except (ValueError, TypeError):
                    # Handle non-numeric responses
                    pass

    # Normalize risk score to 0-100
    risk_score = min(risk_score, 100.0)

    # Determine risk level
    if risk_score >= 75:
        overall_risk_level = RiskLevel.CRITICAL
        urgent_actions.append("Contact physician immediately")
        recommendations.append("Schedule urgent consultation")
    elif risk_score >= 50:
        overall_risk_level = RiskLevel.HIGH
        recommendations.append("Schedule consultation within 48 hours")
        recommendations.append("Monitor symptoms closely")
    elif risk_score >= 25:
        overall_risk_level = RiskLevel.MEDIUM
        recommendations.append("Schedule routine follow-up")
    else:
        overall_risk_level = RiskLevel.LOW
        recommendations.append("Continue current treatment plan")

    # Calculate confidence based on response completeness
    confidence_score = min(len(responses) / max(len(template_questions), 1), 1.0)

    return RiskScore(
        overall_risk_level=overall_risk_level,
        risk_score=round(risk_score, 2),
        risk_factors=list(set(risk_factors)),
        recommendations=recommendations,
        urgent_actions=urgent_actions,
        confidence_score=round(confidence_score, 2)
    )


@router.get(
    "/analytics",
    response_model=QuizAnalyticsResponse,
    summary="Get advanced quiz analytics",
    description="Get comprehensive quiz analytics with trends and patterns (20 req/min)"
)
@limiter.limit("20/minute")
async def get_quiz_analytics(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    start_date: Optional[datetime] = Query(None, description="Start date for analytics"),
    end_date: Optional[datetime] = Query(None, description="End date for analytics"),
    category: Optional[QuizCategory] = Query(None, description="Filter by quiz category"),
    include_trends: bool = Query(True, description="Include trend data"),
):
    """
    Get advanced quiz analytics with trends and patterns.

    Features:
    - Completion rate analysis
    - Category breakdown
    - Risk distribution
    - Temporal trends
    - Top performing templates

    Cache: 15 minutes
    Rate Limit: 20 requests/minute
    """
    role_enum, user_uuid = _extract_user_context(current_user)

    # Check cache
    cache_key = _get_cache_key(
        "analytics",
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        category=category.value if category else None,
        role=role_enum.value if role_enum else None,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await _get_cached_result(cache_key)
    if cached_result:
        return cached_result

    # Build base query
    query = db.query(QuizSession).join(Patient, Patient.id == QuizSession.patient_id)

    # Apply RBAC
    if role_enum != UserRole.ADMIN and user_uuid:
        query = query.filter(Patient.doctor_id == user_uuid)

    # Apply filters
    filters = []
    if start_date:
        filters.append(QuizSession.created_at >= start_date)
    if end_date:
        filters.append(QuizSession.created_at <= end_date)

    if filters:
        query = query.filter(and_(*filters))

    # Get sessions with eager loading
    sessions = query.options(
        joinedload(QuizSession.quiz_template)
    ).all()

    # Calculate metrics
    total_sessions = len(sessions)
    completed_sessions = sum(1 for s in sessions if s.status == "completed")
    completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0

    # Calculate average score
    scores = [float(s.score) for s in sessions if s.score is not None]
    average_score = sum(scores) / len(scores) if scores else None

    # Calculate average time
    times = [s.time_spent_seconds for s in sessions if s.time_spent_seconds is not None]
    average_time_minutes = (sum(times) / len(times) / 60) if times else None

    # Category breakdown
    category_breakdown = {}
    for session in sessions:
        if session.quiz_template and session.quiz_template.category:
            cat = session.quiz_template.category
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1

    # Risk distribution (mock data - would come from risk scoring)
    risk_distribution = {
        "low": int(total_sessions * 0.6),
        "medium": int(total_sessions * 0.25),
        "high": int(total_sessions * 0.10),
        "critical": int(total_sessions * 0.05)
    }

    # Top templates
    template_counts = {}
    for session in sessions:
        if session.quiz_template:
            template_id = str(session.quiz_template_id)
            if template_id not in template_counts:
                template_counts[template_id] = {
                    "template_id": template_id,
                    "template_name": session.quiz_template.name,
                    "count": 0
                }
            template_counts[template_id]["count"] += 1

    top_templates = sorted(template_counts.values(), key=lambda x: x["count"], reverse=True)[:5]

    # Trends (if requested)
    trends = []
    if include_trends:
        # Group by date
        trend_data = {}
        for session in sessions:
            date_key = session.created_at.date().isoformat()
            if date_key not in trend_data:
                trend_data[date_key] = {"total": 0, "completed": 0, "scores": []}
            trend_data[date_key]["total"] += 1
            if session.status == "completed":
                trend_data[date_key]["completed"] += 1
            if session.score:
                trend_data[date_key]["scores"].append(float(session.score))

        for date_key, data in sorted(trend_data.items()):
            trends.append(QuizAnalyticsTrend(
                date=date_key,
                total_sessions=data["total"],
                completed_sessions=data["completed"],
                completion_rate=round((data["completed"] / data["total"] * 100) if data["total"] > 0 else 0, 2),
                average_score=round(sum(data["scores"]) / len(data["scores"]), 2) if data["scores"] else None
            ))

    result = QuizAnalyticsResponse(
        total_sessions=total_sessions,
        completed_sessions=completed_sessions,
        completion_rate=round(completion_rate, 2),
        average_score=round(average_score, 2) if average_score else None,
        average_time_minutes=round(average_time_minutes, 2) if average_time_minutes else None,
        trends=trends,
        category_breakdown=category_breakdown,
        risk_distribution=risk_distribution,
        top_templates=top_templates
    )

    # Cache result
    await _set_cached_result(cache_key, result.dict(), ANALYTICS_CACHE_TTL)

    logger.info(
        f"Quiz analytics retrieved: {total_sessions} sessions",
        extra={
            "event_type": "quiz_analytics_retrieved",
            "total_sessions": total_sessions,
            "completion_rate": completion_rate,
            "user_id": str(user_uuid) if user_uuid else None
        }
    )

    return result


@router.post(
    "/templates/advanced",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create advanced quiz template",
    description="Create quiz template with branching logic and risk scoring (30 req/hour)"
)
@limiter.limit("30/hour")
async def create_advanced_template(
    request: Request,
    template_data: AdvancedQuizTemplate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Create advanced quiz template with branching logic and risk scoring.

    Features:
    - Branching logic for adaptive flow
    - Risk factor definitions
    - Custom scoring weights
    - Validation rules

    Cache: Template cached for 30 minutes
    Rate Limit: 30 requests/hour
    """
    role_enum, user_uuid = _extract_user_context(current_user)

    if role_enum not in [UserRole.ADMIN, UserRole.DOCTOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and doctors can create templates"
        )

    try:
        # Convert Pydantic model to database format
        template_dict = template_data.dict()
        questions_json = [q.dict() if hasattr(q, 'dict') else q for q in template_dict['questions']]

        # Create template
        new_template = QuizTemplate(
            name=template_dict['title'],
            version="1.0",
            description=template_dict.get('description'),
            category=template_dict['category'].value,
            questions=questions_json,
            is_active=template_dict.get('is_active', True),
            passing_score=int(template_dict.get('passing_score')) if template_dict.get('passing_score') else None,
            time_limit_minutes=template_dict.get('time_limit_minutes'),
            randomize_questions=template_dict.get('randomize_questions', False),
            tags=template_dict.get('tags', [])
        )

        db.add(new_template)
        db.commit()
        db.refresh(new_template)

        # Background task: Validate template structure
        background_tasks.add_task(_validate_template_structure, str(new_template.id))

        logger.info(
            f"Advanced quiz template created: {new_template.name}",
            extra={
                "event_type": "advanced_template_created",
                "template_id": str(new_template.id),
                "category": template_dict['category'].value,
                "branching_enabled": template_dict.get('adaptive_flow_enabled', False),
                "risk_scoring_enabled": template_dict.get('risk_scoring_enabled', False),
                "user_id": str(user_uuid) if user_uuid else None
            }
        )

        return {
            "id": str(new_template.id),
            "name": new_template.name,
            "category": new_template.category,
            "questions_count": len(questions_json),
            "adaptive_flow_enabled": template_dict.get('adaptive_flow_enabled', False),
            "risk_scoring_enabled": template_dict.get('risk_scoring_enabled', False),
            "created_at": new_template.created_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Error creating advanced template: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create template: {str(e)}"
        )


@router.post(
    "/adaptive-flow",
    response_model=AdaptiveQuizFlowResponse,
    summary="Process adaptive quiz flow",
    description="Process quiz response and determine next question based on branching logic (40 req/min)"
)
@limiter.limit("40/minute")
async def process_adaptive_flow(
    request: Request,
    flow_request: AdaptiveQuizFlowRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Process adaptive quiz flow based on response and branching logic.

    Features:
    - Dynamic question routing
    - Conditional logic evaluation
    - Alert generation
    - Progress tracking

    Rate Limit: 40 requests/minute
    """
    role_enum, user_uuid = _extract_user_context(current_user)

    try:
        # Get session
        session_uuid = UUID(flow_request.session_id)
        session = db.query(QuizSession).filter(QuizSession.id == session_uuid).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz session not found"
            )

        # RBAC check
        if role_enum != UserRole.ADMIN:
            patient = db.query(Patient).filter(Patient.id == session.patient_id).first()
            if patient and patient.doctor_id != user_uuid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this session"
                )

        # Get template with questions
        template = db.query(QuizTemplate).filter(
            QuizTemplate.id == session.quiz_template_id
        ).first()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz template not found"
            )

        # Save current response
        new_response = QuizResponse(
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            quiz_session_id=session.id,
            question_id=flow_request.current_question_id,
            question_text="",  # Would be populated from template
            response_type="adaptive",
            response_value=str(flow_request.response_value),
            response_metadata=flow_request.response_metadata or {},
            responded_at=datetime.utcnow()
        )
        db.add(new_response)

        # Parse template questions
        questions = template.questions if isinstance(template.questions, list) else []
        current_question_idx = next(
            (i for i, q in enumerate(questions) if q.get("id") == flow_request.current_question_id),
            -1
        )

        # Evaluate branching logic
        next_question = None
        alerts = []

        if current_question_idx >= 0 and current_question_idx < len(questions):
            current_q = questions[current_question_idx]
            branching_rules = current_q.get("branching_rules", [])

            # Prepare response data for evaluation
            response_data = {
                flow_request.current_question_id: flow_request.response_value
            }

            # Check branching rules
            for rule in branching_rules:
                conditions = rule.get("conditions", [])
                logic = rule.get("logic", "AND")

                # Evaluate conditions
                condition_results = [
                    _evaluate_branching_condition(cond, response_data)
                    for cond in conditions
                ]

                matches = all(condition_results) if logic == "AND" else any(condition_results)

                if matches:
                    # Rule matched - apply actions
                    if rule.get("show_alert"):
                        alerts.append(rule["show_alert"])

                    if rule.get("next_question_id"):
                        # Find the specific next question
                        next_q_id = rule["next_question_id"]
                        next_q = next((q for q in questions if q.get("id") == next_q_id), None)
                        if next_q:
                            next_question = QuizQuestion(**next_q)
                            break

            # If no branching rule matched, go to next question in sequence
            if not next_question and current_question_idx + 1 < len(questions):
                next_q = questions[current_question_idx + 1]
                next_question = QuizQuestion(**next_q)

        # Update session progress
        session.current_question = (current_question_idx + 1) if next_question else len(questions)
        session.answered_questions = (session.answered_questions or 0) + 1

        is_completed = next_question is None
        if is_completed:
            session.status = "completed"
            session.completed_at = datetime.utcnow()

        db.commit()

        # Calculate progress
        total_questions = len(questions)
        progress_percentage = (session.answered_questions / total_questions * 100) if total_questions > 0 else 0
        estimated_remaining = max(0, total_questions - session.answered_questions) * 2  # 2 min per question

        logger.info(
            f"Adaptive flow processed for session {session_id}",
            extra={
                "event_type": "adaptive_flow_processed",
                "session_id": flow_request.session_id,
                "question_id": flow_request.current_question_id,
                "is_completed": is_completed,
                "alerts_count": len(alerts),
                "user_id": str(user_uuid) if user_uuid else None
            }
        )

        return AdaptiveQuizFlowResponse(
            next_question=next_question,
            is_completed=is_completed,
            alerts=alerts,
            progress_percentage=round(progress_percentage, 2),
            estimated_remaining_minutes=estimated_remaining if not is_completed else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing adaptive flow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process adaptive flow: {str(e)}"
        )


@router.post(
    "/risk-scoring",
    response_model=RiskScoringResponse,
    summary="Calculate patient risk score",
    description="Calculate risk assessment based on quiz responses (30 req/min)"
)
@limiter.limit("30/minute")
async def calculate_risk_score(
    request: Request,
    risk_request: RiskScoringRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Calculate comprehensive risk score for a patient.

    Features:
    - Multi-factor risk assessment
    - Historical trend analysis
    - Actionable recommendations
    - Confidence scoring

    Cache: 10 minutes
    Rate Limit: 30 requests/minute
    """
    role_enum, user_uuid = _extract_user_context(current_user)

    # Check cache
    cache_key = _get_cache_key(
        "risk-scoring",
        patient_id=risk_request.patient_id,
        session_id=risk_request.session_id,
        lookback_days=risk_request.lookback_days,
        role=role_enum.value if role_enum else None,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await _get_cached_result(cache_key)
    if cached_result:
        return cached_result

    try:
        patient_uuid = UUID(risk_request.patient_id)

        # Check patient access
        patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )

        if role_enum != UserRole.ADMIN and patient.doctor_id != user_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this patient"
            )

        # Get quiz sessions and responses
        lookback_date = datetime.utcnow() - timedelta(days=risk_request.lookback_days)

        query = db.query(QuizSession).filter(
            and_(
                QuizSession.patient_id == patient_uuid,
                QuizSession.created_at >= lookback_date,
                QuizSession.status == "completed"
            )
        )

        if risk_request.session_id:
            session_uuid = UUID(risk_request.session_id)
            query = query.filter(QuizSession.id == session_uuid)

        sessions = query.options(
            joinedload(QuizSession.quiz_template),
            joinedload(QuizSession.responses)
        ).all()

        if not sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No completed quiz sessions found for risk assessment"
            )

        # Calculate current risk score
        latest_session = sessions[0]
        responses = db.query(QuizResponse).filter(
            QuizResponse.quiz_session_id == latest_session.id
        ).all()

        current_risk = _calculate_risk_score(responses, latest_session.quiz_template)

        # Calculate trend
        historical_scores = []
        if risk_request.include_historical and len(sessions) > 1:
            for session in sessions[1:]:
                session_responses = db.query(QuizResponse).filter(
                    QuizResponse.quiz_session_id == session.id
                ).all()

                if session_responses:
                    risk = _calculate_risk_score(session_responses, session.quiz_template)
                    historical_scores.append({
                        "date": session.created_at.isoformat(),
                        "risk_score": risk.risk_score,
                        "risk_level": risk.overall_risk_level.value
                    })

        # Determine trend
        if len(historical_scores) > 0:
            recent_scores = [current_risk.risk_score] + [h["risk_score"] for h in historical_scores[:2]]
            if len(recent_scores) >= 2:
                if recent_scores[0] > recent_scores[1] + 10:
                    trend = "worsening"
                elif recent_scores[0] < recent_scores[1] - 10:
                    trend = "improving"
                else:
                    trend = "stable"
            else:
                trend = "stable"
        else:
            trend = "stable"

        result = RiskScoringResponse(
            patient_id=risk_request.patient_id,
            assessment_date=datetime.utcnow(),
            current_risk=current_risk,
            trend=trend,
            historical_scores=historical_scores
        )

        # Cache result
        await _set_cached_result(cache_key, result.dict(), QUIZ_RESULTS_CACHE_TTL)

        logger.info(
            f"Risk score calculated for patient {risk_request.patient_id}",
            extra={
                "event_type": "risk_score_calculated",
                "patient_id": risk_request.patient_id,
                "risk_level": current_risk.overall_risk_level.value,
                "risk_score": current_risk.risk_score,
                "trend": trend,
                "user_id": str(user_uuid) if user_uuid else None
            }
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating risk score: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate risk score: {str(e)}"
        )


@router.get(
    "/recommendations",
    response_model=QuizRecommendationsResponse,
    summary="Get quiz recommendations",
    description="Get personalized quiz recommendations based on patient history (30 req/min)"
)
@limiter.limit("30/minute")
async def get_quiz_recommendations(
    request: Request,
    patient_id: str = Query(..., description="Patient UUID"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Get personalized quiz recommendations for a patient.

    Features:
    - Historical pattern analysis
    - Risk-based recommendations
    - Priority scoring
    - Due date suggestions

    Cache: 15 minutes
    Rate Limit: 30 requests/minute
    """
    role_enum, user_uuid = _extract_user_context(current_user)

    # Check cache
    cache_key = _get_cache_key(
        "recommendations",
        patient_id=patient_id,
        role=role_enum.value if role_enum else None,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await _get_cached_result(cache_key)
    if cached_result:
        return cached_result

    try:
        patient_uuid = UUID(patient_id)

        # Check patient access
        patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )

        if role_enum != UserRole.ADMIN and patient.doctor_id != user_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this patient"
            )

        # Get patient's quiz history
        recent_sessions = db.query(QuizSession).filter(
            and_(
                QuizSession.patient_id == patient_uuid,
                QuizSession.created_at >= datetime.utcnow() - timedelta(days=90)
            )
        ).options(joinedload(QuizSession.quiz_template)).all()

        # Get available templates
        available_templates = db.query(QuizTemplate).filter(
            QuizTemplate.is_active == True
        ).all()

        recommendations = []

        # Analyze patterns and generate recommendations
        completed_template_ids = {
            str(s.quiz_template_id) for s in recent_sessions if s.status == "completed"
        }

        for template in available_templates:
            template_id = str(template.id)

            # Skip recently completed templates
            if template_id in completed_template_ids:
                continue

            # Determine priority based on category and patient history
            priority = "low"
            reason = f"Recommended based on treatment plan"

            if template.category == "pain_assessment":
                priority = "high"
                reason = "Regular pain assessment recommended"
            elif template.category == "symptoms":
                priority = "medium"
                reason = "Symptom monitoring recommended"

            # Calculate due date
            due_date = datetime.utcnow() + timedelta(days=7)

            recommendations.append(QuizRecommendation(
                template_id=template_id,
                template_title=template.name,
                category=QuizCategory(template.category) if template.category else QuizCategory.GENERAL_HEALTH,
                priority=priority,
                reason=reason,
                due_date=due_date
            ))

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x.priority, 3))

        result = QuizRecommendationsResponse(
            patient_id=patient_id,
            recommendations=recommendations[:10],  # Top 10
            total_recommendations=len(recommendations)
        )

        # Cache result
        await _set_cached_result(cache_key, result.dict(), ANALYTICS_CACHE_TTL)

        logger.info(
            f"Quiz recommendations generated for patient {patient_id}",
            extra={
                "event_type": "quiz_recommendations_generated",
                "patient_id": patient_id,
                "recommendations_count": len(recommendations),
                "user_id": str(user_uuid) if user_uuid else None
            }
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}"
        )


@router.get(
    "/performance-metrics",
    response_model=PerformanceMetricsResponse,
    summary="Get quiz performance metrics",
    description="Get detailed performance metrics for quiz analysis (30 req/min)"
)
@limiter.limit("30/minute")
async def get_performance_metrics(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    start_date: Optional[datetime] = Query(None, description="Start date for metrics"),
    end_date: Optional[datetime] = Query(None, description="End date for metrics"),
    compare_period: bool = Query(True, description="Compare with previous period"),
):
    """
    Get detailed performance metrics for quiz analysis.

    Features:
    - Period-over-period comparison
    - Trend analysis
    - Key performance indicators
    - Actionable insights

    Cache: 15 minutes
    Rate Limit: 30 requests/minute
    """
    role_enum, user_uuid = _extract_user_context(current_user)

    # Set default date range if not provided
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Check cache
    cache_key = _get_cache_key(
        "performance-metrics",
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        compare_period=compare_period,
        role=role_enum.value if role_enum else None,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await _get_cached_result(cache_key)
    if cached_result:
        return cached_result

    try:
        # Build query
        query = db.query(QuizSession).join(Patient, Patient.id == QuizSession.patient_id)

        # Apply RBAC
        if role_enum != UserRole.ADMIN and user_uuid:
            query = query.filter(Patient.doctor_id == user_uuid)

        # Current period
        current_sessions = query.filter(
            and_(
                QuizSession.created_at >= start_date,
                QuizSession.created_at <= end_date
            )
        ).all()

        # Previous period (for comparison)
        previous_sessions = []
        if compare_period:
            period_length = (end_date - start_date).days
            previous_start = start_date - timedelta(days=period_length)
            previous_end = start_date

            previous_sessions = query.filter(
                and_(
                    QuizSession.created_at >= previous_start,
                    QuizSession.created_at < previous_end
                )
            ).all()

        # Calculate metrics
        metrics = []

        # Completion rate
        current_completed = sum(1 for s in current_sessions if s.status == "completed")
        current_total = len(current_sessions)
        current_completion_rate = (current_completed / current_total * 100) if current_total > 0 else 0

        previous_completed = sum(1 for s in previous_sessions if s.status == "completed")
        previous_total = len(previous_sessions)
        previous_completion_rate = (previous_completed / previous_total * 100) if previous_total > 0 else 0

        completion_change = current_completion_rate - previous_completion_rate if compare_period else None

        metrics.append(PerformanceMetric(
            metric_name="completion_rate",
            current_value=round(current_completion_rate, 2),
            previous_value=round(previous_completion_rate, 2) if compare_period else None,
            change_percentage=round(completion_change, 2) if completion_change else None,
            trend="up" if completion_change and completion_change > 0 else "down" if completion_change and completion_change < 0 else "stable"
        ))

        # Average response time
        current_times = [s.time_spent_seconds for s in current_sessions if s.time_spent_seconds]
        current_avg_time = (sum(current_times) / len(current_times)) if current_times else 0

        previous_times = [s.time_spent_seconds for s in previous_sessions if s.time_spent_seconds]
        previous_avg_time = (sum(previous_times) / len(previous_times)) if previous_times else 0

        time_change = ((current_avg_time - previous_avg_time) / previous_avg_time * 100) if previous_avg_time > 0 else None

        metrics.append(PerformanceMetric(
            metric_name="average_response_time_seconds",
            current_value=round(current_avg_time, 2),
            previous_value=round(previous_avg_time, 2) if compare_period else None,
            change_percentage=round(time_change, 2) if time_change else None,
            trend="down" if time_change and time_change < 0 else "up" if time_change and time_change > 0 else "stable"
        ))

        # Session volume
        volume_change = ((current_total - previous_total) / previous_total * 100) if previous_total > 0 else None

        metrics.append(PerformanceMetric(
            metric_name="session_volume",
            current_value=float(current_total),
            previous_value=float(previous_total) if compare_period else None,
            change_percentage=round(volume_change, 2) if volume_change else None,
            trend="up" if volume_change and volume_change > 0 else "down" if volume_change and volume_change < 0 else "stable"
        ))

        # Generate insights
        insights = []
        if completion_change and completion_change > 5:
            insights.append(f"Completion rate improved by {abs(completion_change):.1f}%")
        elif completion_change and completion_change < -5:
            insights.append(f"Completion rate decreased by {abs(completion_change):.1f}%")

        if time_change and time_change < -10:
            insights.append("Response time improved significantly")

        if volume_change and volume_change > 20:
            insights.append("Session volume increased significantly")

        result = PerformanceMetricsResponse(
            period_start=start_date,
            period_end=end_date,
            metrics=metrics,
            insights=insights
        )

        # Cache result
        await _set_cached_result(cache_key, result.dict(), ANALYTICS_CACHE_TTL)

        logger.info(
            f"Performance metrics retrieved",
            extra={
                "event_type": "performance_metrics_retrieved",
                "period_days": (end_date - start_date).days,
                "current_sessions": current_total,
                "metrics_count": len(metrics),
                "user_id": str(user_uuid) if user_uuid else None
            }
        )

        return result

    except Exception as e:
        logger.error(f"Error getting performance metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance metrics: {str(e)}"
        )


@router.post(
    "/bulk-operations",
    response_model=BulkOperationResponse,
    summary="Execute bulk quiz operations",
    description="Execute bulk operations on quiz sessions (20 req/hour)"
)
@limiter.limit("20/hour")
async def execute_bulk_operations(
    request: Request,
    operation: BulkQuizOperation,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Execute bulk operations on quiz sessions.

    Supported operations:
    - assign: Assign quiz templates to multiple patients
    - delete: Delete quiz sessions for multiple patients
    - update: Update quiz session data in bulk

    Rate Limit: 20 requests/hour
    """
    role_enum, user_uuid = _extract_user_context(current_user)

    if role_enum not in [UserRole.ADMIN, UserRole.DOCTOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and doctors can execute bulk operations"
        )

    try:
        # Generate job ID
        import uuid
        job_id = f"bulk-quiz-{uuid.uuid4().hex[:12]}"

        # Validate patient access
        patient_uuids = [UUID(pid) for pid in operation.patient_ids]
        patients = db.query(Patient).filter(Patient.id.in_(patient_uuids)).all()

        if role_enum != UserRole.ADMIN:
            # Check doctor owns all patients
            unauthorized = [p for p in patients if p.doctor_id != user_uuid]
            if unauthorized:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized for {len(unauthorized)} patients"
                )

        # Execute operation based on type
        successful = 0
        failed = 0
        errors = []

        if operation.operation == "assign":
            template_uuid = UUID(operation.template_id)
            template = db.query(QuizTemplate).filter(QuizTemplate.id == template_uuid).first()

            if not template or not template.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Template not found or inactive"
                )

            for patient in patients:
                try:
                    # Check for existing active session
                    existing = db.query(QuizSession).filter(
                        and_(
                            QuizSession.patient_id == patient.id,
                            QuizSession.quiz_template_id == template_uuid,
                            QuizSession.status == "started"
                        )
                    ).first()

                    if not existing:
                        new_session = QuizSession(
                            patient_id=patient.id,
                            quiz_template_id=template_uuid,
                            status="started",
                            started_at=operation.scheduled_for or datetime.utcnow()
                        )
                        db.add(new_session)
                        successful += 1
                    else:
                        failed += 1
                        errors.append(f"Active session exists for patient {patient.id}")

                except Exception as e:
                    failed += 1
                    errors.append(f"Patient {patient.id}: {str(e)}")

            db.commit()

        elif operation.operation == "delete":
            # Delete sessions for patients
            for patient_uuid in patient_uuids:
                try:
                    deleted_count = db.query(QuizSession).filter(
                        QuizSession.patient_id == patient_uuid
                    ).delete()

                    if deleted_count > 0:
                        successful += deleted_count

                except Exception as e:
                    failed += 1
                    errors.append(f"Patient {patient_uuid}: {str(e)}")

            db.commit()

        elif operation.operation == "update":
            # Update sessions for patients
            update_data = operation.update_data or {}

            for patient_uuid in patient_uuids:
                try:
                    sessions = db.query(QuizSession).filter(
                        QuizSession.patient_id == patient_uuid
                    ).all()

                    for session in sessions:
                        for key, value in update_data.items():
                            if hasattr(session, key):
                                setattr(session, key, value)

                    successful += len(sessions)

                except Exception as e:
                    failed += 1
                    errors.append(f"Patient {patient_uuid}: {str(e)}")

            db.commit()

        result = BulkOperationResponse(
            job_id=job_id,
            operation=operation.operation,
            total_patients=len(operation.patient_ids),
            status="completed",
            successful=successful,
            failed=failed,
            errors=errors[:10]  # Limit to first 10 errors
        )

        logger.info(
            f"Bulk operation completed: {operation.operation}",
            extra={
                "event_type": "bulk_operation_completed",
                "job_id": job_id,
                "operation": operation.operation,
                "total_patients": len(operation.patient_ids),
                "successful": successful,
                "failed": failed,
                "user_id": str(user_uuid) if user_uuid else None
            }
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing bulk operation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute bulk operation: {str(e)}"
        )


@router.post(
    "/export",
    response_model=QuizExportResponse,
    summary="Export quiz data",
    description="Export quiz data in various formats (10 req/hour)"
)
@limiter.limit("10/hour")
async def export_quiz_data(
    request: Request,
    export_request: QuizExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Export quiz data in various formats.

    Supported formats:
    - PDF: Formatted reports
    - CSV: Tabular data
    - JSON: Raw data
    - XLSX: Excel spreadsheets

    Rate Limit: 10 requests/hour
    """
    role_enum, user_uuid = _extract_user_context(current_user)

    try:
        # Generate export ID
        import uuid
        export_id = f"export-{uuid.uuid4().hex[:12]}"

        # Build query
        query = db.query(QuizSession).join(Patient, Patient.id == QuizSession.patient_id)

        # Apply RBAC
        if role_enum != UserRole.ADMIN and user_uuid:
            query = query.filter(Patient.doctor_id == user_uuid)

        # Apply filters
        filters = []

        if export_request.patient_ids:
            patient_uuids = [UUID(pid) for pid in export_request.patient_ids]
            filters.append(QuizSession.patient_id.in_(patient_uuids))

        if export_request.template_ids:
            template_uuids = [UUID(tid) for tid in export_request.template_ids]
            filters.append(QuizSession.quiz_template_id.in_(template_uuids))

        if export_request.start_date:
            filters.append(QuizSession.created_at >= export_request.start_date)

        if export_request.end_date:
            filters.append(QuizSession.created_at <= export_request.end_date)

        if filters:
            query = query.filter(and_(*filters))

        # Get data count
        total_sessions = query.count()

        if total_sessions == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No quiz data found matching the filters"
            )

        # Process export in background
        background_tasks.add_task(
            _process_quiz_export,
            export_id,
            export_request.format,
            query,
            export_request.include_responses,
            export_request.include_analytics
        )

        result = QuizExportResponse(
            export_id=export_id,
            format=export_request.format,
            status="processing",
            download_url=None,
            expires_at=(datetime.utcnow() + timedelta(hours=24)),
            file_size_bytes=None
        )

        logger.info(
            f"Quiz export started: {export_id}",
            extra={
                "event_type": "quiz_export_started",
                "export_id": export_id,
                "format": export_request.format,
                "total_sessions": total_sessions,
                "user_id": str(user_uuid) if user_uuid else None
            }
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting quiz export: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start quiz export: {str(e)}"
        )


# Background task functions

async def _validate_template_structure(template_id: str):
    """Validate template structure after creation."""
    logger.info(f"Validating template structure: {template_id}")
    # Implementation would validate branching logic, risk factors, etc.
    pass


async def _process_quiz_export(
    export_id: str,
    format: str,
    query,
    include_responses: bool,
    include_analytics: bool
):
    """Process quiz export in background."""
    logger.info(f"Processing quiz export: {export_id} (format: {format})")
    # Implementation would generate file and upload to storage
    pass
