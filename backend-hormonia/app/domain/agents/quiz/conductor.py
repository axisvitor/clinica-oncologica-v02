"""
Quiz Conductor - Main orchestrator for quiz sessions.

Coordinates quiz flow with adaptive intelligence and multi-agent collaboration.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent, MessagePriority
from app.services.quiz import QuizTemplateService, QuizSessionService, QuizResponseService
from app.domain.messaging.delivery import MessageSender
from app.repositories.patient import PatientRepository
from app.integrations.gemini_client import get_gemini_client

from .session_coordinator import SessionCoordinator, QuizContext
from .question_presenter import QuestionPresenter
from .response_handler import ResponseHandler
from .progress_tracker import ProgressTracker
from .notification_manager import NotificationManager, QuizAdaptationType


class QuizConductor(BaseAgent):
    """
    Main agent responsible for conducting intelligent quiz sessions.

    Key responsibilities:
    - Orchestrate quiz session flow and progression
    - Adapt questions in real-time based on responses
    - Coordinate with other agents for comprehensive analysis
    - Personalize quiz experience based on patient context
    - Handle complex response interpretation using AI
    - Manage quiz completion and follow-up actions
    """

    def __init__(self, db_session: Session, **kwargs):
        """Initialize QuizConductor."""
        super().__init__(
            agent_id=f"quiz_conductor_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            agent_type="communication",
            specialization="quiz_conductor",
            db_session=db_session,
            **kwargs
        )

        # Service dependencies
        self.quiz_template_service = QuizTemplateService(db_session)
        self.quiz_session_service = QuizSessionService(db_session)
        self.quiz_response_service = QuizResponseService(db_session)
        self.message_sender = MessageSender(db_session)
        self.patient_repo = PatientRepository(db_session)

        # AI and memory dependencies
        self.gemini_client = None  # Initialized during start

        # Initialize specialized components
        self.session_coordinator = SessionCoordinator(
            db_session=db_session,
            quiz_template_service=self.quiz_template_service,
            quiz_session_service=self.quiz_session_service,
            patient_repo=self.patient_repo,
            agent_id=self.agent_id,
            logger=self.logger
        )

        self.question_presenter = QuestionPresenter(
            db_session=db_session,
            quiz_template_service=self.quiz_template_service,
            message_sender=self.message_sender,
            agent_id=self.agent_id,
            gemini_client=None,  # Set during initialization
            logger=self.logger
        )

        self.response_handler = ResponseHandler(
            db_session=db_session,
            quiz_session_service=self.quiz_session_service,
            quiz_response_service=self.quiz_response_service,
            agent_id=self.agent_id,
            gemini_client=None,  # Set during initialization
            knowledge_graph=None,  # Set during initialization
            logger=self.logger
        )

        self.progress_tracker = ProgressTracker(logger=self.logger)

        self.notification_manager = NotificationManager(
            db_session=db_session,
            message_sender=self.message_sender,
            agent_id=self.agent_id,
            logger=self.logger
        )

        # Agent capabilities
        self.capabilities = [
            "quiz_conduction",
            "adaptive_questioning",
            "response_interpretation",
            "mood_detection",
            "engagement_analysis",
            "personalization",
            "consensus_analysis"
        ]

        # Quiz parameters
        self.max_questions_per_session = 10
        self.response_timeout_minutes = 30
        self.adaptation_threshold = 0.6
        self.stress_threshold = 0.7
        self.engagement_threshold = 0.4

    async def _initialize(self):
        """Initialize agent-specific resources."""
        try:
            # Initialize AI client
            self.gemini_client = get_gemini_client()

            # Update component references
            self.question_presenter.gemini_client = self.gemini_client
            self.response_handler.gemini_client = self.gemini_client

            # Initialize knowledge graph
            await self.session_coordinator.initialize_knowledge_graph()
            self.response_handler.knowledge_graph = self.session_coordinator.knowledge_graph

            # Load quiz templates
            await self.question_presenter.load_quiz_templates()

            self.logger.info("QuizConductor initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize QuizConductor: {e}")
            raise

    async def _cleanup(self):
        """Cleanup agent resources."""
        if self.session_coordinator.knowledge_graph:
            await self.session_coordinator.knowledge_graph.close()

    async def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return self.capabilities

    async def validate_task(self, task_data: Dict[str, Any]) -> bool:
        """Validate if agent can handle the task."""
        task_type = task_data.get("type", "")
        payload = task_data.get("payload", {})

        # Check task type compatibility
        compatible_tasks = [
            "conduct_quiz_session",
            "process_quiz_response",
            "adapt_quiz_questions",
            "analyze_quiz_completion",
            "trigger_monthly_quiz"
        ]

        if task_type not in compatible_tasks:
            return False

        # Check required fields
        if task_type in ["conduct_quiz_session", "trigger_monthly_quiz"]:
            return "patient_id" in payload
        elif task_type == "process_quiz_response":
            return all(key in payload for key in ["patient_id", "response_text"])
        elif task_type == "adapt_quiz_questions":
            return all(key in payload for key in ["patient_id", "session_id"])

        return True

    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process assigned task."""
        task_type = task_data.get("type")
        payload = task_data.get("payload", {})

        self.logger.info(f"Processing quiz task: {task_type}")

        try:
            if task_type == "conduct_quiz_session":
                return await self._conduct_quiz_session(payload)
            elif task_type == "process_quiz_response":
                return await self._process_quiz_response(payload)
            elif task_type == "adapt_quiz_questions":
                return await self._adapt_quiz_questions(payload)
            elif task_type == "analyze_quiz_completion":
                return await self._analyze_quiz_completion(payload)
            elif task_type == "trigger_monthly_quiz":
                return await self._trigger_monthly_quiz(payload)
            else:
                return {"success": False, "error": f"Unknown task type: {task_type}"}

        except Exception as e:
            self.logger.error(f"Quiz task processing failed: {e}")
            return {"success": False, "error": str(e)}

    async def _conduct_quiz_session(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Conduct complete quiz session with adaptive intelligence."""
        patient_id = UUID(payload["patient_id"])
        quiz_type = payload.get("quiz_type", "monthly_checkup")

        # Build quiz context
        context = await self.session_coordinator.build_quiz_context(
            patient_id, quiz_type, self.progress_tracker
        )

        if not context.patient_data:
            return {"success": False, "error": "Patient not found"}

        # Create or get active session
        if not context.session:
            session = await self.session_coordinator.create_quiz_session(
                context, quiz_type, self.question_presenter
            )
            if not session:
                return {"success": False, "error": "Failed to create quiz session"}
            context.session = session

        # Conduct quiz with swarm intelligence
        conduction_result = await self._conduct_adaptive_quiz(context)

        return {
            "success": True,
            "patient_id": str(patient_id),
            "session_id": str(context.session.id),
            "quiz_type": quiz_type,
            "questions_asked": len(context.responses_so_far),
            "adaptations_made": len(context.adaptation_history),
            "completion_status": conduction_result
        }

    async def _conduct_adaptive_quiz(self, context: QuizContext) -> Dict[str, Any]:
        """Conduct quiz with real-time adaptation."""
        completion_status = {
            "completed": False,
            "total_questions": len(context.template.questions) if context.template else 0,
            "questions_asked": 0,
            "adaptations_made": 0,
            "early_completion": False,
            "intervention_triggered": False
        }

        try:
            # Start with welcome message
            await self.notification_manager.send_quiz_introduction(
                context, self.max_questions_per_session, self.stress_threshold
            )

            # Process questions with adaptation
            while (context.current_question_index < len(context.template.questions) and
                   context.current_question_index < self.max_questions_per_session):

                # Check if adaptation is needed
                if await self._should_adapt_quiz(context):
                    adaptation = await self._determine_adaptation(context)
                    await self.notification_manager.send_adaptation_message(context, adaptation)
                    context.adaptation_history.append({
                        "adaptation_type": adaptation.value,
                        "question_index": context.current_question_index,
                        "reason": self.notification_manager.get_adaptation_reason(context, adaptation),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    completion_status["adaptations_made"] += 1

                # Send current question
                question_result = await self.question_presenter.send_quiz_question(
                    context, self.max_questions_per_session, self.stress_threshold
                )

                if not question_result["success"]:
                    break

                completion_status["questions_asked"] += 1
                context.current_question_index += 1

                # Check for early completion triggers
                if await self.progress_tracker.should_complete_early(context):
                    completion_status["early_completion"] = True
                    break

                # Check for intervention triggers
                if await self.progress_tracker.should_trigger_intervention(context):
                    await self._trigger_intervention(context)
                    completion_status["intervention_triggered"] = True
                    break

            # Complete session
            if context.current_question_index >= len(context.template.questions):
                await self.session_coordinator.complete_quiz_session(
                    context, self.send_message
                )
                await self.notification_manager.send_completion_message(context)
                completion_status["completed"] = True

            return completion_status

        except Exception as e:
            self.logger.error(f"Quiz conduction failed: {e}")
            completion_status["error"] = str(e)
            return completion_status

    async def _process_quiz_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process patient response with swarm analysis."""
        return await self.response_handler.process_quiz_response(
            payload,
            build_context_callback=lambda pid, qt: self.session_coordinator.build_quiz_context(
                pid, qt, self.progress_tracker
            ),
            send_next_question_callback=lambda ctx: self.question_presenter.send_quiz_question(
                ctx, self.max_questions_per_session, self.stress_threshold
            ),
            complete_session_callback=lambda ctx: self._complete_session_with_notification(ctx),
            send_clarification_callback=self.notification_manager.send_clarification_message
        )

    async def _complete_session_with_notification(self, context: QuizContext):
        """Complete session and send notification."""
        await self.session_coordinator.complete_quiz_session(context, self.send_message)
        await self.notification_manager.send_completion_message(context)

    async def _should_adapt_quiz(self, context: QuizContext) -> bool:
        """Determine if quiz adaptation is needed."""
        # Check stress level
        if context.stress_level > self.stress_threshold:
            return True

        # Check engagement
        if context.engagement_score < self.engagement_threshold:
            return True

        # Check mood indicators
        if context.mood_indicators.get("distress", 0) > 0.7:
            return True

        # Check response patterns
        if len(context.responses_so_far) >= 3:
            # Check for pattern of short or unclear responses
            unclear_responses = sum(1 for r in context.responses_so_far[-3:]
                                  if r.get("confidence", 1.0) < 0.6)
            if unclear_responses >= 2:
                return True

        return False

    async def _determine_adaptation(self, context: QuizContext) -> QuizAdaptationType:
        """Determine what type of adaptation is needed."""
        # High stress - reduce complexity
        if context.stress_level > self.stress_threshold:
            return QuizAdaptationType.REDUCE_COMPLEXITY

        # Low engagement - increase support
        if context.engagement_score < self.engagement_threshold:
            return QuizAdaptationType.INCREASE_SUPPORT

        # Mood distress - focus on mood
        if context.mood_indicators.get("distress", 0) > 0.7:
            return QuizAdaptationType.FOCUS_ON_MOOD

        # Pattern of unclear responses - add clarification
        if len(context.responses_so_far) >= 2:
            recent_unclear = [r for r in context.responses_so_far[-2:]
                            if r.get("confidence", 1.0) < 0.6]
            if len(recent_unclear) >= 1:
                return QuizAdaptationType.ADD_CLARIFICATION

        return QuizAdaptationType.INCREASE_SUPPORT

    async def _trigger_intervention(self, context: QuizContext):
        """Trigger medical intervention."""
        # Send urgent message to alert analyzer
        await self.send_message(
            "alert_analyzer_agent",
            "urgent_intervention_needed",
            {
                "patient_id": str(context.patient_id),
                "quiz_session_id": str(context.session.id),
                "trigger_reason": "concerning_quiz_responses",
                "mood_indicators": context.mood_indicators,
                "stress_level": context.stress_level
            },
            MessagePriority.CRITICAL
        )

    async def _adapt_quiz_questions(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt quiz questions mid-session."""
        patient_id = UUID(payload["patient_id"])
        session_id = UUID(payload["session_id"])

        context = await self.session_coordinator.build_quiz_context(
            patient_id, "current", self.progress_tracker
        )

        if not context.session or str(context.session.id) != str(session_id):
            return {"success": False, "error": "Session not found or inactive"}

        # Determine needed adaptation
        adaptation = await self._determine_adaptation(context)

        # Apply adaptation
        await self.notification_manager.send_adaptation_message(context, adaptation)

        return {
            "success": True,
            "adaptation_applied": adaptation.value,
            "reason": self.notification_manager.get_adaptation_reason(context, adaptation)
        }

    async def _analyze_quiz_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze completed quiz session."""
        session_id = UUID(payload["session_id"])

        # Get completed session
        session = self.quiz_session_service.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Build analysis context
        context = await self.session_coordinator.build_quiz_context(
            session.patient_id, "analysis", self.progress_tracker
        )
        context.session = session

        # Perform comprehensive analysis
        analysis = {
            "session_id": str(session_id),
            "patient_id": str(session.patient_id),
            "completion_quality": await self.progress_tracker.assess_completion_quality(context),
            "mood_analysis": context.mood_indicators,
            "engagement_metrics": {
                "score": context.engagement_score,
                "adaptations_needed": len(context.adaptation_history)
            },
            "medical_insights": await self.progress_tracker.extract_medical_insights(context),
            "recommendations": await self.progress_tracker.generate_follow_up_recommendations(context)
        }

        return {"success": True, "analysis": analysis}

    async def _trigger_monthly_quiz(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger monthly quiz for patient."""
        patient_id = UUID(payload["patient_id"])

        # Build context
        context = await self.session_coordinator.build_quiz_context(
            patient_id, "monthly_checkup", self.progress_tracker
        )

        if not context.patient_data:
            return {"success": False, "error": "Patient not found"}

        # Check if already has active session
        active_session = self.quiz_session_service.get_active_session(patient_id)
        if active_session:
            return {"success": False, "error": "Patient already has active quiz session"}

        # Create and start quiz session
        result = await self._conduct_quiz_session({
            "patient_id": str(patient_id),
            "quiz_type": "monthly_checkup"
        })

        return result


# Backward compatibility alias
QuizConductorAgent = QuizConductor
