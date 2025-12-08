"""
Tone Adaptation Module

Handles adaptive tone adjustment for messages based on patient context.
"""

from typing import Dict, Any

from app.integrations.gemini_client import GeminiClient
from app.utils.logging import get_logger


class MessageToneAdapter:
    """Adapts message tone based on patient emotional state."""

    def __init__(self, gemini_client: GeminiClient):
        """Initialize tone adapter."""
        self.gemini_client = gemini_client
        self.logger = get_logger("message_composer.tone")

    async def adapt_message_tone(self, payload: Dict[str, Any]) -> str:
        """Adapt message tone based on patient context."""
        try:
            content = payload.get("content", "")
            patient_context = payload.get("patient_context", {})
            target_tone = payload.get("target_tone", "supportive")

            if not content:
                return content

            # Analyze current emotional state
            emotional_context = patient_context.get("emotional_context", {})
            mood_score = emotional_context.get("mood_score", 0.5)
            stress_level = emotional_context.get("stress_level", 0.5)

            # Determine appropriate tone adaptation
            target_tone = self._determine_appropriate_tone(mood_score, stress_level, target_tone)

            # Apply tone adaptation with AI
            adapted_content = await self._apply_ai_tone_adaptation(
                content, target_tone, mood_score, stress_level
            )

            return adapted_content if adapted_content else content

        except Exception as e:
            self.logger.error(f"Tone adaptation failed: {e}")
            return payload.get("content", "")

    def _determine_appropriate_tone(
        self,
        mood_score: float,
        stress_level: float,
        default_tone: str
    ) -> str:
        """Determine appropriate tone based on emotional indicators."""
        if mood_score < 0.3 or stress_level > 0.7:
            # Patient seems distressed - use gentle, supportive tone
            return "gentle_supportive"
        elif mood_score > 0.7:
            # Patient seems positive - use encouraging tone
            return "encouraging"
        else:
            return default_tone

    async def _apply_ai_tone_adaptation(
        self,
        content: str,
        target_tone: str,
        mood_score: float,
        stress_level: float
    ) -> str:
        """Apply tone adaptation using AI."""
        try:
            tone_prompt = f"""
            Adapte o tom desta mensagem para ser mais {target_tone}:

            Mensagem original: "{content}"

            Contexto emocional da paciente:
            - Humor: {mood_score} (0-1 scale)
            - Stress: {stress_level} (0-1 scale)

            Tom desejado: {target_tone}

            Mantenha o conteúdo principal mas ajuste o tom e as palavras.
            Retorne apenas a mensagem adaptada.
            """

            adapted_content = await self.gemini_client.generate_content(tone_prompt)

            if adapted_content:
                return self._clean_message_content(adapted_content)
            else:
                return content

        except Exception as e:
            self.logger.error(f"AI tone adaptation failed: {e}")
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

        return content
