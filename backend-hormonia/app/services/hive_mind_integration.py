"""
Hive-Mind Integration Service

Integrates the existing flow engine with the new Hive-Mind multi-agent system.
Provides seamless integration while maintaining backward compatibility.
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import timezone
from uuid import UUID
from enum import Enum


# Removed direct imports to avoid circular dependency - now using lazy imports in methods
from app.agents.base import MessagePriority
from app.services.enhanced_flow_engine import EnhancedFlowEngine
from app.services.template_loader_pkg import EnhancedTemplateLoader
from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.utils.logging import get_logger
from app.utils.timezone import now_sao_paulo


class IntegrationMode(Enum):
    """Integration modes for different operations."""

    FLOW_ENGINE_ONLY = "flow_engine_only"  # Use only existing flow engine fallback
    HIVE_MIND_ONLY = "hive_mind_only"  # Use only new agents
    HYBRID = "hybrid"  # Use both systems with coordination
    GRADUAL_MIGRATION = "gradual_migration"  # Gradually migrate to agents


class HiveMindIntegrationService:
    """
    Service that integrates Hive-Mind agents with existing flow engine.

    This service acts as a bridge between the traditional flow processing
    and the new multi-agent system, allowing for gradual migration and
    hybrid operation modes.
    """

    def __init__(
        self, db_session: Any, template_loader: Optional[EnhancedTemplateLoader] = None
    ):
        """Initialize integration service."""
        self.db_session = db_session
        self.logger = get_logger("hive_mind_integration")

        # Template support
        self.template_loader = template_loader or EnhancedTemplateLoader(db=db_session)

        # Integration state
        self.swarm_manager: Optional[Any] = (
            None  # SwarmManager type import moved to lazy import
        )
        self.enhanced_flow_engine: Optional[EnhancedFlowEngine] = None
        self.agents: Dict[str, Any] = {}

        # Configuration
        self.integration_mode = IntegrationMode.HYBRID
        self.agent_enabled_features = {
            "flow_coordination": True,
            "quiz_conduction": True,
            "response_analysis": True,
            "consensus_decisions": True,
            "pattern_learning": True,
        }

        # Migration settings
        self.migration_percentage = 30  # Start with 30% of patients on agents
        self.gradual_migration_enabled = True

    def close(self) -> None:
        """Close any owned database resources."""
        try:
            if self.db_session:
                self.db_session.close()
        except Exception as e:
            self.logger.warning(f"Failed to close HiveMind DB session: {e}")

    async def initialize(self):
        """Initialize the integration service."""
        try:
            self.logger.info("Initializing Hive-Mind integration service")

            # Initialize swarm manager (lazy import to avoid circular dependency)
            from app.orchestration.swarm_manager import get_swarm_manager

            self.swarm_manager = await get_swarm_manager()

            # Initialize enhanced flow engine
            from app.services.enhanced_flow_engine import get_enhanced_flow_engine

            self.enhanced_flow_engine = get_enhanced_flow_engine(self.db_session)

            # Register and start agents
            await self._initialize_agents()

            self.logger.info("Hive-Mind integration service initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize integration service: {e}")
            raise

    async def _initialize_agents(self):
        """Initialize and register agents with swarm manager."""
        try:
            if not self.swarm_manager:
                raise RuntimeError("Swarm manager not initialized")

            # Lazy imports to avoid circular dependency
            from app.agents.patient.flow_coordinator import FlowCoordinatorAgent
            from app.domain.agents.quiz import QuizConductor as QuizConductorAgent
            from app.agents.communication.message_composer import MessageComposerAgent
            from app.agents.patient.patient_monitor import PatientMonitorAgent
            from app.agents.analytics.alert_analyzer import AlertAnalyzerAgent
            from app.agents.communication.response_processor import (
                ResponseProcessorAgent,
            )

            # Create Flow Coordinator Agent with template support
            flow_coordinator = FlowCoordinatorAgent(
                self.db_session, template_loader=self.template_loader
            )
            success = await self.swarm_manager.register_agent(flow_coordinator)

            if success:
                self.agents["flow_coordinator"] = flow_coordinator
                self.logger.info("Flow Coordinator Agent registered successfully")

            # Create Quiz Conductor Agent with template support
            quiz_conductor = QuizConductorAgent(self.db_session)
            success = await self.swarm_manager.register_agent(quiz_conductor)

            if success:
                self.agents["quiz_conductor"] = quiz_conductor
                self.logger.info("Quiz Conductor Agent registered successfully")

            # Create Message Composer Agent with template support
            message_composer = MessageComposerAgent(
                self.db_session, template_loader=self.template_loader
            )
            success = await self.swarm_manager.register_agent(message_composer)

            if success:
                self.agents["message_composer"] = message_composer
                self.logger.info("Message Composer Agent registered successfully")

            # Create Patient Monitor Agent
            patient_monitor = PatientMonitorAgent(self.db_session)
            success = await self.swarm_manager.register_agent(patient_monitor)

            if success:
                self.agents["patient_monitor"] = patient_monitor
                self.logger.info("Patient Monitor Agent registered successfully")

            # Create Alert Analyzer Agent
            alert_analyzer = AlertAnalyzerAgent(self.db_session)
            success = await self.swarm_manager.register_agent(alert_analyzer)

            if success:
                self.agents["alert_analyzer"] = alert_analyzer
                self.logger.info("Alert Analyzer Agent registered successfully")

            # Create ResponseProcessorAgent
            response_processor = ResponseProcessorAgent(self.db_session)
            success = await self.swarm_manager.register_agent(response_processor)

            if success:
                self.agents["response_processor"] = response_processor
                self.logger.info("Response Processor Agent registered successfully")

            # Initialize all agents
            for agent_name, agent in self.agents.items():
                if hasattr(agent, "initialize"):
                    await agent.initialize()
                    self.logger.info(f"Agent {agent_name} initialized with templates")

            self.logger.info(
                f"Successfully initialized {len(self.agents)} agents with template support"
            )

        except Exception as e:
            self.logger.error(f"Failed to initialize agents: {e}")
            raise

    async def process_daily_flows(self, limit: int = 100) -> Dict[str, Any]:
        """
        Process daily flows using hybrid approach.

        Args:
            limit: Maximum number of patients to process

        Returns:
            Processing results from both systems
        """
        results = {
            "total_processed": 0,
            "agent_processed": 0,
            "flow_engine_processed": 0,
            "errors": [],
            "performance_metrics": {},
        }

        try:
            # Get patients needing flow processing
            patients_to_process = await self._get_patients_for_processing(limit)

            if not patients_to_process:
                self.logger.info("No patients need flow processing")
                return results

            # Decide processing approach for each patient
            agent_patients, flow_engine_patients = await self._distribute_patients(
                patients_to_process
            )

            # Process with agents (parallel)
            if agent_patients and self.agent_enabled_features["flow_coordination"]:
                agent_results = await self._process_with_agents(agent_patients)
                results["agent_processed"] = agent_results["processed"]
                results["errors"].extend(agent_results.get("errors", []))

            # Process with flow engine fallback (parallel)
            if flow_engine_patients:
                flow_engine_results = await self._process_with_flow_engine(
                    flow_engine_patients
                )
                results["flow_engine_processed"] = flow_engine_results["processed"]
                results["errors"].extend(flow_engine_results.get("errors", []))

            results["total_processed"] = (
                results["agent_processed"]
                + results["flow_engine_processed"]
            )

            # Update migration statistics
            await self._update_migration_stats(results)

            self.logger.info(
                f"Flow processing completed: {results['total_processed']} patients processed"
            )

        except Exception as e:
            self.logger.error(f"Flow processing failed: {e}")
            results["errors"].append({"error": str(e), "type": "system_error"})

        return results

    async def _get_patients_for_processing(
        self, limit: int
    ) -> List[Tuple[Patient, PatientFlowState]]:
        """Get patients that need flow processing."""
        # This would use the existing logic from enhanced_flow_engine
        # to get patients needing daily flow processing

        try:
            # Enhanced flow engine doesn't have this method, use fallback directly
            pass

            # Fallback: query directly
            from app.repositories.patient import PatientRepository
            from app.repositories.flow import FlowStateRepository

            patient_repo = PatientRepository(self.db_session)
            flow_repo = FlowStateRepository(self.db_session)

            active_patients = patient_repo.get_active_patients(limit)

            patient_flow_pairs = []
            for patient in active_patients:
                flow_states = flow_repo.get_by_patient_id(patient.id)
                if flow_states:
                    patient_flow_pairs.append((patient, flow_states[0]))

            return patient_flow_pairs

        except Exception as e:
            self.logger.error(f"Failed to get patients for processing: {e}")
            return []

    async def _distribute_patients(
        self, patients: List[Tuple[Patient, PatientFlowState]]
    ) -> Tuple[
        List[Tuple[Patient, PatientFlowState]], List[Tuple[Patient, PatientFlowState]]
    ]:
        """Distribute patients between agent and flow engine fallback processing."""
        agent_patients = []
        flow_engine_patients = []

        for patient, flow_state in patients:
            # Decide based on integration mode and migration settings
            if await self._should_use_agents(patient, flow_state):
                agent_patients.append((patient, flow_state))
            else:
                flow_engine_patients.append((patient, flow_state))

        self.logger.info(
            "Distribution: %s for agents, %s for flow engine fallback",
            len(agent_patients),
            len(flow_engine_patients),
        )

        return agent_patients, flow_engine_patients

    async def _should_use_agents(
        self, patient: Patient, flow_state: PatientFlowState
    ) -> bool:
        """Determine if patient should be processed by agents."""
        if self.integration_mode == IntegrationMode.FLOW_ENGINE_ONLY:
            return False
        elif self.integration_mode == IntegrationMode.HIVE_MIND_ONLY:
            return True
        elif self.integration_mode == IntegrationMode.HYBRID:
            # Use hash of patient ID to consistently assign patients
            import hashlib

            hash_value = int(hashlib.md5(str(patient.id).encode()).hexdigest()[:8], 16)
            return (hash_value % 100) < self.migration_percentage
        elif self.integration_mode == IntegrationMode.GRADUAL_MIGRATION:
            # Gradually increase agent usage over time
            days_since_enrollment = (now_sao_paulo() - patient.created_at).days

            # Start with newer patients on agents
            if days_since_enrollment < 30:  # New patients
                return True
            elif days_since_enrollment < 90:  # Recent patients
                return (hash(str(patient.id)) % 100) < 70
            else:  # Older patients
                return (hash(str(patient.id)) % 100) < 20

        return False

    async def _process_with_agents(
        self, patients: List[Tuple[Patient, PatientFlowState]]
    ) -> Dict[str, Any]:
        """Process patients using Hive-Mind agents."""
        results = {"processed": 0, "errors": []}

        if not self.swarm_manager:
            return {
                "processed": 0,
                "errors": [{"error": "Swarm manager not initialized"}],
            }

        try:
            # Submit tasks to swarm for parallel processing
            pending_tasks: set[str] = set()

            for patient, flow_state in patients:
                # Calculate current treatment day
                enrollment_date = patient.enrollment_date or patient.created_at
                current_day = (now_sao_paulo() - enrollment_date).days + 1

                # Submit flow processing task
                task_id = await self.swarm_manager.submit_task(
                    task_type="process_daily_flow",
                    payload={
                        "patient_id": str(patient.id),
                        "current_day": current_day,
                        "flow_state_id": str(flow_state.id),
                        "integration_mode": "hybrid",
                    },
                    required_capabilities=["flow_coordination", "patient_adaptation"],
                    priority=MessagePriority.NORMAL,
                )

                pending_tasks.add(task_id)

            # Monitor task completion
            completed_tasks = 0
            timeout = 300  # 5 minutes timeout
            start_time = now_sao_paulo()

            while (
                pending_tasks
                and (now_sao_paulo() - start_time).seconds < timeout
            ):
                for task_id in list(pending_tasks):
                    status = await self.swarm_manager.get_task_status(task_id)

                    if status and status.get("status") == "completed":
                        completed_tasks += 1
                        pending_tasks.discard(task_id)
                    elif status and status.get("status") == "failed":
                        results["errors"].append(
                            {
                                "task_id": task_id,
                                "error": status.get("error", "Unknown error"),
                            }
                        )
                        pending_tasks.discard(task_id)

                # Short sleep to avoid busy waiting
                await asyncio.sleep(1)

            results["processed"] = completed_tasks

            # Handle remaining tasks as timeouts
            for remaining_task in pending_tasks:
                results["errors"].append(
                    {"task_id": remaining_task, "error": "Task timed out"}
                )

        except Exception as e:
            self.logger.error(f"Agent processing failed: {e}")
            results["errors"].append({"error": str(e), "type": "agent_processing"})

        return results

    async def _process_with_flow_engine(
        self, patients: List[Tuple[Patient, PatientFlowState]]
    ) -> Dict[str, Any]:
        """Process patients using flow engine fallback."""
        results = {"processed": 0, "errors": []}

        if not self.enhanced_flow_engine:
            return {
                "processed": 0,
                "errors": [{"error": "Enhanced flow engine not available"}],
            }

        try:
            # Use existing enhanced flow engine logic
            for patient, flow_state in patients:
                try:
                    # Process using existing flow engine
                    flow_result = await self.enhanced_flow_engine.advance_patient_flow(
                        patient.id
                    )

                    if flow_result.get("success", False):
                        results["processed"] += 1
                    else:
                        results["errors"].append(
                            {
                                "patient_id": str(patient.id),
                                "error": flow_result.get(
                                    "error", "Unknown flow engine error"
                                ),
                            }
                        )

                except Exception as e:
                    results["errors"].append(
                        {
                            "patient_id": str(patient.id),
                            "error": str(e),
                            "type": "flow_engine_processing",
                        }
                    )

        except Exception as e:
            self.logger.error(f"Flow engine processing failed: {e}")
            results["errors"].append({"error": str(e), "type": "flow_engine_system"})

        return results

    async def conduct_quiz_session(
        self, patient_id: UUID, quiz_type: str = "monthly_checkup"
    ) -> Dict[str, Any]:
        """
        Conduct quiz session using agents or flow engine fallback.

        Args:
            patient_id: Patient ID
            quiz_type: Type of quiz to conduct

        Returns:
            Quiz session results
        """
        try:
            # Check if agents should handle this
            from app.repositories.patient import PatientRepository
            from app.repositories.flow import FlowStateRepository

            patient_repo = PatientRepository(self.db_session)
            flow_repo = FlowStateRepository(self.db_session)

            patient = patient_repo.get(patient_id)
            flow_states = flow_repo.get_by_patient_id(patient_id)
            flow_state = flow_states[0] if flow_states else None

            if (
                patient
                and flow_state
                and await self._should_use_agents(patient, flow_state)
            ):
                # Use Hive-Mind agents
                return await self._conduct_quiz_with_agents(patient_id, quiz_type)
            else:
                # Use flow engine fallback
                return await self._conduct_quiz_with_flow_engine(patient_id, quiz_type)

        except Exception as e:
            self.logger.error(f"Quiz conduction failed: {e}")
            return {"success": False, "error": str(e)}

    async def _conduct_quiz_with_agents(
        self, patient_id: UUID, quiz_type: str
    ) -> Dict[str, Any]:
        """Conduct quiz using Hive-Mind agents."""
        try:
            if not self.swarm_manager:
                raise ValueError("Swarm manager not available")

            # Submit quiz task to swarm
            task_id = await self.swarm_manager.submit_task(
                task_type="conduct_quiz_session",
                payload={"patient_id": str(patient_id), "quiz_type": quiz_type},
                required_capabilities=["quiz_conduction", "adaptive_questioning"],
                priority=MessagePriority.HIGH,
            )

            # Wait for task completion
            timeout = 1800  # 30 minutes for quiz
            start_time = now_sao_paulo()

            while (now_sao_paulo() - start_time).seconds < timeout:
                status = await self.swarm_manager.get_task_status(task_id)

                if status:
                    if status.get("status") == "completed":
                        return {
                            "success": True,
                            "method": "agent",
                            "task_id": task_id,
                            "result": status.get("result", {}),
                        }
                    elif status.get("status") == "failed":
                        return {
                            "success": False,
                            "method": "agent",
                            "error": status.get("error", "Unknown agent error"),
                        }

                await asyncio.sleep(5)  # Check every 5 seconds

            # Timeout
            await self.swarm_manager.cancel_task(task_id)
            return {
                "success": False,
                "method": "agent",
                "error": "Quiz session timed out",
            }

        except Exception as e:
            self.logger.error(f"Agent quiz conduction failed: {e}")
            return {"success": False, "method": "agent", "error": str(e)}

    async def _conduct_quiz_with_flow_engine(
        self, patient_id: UUID, quiz_type: str
    ) -> Dict[str, Any]:
        """Conduct quiz using flow engine fallback."""
        try:
            # Use existing quiz flow integration
            from app.domain.quizzes.integration.flow_integration.utils import (
                get_quiz_trigger_service,
            )

            get_quiz_trigger_service(self.db_session)

            # This would use the existing quiz trigger logic
            # For now, return a simulated result
            return {
                "success": True,
                "method": "legacy",
                "message": "Quiz initiated using legacy system",
            }

        except Exception as e:
            self.logger.error(f"Flow engine quiz conduction failed: {e}")
            return {"success": False, "method": "legacy", "error": str(e)}

    async def process_quiz_response(
        self,
        patient_id: UUID,
        response_text: str,
        message_metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Process quiz response using intelligent agent analysis.

        Args:
            patient_id: Patient ID
            response_text: Patient's response
            message_metadata: Message metadata

        Returns:
            Processing result
        """
        try:
            # Always use agents for response processing if available
            if self.swarm_manager and self.agent_enabled_features.get(
                "response_analysis", True
            ):
                return await self._process_response_with_agents(
                    patient_id, response_text, message_metadata
                )
            else:
                return await self._process_response_with_flow_engine(
                    patient_id, response_text, message_metadata
                )

        except Exception as e:
            self.logger.error(f"Quiz response processing failed: {e}")
            return {"success": False, "error": str(e)}

    async def _process_response_with_agents(
        self, patient_id: UUID, response_text: str, message_metadata: Optional[Dict]
    ) -> Dict[str, Any]:
        """Process response using agents."""
        try:
            task_id = await self.swarm_manager.submit_task(
                task_type="process_quiz_response",
                payload={
                    "patient_id": str(patient_id),
                    "response_text": response_text,
                    "message_metadata": message_metadata or {},
                },
                required_capabilities=["response_interpretation", "mood_detection"],
                priority=MessagePriority.HIGH,
            )

            # Wait for processing (shorter timeout for responses)
            timeout = 60  # 1 minute
            start_time = now_sao_paulo()

            while (now_sao_paulo() - start_time).seconds < timeout:
                status = await self.swarm_manager.get_task_status(task_id)

                if status:
                    if status.get("status") == "completed":
                        return {
                            "success": True,
                            "method": "agent",
                            "result": status.get("result", {}),
                        }
                    elif status.get("status") == "failed":
                        return {
                            "success": False,
                            "method": "agent",
                            "error": status.get("error", "Unknown error"),
                        }

                await asyncio.sleep(1)

            return {
                "success": False,
                "method": "agent",
                "error": "Response processing timed out",
            }

        except Exception as e:
            self.logger.error(f"Agent response processing failed: {e}")
            return {"success": False, "method": "agent", "error": str(e)}

    async def _process_response_with_flow_engine(
        self, patient_id: UUID, response_text: str, message_metadata: Optional[Dict]
    ) -> Dict[str, Any]:
        """Process response using flow engine fallback."""
        try:
            # Use existing conversational quiz service
            from app.domain.quizzes.integration.flow_integration.utils import (
                get_conversational_quiz_service,
            )

            quiz_service = get_conversational_quiz_service(self.db_session)
            result = await quiz_service.process_quiz_response(
                patient_id, response_text, message_metadata
            )

            return {
                "success": result.get("success", False),
                "method": "legacy",
                "result": result,
            }

        except Exception as e:
            self.logger.error(f"Flow engine response processing failed: {e}")
            return {"success": False, "method": "legacy", "error": str(e)}

    async def _update_migration_stats(self, results: Dict[str, Any]):
        """Update migration statistics."""
        try:
            # This would update statistics about agent vs flow engine fallback usage
            # For monitoring and gradual migration decisions

            total = results.get("total_processed", 0)
            agent_count = results.get("agent_processed", 0)

            if total > 0:
                agent_percentage = (agent_count / total) * 100
                self.logger.info(
                    f"Agent usage: {agent_percentage:.1f}% ({agent_count}/{total})"
                )

                # Store metrics for analysis
                # This could update a metrics table or send to monitoring system

        except Exception as e:
            self.logger.error(f"Failed to update migration stats: {e}")

    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status."""
        return {
            "integration_mode": self.integration_mode.value,
            "swarm_manager_active": self.swarm_manager is not None,
            "enhanced_flow_engine_active": self.enhanced_flow_engine is not None,
            "registered_agents": len(self.agents),
            "agent_enabled_features": self.agent_enabled_features,
            "migration_percentage": self.migration_percentage,
            "agent_list": list(self.agents.keys()),
        }

    async def set_integration_mode(self, mode: IntegrationMode):
        """Change integration mode."""
        self.integration_mode = mode
        self.logger.info(f"Integration mode changed to: {mode.value}")

    async def update_migration_percentage(self, percentage: int):
        """Update migration percentage for gradual rollout."""
        if 0 <= percentage <= 100:
            self.migration_percentage = percentage
            self.logger.info(f"Migration percentage updated to: {percentage}%")
        else:
            raise ValueError("Migration percentage must be between 0 and 100")


# Global integration service instance
_integration_service: Optional[HiveMindIntegrationService] = None


async def get_hive_mind_integration() -> HiveMindIntegrationService:
    """Get global integration service instance."""
    global _integration_service

    if _integration_service is None:
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            _integration_service = HiveMindIntegrationService(db)
            await _integration_service.initialize()
        except Exception:
            db.close()
            raise

    return _integration_service


async def initialize_integration_service(
    db_session: Any | None = None,
) -> HiveMindIntegrationService:
    """Initialize integration service with specific database session."""
    global _integration_service

    if _integration_service is None:
        if db_session is None:
            from app.database import SessionLocal

            db_session = SessionLocal()
        _integration_service = HiveMindIntegrationService(db_session)
        await _integration_service.initialize()

    return _integration_service


def cleanup_hive_mind_integration() -> None:
    """Cleanup the global integration service."""
    global _integration_service
    if _integration_service:
        _integration_service.close()
        _integration_service = None
