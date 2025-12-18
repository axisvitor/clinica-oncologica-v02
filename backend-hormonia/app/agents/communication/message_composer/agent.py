"""
Message Composer Agent

Main agent class responsible for orchestrating message composition.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent, AgentCapabilities
from app.integrations.gemini_client import get_gemini_client
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.services.conversation_memory import get_conversation_memory
from app.services.template_loader import EnhancedTemplateLoader
from app.utils.logging import get_logger

from .templates import MessageTemplateManager
from .context_builder import MessageContextBuilder
from .tone_adapter import MessageToneAdapter
from .composer import MessageComposer


class MessageComposerAgent(BaseAgent):
    """
    Agent specialized in intelligent message composition and personalization.

    Capabilities:
    - Contextual message generation
    - Personalization based on patient history
    - Emotional tone adaptation
    - Multi-language support
    - Template customization
    - Conversation continuity
    """

    def __init__(
        self,
        db_session: Session,
        template_loader: Optional[EnhancedTemplateLoader] = None,
    ):
        """Initialize Message Composer Agent."""
        super().__init__(
            agent_id="message_composer",
            agent_type="communication",
            specialization="message_composer",
            db_session=db_session,
            capabilities=[
                AgentCapabilities.MESSAGE_COMPOSITION,
                AgentCapabilities.PERSONALIZATION,
                AgentCapabilities.EMOTIONAL_INTELLIGENCE,
                AgentCapabilities.PATIENT_ADAPTATION,
            ],
        )

        self.db_session = db_session
        self.patient_repo = PatientRepository(db_session)
        self.gemini_client = get_gemini_client()
        self.conversation_memory = get_conversation_memory()
        self.logger = get_logger(f"agent.{self.agent_id}")

        # Message composition configuration
        self.composition_config = {
            "max_message_length": 1000,
            "personalization_level": "high",
            "empathy_threshold": 0.7,
            "context_window": 10,  # Previous messages to consider
            "languages": ["pt-BR", "en", "es"],
            "tone_adaptation": True,
            "emoji_usage": "contextual",
        }

        # Initialize components
        self.template_manager = MessageTemplateManager(db_session, template_loader)
        self.context_builder = MessageContextBuilder(
            self.gemini_client,
            self.conversation_memory,
            self.composition_config["context_window"],  # type: ignore[arg-type]
        )
        self.tone_adapter = MessageToneAdapter(self.gemini_client)
        self.composer = MessageComposer(
            self.gemini_client,
            self.composition_config["max_message_length"],  # type: ignore[arg-type]
        )

        self.logger.info("Message Composer Agent initialized")

    async def initialize(self):
        """Initialize the agent and load templates."""
        try:
            await self.template_manager.load_message_templates()
            self.logger.info("Message Composer Agent fully initialized with templates")
        except Exception as e:
            self.logger.error(f"Failed to initialize message templates: {e}")
            # Continue without templates - fallback to hardcoded ones

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process message composition task."""
        try:
            task_type = task.get("task_type")
            payload = task.get("payload", {})

            if task_type == "compose_message":
                return await self._compose_message(payload)
            elif task_type == "personalize_template":
                return await self._personalize_template(payload)
            elif task_type == "adapt_tone":
                return await self._adapt_message_tone(payload)
            elif task_type == "compose_follow_up":
                return await self._compose_follow_up(payload)
            elif task_type == "generate_quiz_message":
                return await self._generate_quiz_message(payload)
            else:
                return {"success": False, "error": f"Unknown task type: {task_type}"}

        except Exception as e:
            self.logger.error(f"Task processing failed: {e}")
            return {"success": False, "error": str(e)}

    async def _compose_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Compose intelligent message based on context."""
        try:
            patient_id = UUID(payload.get("patient_id"))
            message_type = payload.get("message_type", "general")
            context = payload.get("context", {})
            template_id = payload.get("template_id")
            custom_content = payload.get("content")

            # Get patient information
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {"success": False, "error": "Patient not found"}

            # Build composition context
            composition_context = await self.context_builder.build_composition_context(
                patient, context
            )

            # Compose message based on method
            if custom_content:
                # Personalize custom content
                message_content = await self.composer.personalize_custom_content(
                    custom_content,
                    patient,
                    composition_context,
                    self.composition_config["personalization_level"],  # type: ignore[arg-type]
                )
            elif template_id:
                # Use template with personalization
                message_content = self._compose_from_template(
                    template_id, patient, composition_context
                )
            else:
                # AI-generated message
                message_content = await self.composer.generate_contextual_message(
                    message_type, patient, composition_context
                )

            # Fallback if no content generated
            if not message_content:
                message_content = self.template_manager.get_fallback_message(
                    message_type,
                    patient.name,  # type: ignore[arg-type]
                )

            # Apply tone adaptation
            if self.composition_config.get("tone_adaptation", True):
                message_content = await self.tone_adapter.adapt_message_tone(
                    {
                        "content": message_content,
                        "patient_context": composition_context,
                        "target_tone": composition_context.get(
                            "preferred_tone", "supportive"
                        ),
                    }
                )

            # Store message pattern for learning
            await self.conversation_memory.store_message_pattern(
                patient_id, message_content
            )

            # Update knowledge graph
            await self._update_message_knowledge(
                patient_id, message_content, message_type
            )

            return {
                "success": True,
                "message_content": message_content,
                "composition_metadata": {
                    "method": "ai_composed"
                    if not template_id and not custom_content
                    else "template_based",
                    "personalization_level": self.composition_config[
                        "personalization_level"
                    ],
                    "context_tokens": len(str(composition_context)),
                    "generated_at": datetime.utcnow().isoformat(),
                },
            }

        except Exception as e:
            self.logger.error(f"Message composition failed: {e}")
            return {"success": False, "error": str(e)}

    async def _personalize_template(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Personalize message template with patient context."""
        try:
            patient_id = UUID(payload.get("patient_id"))
            template = payload.get("template")
            context = payload.get("context", {})

            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {"success": False, "error": "Patient not found"}

            # Build personalization context
            composition_context = await self.context_builder.build_composition_context(
                patient, context
            )

            # Personalize template
            personalized_content = await self.composer.personalize_template(
                template,
                patient,
                composition_context,  # type: ignore[arg-type]
                self.composition_config["personalization_level"],  # type: ignore[arg-type]
            )

            return {
                "success": True,
                "personalized_content": personalized_content,
                "personalization_metadata": {
                    "template_used": True,
                    "ai_enhanced": self.composition_config["personalization_level"]
                    == "high",
                    "context_applied": len(composition_context) > 0,
                },
            }

        except Exception as e:
            self.logger.error(f"Template personalization failed: {e}")
            return {"success": False, "error": str(e)}

    async def _adapt_message_tone(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt message tone based on patient context."""
        try:
            adapted_content = await self.tone_adapter.adapt_message_tone(payload)

            return {"success": True, "adapted_content": adapted_content}

        except Exception as e:
            self.logger.error(f"Tone adaptation failed: {e}")
            return {"success": False, "error": str(e)}

    async def _compose_follow_up(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Compose intelligent follow-up message."""
        try:
            patient_id = UUID(payload.get("patient_id"))
            previous_interaction = payload.get("previous_interaction", {})
            follow_up_reason = payload.get("reason", "general")

            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {"success": False, "error": "Patient not found"}

            # Analyze previous interaction
            interaction_analysis = (
                await self.context_builder.analyze_previous_interaction(
                    previous_interaction
                )
            )

            # Generate follow-up
            follow_up_content = await self.composer.compose_follow_up(
                patient, previous_interaction, follow_up_reason, interaction_analysis
            )

            return {
                "success": True,
                "follow_up_content": follow_up_content,
                "follow_up_metadata": {
                    "reason": follow_up_reason,
                    "based_on_previous": bool(previous_interaction),
                    "interaction_analysis": interaction_analysis,
                },
            }

        except Exception as e:
            self.logger.error(f"Follow-up composition failed: {e}")
            return {"success": False, "error": str(e)}

    async def _generate_quiz_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate personalized quiz message."""
        try:
            patient_id = UUID(payload.get("patient_id"))
            quiz_context = payload.get("quiz_context", {})
            question_data = payload.get("question_data", {})

            patient = self.patient_repo.get(patient_id)
            if not patient:
                return {"success": False, "error": "Patient not found"}

            # Build quiz context
            composition_context = await self.context_builder.build_composition_context(
                patient, quiz_context
            )

            # Generate quiz message
            quiz_message = await self.composer.generate_quiz_message(
                patient, composition_context, question_data
            )

            return {
                "success": True,
                "quiz_message": quiz_message,
                "quiz_metadata": {
                    "question_type": question_data.get("type", "open_text"),
                    "has_options": len(question_data.get("options", [])) > 0,
                    "personalized": True,
                },
            }

        except Exception as e:
            self.logger.error(f"Quiz message generation failed: {e}")
            return {"success": False, "error": str(e)}

    async def _update_message_knowledge(
        self, patient_id: UUID, message_content: str, message_type: str
    ):
        """Update knowledge graph with message patterns."""
        try:
            # Store message pattern and effectiveness
            await self.coordination_hooks.store_in_memory(  # type: ignore[attr-defined]
                key=f"message_patterns/{patient_id}/{message_type}",
                data={
                    "content": message_content,
                    "type": message_type,
                    "composed_at": datetime.utcnow().isoformat(),
                    "method": "ai_generated",
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to update message knowledge: {e}")

    def _compose_from_template(
        self, template_id: str, patient: Patient, context: Dict[str, Any]
    ) -> str:
        """Compose message from predefined template."""
        time_of_day = context.get("time_context", {}).get("time_of_day", "morning")

        return self.template_manager.get_builtin_template(
            template_id,
            patient.name,
            time_of_day,
            context,  # type: ignore[arg-type]
        )

    # Template management methods
    async def compose_from_flow_template(
        self, flow_type: str, day: int, patient: Patient, context: Dict[str, Any]
    ) -> Optional[str]:
        """Compose message from flow template."""
        try:
            # Get template message
            template_message = self.template_manager.get_template_message(
                flow_type, day
            )
            if not template_message:
                return None

            # Compose using template
            composed_message = await self.composer.compose_from_flow_template(
                template_message, patient, context
            )

            return composed_message

        except Exception as e:
            self.logger.error(f"Failed to compose from flow template: {e}")
            return None

    def get_available_templates(self) -> Dict[str, List[int]]:
        """Get information about available templates."""
        return self.template_manager.get_available_templates()

    async def reload_templates(self) -> bool:
        """Reload all templates from source."""
        return await self.template_manager.reload_templates()
