"""
Message Composer Module

Core message composition logic including AI-based generation and personalization.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from app.integrations.gemini_client import GeminiClient
from app.models.patient import Patient
from app.services.template_loader import MessageTemplate
from app.utils.logging import get_logger


class MessageComposer:
    """Core message composition functionality."""

    def __init__(self, gemini_client: GeminiClient, max_message_length: int = 1000):
        """Initialize message composer."""
        self.gemini_client = gemini_client
        self.max_message_length = max_message_length
        self.logger = get_logger("message_composer.composer")

    async def generate_contextual_message(
        self,
        message_type: str,
        patient: Patient,
        context: Dict[str, Any]
    ) -> str:
        """Generate contextual message using AI."""
        try:
            # Build AI prompt
            prompt = f"""
            Compose uma mensagem personalizada e empática para uma paciente de oncologia.

            Informações da paciente:
            - Nome: {patient.name}
            - Tipo de tratamento: {context['patient'].get('treatment_type', 'terapia hormonal')}
            - Dias desde início: {context['patient'].get('days_since_enrollment', 0)}
            - Fase do tratamento: {context['patient'].get('treatment_phase', 'inicial')}

            Tipo de mensagem: {message_type}

            Contexto emocional: {context.get('emotional_context', {})}

            Preferências de comunicação: {context.get('communication_preferences', {})}

            Histórico recente: {context.get('conversation_history', [])}

            Contexto de tempo: {context.get('time_context', {})}

            Diretrizes:
            1. Use tom acolhedor e empático
            2. Personalize com o nome da paciente
            3. Considere o contexto emocional atual
            4. Mantenha entre 100-300 caracteres
            5. Use emojis apropriados mas moderadamente
            6. Evite linguagem médica técnica
            7. Seja positiva mas realista

            Retorne apenas o texto da mensagem, sem explicações adicionais.
            """

            message_content = await self.gemini_client.generate_content(prompt)

            # Clean and validate message
            if message_content:
                message_content = self._clean_message_content(message_content)
                if len(message_content) > self.max_message_length:
                    message_content = message_content[:self.max_message_length - 3] + "..."

                return message_content
            else:
                return ""

        except Exception as e:
            self.logger.error(f"AI message generation failed: {e}")
            return ""

    async def personalize_custom_content(
        self,
        content: str,
        patient: Patient,
        context: Dict[str, Any],
        personalization_level: str = "high"
    ) -> str:
        """Personalize custom content with patient context."""
        try:
            # Get patient name as string (SQLAlchemy ORM handles Column[str] to str conversion)
            patient_name: str = patient.name  # type: ignore[assignment]

            # Basic substitutions
            personalized = content.replace("{name}", patient_name)
            personalized = personalized.replace("{patient_name}", patient_name)

            # Add AI personalization if enabled
            if personalization_level == "high":
                personalization_prompt = f"""
                Personalize este conteúdo para a paciente:

                Conteúdo: "{personalized}"
                Paciente: {patient.name}
                Contexto: {context}

                Mantenha o sentido mas torne mais pessoal e empático.
                Retorne apenas o conteúdo personalizado.
                """

                ai_personalized = await self.gemini_client.generate_content(personalization_prompt)
                if ai_personalized:
                    personalized = self._clean_message_content(ai_personalized)

            return personalized

        except Exception as e:
            self.logger.error(f"Content personalization failed: {e}")
            return content.replace("{name}", str(patient.name))

    async def personalize_template(
        self,
        template: str,
        patient: Patient,
        context: Dict[str, Any],
        personalization_level: str = "high"
    ) -> str:
        """Personalize message template with patient context."""
        try:
            # Apply basic template substitutions
            personalized_content = template.format(
                name=patient.name,
                **context
            )

            # Apply AI-enhanced personalization
            if personalization_level == "high":
                enhanced_prompt = f"""
                Personalize esta mensagem para a paciente considerando seu contexto:

                Mensagem original: "{personalized_content}"

                Contexto da paciente: {context}

                Mantenha o sentido original mas torne mais pessoal e empática.
                Retorne apenas a mensagem personalizada.
                """

                enhanced_content = await self.gemini_client.generate_content(enhanced_prompt)
                if enhanced_content:
                    personalized_content = self._clean_message_content(enhanced_content)

            return personalized_content

        except Exception as e:
            self.logger.error(f"Template personalization failed: {e}")
            return template.format(name=patient.name, **context)

    async def compose_follow_up(
        self,
        patient: Patient,
        previous_interaction: Dict[str, Any],
        follow_up_reason: str,
        interaction_analysis: Dict[str, Any]
    ) -> str:
        """Compose intelligent follow-up message."""
        try:
            # Generate appropriate follow-up
            follow_up_prompt = f"""
            Compose uma mensagem de follow-up apropriada:

            Paciente: {patient.name}
            Interação anterior: {previous_interaction}
            Análise da interação: {interaction_analysis}
            Motivo do follow-up: {follow_up_reason}

            A mensagem deve:
            1. Referenciar sutilmente a conversa anterior
            2. Mostrar que você prestou atenção às preocupações
            3. Ser empática e de apoio
            4. Oferecer ajuda adicional se necessário

            Retorne apenas a mensagem de follow-up.
            """

            follow_up_content = await self.gemini_client.generate_content(follow_up_prompt)

            if not follow_up_content:
                follow_up_content = f"Oi {patient.name}! Como você está se sentindo após nossa conversa? Estou aqui se precisar de algo. 💙"

            return self._clean_message_content(follow_up_content)

        except Exception as e:
            self.logger.error(f"Follow-up composition failed: {e}")
            return f"Oi {patient.name}! Como você está se sentindo após nossa conversa? Estou aqui se precisar de algo. 💙"

    async def generate_quiz_message(
        self,
        patient: Patient,
        quiz_context: Dict[str, Any],
        question_data: Dict[str, Any]
    ) -> str:
        """Generate personalized quiz message."""
        try:
            question_text = question_data.get("text", "")
            question_type = question_data.get("type", "open_text")
            options = question_data.get("options", [])

            # Generate contextual quiz introduction
            quiz_prompt = f"""
            Crie uma introdução personalizada para uma pergunta de quiz médico:

            Paciente: {patient.name}
            Contexto do tratamento: {quiz_context}

            Pergunta: "{question_text}"
            Tipo: {question_type}
            Opções: {options}

            A introdução deve:
            1. Ser calorosa e acolhedora
            2. Contextualizar a importância da pergunta
            3. Encorajar honestidade na resposta
            4. Não ser muito longa

            Formato: [Introdução] + [Pergunta] + [Opções se necessário]
            """

            quiz_message = await self.gemini_client.generate_content(quiz_prompt)

            if not quiz_message:
                # Fallback quiz message
                quiz_message = f"Olá {patient.name}! Vamos fazer uma pergunta importante para acompanhar seu bem-estar:\n\n{question_text}"

                if options:
                    quiz_message += "\n\nOpções:\n" + "\n".join([f"• {opt}" for opt in options])

            return self._clean_message_content(quiz_message)

        except Exception as e:
            self.logger.error(f"Quiz message generation failed: {e}")
            return f"Olá {patient.name}! Vamos fazer uma pergunta importante para acompanhar seu bem-estar:\n\n{question_data.get('text', '')}"

    async def compose_from_flow_template(
        self,
        template: MessageTemplate,
        patient: Patient,
        context: Dict[str, Any]
    ) -> str:
        """Compose message from flow template."""
        try:
            # Prepare personalization context
            personalization_context = {
                "patient_name": patient.name,
                "current_day": context.get("current_day", 1),
                "mood_trend": context.get("mood_indicators", {}).get("trend", 0),
                "engagement_level": context.get("engagement_score", 0.5),
                "stress_level": context.get("stress_level", 0.0),
                "personalization_hints": template.personalization_hints,
                "core_elements": template.core_elements
            }

            # Use AI instructions if available
            if template.ai_instructions and self.gemini_client:
                composed_message = await self._compose_with_ai_instructions(
                    template, personalization_context
                )
            else:
                # Basic personalization
                composed_message = self._apply_basic_template_personalization(
                    template, personalization_context
                )

            return composed_message

        except Exception as e:
            self.logger.error(f"Failed to compose from flow template: {e}")
            return ""

    async def _compose_with_ai_instructions(
        self, template: MessageTemplate, context: Dict[str, Any]
    ) -> str:
        """Compose message using AI instructions from template."""
        try:
            # Prepare AI prompt using template instructions
            ai_prompt = f"""
            {template.ai_instructions}

            Contexto do paciente:
            - Nome: {context['patient_name']}
            - Dia do tratamento: {context['current_day']}
            - Tendência de humor: {context['mood_trend']}
            - Nível de engajamento: {context['engagement_level']}
            - Nível de stress: {context['stress_level']}

            Dicas de personalização: {', '.join(context['personalization_hints'])}
            Elementos essenciais: {context['core_elements']}

            Conteúdo base: {template.base_content}

            Gere uma mensagem personalizada seguindo as instruções acima.
            Mantenha o tom apropriado para o contexto médico e de apoio.
            """

            response = await self.gemini_client.generate_content(ai_prompt)

            if response and hasattr(response, 'text'):
                return self._clean_message_content(response.text)

            # Fallback to basic personalization
            return self._apply_basic_template_personalization(template, context)

        except Exception as e:
            self.logger.error(f"AI composition failed: {e}")
            return self._apply_basic_template_personalization(template, context)

    def _apply_basic_template_personalization(
        self, template: MessageTemplate, context: Dict[str, Any]
    ) -> str:
        """Apply basic personalization to template."""
        content = template.base_content

        # Replace patient name placeholders
        content = content.replace("{patient_name}", context["patient_name"])
        content = content.replace("{name}", context["patient_name"])

        # Add mood-based personalization
        mood_trend = context.get("mood_trend", 0)
        if mood_trend < -0.5:
            content += " Estou aqui para te apoiar neste momento. 💜"
        elif mood_trend > 0.5:
            content += " Fico feliz em saber que você está bem! 😊"

        # Add engagement-based elements
        engagement = context.get("engagement_level", 0.5)
        if engagement < 0.3:
            content += " Lembre-se que pode me procurar sempre que precisar."

        return content

    def _clean_message_content(self, content: str) -> str:
        """Clean and validate message content."""
        if not content:
            return ""

        # Remove extra whitespace
        content = content.strip()

        # Remove quotes if AI returned quoted text
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]

        # Ensure reasonable length
        if len(content) > self.max_message_length:
            content = content[:self.max_message_length - 3] + "..."

        return content
