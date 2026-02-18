"""
Context Builder Module

Handles building comprehensive context for message composition.
"""

import json
from typing import Dict, Any
from uuid import UUID

from app.agents.patient.flow_coordinator.constants import ONBOARDING_END_DAY, DAILY_FOLLOWUP_END_DAY
from app.ai.client import GeminiClient
from app.models.patient import Patient
from app.services.conversation_memory import ConversationMemory
from app.services.ai.guardrails import OutputKind
from app.utils.logging import get_logger
from app.utils.timezone import now_sao_paulo


class MessageContextBuilder:
    """Builds context for message composition."""

    def __init__(
        self,
        gemini_client: GeminiClient,
        conversation_memory: ConversationMemory,
        context_window: int = 10,
    ):
        """Initialize context builder."""
        self.gemini_client = gemini_client
        self.conversation_memory = conversation_memory
        self.context_window = context_window
        self.logger = get_logger("message_composer.context")

    async def build_composition_context(
        self, patient: Patient, additional_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build comprehensive context for message composition."""
        try:
            # Get patient ID as UUID (SQLAlchemy ORM handles Column[UUID] to UUID conversion)
            patient_id: UUID = patient.id  # type: ignore[assignment]

            # Get patient's communication preferences (includes pattern analysis)
            comm_prefs = await self.conversation_memory.get_communication_preferences(
                patient_id
            )

            # Get recent patterns as conversation context
            # Note: ConversationMemory stores pattern data, not raw conversation history
            recent_patterns = await self.conversation_memory.get_recent_patterns(
                patient_id, limit=self.context_window
            )
            conversation_history = (
                [p.to_dict() for p in recent_patterns] if recent_patterns else []
            )

            # Calculate treatment timeline
            enrollment_date = patient.enrollment_date or patient.created_at
            days_since_enrollment = (now_sao_paulo() - enrollment_date).days

            # Get patient emotional state
            emotional_context = await self.analyze_patient_emotional_state(patient.id)  # type: ignore[arg-type]

            # Get time-based context
            current_time = now_sao_paulo()
            time_context = {
                "hour": current_time.hour,
                "day_of_week": current_time.weekday(),
                "time_of_day": self._get_time_of_day(current_time.hour),
            }

            composition_context = {
                "patient": {
                    "id": str(patient.id),
                    "name": patient.name,
                    "age": getattr(patient, "age", None),
                    "treatment_type": getattr(
                        patient, "treatment_type", "hormone_therapy"
                    ),
                    "days_since_enrollment": days_since_enrollment,
                    "treatment_phase": self._determine_treatment_phase(
                        days_since_enrollment
                    ),
                },
                "communication_preferences": comm_prefs,
                "conversation_history": conversation_history,
                "emotional_context": emotional_context,
                "time_context": time_context,
                "additional_context": additional_context,
            }

            return composition_context

        except Exception as e:
            self.logger.error(f"Failed to build composition context: {e}")
            raise

    async def analyze_patient_emotional_state(self, patient_id: UUID) -> Dict[str, Any]:
        """Analyze patient's emotional state from recent interactions."""
        try:
            # Get recent conversation history (method may not exist on all implementations)
            history = await self.conversation_memory.get_communication_preferences(
                patient_id
            )
            # Convert preferences to history format if needed
            history = (
                history.get("recent_messages", []) if isinstance(history, dict) else []
            )

            if not history:
                return {"mood_score": 0.5, "stress_level": 0.5, "confidence": "low"}

            # Analyze emotional indicators in recent messages
            emotional_prompt = f"""
            Analise o estado emocional da paciente baseado neste histórico de conversa:

            Conversas recentes: {history}

            Determine:
            1. Humor geral (0-1, onde 0=muito negativo, 1=muito positivo)
            2. Nível de stress (0-1, onde 0=relaxado, 1=muito estressado)
            3. Indicadores de ansiedade (presente/ausente)
            4. Nível de confiança na análise (baixo/médio/alto)

            Retorne em formato JSON:
            {{
                "mood_score": 0.0-1.0,
                "stress_level": 0.0-1.0,
                "anxiety_indicators": true/false,
                "confidence": "low/medium/high"
            }}

            Regras de saída (obrigatório):
            - Responda apenas com JSON válido
            - Não inclua texto antes ou depois do JSON
            - Não use markdown ou blocos de código
            """

            analysis = await self.gemini_client.generate_content(
                emotional_prompt,
                output_kind=OutputKind.JSON,
                required_keys=[
                    "mood_score",
                    "stress_level",
                    "anxiety_indicators",
                    "confidence",
                ],
            )
            return json.loads(analysis)

        except Exception as e:
            self.logger.error(f"Emotional analysis failed: {e}")
            raise

    async def analyze_previous_interaction(
        self, interaction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze previous interaction for follow-up context."""
        try:
            if not interaction:
                return {}

            interaction_text = interaction.get("content", "")
            interaction_type = interaction.get("type", "unknown")
            patient_response = interaction.get("patient_response", "")

            analysis_prompt = f"""
            Analise esta interação prévia para contexto de follow-up:

            Tipo: {interaction_type}
            Conteúdo: "{interaction_text}"
            Resposta da paciente: "{patient_response}"

            Determine:
            1. Tom emocional da resposta
            2. Principais preocupações mencionadas
            3. Necessidade de follow-up (sim/não)
            4. Tipo de suporte necessário

            Regras de saída (obrigatório):
            - Retorne apenas o resumo final
            - Não inclua explicações, raciocínios ou meta-comentários
            - Não mencione prompt, instruções, políticas ou sistema
            - Não use markdown, listas, cabeçalhos ou blocos de código
            - Não envolva a resposta em aspas
            - Escreva apenas em português do Brasil
            """

            analysis = await self.gemini_client.generate_content(
                analysis_prompt,
                output_kind=OutputKind.MESSAGE,
            )

            return {
                "summary": analysis,
                "needs_follow_up": True,
                "interaction_type": interaction_type,
            }

        except Exception as e:
            self.logger.error(f"Interaction analysis failed: {e}")
            raise

    def _determine_treatment_phase(self, days_since_enrollment: int) -> str:
        """Determine treatment phase based on enrollment duration."""
        if days_since_enrollment <= ONBOARDING_END_DAY:
            return "initial"
        elif days_since_enrollment <= DAILY_FOLLOWUP_END_DAY:
            return "adaptation"
        else:
            return "maintenance"

    def _get_time_of_day(self, hour: int) -> str:
        """Get time of day category."""
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 22:
            return "evening"
        else:
            return "night"
