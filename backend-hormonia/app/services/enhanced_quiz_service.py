"""
Enhanced Quiz Service
Business logic for advanced quiz operations, risk scoring, and adaptive flows.
"""

from __future__ import annotations

import json
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import joinedload
from sqlalchemy import and_

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
from app.core.redis_unified import get_async_redis
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Cache TTL configurations
QUIZ_TEMPLATE_CACHE_TTL = 1800
QUIZ_RESULTS_CACHE_TTL = 600
ANALYTICS_CACHE_TTL = 900


class EnhancedQuizService:
    """Service for enhanced quiz operations."""

    def __init__(self, db: Any):
        self.db = db

    async def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        try:
            redis_client = await get_async_redis()
            if redis_client is None:
                return None
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
            return None

    async def _set_cached_result(self, cache_key: str, data: Any, ttl: int) -> None:
        try:
            redis_client = await get_async_redis()
            if redis_client is None:
                return

            if hasattr(data, "dict"):
                serialized = json.dumps(data.dict(), default=str)
            elif hasattr(data, "model_dump"):
                serialized = json.dumps(data.model_dump(), default=str)
            else:
                serialized = json.dumps(data, default=str)

            await redis_client.setex(cache_key, ttl, serialized)
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    def _get_cache_key(self, endpoint: str, **params) -> str:
        param_str = json.dumps(params, sort_keys=True, default=str)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        return f"enhanced_quiz:v2:{endpoint}:{param_hash}"

    def _evaluate_branching_condition(
        self, condition: Dict[str, Any], response_data: Dict[str, Any]
    ) -> bool:
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

    def _calculate_risk_score(
        self, responses: List[QuizResponse], template: QuizTemplate
    ) -> RiskScore:
        risk_score = 0.0
        risk_factors = []
        recommendations = []
        urgent_actions = []

        template_questions = (
            template.questions if isinstance(template.questions, list) else []
        )
        risk_mapping = {}
        for question in template_questions:
            if isinstance(question, dict) and "risk_factors" in question:
                risk_mapping[question.get("id")] = question.get("risk_factors", {})

        for response in responses:
            if response.question_id in risk_mapping:
                risk_factors_for_question = risk_mapping[response.question_id]
                for factor_name, factor_weight in risk_factors_for_question.items():
                    try:
                        numeric_value = float(response.response_value)
                        if numeric_value >= 7:
                            risk_score += factor_weight * 10
                            risk_factors.append(factor_name)
                    except (ValueError, TypeError) as e:
                        logger.debug(
                            f"Could not convert response value to numeric for risk scoring: {response.response_value}, error: {e}"
                        )

        risk_score = min(risk_score, 100.0)

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

        confidence_score = min(len(responses) / max(len(template_questions), 1), 1.0)

        return RiskScore(
            overall_risk_level=overall_risk_level,
            risk_score=round(risk_score, 2),
            risk_factors=list(set(risk_factors)),
            recommendations=recommendations,
            urgent_actions=urgent_actions,
            confidence_score=round(confidence_score, 2),
        )

    async def get_quiz_analytics(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        category: Optional[QuizCategory],
        include_trends: bool,
        role_enum: Optional[UserRole],
        user_uuid: Optional[UUID],
    ) -> QuizAnalyticsResponse:
        cache_key = self._get_cache_key(
            "analytics",
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            category=category.value if category else None,
            role=role_enum.value if role_enum else None,
            user=str(user_uuid) if user_uuid else None,
        )
        cached = await self._get_cached_result(cache_key)
        if cached:
            return QuizAnalyticsResponse(**cached)

        query = self.db.query(QuizSession).join(
            Patient, Patient.id == QuizSession.patient_id
        )

        if role_enum != UserRole.ADMIN and user_uuid:
            query = query.filter(Patient.doctor_id == user_uuid)

        filters = []
        if start_date:
            filters.append(QuizSession.created_at >= start_date)
        if end_date:
            filters.append(QuizSession.created_at <= end_date)
        if filters:
            query = query.filter(and_(*filters))

        sessions = query.options(joinedload(QuizSession.quiz_template)).all()

        total_sessions = len(sessions)
        completed_sessions = sum(1 for s in sessions if s.status == "completed")
        completion_rate = (
            (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
        )

        scores = [float(s.score) for s in sessions if s.score is not None]
        average_score = sum(scores) / len(scores) if scores else None

        times = [
            s.time_spent_seconds for s in sessions if s.time_spent_seconds is not None
        ]
        average_time_minutes = (sum(times) / len(times) / 60) if times else None

        category_breakdown = {}
        template_counts = {}
        trend_data = {}

        for session in sessions:
            if session.quiz_template:
                if session.quiz_template.category:
                    cat = session.quiz_template.category
                    category_breakdown[cat] = category_breakdown.get(cat, 0) + 1

                template_id = str(session.quiz_template_id)
                if template_id not in template_counts:
                    template_counts[template_id] = {
                        "template_id": template_id,
                        "template_name": session.quiz_template.name,
                        "count": 0,
                    }
                template_counts[template_id]["count"] += 1

            if include_trends:
                date_key = session.created_at.date().isoformat()
                if date_key not in trend_data:
                    trend_data[date_key] = {"total": 0, "completed": 0, "scores": []}
                trend_data[date_key]["total"] += 1
                if session.status == "completed":
                    trend_data[date_key]["completed"] += 1
                if session.score:
                    trend_data[date_key]["scores"].append(float(session.score))

        top_templates = sorted(
            template_counts.values(), key=lambda x: x["count"], reverse=True
        )[:5]

        trends = []
        if include_trends:
            for date_key, data in sorted(trend_data.items()):
                trends.append(
                    QuizAnalyticsTrend(
                        date=date_key,
                        total_sessions=data["total"],
                        completed_sessions=data["completed"],
                        completion_rate=round(
                            (data["completed"] / data["total"] * 100)
                            if data["total"] > 0
                            else 0,
                            2,
                        ),
                        average_score=round(
                            sum(data["scores"]) / len(data["scores"]), 2
                        )
                        if data["scores"]
                        else None,
                    )
                )

        result = QuizAnalyticsResponse(
            total_sessions=total_sessions,
            completed_sessions=completed_sessions,
            completion_rate=round(completion_rate, 2),
            average_score=round(average_score, 2) if average_score else None,
            average_time_minutes=round(average_time_minutes, 2)
            if average_time_minutes
            else None,
            trends=trends,
            category_breakdown=category_breakdown,
            risk_distribution={
                "low": int(total_sessions * 0.6),
                "medium": int(total_sessions * 0.25),
                "high": int(total_sessions * 0.10),
                "critical": int(total_sessions * 0.05),
            },
            top_templates=top_templates,
        )

        await self._set_cached_result(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

    async def create_advanced_template(
        self, template_data: AdvancedQuizTemplate, user_id: Optional[UUID]
    ) -> Dict[str, Any]:
        template_dict = template_data.dict()
        questions_json = [
            q.dict() if hasattr(q, "dict") else q for q in template_dict["questions"]
        ]

        new_template = QuizTemplate(
            name=template_dict["title"],
            version="1.0",
            description=template_dict.get("description"),
            category=template_dict["category"].value,
            questions=questions_json,
            is_active=template_dict.get("is_active", True),
            passing_score=int(template_dict.get("passing_score"))
            if template_dict.get("passing_score")
            else None,
            time_limit_minutes=template_dict.get("time_limit_minutes"),
            randomize_questions=template_dict.get("randomize_questions", False),
            tags=template_dict.get("tags", []),
        )

        self.db.add(new_template)
        self.db.commit()
        self.db.refresh(new_template)

        return {
            "id": str(new_template.id),
            "name": new_template.name,
            "category": new_template.category,
            "questions_count": len(questions_json),
            "adaptive_flow_enabled": template_dict.get("adaptive_flow_enabled", False),
            "risk_scoring_enabled": template_dict.get("risk_scoring_enabled", False),
            "created_at": new_template.created_at.isoformat(),
        }

    async def process_adaptive_flow(
        self,
        flow_request: AdaptiveQuizFlowRequest,
        user_uuid: Optional[UUID],
        role_enum: Optional[UserRole],
    ) -> AdaptiveQuizFlowResponse:
        session_uuid = UUID(flow_request.session_id)
        session = (
            self.db.query(QuizSession).filter(QuizSession.id == session_uuid).first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Quiz session not found")

        if role_enum != UserRole.ADMIN:
            patient = (
                self.db.query(Patient).filter(Patient.id == session.patient_id).first()
            )
            if patient and patient.doctor_id != user_uuid:
                raise HTTPException(status_code=403, detail="Not authorized")

        template = (
            self.db.query(QuizTemplate)
            .filter(QuizTemplate.id == session.quiz_template_id)
            .first()
        )
        if not template:
            raise HTTPException(status_code=404, detail="Quiz template not found")

        new_response = QuizResponse(
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            quiz_session_id=session.id,
            question_id=flow_request.current_question_id,
            question_text="",
            response_type="adaptive",
            response_value=str(flow_request.response_value),
            response_metadata=flow_request.response_metadata or {},
            responded_at=datetime.now(timezone.utc),
        )
        self.db.add(new_response)

        questions = template.questions if isinstance(template.questions, list) else []
        current_question_idx = next(
            (
                i
                for i, q in enumerate(questions)
                if q.get("id") == flow_request.current_question_id
            ),
            -1,
        )

        next_question = None
        alerts = []

        if current_question_idx >= 0 and current_question_idx < len(questions):
            current_q = questions[current_question_idx]
            branching_rules = current_q.get("branching_rules", [])
            response_data = {
                flow_request.current_question_id: flow_request.response_value
            }

            for rule in branching_rules:
                conditions = rule.get("conditions", [])
                logic = rule.get("logic", "AND")
                condition_results = [
                    self._evaluate_branching_condition(cond, response_data)
                    for cond in conditions
                ]
                matches = (
                    all(condition_results) if logic == "AND" else any(condition_results)
                )

                if matches:
                    if rule.get("show_alert"):
                        alerts.append(rule["show_alert"])
                    if rule.get("next_question_id"):
                        next_q_id = rule["next_question_id"]
                        next_q = next(
                            (q for q in questions if q.get("id") == next_q_id), None
                        )
                        if next_q:
                            next_question = QuizQuestion(**next_q)
                            break

            if not next_question and current_question_idx + 1 < len(questions):
                next_q = questions[current_question_idx + 1]
                next_question = QuizQuestion(**next_q)

        session.current_question = (
            (current_question_idx + 1) if next_question else len(questions)
        )
        session.answered_questions = (session.answered_questions or 0) + 1
        is_completed = next_question is None

        if is_completed:
            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)

        self.db.commit()

        total_questions = len(questions)
        progress_percentage = (
            (session.answered_questions / total_questions * 100)
            if total_questions > 0
            else 0
        )
        estimated_remaining = max(0, total_questions - session.answered_questions) * 2

        return AdaptiveQuizFlowResponse(
            next_question=next_question,
            is_completed=is_completed,
            alerts=alerts,
            progress_percentage=round(progress_percentage, 2),
            estimated_remaining_minutes=estimated_remaining
            if not is_completed
            else None,
        )

    async def calculate_risk_score(
        self,
        risk_request: RiskScoringRequest,
        user_uuid: Optional[UUID],
        role_enum: Optional[UserRole],
    ) -> RiskScoringResponse:
        cache_key = self._get_cache_key(
            "risk-scoring",
            patient_id=risk_request.patient_id,
            session_id=risk_request.session_id,
            lookback_days=risk_request.lookback_days,
            role=role_enum.value if role_enum else None,
            user=str(user_uuid) if user_uuid else None,
        )
        cached = await self._get_cached_result(cache_key)
        if cached:
            return RiskScoringResponse(**cached)

        patient_uuid = UUID(risk_request.patient_id)
        patient = self.db.query(Patient).filter(Patient.id == patient_uuid).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        if role_enum != UserRole.ADMIN and patient.doctor_id != user_uuid:
            raise HTTPException(status_code=403, detail="Not authorized")

        lookback_date = datetime.now(timezone.utc) - timedelta(days=risk_request.lookback_days)
        query = self.db.query(QuizSession).filter(
            and_(
                QuizSession.patient_id == patient_uuid,
                QuizSession.created_at >= lookback_date,
                QuizSession.status == "completed",
            )
        )
        if risk_request.session_id:
            query = query.filter(QuizSession.id == UUID(risk_request.session_id))

        # FIX: Use selectinload for one-to-many relationships to avoid cartesian product
        # joinedload for one-to-one (quiz_template), selectinload for one-to-many (responses)
        from sqlalchemy.orm import selectinload
        sessions = query.options(
            joinedload(QuizSession.quiz_template),
            selectinload(QuizSession.responses)
        ).all()
        if not sessions:
            raise HTTPException(status_code=404, detail="No sessions found")

        latest_session = sessions[0]
        # FIX: Use already-loaded responses from selectinload instead of N+1 queries
        # The responses are already loaded via selectinload(QuizSession.responses) above
        responses = list(latest_session.responses) if latest_session.responses else []
        current_risk = self._calculate_risk_score(
            responses, latest_session.quiz_template
        )

        historical_scores = []
        if risk_request.include_historical and len(sessions) > 1:
            # FIX: Use already-loaded relationships instead of individual queries per session
            # This eliminates the N+1 pattern that was causing len(sessions)-1 extra queries
            for session in sessions[1:]:
                # Use eager-loaded responses directly
                s_responses = list(session.responses) if session.responses else []
                if s_responses:
                    risk = self._calculate_risk_score(
                        s_responses, session.quiz_template
                    )
                    historical_scores.append(
                        {
                            "date": session.created_at.isoformat(),
                            "risk_score": risk.risk_score,
                            "risk_level": risk.overall_risk_level.value,
                        }
                    )

        trend = "stable"
        if len(historical_scores) > 0:
            recent = [current_risk.risk_score] + [
                h["risk_score"] for h in historical_scores[:2]
            ]
            if len(recent) >= 2:
                if recent[0] > recent[1] + 10:
                    trend = "worsening"
                elif recent[0] < recent[1] - 10:
                    trend = "improving"

        result = RiskScoringResponse(
            patient_id=risk_request.patient_id,
            assessment_date=datetime.now(timezone.utc),
            current_risk=current_risk,
            trend=trend,
            historical_scores=historical_scores,
        )
        await self._set_cached_result(cache_key, result, QUIZ_RESULTS_CACHE_TTL)
        return result

    async def get_quiz_recommendations(
        self, patient_id: str, user_uuid: Optional[UUID], role_enum: Optional[UserRole]
    ) -> QuizRecommendationsResponse:
        cache_key = self._get_cache_key(
            "recommendations",
            patient_id=patient_id,
            role=role_enum.value if role_enum else None,
            user=str(user_uuid) if user_uuid else None,
        )
        cached = await self._get_cached_result(cache_key)
        if cached:
            return QuizRecommendationsResponse(**cached)

        patient_uuid = UUID(patient_id)
        patient = self.db.query(Patient).filter(Patient.id == patient_uuid).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        if role_enum != UserRole.ADMIN and patient.doctor_id != user_uuid:
            raise HTTPException(status_code=403, detail="Not authorized")

        recent_sessions = (
            self.db.query(QuizSession)
            .filter(
                and_(
                    QuizSession.patient_id == patient_uuid,
                    QuizSession.created_at >= datetime.now(timezone.utc) - timedelta(days=90),
                )
            )
            .options(joinedload(QuizSession.quiz_template))
            .all()
        )
        available_templates = (
            self.db.query(QuizTemplate).filter(QuizTemplate.is_active).all()
        )
        completed_ids = {
            str(s.quiz_template_id) for s in recent_sessions if s.status == "completed"
        }

        recommendations = []
        for template in available_templates:
            if str(template.id) in completed_ids:
                continue
            priority = "low"
            reason = "Recommended based on treatment plan"
            if template.category == "pain_assessment":
                priority, reason = "high", "Regular pain assessment recommended"
            elif template.category == "symptoms":
                priority, reason = "medium", "Symptom monitoring recommended"

            recommendations.append(
                QuizRecommendation(
                    template_id=str(template.id),
                    template_title=template.name,
                    category=QuizCategory(template.category)
                    if template.category
                    else QuizCategory.GENERAL_HEALTH,
                    priority=priority,
                    reason=reason,
                    due_date=datetime.now(timezone.utc) + timedelta(days=7),
                )
            )

        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x.priority, 3))
        result = QuizRecommendationsResponse(
            patient_id=patient_id,
            recommendations=recommendations[:10],
            total_recommendations=len(recommendations),
        )
        await self._set_cached_result(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

    async def get_performance_metrics(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        compare_period: bool,
        role_enum: Optional[UserRole],
        user_uuid: Optional[UUID],
    ) -> PerformanceMetricsResponse:
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        cache_key = self._get_cache_key(
            "performance-metrics",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            compare_period=compare_period,
            role=role_enum.value if role_enum else None,
            user=str(user_uuid) if user_uuid else None,
        )
        cached = await self._get_cached_result(cache_key)
        if cached:
            return PerformanceMetricsResponse(**cached)

        query = self.db.query(QuizSession).join(
            Patient, Patient.id == QuizSession.patient_id
        )
        if role_enum != UserRole.ADMIN and user_uuid:
            query = query.filter(Patient.doctor_id == user_uuid)

        current_sessions = query.filter(
            and_(
                QuizSession.created_at >= start_date, QuizSession.created_at <= end_date
            )
        ).all()

        previous_sessions = []
        if compare_period:
            period_length = (end_date - start_date).days
            prev_start = start_date - timedelta(days=period_length)
            previous_sessions = query.filter(
                and_(
                    QuizSession.created_at >= prev_start,
                    QuizSession.created_at < start_date,
                )
            ).all()

        metrics = []
        # Completion Rate
        cur_comp = sum(1 for s in current_sessions if s.status == "completed")
        cur_total = len(current_sessions)
        cur_rate = (cur_comp / cur_total * 100) if cur_total > 0 else 0
        prev_comp = sum(1 for s in previous_sessions if s.status == "completed")
        prev_total = len(previous_sessions)
        prev_rate = (prev_comp / prev_total * 100) if prev_total > 0 else 0
        comp_change = cur_rate - prev_rate if compare_period else None
        metrics.append(
            PerformanceMetric(
                metric_name="completion_rate",
                current_value=round(cur_rate, 2),
                previous_value=round(prev_rate, 2) if compare_period else None,
                change_percentage=round(comp_change, 2) if comp_change else None,
                trend="up"
                if comp_change and comp_change > 0
                else "down"
                if comp_change and comp_change < 0
                else "stable",
            )
        )

        # Avg Response Time
        cur_times = [
            s.time_spent_seconds for s in current_sessions if s.time_spent_seconds
        ]
        cur_avg = sum(cur_times) / len(cur_times) if cur_times else 0
        prev_times = [
            s.time_spent_seconds for s in previous_sessions if s.time_spent_seconds
        ]
        prev_avg = sum(prev_times) / len(prev_times) if prev_times else 0
        time_change = ((cur_avg - prev_avg) / prev_avg * 100) if prev_avg > 0 else None
        metrics.append(
            PerformanceMetric(
                metric_name="average_response_time_seconds",
                current_value=round(cur_avg, 2),
                previous_value=round(prev_avg, 2) if compare_period else None,
                change_percentage=round(time_change, 2) if time_change else None,
                trend="down"
                if time_change and time_change < 0
                else "up"
                if time_change and time_change > 0
                else "stable",
            )
        )

        # Volume
        vol_change = (
            ((cur_total - prev_total) / prev_total * 100) if prev_total > 0 else None
        )
        metrics.append(
            PerformanceMetric(
                metric_name="session_volume",
                current_value=float(cur_total),
                previous_value=float(prev_total) if compare_period else None,
                change_percentage=round(vol_change, 2) if vol_change else None,
                trend="up"
                if vol_change and vol_change > 0
                else "down"
                if vol_change and vol_change < 0
                else "stable",
            )
        )

        insights = []
        if comp_change and comp_change > 5:
            insights.append(f"Completion rate improved by {abs(comp_change):.1f}%")
        if time_change and time_change < -10:
            insights.append("Response time improved significantly")

        result = PerformanceMetricsResponse(
            period_start=start_date,
            period_end=end_date,
            metrics=metrics,
            insights=insights,
        )
        await self._set_cached_result(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

    async def execute_bulk_operations(
        self,
        operation: BulkQuizOperation,
        user_uuid: Optional[UUID],
        role_enum: Optional[UserRole],
    ) -> BulkOperationResponse:
        job_id = f"bulk-quiz-{uuid.uuid4().hex[:12]}"
        patient_uuids = [UUID(pid) for pid in operation.patient_ids]
        patients = self.db.query(Patient).filter(Patient.id.in_(patient_uuids)).all()

        if role_enum != UserRole.ADMIN:
            unauthorized = [p for p in patients if p.doctor_id != user_uuid]
            if unauthorized:
                raise HTTPException(
                    status_code=403,
                    detail=f"Not authorized for {len(unauthorized)} patients",
                )

        successful, failed, errors = 0, 0, []

        if operation.operation == "assign":
            template_uuid = UUID(operation.template_id)
            template = (
                self.db.query(QuizTemplate)
                .filter(QuizTemplate.id == template_uuid)
                .first()
            )
            if not template or not template.is_active:
                raise HTTPException(
                    status_code=404, detail="Template not found/inactive"
                )

            for patient in patients:
                try:
                    existing = (
                        self.db.query(QuizSession)
                        .filter(
                            and_(
                                QuizSession.patient_id == patient.id,
                                QuizSession.quiz_template_id == template_uuid,
                                QuizSession.status == "started",
                            )
                        )
                        .first()
                    )
                    if not existing:
                        self.db.add(
                            QuizSession(
                                patient_id=patient.id,
                                quiz_template_id=template_uuid,
                                status="started",
                                started_at=operation.scheduled_for or datetime.now(timezone.utc),
                            )
                        )
                        successful += 1
                    else:
                        failed += 1
                        errors.append(f"Active session exists for patient {patient.id}")
                except Exception as e:
                    failed += 1
                    errors.append(f"Patient {patient.id}: {str(e)}")
            self.db.commit()

        elif operation.operation == "delete":
            for pid in patient_uuids:
                try:
                    count = (
                        self.db.query(QuizSession)
                        .filter(QuizSession.patient_id == pid)
                        .delete()
                    )
                    if count > 0:
                        successful += count
                except Exception as e:
                    failed += 1
                    errors.append(f"Patient {pid}: {str(e)}")
            self.db.commit()

        elif operation.operation == "update":
            update_data = operation.update_data or {}
            for pid in patient_uuids:
                try:
                    sessions = (
                        self.db.query(QuizSession)
                        .filter(QuizSession.patient_id == pid)
                        .all()
                    )
                    for s in sessions:
                        for k, v in update_data.items():
                            if hasattr(s, k):
                                setattr(s, k, v)
                    successful += len(sessions)
                except Exception as e:
                    failed += 1
                    errors.append(f"Patient {pid}: {str(e)}")
            self.db.commit()

        return BulkOperationResponse(
            job_id=job_id,
            operation=operation.operation,
            total_patients=len(operation.patient_ids),
            status="completed",
            successful=successful,
            failed=failed,
            errors=errors[:10],
        )

    async def export_quiz_data(
        self,
        export_request: QuizExportRequest,
        user_uuid: Optional[UUID],
        role_enum: Optional[UserRole],
    ) -> QuizExportResponse:
        export_id = f"export-{uuid.uuid4().hex[:12]}"
        query = self.db.query(QuizSession).join(
            Patient, Patient.id == QuizSession.patient_id
        )
        if role_enum != UserRole.ADMIN and user_uuid:
            query = query.filter(Patient.doctor_id == user_uuid)

        filters = []
        if export_request.patient_ids:
            filters.append(
                QuizSession.patient_id.in_(
                    [UUID(p) for p in export_request.patient_ids]
                )
            )
        if export_request.template_ids:
            filters.append(
                QuizSession.quiz_template_id.in_(
                    [UUID(t) for t in export_request.template_ids]
                )
            )
        if export_request.start_date:
            filters.append(QuizSession.created_at >= export_request.start_date)
        if export_request.end_date:
            filters.append(QuizSession.created_at <= export_request.end_date)
        if filters:
            query = query.filter(and_(*filters))

        total = query.count()
        if total == 0:
            raise HTTPException(status_code=404, detail="No quiz data found")

        return QuizExportResponse(
            export_id=export_id,
            format=export_request.format,
            status="processing",
            download_url=None,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            file_size_bytes=None,
        )
