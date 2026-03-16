"""
Session Coordinator - Manages quiz session lifecycle.

Handles session creation, context building, completion, and state management.
"""

from __future__ import annotations

# Standard library imports
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

# Third-party imports
from sqlalchemy.orm import Session

# Local application imports
from app.agents.base import MessagePriority
from app.agents.registry import ALERT_ANALYZER_ID, PATIENT_MONITOR_ID, FLOW_COORDINATOR_ID
from app.models.quiz import QuizResponse, QuizSession
from app.repositories.patient import PatientRepository
from app.schemas.quiz import QuizSessionCreate
from app.services.quiz import QuizResponseService, QuizSessionService, QuizTemplateService
from .types import QuizContext

if TYPE_CHECKING:
    from app.domain.agents.quiz.progress_tracker import ProgressTracker
    from app.domain.agents.quiz.question_presenter import QuestionPresenter

def _get_knowledge_graph():
    """Lazy import for KnowledgeGraph to prevent startup failures."""
    try:
        from app.memory.knowledge_graph import KnowledgeGraph

        return KnowledgeGraph
    except ImportError as e:
        logging.warning(f"KnowledgeGraph import failed: {e}")
        return None


class SessionCoordinator:
    """
    Coordinates quiz session lifecycle and state management.

    Manages quiz session creation, context building, completion,
    and integration with knowledge graph.

    Attributes:
        db_session: Database session.
        quiz_template_service: Template service.
        quiz_session_service: Session service.
        patient_repo: Patient repository.
        agent_id: ID of owning agent.
        knowledge_graph: Knowledge graph instance.
    """

    def __init__(
        self,
        db_session: Session,
        quiz_template_service: QuizTemplateService,
        quiz_session_service: QuizSessionService,
        quiz_response_service: Optional[QuizResponseService],
        patient_repo: PatientRepository,
        agent_id: str,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize session coordinator.

        Args:
            db_session: Database session.
            quiz_template_service: Quiz template service.
            quiz_session_service: Quiz session service.
            quiz_response_service: Quiz response service.
            patient_repo: Patient repository.
            agent_id: Agent identifier.
            logger: Logger instance.
        """
        self.db_session = db_session
        self.quiz_template_service = quiz_template_service
        self.quiz_session_service = quiz_session_service
        self.quiz_response_service = quiz_response_service
        self.patient_repo = patient_repo
        self.agent_id = agent_id
        self._logger = logger or logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Knowledge graph (initialized during start)
        self.knowledge_graph = None

    async def initialize_knowledge_graph(self):
        """Initialize knowledge graph connection."""
        try:
            KnowledgeGraph = _get_knowledge_graph()
            if KnowledgeGraph:
                self.knowledge_graph = KnowledgeGraph(self.db_session)
                await self.knowledge_graph.initialize()
        except Exception as e:
            self._logger.error(f"Failed to initialize knowledge graph: {e}")

    async def build_quiz_context(
        self, patient_id: UUID, quiz_type: str, progress_tracker: "ProgressTracker"
    ) -> QuizContext:
        """Build comprehensive quiz context."""
        context = QuizContext()
        context.patient_id = patient_id

        # Get patient data
        context.patient_data = self.patient_repo.get(patient_id)
        if context.patient_data is None:
            self._logger.warning("Patient %s not found while building quiz context", patient_id)

        # Get active quiz session
        active_session = self.quiz_session_service.get_active_session(patient_id)
        if active_session:
            context.session = active_session
            try:
                context.current_question = int(
                    getattr(active_session, "current_question", 0) or 0
                )
            except (TypeError, ValueError):
                context.current_question = 0

            # Get template
            try:
                context.template = await self.quiz_template_service.get_template(
                    active_session.quiz_template_id
                )
            except Exception as exc:
                self._logger.error(
                    "Failed to load template %s for session %s: %s",
                    active_session.quiz_template_id,
                    active_session.id,
                    exc,
                )
                context.template = None

        # Get knowledge graph context
        if self.knowledge_graph:
            try:
                context.knowledge_context = (
                    await self.knowledge_graph.get_patient_context(patient_id)
                )
            except Exception as e:
                self._logger.error(f"Failed to get knowledge context: {e}")
                context.knowledge_context = {}

        # Analyze patient state using progress tracker
        context.mood_indicators = await progress_tracker.analyze_current_mood(context)
        context.stress_level = await progress_tracker.assess_stress_level(context)
        context.engagement_score = await progress_tracker.calculate_engagement_score(
            context
        )

        # Get previous responses
        if context.session:
            context.responses_so_far = await self.get_session_responses(
                context.session.id
            )

        return context

    async def create_quiz_session(
        self,
        context: QuizContext,
        quiz_type: str,
        question_presenter: "QuestionPresenter",
    ) -> Optional[QuizSession]:
        """Create new quiz session."""
        try:
            if not context.patient_id:
                self._logger.error("Cannot create quiz session without patient_id")
                return None

            # Get or create appropriate template
            template = context.template or await question_presenter.get_or_create_quiz_template(
                quiz_type, context
            )

            if not template:
                self._logger.error(f"Failed to get quiz template for type: {quiz_type}")
                return None

            # Create session
            session_data = QuizSessionCreate(
                patient_id=context.patient_id, quiz_template_id=template.id
            )

            session = self.quiz_session_service.start_quiz_session(session_data)

            # Update session metadata with swarm context
            session_metadata = {
                "quiz_type": quiz_type,
                "conducted_by_agent": self.agent_id,
                "initial_mood": context.mood_indicators,
                "initial_stress": context.stress_level,
                "personalization_applied": True,
                "swarm_coordination": True,
            }

            # Add context from knowledge graph
            if context.knowledge_context.get("patterns"):
                session_metadata["known_patterns"] = [
                    p.get("pattern_type")
                    for p in context.knowledge_context["patterns"][-3:]
                ]

            existing_metadata = getattr(session, "session_metadata", None)
            if not isinstance(existing_metadata, dict):
                existing_metadata = {}
            session.session_metadata = {**existing_metadata, **session_metadata}
            self.db_session.flush()

            context.template = template
            context.session = session
            return session

        except Exception as e:
            self._logger.error(f"Failed to create quiz session: {e}")
            return None

    async def complete_quiz_session(self, context: QuizContext, send_message_callback):
        """Complete quiz session with comprehensive analysis."""
        try:
            if not context.session:
                self._logger.warning(
                    "Quiz completion requested without active session for patient %s",
                    context.patient_id,
                )
                return

            # Mark session as completed
            self.quiz_session_service.complete_session(context.session.id)

            # Evaluate quiz responses against clinical alert rules
            try:
                from app.domain.quizzes.evaluation.response_evaluator import QuizResponseEvaluator

                # Transform responses_so_far (List[Dict]) into flat Dict[str, Any]
                flat_responses: Dict[str, Any] = {}
                for resp in (context.responses_so_far or []):
                    q_id = resp.get("question_id")
                    if q_id is not None:
                        flat_responses[str(q_id)] = resp.get("response_value")

                if flat_responses:
                    evaluator = QuizResponseEvaluator(self.db_session)
                    alerts, risk_score = await evaluator.evaluate_quiz_session(
                        context.session.id, context.patient_id, flat_responses
                    )
                    if alerts:
                        self._logger.info(
                            "Quiz evaluation produced %d alerts (risk %.1f) for patient %s",
                            len(alerts), risk_score, context.patient_id,
                        )
                else:
                    self._logger.debug(
                        "No flat responses to evaluate for session %s",
                        context.session.id,
                    )
            except Exception as e:
                self._logger.error(
                    "Quiz response evaluation failed for session %s: %s",
                    context.session.id, e,
                    exc_info=True,
                )

            # Trigger comprehensive analysis
            await self.trigger_comprehensive_analysis(context, send_message_callback)

            # Update knowledge graph with session insights
            if self.knowledge_graph:
                try:
                    await self.knowledge_graph.add_quiz_session_node(context.session)

                    # Discover new patterns
                    patterns = await self.knowledge_graph.discover_patterns(
                        context.patient_id
                    )
                    if patterns:
                        self._logger.info(
                            f"Discovered {len(patterns)} new patterns for patient {context.patient_id}"
                        )
                except Exception as e:
                    self._logger.error(f"Failed to update knowledge graph: {e}")

        except Exception as e:
            self._logger.error(f"Quiz completion failed: {e}")

    async def trigger_comprehensive_analysis(
        self, context: QuizContext, send_message_callback
    ):
        """Trigger comprehensive analysis by multiple agents."""
        analysis_data = {
            "patient_id": str(context.patient_id),
            "session_id": str(context.session.id),
            "responses_count": len(context.responses_so_far),
            "adaptations_made": len(context.adaptation_history),
            "final_mood": context.mood_indicators,
            "engagement_level": context.engagement_score,
        }

        # Request analysis from different agents
        analysis_agents = [
            ALERT_ANALYZER_ID,
            PATIENT_MONITOR_ID,
            FLOW_COORDINATOR_ID,
        ]

        for agent_id in analysis_agents:
            try:
                await send_message_callback(
                    agent_id,
                    "analyze_completed_quiz",
                    analysis_data,
                    MessagePriority.NORMAL,
                )
            except Exception as e:
                self._logger.error(f"Failed to request analysis from {agent_id}: {e}")

    async def get_session_responses(
        self, session_id: UUID, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get most recent responses for current session (default: last 5)."""
        if self.quiz_response_service is not None:
            responses = self.quiz_response_service.get_session_responses(session_id)
            if limit > 0:
                responses = responses[-limit:]
        else:
            responses = (
                self.db_session.query(QuizResponse)
                .filter(QuizResponse.quiz_session_id == session_id)
                .order_by(QuizResponse.responded_at.desc())
                .limit(limit)
                .all()
            )
            responses = list(reversed(responses))

        payloads: List[Dict[str, Any]] = []
        for response in responses:
            metadata = response.response_metadata or {}
            confidence = metadata.get("confidence", 1.0)
            value = response.response_value
            payloads.append(
                {
                    "question_id": response.question_id,
                    "question_text": response.question_text,
                    "response_type": response.response_type,
                    "processed_value": value,
                    "confidence": confidence,
                    "responded_at": response.responded_at.isoformat()
                    if response.responded_at
                    else None,
                }
            )

        return payloads
