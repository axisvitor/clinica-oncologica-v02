"""
Template Management Module

Handles loading, management and retrieval of message templates.
"""

from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session

from app.agents.patient.flow_coordinator.constants import FLOW_TYPES

from app.services.template_loader_pkg import (
    EnhancedTemplateLoader,
    MessageTemplate,
    FlowTemplateData,
)
from app.utils.logging import get_logger


class MessageTemplateManager:
    """Manages message templates for the Message Composer Agent."""

    def __init__(
        self,
        db_session: Session,
        template_loader: Optional[EnhancedTemplateLoader] = None,
    ):
        """Initialize template manager."""
        self.db_session = db_session
        self.logger = get_logger("message_composer.templates")

        # Template loader
        self.template_loader = template_loader or EnhancedTemplateLoader(db=db_session)
        self.loaded_templates: Dict[str, FlowTemplateData] = {}

        # Built-in message templates by category
        self.message_templates = {
            "greeting": {
                "morning": "Bom dia {name}! Como você está se sentindo hoje? 🌅",
                "afternoon": "Boa tarde {name}! Espero que esteja tendo um dia tranquilo. ☀️",
                "evening": "Boa noite {name}! Como foi seu dia? 🌙",
            },
            "checkup": {
                "daily": "Olá {name}! É hora do nosso check-in diário. Como você está? 💙",
                "weekly": "Olá {name}! Vamos fazer nosso acompanhamento semanal? 📋",
                "monthly": "Olá {name}! É hora do check-up mensal. Preparada? ✨",
            },
            "support": {
                "encouragement": "Você está indo muito bem, {name}! Continue assim! 💪",
                "comfort": "Entendo que pode ser difícil, {name}. Estou aqui para apoiá-la. 🤗",
                "celebration": "Parabéns, {name}! Esse é um marco importante! 🎉",
            },
            "medical": {
                "reminder": "Lembrete gentil para {name}: {reminder_text} 💊",
                "appointment": "Oi {name}! Seu próximo appointment é {date}. Está tudo ok? 📅",
                "results": "Olá {name}! Seus resultados chegaram. Vamos conversar sobre eles? 📄",
            },
        }

    async def load_message_templates(self) -> None:
        """Load message templates from template files."""
        try:
            # Load flow templates that contain message templates
            flow_types = FLOW_TYPES

            for flow_type in flow_types:
                try:
                    template_data = self.template_loader.load_flow_template(flow_type)
                    self.loaded_templates[flow_type] = template_data
                    self.logger.info(
                        f"Loaded {flow_type} template: {len(template_data.messages)} message templates"
                    )
                except Exception as e:
                    self.logger.warning(f"Could not load {flow_type} template: {e}")

            self.logger.info(
                f"Successfully loaded {len(self.loaded_templates)} flow templates"
            )

        except Exception as e:
            self.logger.error(f"Failed to load message templates: {e}")

    def get_template_message(
        self, flow_type: str, day: int
    ) -> Optional[MessageTemplate]:
        """Get message template for specific flow type and day."""
        template_data = self.loaded_templates.get(flow_type)
        if template_data:
            return template_data.messages.get(day)
        return None

    def get_available_templates(self) -> Dict[str, List[int]]:
        """Get information about available templates."""
        available = {}
        for flow_type, template_data in self.loaded_templates.items():
            available[flow_type] = list(template_data.messages.keys())
        return available

    async def reload_templates(self) -> bool:
        """Reload all templates from source."""
        try:
            self.loaded_templates.clear()
            await self.load_message_templates()
            return len(self.loaded_templates) > 0
        except Exception as e:
            self.logger.error(f"Failed to reload templates: {e}")
            return False

    def get_builtin_template(
        self,
        template_id: str,
        patient_name: str,
        time_of_day: str,
        context: Dict[str, Any],
    ) -> str:
        """Get message from built-in templates."""
        if template_id in self.message_templates:
            template_category = self.message_templates[template_id]
            if time_of_day in template_category:
                return template_category[time_of_day].format(
                    name=patient_name, **context
                )
            else:
                # Use first available template in category
                first_template = list(template_category.values())[0]
                return first_template.format(name=patient_name, **context)
        raise ValueError(f"Template not found: {template_id} ({time_of_day})")
