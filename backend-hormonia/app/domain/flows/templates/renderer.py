"""
Template Rendering Module - Flow Template Loading and Rendering

Handles template loading, validation, and rendering for flow messages.
"""

import logging
from typing import Dict, Any, Optional

from app.services.template_loader import EnhancedTemplateLoader, MessageTemplate
from app.config.flow_templates import FlowTemplateLoader


logger = logging.getLogger(__name__)


class TemplateRenderer:
    """
    Manages template loading and rendering.

    Responsibilities:
    - Load flow templates from configuration
    - Get message templates for specific days
    - Validate template availability
    - Handle template fallbacks
    """

    def __init__(
        self,
        template_loader: EnhancedTemplateLoader,
        flow_template_loader: FlowTemplateLoader,
    ):
        """
        Initialize TemplateRenderer.

        Args:
            template_loader: Enhanced template loader service
            flow_template_loader: Flow template configuration loader
        """
        self.template_loader = template_loader
        self.flow_template_loader = flow_template_loader

        logger.info("TemplateRenderer initialized")

    async def load_flow_template(self, flow_type: str) -> Optional[Dict[str, Any]]:
        """
        Load flow template configuration from flow_templates.yaml.

        Args:
            flow_type: Flow type identifier

        Returns:
            Template configuration dictionary or None
        """
        try:
            config = self.flow_template_loader.get_flow_config(flow_type)

            if config:
                logger.debug(f"Flow template loaded for type: {flow_type}")
            else:
                logger.warning(f"No flow template found for type: {flow_type}")

            return config

        except Exception as e:
            logger.error(f"Error loading flow template {flow_type}: {e}")
            return None

    async def get_message_template_for_day(
        self, flow_type: str, day: int
    ) -> Optional[MessageTemplate]:
        """
        Get message template for specific flow type and day.

        Args:
            flow_type: Flow type identifier
            day: Day number in flow

        Returns:
            MessageTemplate or None if not found
        """
        try:
            # Load flow template using enhanced template loader
            from app.services.enhanced_flow_engine import FlowType

            flow_type_enum = FlowType(flow_type)
            flow_template = self.template_loader.load_flow_template(
                flow_type_enum.value
            )

            if day in flow_template.messages:
                template = flow_template.messages[day]
                logger.debug(f"Message template found for {flow_type} day {day}")
                return template

            logger.warning(f"No message template for {flow_type} day {day}")
            return None

        except Exception as e:
            logger.error(f"Error getting message template: {e}")
            return None

    def validate_template_availability(
        self, flow_type: str, days: list[int]
    ) -> Dict[int, bool]:
        """
        Validate template availability for multiple days.

        Args:
            flow_type: Flow type identifier
            days: List of days to check

        Returns:
            Dictionary mapping day to availability
        """
        availability = {}

        try:
            from app.services.enhanced_flow_engine import FlowType

            flow_type_enum = FlowType(flow_type)
            flow_template = self.template_loader.load_flow_template(
                flow_type_enum.value
            )

            for day in days:
                availability[day] = day in flow_template.messages

            logger.debug(f"Template availability check for {flow_type}: {availability}")

        except Exception as e:
            logger.error(f"Error validating template availability: {e}")
            # Mark all as unavailable on error
            for day in days:
                availability[day] = False

        return availability

    def get_template_metadata(
        self, flow_type: str, day: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific template.

        Args:
            flow_type: Flow type identifier
            day: Day number

        Returns:
            Template metadata or None
        """
        try:
            from app.services.enhanced_flow_engine import FlowType

            flow_type_enum = FlowType(flow_type)
            flow_template = self.template_loader.load_flow_template(
                flow_type_enum.value
            )

            if day in flow_template.messages:
                template = flow_template.messages[day]
                return {
                    "intent": template.intent,
                    "day": template.day,
                    "has_content": bool(template.base_content),
                    "content_length": len(template.base_content)
                    if template.base_content
                    else 0,
                }

            return None

        except Exception as e:
            logger.error(f"Error getting template metadata: {e}")
            return None
