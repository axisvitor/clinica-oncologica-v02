"""State Manager - Manages flow context and patient state."""

from __future__ import annotations

# DDD service agent - no LLM calls, not a pydantic-ai migration target.

# Standard library
import logging
from datetime import timedelta
from typing import Any, Dict, List
from uuid import UUID

# Third-party
from sqlalchemy import func
from sqlalchemy.orm import Session

# Local
from app.models.message import Message, MessageDirection
from app.models.quiz import QuizSession
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.services.flow.flags import message_expects_response
from app.utils.timezone import now_sao_paulo

from .models import FlowContext


def _get_knowledge_graph():
    """Lazy import for KnowledgeGraph to prevent startup failures."""
    try:
        from app.memory.knowledge_graph import KnowledgeGraph

        return KnowledgeGraph
    except ImportError as e:
        logging.warning(f"KnowledgeGraph import failed: {e}")
        return None


class StateManager:
    """
    Manages flow state and context building.

    Builds comprehensive context for flow decision making
    by aggregating patient data, flow states, interactions,
    and knowledge graph insights.

    Attributes:
        db_session: Database session.
        agent_id: Unique agent identifier.
        logger: Logger instance.
        patient_repo: Patient repository.
        flow_repo: Flow state repository.
        knowledge_graph: Knowledge graph instance (optional).
    """

    def __init__(self, db_session: Session, agent_id: str, logger: logging.Logger):
        self.db_session = db_session
        self.agent_id = agent_id
        self.logger = logger
        self.patient_repo = PatientRepository(db_session)
        self.flow_repo = FlowStateRepository(db_session)
        self.knowledge_graph = None

    async def initialize_knowledge_graph(self):
        """Initialize knowledge graph with lazy loading."""
        KnowledgeGraph = _get_knowledge_graph()
        if KnowledgeGraph:
            self.knowledge_graph = KnowledgeGraph(self.db_session)
            await self.knowledge_graph.initialize()
        else:
            self.knowledge_graph = None
            self.logger.warning(
                "Knowledge graph not available - some features may be limited"
            )

    async def build_flow_context(
        self, patient_id: UUID, current_day: int
    ) -> FlowContext:
        """Build comprehensive context for flow decision making."""
        context = FlowContext()
        context.patient_id = patient_id
        context.current_day = current_day

        # Get patient data
        context.patient_data = self.patient_repo.get(patient_id)

        # Get flow state
        flow_states = self.flow_repo.get_by_patient_id(patient_id)
        context.flow_state = flow_states[0] if flow_states else None

        # Get knowledge graph context
        if self.knowledge_graph:
            context.knowledge_context = await self.knowledge_graph.get_patient_context(
                patient_id
            )

        # Analyze recent interactions
        context.recent_interactions = await self._get_recent_interactions(patient_id)

        # Calculate mood indicators
        context.mood_indicators = await self._analyze_mood_indicators(context)

        # Calculate adherence metrics
        context.adherence_metrics = await self._calculate_adherence_metrics(context)

        # Identify risk factors
        context.risk_factors = await self._identify_risk_factors(context)

        return context

    async def _get_recent_interactions(self, patient_id: UUID) -> List[Dict]:
        """Get recent patient interactions."""
        messages = (
            self.db_session.query(Message)
            .filter(
                Message.patient_id == patient_id,
                Message.content.isnot(None),
                Message.content != "",
            )
            .order_by(Message.created_at.desc())
            .limit(40)
            .all()
        )
        if not messages:
            return []

        interactions: List[Dict[str, Any]] = []
        current_question: Message | None = None
        current_responses: List[Message] = []

        for msg in reversed(messages):
            if msg.direction == MessageDirection.OUTBOUND and message_expects_response(msg):
                if current_question and current_responses:
                    interactions.append(
                        self._build_interaction_payload(
                            current_question, current_responses
                        )
                    )
                current_question = msg
                current_responses = []
                continue

            if msg.direction == MessageDirection.INBOUND and current_question:
                current_responses.append(msg)

        if current_question and current_responses:
            interactions.append(
                self._build_interaction_payload(current_question, current_responses)
            )

        return interactions[-7:]

    @staticmethod
    def _build_interaction_payload(
        question: Message, responses: List[Message]
    ) -> Dict[str, Any]:
        """Build normalized interaction payload from one outbound question and responses."""
        return {
            "question": question.content,
            "answer": "\n".join(
                response.content for response in responses if response.content
            ).strip(),
            "asked_at": (question.sent_at or question.created_at).isoformat()
            if (question.sent_at or question.created_at)
            else None,
            "answered_at": responses[-1].created_at.isoformat()
            if responses[-1].created_at
            else None,
        }

    async def _analyze_mood_indicators(self, context: FlowContext) -> Dict[str, Any]:
        """Analyze mood indicators from patient context."""
        mood_data = {"trend": 0.0, "current_level": 3.0, "confidence": 0.5}

        # Extract mood data from knowledge graph
        if context.knowledge_context.get("patterns"):
            for pattern in context.knowledge_context["patterns"]:
                if "mood" in pattern.get("pattern_type", ""):
                    if "improvement" in pattern["pattern_type"]:
                        mood_data["trend"] = 0.7
                    elif "decline" in pattern["pattern_type"]:
                        mood_data["trend"] = -0.7

                    mood_data["confidence"] = pattern.get("confidence", 0.5)
                    break

        return mood_data

    async def _calculate_adherence_metrics(
        self, context: FlowContext
    ) -> Dict[str, float]:
        """Calculate patient adherence metrics."""
        if not context.patient_id:
            return {
                "message_response_rate": 0.0,
                "quiz_completion_rate": 0.0,
                "scheduled_engagement_rate": 0.0,
            }

        interactions = context.recent_interactions or []
        answered = sum(1 for interaction in interactions if interaction.get("answer"))
        total_questions = len(interactions)
        message_response_rate = (
            answered / total_questions if total_questions > 0 else 0.0
        )

        window_start = now_sao_paulo() - timedelta(days=30)
        recent_quizzes = (
            self.db_session.query(QuizSession.status)
            .filter(
                QuizSession.patient_id == context.patient_id,
                QuizSession.started_at >= window_start,
            )
            .all()
        )
        total_quizzes = len(recent_quizzes)
        completed_quizzes = sum(
            1 for quiz_status, in recent_quizzes if str(quiz_status) == "completed"
        )
        quiz_completion_rate = (
            completed_quizzes / total_quizzes if total_quizzes > 0 else 0.0
        )

        active_days = (
            self.db_session.query(func.count(func.distinct(func.date(Message.created_at))))
            .filter(
                Message.patient_id == context.patient_id,
                Message.created_at >= window_start,
            )
            .scalar()
            or 0
        )
        expected_days = min(30, max(int(context.current_day or 1), 1))
        scheduled_engagement_rate = min(1.0, float(active_days) / float(expected_days))

        return {
            "message_response_rate": round(message_response_rate, 4),
            "quiz_completion_rate": round(quiz_completion_rate, 4),
            "scheduled_engagement_rate": round(scheduled_engagement_rate, 4),
        }

    async def _identify_risk_factors(self, context: FlowContext) -> List[str]:
        """Identify risk factors from patient context."""
        risk_factors = []

        # Check mood decline
        if context.mood_indicators.get("trend", 0) < -0.6:
            risk_factors.append("mood_decline")

        # Check low engagement
        if context.adherence_metrics.get("message_response_rate", 1.0) < 0.3:
            risk_factors.append("low_engagement")

        # Check recurring symptoms from patterns
        if context.knowledge_context.get("patterns"):
            for pattern in context.knowledge_context["patterns"]:
                if pattern.get("pattern_type") == "recurring_symptom":
                    risk_factors.append(
                        f"recurring_{pattern.get('description', 'symptom')}"
                    )

        return risk_factors

    async def close(self):
        """Cleanup resources."""
        if self.knowledge_graph:
            await self.knowledge_graph.close()
