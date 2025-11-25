"""
Message Generator - Generates and personalizes flow messages.
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.template_loader import EnhancedTemplateLoader, FlowTemplateData, MessageTemplate
from app.integrations.gemini_client import get_gemini_client
from app.utils.template_variables import TemplateVariableProcessor
from .models import FlowContext


class MessageGenerator:
    """Generates and personalizes flow messages."""

    def __init__(
        self,
        db_session: Session,
        agent_id: str,
        logger: logging.Logger,
        template_loader: Optional[EnhancedTemplateLoader] = None
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
            flow_types = ["initial_15_days", "days_16_45", "monthly_recurring"]

            for flow_type in flow_types:
                try:
                    template_data = self.template_loader.load_flow_template(flow_type)
                    self.flow_templates[flow_type] = template_data
                    self.logger.info(f"Loaded {flow_type} template: {len(template_data.messages)} messages")
                except Exception as e:
                    self.logger.warning(f"Could not load {flow_type} template: {e}")

            self.logger.info(f"Successfully loaded {len(self.flow_templates)} flow templates")

        except Exception as e:
            self.logger.error(f"Failed to load flow templates: {e}")

    async def generate_daily_message(self, context: FlowContext) -> Optional[Dict[str, Any]]:
        """Generate appropriate daily message using templates and AI optimization."""
        if not context.patient_data:
            return None

        try:
            # Determine appropriate flow template based on current day
            flow_type = self._determine_flow_type(context.current_day)

            # Try to get message from templates first
            template_message = await self._get_template_message(flow_type, context.current_day)

            if template_message:
                # Use AI to generate personalized content based on template
                personalized_content = await self._personalize_template_message(
                    template_message, context
                )
                return personalized_content

            # Fallback to legacy generation if template not found
            return await self._generate_legacy_message(context)

        except Exception as e:
            self.logger.error(f"Error generating daily message: {e}")
            # Fallback to legacy generation
            return await self._generate_legacy_message(context)

    def _determine_flow_type(self, current_day: int) -> str:
        """Determine appropriate flow type based on current day."""
        if current_day <= 15:
            return "initial_15_days"
        elif current_day <= 45:
            return "days_16_45"
        else:
            return "monthly_recurring"

    async def _get_template_message(self, flow_type: str, day: int) -> Optional[MessageTemplate]:
        """Get message template for specific flow type and day."""
        try:
            # Check if template is already loaded
            if flow_type not in self.flow_templates:
                await self._load_specific_template(flow_type)

            flow_template = self.flow_templates.get(flow_type)
            if flow_template:
                return flow_template.messages.get(day)

        except Exception as e:
            self.logger.warning(f"Could not get template message for {flow_type}, day {day}: {e}")

        return None

    async def _load_specific_template(self, flow_type: str) -> None:
        """Load specific flow template."""
        try:
            template_data = self.template_loader.load_flow_template(flow_type)
            self.flow_templates[flow_type] = template_data
            self.logger.info(f"Loaded template for {flow_type}: {len(template_data.messages)} messages")
        except Exception as e:
            self.logger.error(f"Failed to load template {flow_type}: {e}")

    async def _personalize_template_message(
        self, template: MessageTemplate, context: FlowContext
    ) -> Dict[str, Any]:
        """Personalize template message using AI and context."""
        try:
            # Prepare personalization context
            personalization_context = {
                "patient_name": context.patient_data.name if context.patient_data else "Cliente",
                "current_day": context.current_day,
                "mood_trend": context.mood_indicators.get("trend", 0),
                "engagement_level": context.adherence_metrics.get("message_response_rate", 0.5),
                "risk_factors": context.risk_factors,
                "personalization_hints": template.personalization_hints,
                "core_elements": template.core_elements
            }

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
                "personalization_level": "high" if template.ai_instructions else "standard",
                "template_intent": template.intent,
                "generated_at": datetime.utcnow().isoformat(),
                "source": "template"
            }

        except Exception as e:
            self.logger.error(f"Error personalizing template message: {e}")
            # Fallback to base content
            return {
                "content": template.base_content.replace("{patient_name}",
                    context.patient_data.name if context.patient_data else "Cliente"),
                "personalization_level": "basic",
                "template_intent": template.intent,
                "generated_at": datetime.utcnow().isoformat(),
                "source": "template_fallback"
            }

    async def _generate_ai_content(
        self, template: MessageTemplate, context: Dict[str, Any]
    ) -> str:
        """Generate AI-optimized content based on template and context."""
        try:
            # Prepare AI prompt
            ai_prompt = f"""
            {template.ai_instructions}

            Contexto do paciente:
            - Nome: {context['patient_name']}
            - Dia do tratamento: {context['current_day']}
            - Tendência de humor: {context['mood_trend']}
            - Nível de engajamento: {context['engagement_level']}
            - Fatores de risco: {', '.join(context['risk_factors'])}

            Dicas de personalização: {', '.join(context['personalization_hints'])}
            Elementos essenciais: {context['core_elements']}

            Conteúdo base: {template.base_content}

            Gere uma mensagem personalizada seguindo as instruções acima:
            """

            # Call AI service
            response = await self.gemini_client.generate_content(ai_prompt)

            if response and hasattr(response, 'text'):
                return response.text.strip()

            # Fallback if AI fails
            return self._apply_basic_personalization(template, context)

        except Exception as e:
            self.logger.error(f"AI content generation failed: {e}")
            return self._apply_basic_personalization(template, context)

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

    async def _generate_legacy_message(self, context: FlowContext) -> Dict[str, Any]:
        """Generate message using legacy approach (fallback)."""
        if not context.patient_data:
            return None

        try:
            # Base message template based on day
            if context.current_day <= 7:
                # Welcome phase
                base_template = f"Bom dia, {context.patient_data.name}! Como você está se sentindo hoje? Lembre-se de que estou aqui para acompanhar sua jornada. 💜"
            elif context.current_day <= 21:
                # Adaptation phase
                base_template = f"Olá {context.patient_data.name}! Espero que você esteja bem hoje. Como tem sido sua experiência com o tratamento?"
            elif context.current_day <= 45:
                # Stabilization phase
                base_template = f"Oi {context.patient_data.name}! Continuamos juntas nessa jornada. Como você se sente hoje?"
            else:
                # Maintenance phase
                base_template = f"Olá {context.patient_data.name}! Que bom te ouvir novamente. Como tem passado?"

            # Personalize based on mood indicators and patterns
            if context.mood_indicators.get("trend", 0) < -0.5:
                # Recent mood decline
                personalization = " Notei que você pode estar passando por um momento mais difícil. Gostaria de conversar sobre isso?"
                base_template += personalization
            elif context.mood_indicators.get("trend", 0) > 0.5:
                # Mood improvement
                personalization = " Fico feliz em perceber que você parece estar se sentindo melhor! 😊"
                base_template += personalization

            # Add contextual elements based on knowledge graph
            if context.knowledge_context.get("patterns"):
                recent_patterns = context.knowledge_context["patterns"]
                for pattern in recent_patterns[-2:]:  # Last 2 patterns
                    if pattern.get("pattern_type") == "recurring_symptom":
                        symptom_note = f" Se algum sintoma estiver incomodando, não hesite em me contar."
                        if symptom_note not in base_template:
                            base_template += symptom_note
                        break

            return {
                "content": base_template,
                "personalization_level": "high" if len(base_template) > 150 else "standard",
                "generated_at": datetime.utcnow().isoformat(),
                "source": "legacy"
            }

        except Exception as e:
            self.logger.error(f"Error generating legacy message: {e}")
            return None

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
