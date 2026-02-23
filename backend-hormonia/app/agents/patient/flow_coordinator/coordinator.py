"""Flow Coordinator Agent - Main coordinator class."""

from __future__ import annotations

# Standard library
from typing import Any, Dict, List, Optional
from uuid import UUID

# Third-party
from sqlalchemy.orm import Session

# Local
from app.agents.base import BaseAgent
from app.agents.registry import FLOW_COORDINATOR_ID
from app.services.template_loader_pkg import EnhancedTemplateLoader

from .consensus_manager import ConsensusManager
from .constants import (
    DEFAULT_DAILY_FLOW_HOURS,
    DEFAULT_QUIZ_TRIGGER_DAY,
    normalize_flow_day,
    resolve_flow_type_and_day,
)
from .decision_engine import DecisionEngine
from .message_generator import MessageGenerator
from .models import FlowContext, FlowDecision
from .state_manager import StateManager
from .transition_handler import TransitionHandler


class FlowCoordinatorAgent(BaseAgent):
    """
    Coordinates patient treatment flow progression.

    Manages state transitions, consensus building, and
    message generation for patient treatment flows.

    Key responsibilities:
    - Analyze patient progress through treatment phases.
    - Make decisions on flow progression and timing.
    - Coordinate with other agents for consensus on critical decisions.
    - Adapt flows based on patient responses and patterns.
    - Manage transitions between different flow types.

    Attributes:
        state_manager: Manages flow states and context.
        decision_engine: Makes flow decisions.
        message_generator: Generates and personalizes messages.
        transition_handler: Handles phase transitions.
        consensus_manager: Manages agent consensus.
    """

    VALID_TASK_TYPES = {
        "process_daily_flow",
        "evaluate_flow_transition",
        "optimize_message_timing",
        "adapt_flow_content",
        "coordinate_intervention",
    }

    def __init__(
        self,
        db_session: Session,
        template_loader: Optional[EnhancedTemplateLoader] = None,
        **kwargs,
    ):
        """Initialize FlowCoordinatorAgent."""
        super().__init__(
            agent_id=FLOW_COORDINATOR_ID,
            agent_type="patient",
            specialization="flow_coordinator",
            db_session=db_session,
            **kwargs,
        )

        # Initialize component managers
        self.state_manager = StateManager(db_session, self.agent_id, self.logger)
        self.decision_engine = DecisionEngine(self.agent_id, self.logger)
        self.message_generator = MessageGenerator(
            db_session, self.agent_id, self.logger, template_loader
        )
        self.transition_handler = TransitionHandler(
            db_session, self.agent_id, self.logger
        )
        self.consensus_manager = ConsensusManager(
            self.agent_id,
            self.logger,
            self.send_message,
            fetch_votes_fn=self._consume_consensus_votes,
            prepare_vote_collection_fn=self._reset_consensus_vote_buffer,
        )
        self._captured_consensus_votes: Dict[str, Dict[str, Any]] = {}
        self.register_message_handler(
            "consensus_request_response", self._handle_consensus_request_response
        )

        # Service dependencies (LangGraph handles flow sending)

        # Agent capabilities
        self.capabilities = [
            "flow_analysis",
            "flow_coordination",
            "timing_optimization",
            "phase_transition",
            "patient_adaptation",
            "consensus_participation",
        ]

        # Flow timing parameters
        self.daily_flow_hours = DEFAULT_DAILY_FLOW_HOURS  # Default message times
        self.quiz_trigger_day = DEFAULT_QUIZ_TRIGGER_DAY  # Day of month to trigger quiz (monthly cycle)

    async def _initialize(self):
        """Initialize agent-specific resources."""
        try:
            # Initialize state manager
            await self.state_manager.initialize_knowledge_graph()

            # Initialize message generator
            self.message_generator.initialize_gemini()
            await self.message_generator.load_flow_templates()

            self.logger.info("FlowCoordinatorAgent initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize FlowCoordinatorAgent: {e}")
            raise

    async def _cleanup(self):
        """Cleanup agent resources."""
        await self.state_manager.close()

    async def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return self.capabilities

    async def validate_task(self, task_data: Dict[str, Any]) -> bool:
        """Validate if agent can handle the task."""
        task_type = task_data.get("task_type", "")
        required_fields = task_data.get("payload", {})

        if task_type not in self.VALID_TASK_TYPES:
            return False

        # Check required fields
        if task_type == "process_daily_flow":
            return "patient_id" in required_fields and "current_day" in required_fields
        elif task_type == "evaluate_flow_transition":
            return (
                "patient_id" in required_fields and "flow_state_id" in required_fields
            )
        elif task_type in ["optimize_message_timing", "adapt_flow_content"]:
            return "patient_id" in required_fields

        return True

    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process assigned task."""
        task_type = task_data.get("task_type")
        payload = task_data.get("payload", {})

        self.logger.info(f"Processing task: {task_type}")

        try:
            if task_type == "process_daily_flow":
                return await self._process_daily_flow(payload)
            elif task_type == "evaluate_flow_transition":
                return await self._evaluate_flow_transition(payload)
            elif task_type == "optimize_message_timing":
                return await self._optimize_message_timing(payload)
            elif task_type == "adapt_flow_content":
                return await self._adapt_flow_content(payload)
            elif task_type == "coordinate_intervention":
                return await self._coordinate_intervention(payload)
            else:
                return {"success": False, "error": f"Unknown task type: {task_type}"}

        except Exception as e:
            self.logger.error(f"Task processing failed: {e}")
            return {"success": False, "error": str(e)}

    async def _process_daily_flow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process daily flow for a patient."""
        patient_id = UUID(payload["patient_id"])
        current_day = int(payload["current_day"])

        # Build flow context
        context = await self.state_manager.build_flow_context(patient_id, current_day)

        if not context.patient_data or not context.flow_state:
            return {"success": False, "error": "Patient or flow state not found"}

        # Analyze current situation
        analysis = await self.decision_engine.analyze_flow_situation(context)

        # Make flow decision
        decision = await self.decision_engine.make_flow_decision(
            context,
            analysis,
            self.decision_engine.requires_consensus_decision,
            self.consensus_manager.seek_agent_consensus,
        )

        # Execute decision
        execution_result = await self._execute_flow_decision(decision, context)

        return {
            "success": True,
            "patient_id": str(patient_id),
            "current_day": current_day,
            "decision": decision.value,
            "analysis": analysis,
            "execution": execution_result,
        }

    async def _execute_flow_decision(
        self, decision: FlowDecision, context: FlowContext
    ) -> Dict[str, Any]:
        """Execute the flow decision."""
        execution_result = {"decision": decision.value, "actions_taken": []}

        try:
            if decision == FlowDecision.CONTINUE_CURRENT:
                # Process normal daily flow
                result = await self._process_normal_flow(context)
                execution_result["actions_taken"].append("processed_daily_messages")
                execution_result["messages_sent"] = result.get("messages_sent", 0)

            elif decision == FlowDecision.ADVANCE_PHASE:
                # Transition to next phase
                await self.transition_handler.transition_flow_phase(context)
                execution_result["actions_taken"].append("advanced_to_monthly_phase")

            elif decision == FlowDecision.ADJUST_TIMING:
                # Optimize message timing
                new_timing = await self.transition_handler.optimize_timing(context)
                execution_result["actions_taken"].append("optimized_timing")
                execution_result["new_timing"] = new_timing

            elif decision == FlowDecision.PERSONALIZE_CONTENT:
                # Personalize content and messages
                await self.transition_handler.personalize_content(context)
                execution_result["actions_taken"].append("personalized_content")

            elif decision == FlowDecision.ESCALATE_INTERVENTION:
                # Escalate for medical intervention
                await self.consensus_manager.escalate_intervention(context)
                execution_result["actions_taken"].append("escalated_intervention")

            elif decision == FlowDecision.PAUSE_FLOW:
                # Pause flow temporarily
                await self.transition_handler.pause_flow(context)
                execution_result["actions_taken"].append("paused_flow")

            elif decision == FlowDecision.RESUME_FLOW:
                # Resume paused flow
                await self.transition_handler.resume_flow(context)
                execution_result["actions_taken"].append("resumed_flow")

            execution_result["success"] = True

        except Exception as e:
            self.logger.error(f"Failed to execute decision {decision.value}: {e}")
            execution_result["success"] = False
            execution_result["error"] = str(e)

        return execution_result

    async def _process_normal_flow(self, context: FlowContext) -> Dict[str, Any]:
        """Process normal daily flow messages."""
        messages_sent = 0
        flow_result: Optional[Dict[str, Any]] = None

        try:
            current_day = normalize_flow_day(context.current_day)

            flow_kind, day_in_flow = resolve_flow_type_and_day(current_day)

            from app.services.flow.sequential_message_handler import (
                SequentialMessageHandler,
            )

            # Note: FlowCoordinatorAgent receives db_session from the agent framework
            # (sync Session via SessionLocal). SequentialMessageHandler now expects
            # AsyncSession for the FastAPI hot-path. This Hive-Mind agent path should
            # be migrated to AsyncSession in a follow-up task.
            handler = SequentialMessageHandler(self.db_session)
            flow_result = await handler.send_day_messages(
                patient_id=context.patient_id,
                day_number=day_in_flow,
                flow_kind=flow_kind,
            )

            messages_sent = flow_result.get("sent_count", 0) if flow_result else 0
            if messages_sent == 0 and flow_result:
                if flow_result.get("status") in {"waiting", "ok", "complete"}:
                    messages_sent = 1

        except Exception as e:
            self.logger.error(f"Error processing normal flow: {e}")

        return {"messages_sent": messages_sent, "flow_result": flow_result}

    async def _evaluate_flow_transition(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate if patient should transition flow phases."""
        patient_id = UUID(payload["patient_id"])
        flow_state_id = payload["flow_state_id"]

        # Get flow state
        flow_state = self.state_manager.flow_repo.get_by_id(flow_state_id)
        if not flow_state:
            return {"success": False, "error": "Flow state not found"}

        # Build context for evaluation
        context = await self.state_manager.build_flow_context(
            patient_id, flow_state.current_day or 0
        )

        # Analyze readiness for transition
        analysis = await self.decision_engine.analyze_flow_situation(context)

        # Determine if transition is recommended
        transition_ready = (
            analysis["progress_score"] >= 0.6
            and analysis["risk_level"] != "high"
            and analysis["engagement_score"] >= 0.4
        )

        return {
            "success": True,
            "patient_id": str(patient_id),
            "transition_ready": transition_ready,
            "analysis": analysis,
            "recommendations": analysis["recommendations"],
        }

    async def _optimize_message_timing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize message timing for patient."""
        patient_id = UUID(payload["patient_id"])

        # Build context
        context = await self.state_manager.build_flow_context(patient_id, 0)

        # Optimize timing
        optimized_timing = await self.transition_handler.optimize_timing(context)

        return {
            "success": True,
            "patient_id": str(patient_id),
            "optimized_timing": optimized_timing,
        }

    async def _adapt_flow_content(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt flow content for patient."""
        patient_id = UUID(payload["patient_id"])

        # Build context
        context = await self.state_manager.build_flow_context(patient_id, 0)

        # Personalize content
        await self.transition_handler.personalize_content(context)

        return {"success": True, "patient_id": str(patient_id), "content_adapted": True}

    async def _coordinate_intervention(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Coordinate intervention for patient."""
        patient_id = UUID(payload["patient_id"])
        intervention_type = payload.get("intervention_type", "standard")

        # Build context
        context = await self.state_manager.build_flow_context(patient_id, 0)

        # Coordinate based on intervention type
        if intervention_type == "escalation":
            await self.consensus_manager.escalate_intervention(context)
        elif intervention_type == "pause":
            await self.transition_handler.pause_flow(context)
        elif intervention_type == "resume":
            await self.transition_handler.resume_flow(context)

        return {
            "success": True,
            "patient_id": str(patient_id),
            "intervention_type": intervention_type,
            "coordinated": True,
        }

    async def _handle_consensus_request_response(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Capture inbound consensus responses for later LangGraph vote polling."""
        if not isinstance(payload, dict):
            return {"captured": False, "reason": "invalid_payload"}

        agent_id = str(payload.get("agent_id") or payload.get("responder_id") or "").strip()
        vote = str(payload.get("vote") or "").strip().lower()

        if not agent_id:
            return {"captured": False, "reason": "missing_agent_id"}
        if vote not in {"approve", "reject", "abstain"}:
            return {"captured": False, "reason": "missing_or_invalid_vote"}

        captured_payload = dict(payload)
        captured_payload["vote"] = vote
        self._captured_consensus_votes[agent_id] = captured_payload
        return {"captured": True, "agent_id": agent_id}

    def _reset_consensus_vote_buffer(self, agent_ids: List[str]) -> None:
        """Drop stale captured votes before dispatching a new consensus request."""
        for agent_id in agent_ids:
            self._captured_consensus_votes.pop(agent_id, None)

    def _consume_consensus_votes(
        self, correlation_ids: Dict[str, Optional[str]]
    ) -> Dict[str, Dict[str, Any]]:
        """Return and clear captured votes for the expected agent set."""
        if not isinstance(correlation_ids, dict):
            return {}

        votes: Dict[str, Dict[str, Any]] = {}
        for agent_id in correlation_ids:
            captured_payload = self._captured_consensus_votes.pop(agent_id, None)
            if isinstance(captured_payload, dict):
                votes[agent_id] = captured_payload
        return votes

    # Template management methods
    def get_loaded_templates(self) -> Dict[str, str]:
        """Get information about loaded templates."""
        return self.message_generator.get_loaded_templates()

    async def reload_templates(self) -> bool:
        """Reload all templates from source."""
        return await self.message_generator.reload_templates()
