"""
Message Composer Module

Core message composition logic including AI-based generation and personalization.
"""

from typing import Dict, Any, Optional

from app.agents.communication.utils import clean_message_content
from app.ai.client import GeminiClient
from app.models.patient import Patient
from app.services.ai.guardrails import OutputKind
from app.services.ai.output_profiles import MESSAGE_HUMANIZED, MESSAGE_STANDARD
from app.services.template_loader_pkg import MessageTemplate
from app.utils.logging import get_logger
from app.utils.thread_ids import sanitize_thread_component

# Shared AI output rules appended to all composition prompts
_OUTPUT_RULES = """
Regras de saida (obrigatorio):
- Retorne apenas o texto final
- Gere apenas UMA mensagem para este envio
- Se precisar fazer pergunta, faca no maximo UMA
- Nao antecipe mensagens futuras nem mencione sequencia
- Nao inclua explicacoes, raciocinios ou meta-comentarios
- Nao mencione prompt, instrucoes, politicas ou sistema
- Nao use markdown, listas, cabecalhos ou blocos de codigo
- Nao envolva a resposta em aspas
- Escreva apenas em portugues do Brasil
""".strip()


class MessageComposer:
    """Core message composition functionality."""

    def __init__(self, gemini_client: GeminiClient, max_message_length: int = 1000):
        """Initialize message composer."""
        self.gemini_client = gemini_client
        self.max_message_length = max_message_length
        self.logger = get_logger("message_composer.composer")

    async def generate_contextual_message(
        self, message_type: str, patient: Patient, context: Dict[str, Any]
    ) -> str:
        """Generate contextual message using AI."""
        try:
            # Build AI prompt
            prompt = f"""
            Compose uma mensagem personalizada e empatica para uma paciente de oncologia.

            Informacoes da paciente:
            - Nome: {patient.name}
            - Tipo de tratamento: {context["patient"].get("treatment_type", "terapia hormonal")}
            - Dias desde inicio: {context["patient"].get("days_since_enrollment", 0)}
            - Fase do tratamento: {context["patient"].get("treatment_phase", "inicial")}

            Tipo de mensagem: {message_type}

            Contexto emocional: {context.get("emotional_context", {})}

            Preferencias de comunicacao: {context.get("communication_preferences", {})}

            Historico recente: {context.get("conversation_history", [])}

            Contexto de tempo: {context.get("time_context", {})}

            Diretrizes:
            1. Use tom acolhedor e empatico
            2. Personalize com o nome da paciente
            3. Considere o contexto emocional atual
            4. Mantenha entre 100-300 caracteres
            5. Use emojis apropriados mas moderadamente
            6. Evite linguagem medica tecnica
            7. Seja positiva mas realista

            {_OUTPUT_RULES}
            """

            # Call generate_content directly — no LangGraph intermediary (Phase 8 AI-03)
            message_content = await self.gemini_client.generate_content(
                prompt,
                output_kind=OutputKind.MESSAGE,
                profile=MESSAGE_STANDARD,
            )

            # Clean and validate message
            if not message_content:
                raise ValueError("AI returned empty message")

            message_content = clean_message_content(message_content)
            if len(message_content) > self.max_message_length:
                message_content = message_content[: self.max_message_length - 3] + "..."

            return message_content

        except Exception as e:
            self.logger.error(f"AI message generation failed: {e}")
            raise

    async def personalize_custom_content(
        self,
        content: str,
        patient: Patient,
        context: Dict[str, Any],
        personalization_level: str = "high",
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
                Personalize este conteudo para a paciente:

                Conteudo: "{personalized}"
                Paciente: {patient.name}
                Contexto: {context}

                Mantenha o sentido mas torne mais pessoal e empatico.
                {_OUTPUT_RULES}
                """

                # Call generate_content directly — no LangGraph intermediary (Phase 8 AI-03)
                ai_personalized = await self.gemini_client.generate_content(
                    personalization_prompt,
                    output_kind=OutputKind.MESSAGE,
                    profile=MESSAGE_STANDARD,
                )
                if not ai_personalized:
                    raise ValueError("AI returned empty personalized content")
                personalized = clean_message_content(ai_personalized)

            return personalized

        except Exception as e:
            self.logger.error(f"Content personalization failed: {e}")
            raise

    async def personalize_template(
        self,
        template: str,
        patient: Patient,
        context: Dict[str, Any],
        personalization_level: str = "high",
    ) -> str:
        """Personalize message template with patient context."""
        try:
            # Apply basic template substitutions
            personalized_content = template.format(name=patient.name, **context)

            # Apply AI-enhanced personalization
            if personalization_level == "high":
                enhanced_prompt = f"""
                Personalize esta mensagem para a paciente considerando seu contexto:

                Mensagem original: "{personalized_content}"

                Contexto da paciente: {context}

                Mantenha o sentido original mas torne mais pessoal e empatica.
                {_OUTPUT_RULES}
                """

                # Call generate_content directly — no LangGraph intermediary (Phase 8 AI-03)
                enhanced_content = await self.gemini_client.generate_content(
                    enhanced_prompt,
                    output_kind=OutputKind.MESSAGE,
                    profile=MESSAGE_STANDARD,
                )
                if not enhanced_content:
                    raise ValueError("AI returned empty enhanced content")
                personalized_content = clean_message_content(enhanced_content)

            return personalized_content

        except Exception as e:
            self.logger.error(f"Template personalization failed: {e}")
            raise

    async def compose_follow_up(
        self,
        patient: Patient,
        previous_interaction: Dict[str, Any],
        follow_up_reason: str,
        interaction_analysis: Dict[str, Any],
    ) -> str:
        """Compose intelligent follow-up message."""
        try:
            # Generate appropriate follow-up
            follow_up_prompt = f"""
            Compose uma mensagem de follow-up apropriada:

            Paciente: {patient.name}
            Interacao anterior: {previous_interaction}
            Analise da interacao: {interaction_analysis}
            Motivo do follow-up: {follow_up_reason}

            A mensagem deve:
            1. Referenciar sutilmente a conversa anterior
            2. Mostrar que voce prestou atencao as preocupacoes
            3. Ser empatica e de apoio
            4. Oferecer ajuda adicional se necessario

            {_OUTPUT_RULES}
            """

            # Call generate_content directly — no LangGraph intermediary (Phase 8 AI-03)
            follow_up_content = await self.gemini_client.generate_content(
                follow_up_prompt,
                output_kind=OutputKind.MESSAGE,
                profile=MESSAGE_STANDARD,
            )
            if not follow_up_content:
                raise ValueError("AI returned empty follow-up")

            return clean_message_content(follow_up_content)

        except Exception as e:
            self.logger.error(f"Follow-up composition failed: {e}")
            raise

    async def generate_quiz_message(
        self,
        patient: Patient,
        quiz_context: Dict[str, Any],
        question_data: Dict[str, Any],
    ) -> str:
        """Generate personalized quiz message."""
        try:
            question_text = question_data.get("text", "")
            question_type = question_data.get("type", "open_text")
            options = question_data.get("options", [])

            # Generate contextual quiz introduction
            quiz_prompt = f"""
            Crie uma introducao personalizada para uma pergunta de quiz medico:

            Paciente: {patient.name}
            Contexto do tratamento: {quiz_context}

            Pergunta: "{question_text}"
            Tipo: {question_type}
            Opcoes: {options}

            A introducao deve:
            1. Ser calorosa e acolhedora
            2. Contextualizar a importancia da pergunta
            3. Encorajar honestidade na resposta
            4. Nao ser muito longa

            Formato: [Introducao] + [Pergunta] + [Opcoes se necessario]

            {_OUTPUT_RULES}
            """

            # Call generate_content directly — no LangGraph intermediary (Phase 8 AI-03)
            quiz_message = await self.gemini_client.generate_content(
                quiz_prompt,
                output_kind=OutputKind.MESSAGE,
                profile=MESSAGE_STANDARD,
            )
            if not quiz_message:
                raise ValueError("AI returned empty quiz message")

            return clean_message_content(quiz_message)

        except Exception as e:
            self.logger.error(f"Quiz message generation failed: {e}")
            raise

    async def compose_from_flow_template(
        self, template: MessageTemplate, patient: Patient, context: Dict[str, Any]
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
                "core_elements": template.core_elements,
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
            raise

    async def _compose_with_ai_instructions(
        self, template: MessageTemplate, context: Dict[str, Any]
    ) -> str:
        """Compose message using AI instructions from template."""
        try:
            from app.ai.langgraph.nodes_ai import _coerce_recent_interactions, _replace_patient_name
            from app.ai.langgraph.prompts import build_humanization_prompt

            patient_name = context.get("patient_name", "")
            recent_interactions = _coerce_recent_interactions(
                context.get("recent_interactions"),
                fallback_history=context.get("conversation_history", []),
            )
            template_text = _replace_patient_name(template.base_content, patient_name)
            prompt = build_humanization_prompt(
                template=template_text,
                ai_instructions=template.ai_instructions,
                recent_interactions=recent_interactions,
            )
            # Call generate_content directly — no LangGraph intermediary (Phase 8 AI-03)
            composed_message = await self.gemini_client.generate_content(
                prompt,
                profile=MESSAGE_HUMANIZED,
            )

            if not composed_message:
                raise ValueError("AI returned empty composed message")

            return clean_message_content(composed_message)

        except Exception as e:
            self.logger.error(f"AI composition failed: {e}")
            raise

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

    def _build_thread_id(
        self,
        scope: str,
        *,
        patient: Optional[Patient] = None,
        context: Optional[Dict[str, Any]] = None,
        detail: Optional[Any] = None,
    ) -> str:
        """Build deterministic thread_id for LangGraph invocations."""
        context_data = context or {}
        patient_key = (
            getattr(patient, "id", None)
            or context_data.get("patient_id")
            or context_data.get("id")
            or "unknown_patient"
        )
        context_key = (
            context_data.get("session_id")
            or context_data.get("quiz_session_id")
            or context_data.get("question_id")
            or context_data.get("message_id")
            or context_data.get("current_day")
            or detail
            or "default"
        )

        return (
            f"composer:{sanitize_thread_component(scope)}:"
            f"patient:{sanitize_thread_component(patient_key)}:"
            f"context:{sanitize_thread_component(context_key)}"
        )
