"""
Template Management Module.
Handles template loading, fallback generation, and template error handling.
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.services.enhanced_flow_engine import FlowType
from app.services.template_loader import (
    EnhancedTemplateLoader,
    MessageTemplate,
    TemplateLoadError,
    FlowTemplateData,
    MessageType as TemplateMessageType
)

logger = logging.getLogger(__name__)


class MessageTemplateLoader:
    """Manages template loading and fallback generation for flow messages."""

    def __init__(self, db: Session, template_loader: Optional[EnhancedTemplateLoader] = None):
        """
        Initialize template manager.

        Args:
            db: Database session
            template_loader: Template loader instance
        """
        self.db = db
        self.template_loader = template_loader or EnhancedTemplateLoader(db=db)

    async def get_message_template_for_day(self,
                                          flow_type: FlowType,
                                          day: int) -> Optional[MessageTemplate]:
        """
        Get message template for specific flow type and day with comprehensive error handling.

        This function implements multiple fallback layers:
        1. Primary: Load template from template_loader
        2. Fallback: Use predefined fallback templates in Portuguese
        3. Last resort: Return None (caller handles gracefully)

        Error handling:
        - TemplateLoadError: Template syntax/parsing errors → fallback
        - FileNotFoundError: Template file missing → fallback
        - Generic exceptions: Unexpected errors → fallback with full trace

        Args:
            flow_type: Type of flow (INITIAL_15_DAYS, DAYS_16_45, MONTHLY_RECURRING)
            day: Day number in the flow

        Returns:
            MessageTemplate or None if all fallbacks fail
        """
        try:
            # Load flow template with proper error handling
            try:
                flow_template: FlowTemplateData = self.template_loader.load_flow_template(flow_type.value)
            except TemplateLoadError as e:
                logger.error(
                    f"Template load error for {flow_type.value}: {e}. "
                    f"Using fallback message."
                )
                return await self.get_fallback_template(flow_type, day)
            except FileNotFoundError as e:
                logger.error(
                    f"Template file not found for {flow_type.value}: {e}. "
                    f"Using fallback message."
                )
                return await self.get_fallback_template(flow_type, day)
            except Exception as e:
                logger.error(
                    f"Unexpected error loading template {flow_type.value}: {e}. "
                    f"Using fallback message.",
                    exc_info=True
                )
                return await self.get_fallback_template(flow_type, day)

            # Get message for specific day from FlowTemplateData.messages dict
            if day in flow_template.messages:
                message_template = flow_template.messages[day]
                logger.debug(f"Found message template for {flow_type.value} day {day}")
                return message_template

            logger.warning(
                f"No message template found for {flow_type.value} day {day}. "
                f"Using fallback message."
            )
            return await self.get_fallback_template(flow_type, day)

        except Exception as e:
            logger.error(
                f"Critical error getting message template for {flow_type.value} day {day}: {e}. "
                f"Using fallback message.",
                exc_info=True
            )
            return await self.get_fallback_template(flow_type, day)

    async def get_fallback_template(self, flow_type: FlowType, day: int) -> Optional[MessageTemplate]:
        """Provide fallback template when primary template loading fails."""
        try:
            # Create a simple fallback message template in Portuguese
            fallback_messages = {
                FlowType.INITIAL_15_DAYS: {
                    'content': "Olá! Como você está se sentindo hoje?",
                    'intent': 'daily_check_initial',
                    'ai_instructions': 'Generate a warm, caring message asking about patient well-being'
                },
                FlowType.DAYS_16_45: {
                    'content': "Esperamos que você esteja bem. Como está seu tratamento?",
                    'intent': 'treatment_followup',
                    'ai_instructions': 'Generate an empathetic message about treatment progress'
                },
                FlowType.MONTHLY_RECURRING: {
                    'content': "Olá! É hora de fazer seu check-in mensal.",
                    'intent': 'monthly_checkin',
                    'ai_instructions': 'Generate a friendly monthly check-in message'
                }
            }

            fallback_data = fallback_messages.get(
                flow_type,
                {
                    'content': "Olá! Como podemos ajudá-lo hoje?",
                    'intent': 'general_checkin',
                    'ai_instructions': 'Generate a supportive, caring message'
                }
            )

            logger.warning(
                f"Using fallback template for {flow_type.value} day {day}. "
                f"Template loading failed, providing default Portuguese message."
            )

            return MessageTemplate(
                day=day,
                intent=fallback_data['intent'],
                base_content=fallback_data['content'],
                core_elements={"greeting": True, "care": True, "support": True},
                personalization_hints=["patient_name", "treatment_type", "patient_condition"],
                ai_instructions=fallback_data['ai_instructions'],
                message_type=TemplateMessageType.TEXT,
                variations=[]  # No variations for fallback
            )
        except Exception as e:
            logger.error(
                f"Critical failure generating fallback template: {e}. "
                f"Returning None - flow will skip this day.",
                exc_info=True
            )
            return None

    def validate_template(self, template: MessageTemplate) -> bool:
        """
        Validate template has all required fields and proper structure.

        Args:
            template: Template to validate

        Returns:
            bool: True if template is valid
        """
        try:
            if not template:
                return False

            # Check required fields
            required_fields = ['intent', 'base_content', 'ai_instructions']
            for field in required_fields:
                if not hasattr(template, field) or not getattr(template, field):
                    logger.warning(f"Template missing required field: {field}")
                    return False

            # Validate day number
            if hasattr(template, 'day') and template.day < 0:
                logger.warning("Template has invalid day number")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating template: {e}")
            return False

    async def load_all_templates_for_flow(self, flow_type: FlowType) -> dict[int, MessageTemplate]:
        """
        Load all templates for a given flow type.

        Args:
            flow_type: Type of flow

        Returns:
            Dictionary mapping day number to MessageTemplate
        """
        try:
            flow_template: FlowTemplateData = self.template_loader.load_flow_template(flow_type.value)
            return flow_template.messages
        except Exception as e:
            logger.error(f"Failed to load all templates for {flow_type.value}: {e}")
            return {}

    async def get_template_metadata(self, flow_type: FlowType, day: int) -> dict:
        """
        Get metadata about a template without loading full content.

        Args:
            flow_type: Type of flow
            day: Day number

        Returns:
            Template metadata
        """
        try:
            template = await self.get_message_template_for_day(flow_type, day)
            if not template:
                return {'exists': False}

            return {
                'exists': True,
                'intent': template.intent,
                'day': template.day,
                'message_type': template.message_type.value if hasattr(template.message_type, 'value') else str(template.message_type),
                'has_variations': bool(template.variations),
                'personalization_hints_count': len(template.personalization_hints) if template.personalization_hints else 0
            }
        except Exception as e:
            logger.error(f"Failed to get template metadata: {e}")
            return {'exists': False, 'error': str(e)}
