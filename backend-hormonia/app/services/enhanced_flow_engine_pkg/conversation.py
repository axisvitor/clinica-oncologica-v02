from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.models.message import Message, MessageDirection
from app.services.flow.flags import message_expects_response
from app.utils.db_retry import with_db_retry
from app.utils.text import clip_text
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class FlowConversationMixin:
    """Conversation-memory and health-check behavior for EnhancedFlowEngine."""

    @with_db_retry(max_retries=3)
    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on FlowEngine components.
        Extends FlowCore health check with AI-specific components.

        Returns:
            Health check results
        """
        results = await super().health_check()

        results["service"] = "EnhancedFlowEngine"
        results["gemini_client"] = False
        results["conversation_memory"] = False

        try:
            results["gemini_client"] = await self.gemini_client.health_check()
        except Exception as e:
            logger.error(f"Gemini client health check failed: {e}")
            results["gemini_client"] = False

        try:
            results["conversation_memory"] = await self.conversation_memory.health_check()
        except Exception as e:
            logger.error(f"Conversation memory health check failed: {e}")
            results["conversation_memory"] = False

        results["overall_healthy"] = all(
            [
                results["flow_core"],
                results["database"],
                results["template_cache"],
                results["gemini_client"],
                results["conversation_memory"],
            ]
        )

        return results

    @with_db_retry(max_retries=3)
    async def _get_conversation_history(
        self, patient_id: UUID, limit: int = 10
    ) -> list[str]:
        """
        Get recent conversation history for patient.

        Retrieves the most recent messages between the clinic and patient,
        formatted for AI context. Messages are ordered newest-first but
        returned in chronological order (oldest-first) for natural context.

        Args:
            patient_id: UUID of the patient
            limit: Maximum number of messages to retrieve (default 10)

        Returns:
            List of formatted message strings.
        """
        try:
            result = await self._execute(
                select(Message)
                .filter(
                    Message.patient_id == patient_id,
                    Message.content.isnot(None),
                    Message.content != "",
                )
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            messages = result.scalars().all()

            if not messages:
                logger.debug(f"No conversation history found for patient {patient_id}")
                return []

            formatted_history = []
            for msg in reversed(messages):
                if msg.direction == MessageDirection.INBOUND:
                    prefix = "Paciente"
                else:
                    prefix = "Clínica"

                content = msg.content[:500] if len(msg.content) > 500 else msg.content
                formatted_history.append(f"{prefix}: {content}")

            logger.debug(
                f"Retrieved {len(formatted_history)} messages for patient {patient_id}"
            )
            return formatted_history

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to get conversation history for {patient_id}: {e}")
            return []

    @with_db_retry(max_retries=3)
    async def _get_recent_interactions(
        self,
        patient_id: UUID,
        *,
        interaction_limit: int = 2,
        scan_limit: int = 40,
    ) -> list[dict[str, Any]]:
        """
        Get the most recent question/answer interactions for the patient.

        Interactions are derived from outbound flow messages that expect a response
        and the subsequent inbound reply(ies). Returns the last N completed pairs.
        """
        try:
            result = await self._execute(
                select(Message)
                .filter(
                    Message.patient_id == patient_id,
                    Message.content.isnot(None),
                    Message.content != "",
                )
                .order_by(Message.created_at.desc())
                .limit(scan_limit)
            )
            messages = result.scalars().all()
            if not messages:
                return []

            def _build_interaction(
                question_msg: Message, response_msgs: list[Message]
            ) -> dict[str, Any]:
                metadata = question_msg.message_metadata or {}
                answered_at = response_msgs[-1].created_at if response_msgs else None
                response_texts = [msg.content for msg in response_msgs if msg.content]
                response_text = "\n".join(response_texts).strip()
                return {
                    "question": clip_text(question_msg.content or "", max_len=360, ellipsis="…"),
                    "answer": clip_text(response_text, max_len=360, ellipsis="…"),
                    "flow_kind": metadata.get("flow_kind"),
                    "flow_day": metadata.get("flow_day"),
                    "message_index": metadata.get("message_index"),
                    "asked_at": (question_msg.sent_at or question_msg.created_at).isoformat()
                    if (question_msg.sent_at or question_msg.created_at)
                    else None,
                    "answered_at": answered_at.isoformat() if answered_at else None,
                }

            interactions: list[dict[str, Any]] = []
            current_question: Message | None = None
            current_responses: list[Message] = []

            for msg in reversed(messages):
                if msg.direction == MessageDirection.OUTBOUND and message_expects_response(msg):
                    if current_question and current_responses:
                        interactions.append(
                            _build_interaction(current_question, current_responses)
                        )
                    current_question = msg
                    current_responses = []
                    continue

                if msg.direction == MessageDirection.INBOUND and current_question:
                    current_responses.append(msg)

            if current_question and current_responses:
                interactions.append(
                    _build_interaction(current_question, current_responses)
                )

            if not interactions:
                return []

            return interactions[-interaction_limit:]

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Failed to get recent interactions for %s: %s", patient_id, e)
            return []

    def _tone_for_time_of_day(self) -> str:
        """Derive a gentle tone based on time of day to help variation."""
        hour = now_sao_paulo().hour
        if hour < 12:
            return "cheerful"
        if hour < 18:
            return "friendly"
        return "calm"


__all__ = ["FlowConversationMixin"]
