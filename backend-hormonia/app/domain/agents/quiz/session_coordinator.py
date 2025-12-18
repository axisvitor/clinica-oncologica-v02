"""
Session Coordinator - Manages quiz session lifecycle.

Handles session creation, context building, completion, and state management.
"""

import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.domain.agents.quiz.progress_tracker import ProgressTracker
    from app.domain.agents.quiz.question_presenter import QuestionPresenter

from app.models.patient import Patient
from app.models.quiz import QuizTemplate, QuizSession
from app.schemas.quiz import QuizSessionCreate
from app.services.quiz import QuizTemplateService, QuizSessionService
from app.repositories.patient import PatientRepository
from app.agents.base import MessagePriority


def _get_knowledge_graph():
    """Lazy import for KnowledgeGraph to prevent startup failures."""
    try:
        from app.memory.knowledge_graph import KnowledgeGraph

        return KnowledgeGraph
    except ImportError as e:
        logging.warning(f"KnowledgeGraph import failed: {e}")
        return None


class QuizContext:
    """Context for quiz conduction and adaptation."""

    def __init__(self):
        self.patient_id: Optional[UUID] = None
        self.session: Optional[QuizSession] = None
        self.template: Optional[QuizTemplate] = None
        self.patient_data: Optional[Patient] = None
        self.current_question_index: int = 0
        self.responses_so_far: List[Dict] = []
        self.mood_indicators: Dict[str, Any] = {}
        self.stress_level: float = 0.0
        self.engagement_score: float = 1.0
        self.knowledge_context: Dict[str, Any] = {}
        self.adaptation_history: List[Dict] = []


class SessionCoordinator:
    """
    Coordinates quiz session lifecycle and state management.

    Responsibilities:
    - Build comprehensive quiz context
    - Create and initialize quiz sessions
    - Complete quiz sessions
    - Manage session state and metadata
    - Trigger comprehensive analysis
    - Coordinate with knowledge graph
    """

    def __init__(
        self,
        db_session: Session,
        quiz_template_service: QuizTemplateService,
        quiz_session_service: QuizSessionService,
        patient_repo: PatientRepository,
        agent_id: str,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize session coordinator."""
        self.db_session = db_session
        self.quiz_template_service = quiz_template_service
        self.quiz_session_service = quiz_session_service
        self.patient_repo = patient_repo
        self.agent_id = agent_id
        self.logger = logger or logging.getLogger(__name__)

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
            self.logger.error(f"Failed to initialize knowledge graph: {e}")

    async def build_quiz_context(
        self, patient_id: UUID, quiz_type: str, progress_tracker: "ProgressTracker"
    ) -> QuizContext:
        """Build comprehensive quiz context."""
        context = QuizContext()
        context.patient_id = patient_id

        # Get patient data
        context.patient_data = self.patient_repo.get(patient_id)

        # Get active quiz session
        active_session = self.quiz_session_service.get_active_session(patient_id)
        if active_session:
            context.session = active_session
            context.current_question_index = active_session.current_question_index

            # Get template
            context.template = self.quiz_template_service.get_template(
                active_session.quiz_template_id
            )

        # Get knowledge graph context
        if self.knowledge_graph:
            try:
                context.knowledge_context = (
                    await self.knowledge_graph.get_patient_context(patient_id)
                )
            except Exception as e:
                self.logger.error(f"Failed to get knowledge context: {e}")
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
            # Get or create appropriate template
            template = await question_presenter.get_or_create_quiz_template(
                quiz_type, context
            )

            if not template:
                self.logger.error(f"Failed to get quiz template for type: {quiz_type}")
                return None

            # Create session
            session_data = QuizSessionCreate(
                patient_id=context.patient_id, quiz_template_id=template.id
            )

            session = await self.quiz_session_service.start_quiz_session(session_data)

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

            # Store metadata (this would need to be added to the session model)

            context.template = template
            return session

        except Exception as e:
            self.logger.error(f"Failed to create quiz session: {e}")
            return None

    async def complete_quiz_session(self, context: QuizContext, send_message_callback):
        """Complete quiz session with comprehensive analysis."""
        try:
            # Mark session as completed
            await self.quiz_session_service.complete_session(context.session.id)

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
                        self.logger.info(
                            f"Discovered {len(patterns)} new patterns for patient {context.patient_id}"
                        )
                except Exception as e:
                    self.logger.error(f"Failed to update knowledge graph: {e}")

        except Exception as e:
            self.logger.error(f"Quiz completion failed: {e}")

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
            "alert_analyzer_agent",
            "patient_monitor_agent",
            "flow_coordinator_agent",
            "insight_generator_agent",
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
                self.logger.error(f"Failed to request analysis from {agent_id}: {e}")

    async def get_session_responses(self, session_id: UUID) -> List[Dict]:
        """Get responses for current session."""
        # This would query actual responses from database
        # For now, return empty list
        return []
