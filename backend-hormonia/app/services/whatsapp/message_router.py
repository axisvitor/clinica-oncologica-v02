"""
Routing module for WhatsApp messages.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class MessageRouter:
    """
    Handles routing logic for incoming WhatsApp messages.
    Decides the target service based on message content and user context.
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client

    def extract_message_text(self, message: Dict[str, Any]) -> str:
        """
        Extract text content from WhatsApp message.

        Handles different message types (text, buttons, lists, etc).

        Args:
            message: WhatsApp message object

        Returns:
            Extracted text content
        """
        # Text message
        if "text" in message:
            return message["text"].get("body", "")

        # Button response
        if "button" in message:
            return message["button"].get("text", "")

        # List response
        if "list" in message:
            return message["list"].get("title", "")

        # Interactive response
        if "interactive" in message:
            interactive = message["interactive"]
            if "button_reply" in interactive:
                return interactive["button_reply"].get("title", "")
            if "list_reply" in interactive:
                return interactive["list_reply"].get("title", "")

        return ""

    async def determine_routing_target(
        self,
        phone_number: str,
        message_text: str
    ) -> str:
        """
        Determine where to route the message.

        Uses pattern matching and context to decide routing.

        Args:
            phone_number: Sender phone number
            message_text: Message text content

        Returns:
            Routing target: "quiz", "flow", "support", or "general"
        """
        # Check for quiz keywords
        quiz_keywords = ["questionário", "quiz", "responder", "sintomas"]
        if any(keyword in message_text.lower() for keyword in quiz_keywords):
            return "quiz"

        # Check for flow keywords
        flow_keywords = ["jornada", "consulta", "agendar", "medicação"]
        if any(keyword in message_text.lower() for keyword in flow_keywords):
            return "flow"

        # Check for support keywords
        support_keywords = ["ajuda", "suporte", "dúvida", "problema", "urgente"]
        if any(keyword in message_text.lower() for keyword in support_keywords):
            return "support"

        # Check if user has active quiz session
        if self.redis:
            try:
                active_quiz = await self.redis.get(f"quiz:active:{phone_number}")
                if active_quiz:
                    return "quiz"

                active_flow = await self.redis.get(f"flow:active:{phone_number}")
                if active_flow:
                    return "flow"
            except Exception as e:
                logger.warning(f"Failed to check active sessions: {e}")

        # Default to general handler
        return "general"
