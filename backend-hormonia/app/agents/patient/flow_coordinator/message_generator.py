"""Message Generator - Generates and personalizes flow messages."""

from __future__ import annotations

# Standard library
import logging
from typing import Any, Dict, Optional

# Third-party
from sqlalchemy.orm import Session

# Local
from app.ai.client import get_gemini_client
from app.ai.pii_redaction import redact_conversation_history, redact_patient_context
from app.services.template_loader_pkg import (
    EnhancedTemplateLoader,
    FlowTemplateData,
    MessageTemplate,
)
from app.utils.template_variables import TemplateVariableProcessor

from .constants import FLOW_TYPES, normalize_flow_day, resolve_flow_type_and_day
from .models import FlowContext
from app.utils.timezone import now_sao_paulo


class MessageGenerator:
    """
    Generates and personalizes flow messages.

    Loads flow templates and generates personalized messages
    using AI-powered content generation and context-aware
    personalization.

    Attributes:
        db_session: Database session.
        agent_id: Unique agent identifier.
        logger: Logger instance.
        template_loader: Template loader instance.
        flow_templates: Loaded flow templates.
        gemini_client: Gemini AI client for content generation.
    """

    def __init__(
        self,
        db_session: Session,
        agent_id: str,
        logger: logging.Logger,
        template_loader: Optional[EnhancedTemplateLoader] = None,
    ):
        self.db_session = db_session
        self.agent_id = agent_id
        self.logger = logger
        self.template_loader = template_loader or EnhancedTemplateLoader(db=db_session)
        self.flow_templates: Dict[str, FlowTemplateData] = {}
        self.gemini_client = None

    def initialize_gemini(self):
        """Initialize Gemini client."""
        self.gemini_client = get_gemini_client()

    async def load_flow_templates(self) -> None:
        """Load all available flow templates."""
        try:
            # Load main flow templates
            flow_types = FLOW_TYPES

            for flow_type in flow_types:
                try:
                    template_data = self.template_loader.load_flow_template(flow_type)
                    self.flow_templates[flow_type] = template_data
                    self.logger.info(
                        f"Loaded {flow_type} template: {len(template_data.messages)} messages"
                    )
                except Exception as e:
                    self.logger.warning(f"Could not load {flow_type} template: {e}")

            self.logger.info(
                f"Successfully loaded {len(self.flow_templates)} flow templates"
            )

        except Exception as e:
            self.logger.error(f"Failed to load flow templates: {e}")

    async def generate_daily_message(
        self, context: FlowContext
    ) -> Optional[Dict[str, Any]]:
        """Generate appropriate daily message using templates and AI optimization."""
        if not context.patient_data:
            return None

        try:
            # Determine appropriate flow template based on current day
            flow_type, template_day = self._resolve_flow_type_and_day(
                context.current_day
            )

            # Try to get message from templates first
            template_message = await self._get_template_message(
                flow_type, template_day
            )

            if template_message:
                # Use AI to generate personalized content based on template
                personalized_content = await self._personalize_template_message(
                    template_message, context
                )
                return personalized_content

            # Template not found - this should not happen in production
            # All templates MUST be in the database (see template_loader.py)
            self.logger.critical(
                f"TEMPLATE_MISSING: No template found for flow_type={flow_type}, day={context.current_day}. "
                f"Patient ID: {getattr(context.patient_data, 'id', 'unknown') if context.patient_data else 'unknown'}. "
                "Please ensure all templates are loaded in the database."
            )
            raise ValueError(
                f"Missing template: flow_type={flow_type}, day={context.current_day}"
            )

        except ValueError:
            # Re-raise template missing errors
            raise
        except Exception as e:
            self.logger.error(f"Error generating daily message: {e}")
            raise

    def _resolve_flow_type_and_day(self, current_day: int) -> tuple[str, int]:
        """Determine flow type and template day based on current day."""
        normalized_day = normalize_flow_day(current_day)
        return resolve_flow_type_and_day(normalized_day)

    async def _get_template_message(
        self, flow_type: str, day: int
    ) -> Optional[MessageTemplate]:
        """Get message template for specific flow type and day."""
        try:
            # Check if template is already loaded
            if flow_type not in self.flow_templates:
                await self._load_specific_template(flow_type)

            flow_template = self.flow_templates.get(flow_type)
            if flow_template:
                return flow_template.messages.get(day)

        except Exception as e:
            self.logger.warning(
                f"Could not get template message for {flow_type}, day {day}: {e}"
            )

        return None

    async def _load_specific_template(self, flow_type: str) -> None:
        """Load specific flow template."""
        try:
            template_data = self.template_loader.load_flow_template(flow_type)
            self.flow_templates[flow_type] = template_data
            self.logger.info(
                f"Loaded template for {flow_type}: {len(template_data.messages)} messages"
            )
        except Exception as e:
            self.logger.error(f"Failed to load template {flow_type}: {e}")

    async def _personalize_template_message(
        self, template: MessageTemplate, context: FlowContext
    ) -> Dict[str, Any]:
        """Personalize template message using AI and context."""
        try:
            # Prepare personalization context
            personalization_context = {
                "patient_name": context.patient_data.name
                if context.patient_data
                else "Cliente",
                "current_day": context.current_day,
                "mood_trend": context.mood_indicators.get("trend", 0),
                "engagement_level": context.adherence_metrics.get(
                    "message_response_rate", 0.5
                ),
                "risk_factors": context.risk_factors,
                "personalization_hints": template.personalization_hints,
                "core_elements": template.core_elements,
            }
            flow_state_data: Dict[str, Any] = {}
            flow_kind = None
            send_mode = None
            message_index = None
            if context.flow_state:
                try:
                    flow_state_data = context.flow_state.state_data or {}
                except Exception:
                    flow_state_data = {}
                flow_kind = flow_state_data.get("flow_kind")
                send_mode = (
                    flow_state_data.get("send_mode")
                    or flow_state_data.get("daily_send_mode")
                )
                message_index = flow_state_data.get("current_day_message_index")
                if not flow_kind:
                    try:
                        flow_kind = str(context.flow_state.flow_type)
                    except Exception:
                        flow_kind = None

            personalization_context.update(
                {
                    "flow_kind": flow_kind or "unknown",
                    "send_mode": send_mode or "single",
                    "message_index": message_index,
                }
            )

            # Generate personalized content using AI if available
            if template.ai_instructions and self.gemini_client:
                personalized_content = await self._generate_ai_content(
                    template, personalization_context
                )
            else:
                # Use base template with basic personalization
                personalized_content = self._apply_basic_personalization(
                    template, personalization_context
                )

            return {
                "content": personalized_content,
                "personalization_level": "high"
                if template.ai_instructions
                else "standard",
                "template_intent": template.intent,
                "generated_at": now_sao_paulo().isoformat(),
                "source": "template",
            }

        except Exception as e:
            self.logger.error(f"Error personalizing template message: {e}")
            raise

    async def _generate_ai_content(
        self, template: MessageTemplate, context: Dict[str, Any]
    ) -> str:
        """Generate AI-optimized content based on template and context."""
        try:
            patient_name = str(context.get("patient_name") or "").strip()
            safe_context = redact_patient_context(context)
            safe_history = redact_conversation_history(
                context.get("conversation_history", []),
                patient_names=[patient_name] if patient_name else None,
            )
            personalized = await self.gemini_client.humanize_flow_message(
                template=template.base_content,
                patient_name=str(safe_context.get("patient_name", "Paciente")),
                patient_context=safe_context,
                conversation_history=safe_history,
                personalization_hints=context.get("personalization_hints", []),
                ai_instructions=template.ai_instructions,
                strict=True,
            )

            if not personalized:
                raise ValueError("AI returned empty flow message")

            return personalized.strip()

        except Exception as e:
            self.logger.error(f"AI content generation failed: {e}")
            raise

    def _apply_basic_personalization(
        self, template: MessageTemplate, context: Dict[str, Any]
    ) -> str:
        """Apply basic personalization to template."""
        content = template.base_content

        # Use TemplateVariableProcessor for comprehensive variable substitution
        content = TemplateVariableProcessor.substitute_variables(content, context)

        # Validate that all variables were replaced
        unreplaced = TemplateVariableProcessor.validate_variables(content)
        if unreplaced:
            self.logger.warning(f"Unreplaced variables in message: {unreplaced}")

        # Add mood-based personalization
        mood_trend = context.get("mood_trend", 0)
        if mood_trend < -0.5:
            content += " Notei que você pode estar passando por um momento mais difícil. Estou aqui para te apoiar. 💜"
        elif mood_trend > 0.5:
            content += " Que bom perceber que você parece estar se sentindo melhor! 😊"

        # Add engagement-based elements
        engagement = context.get("engagement_level", 0.5)
        if engagement < 0.3:
            content += " Lembre-se: pode me procurar sempre que precisar, ok?"

        return content

    def get_loaded_templates(self) -> Dict[str, str]:
        """Get information about loaded templates."""
        return {
            flow_type: f"{template.name} v{template.version} ({len(template.messages)} messages)"
            for flow_type, template in self.flow_templates.items()
        }

    async def reload_templates(self) -> bool:
        """Reload all templates from source."""
        try:
            self.flow_templates.clear()
            await self.load_flow_templates()
            return len(self.flow_templates) > 0
        except Exception as e:
            self.logger.error(f"Failed to reload templates: {e}")
            return False
