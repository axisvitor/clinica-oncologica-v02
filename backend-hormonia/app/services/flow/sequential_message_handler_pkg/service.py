import logging
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.flow import FlowStateRepository
from app.repositories.message import MessageRepository

from .personalization import PersonalizationMixin
from .quiz import QuizMixin
from .sequencing import SequencingMixin
from .state import StateMixin

if TYPE_CHECKING:
    from app.services.enhanced_flow_engine import EnhancedFlowEngine

logger = logging.getLogger(__name__)


class SequentialMessageHandler(
    SequencingMixin,
    StateMixin,
    PersonalizationMixin,
    QuizMixin,
):
    """
    Orchestrates sequential message sending within a day.

    Tracks which message the patient is on via patient_flow_states.step_data:
    {
        "current_day_message_index": 0,
        "day_messages_completed": [0, 1, 2],
        "awaiting_response": true
    }
    """

    def __init__(
        self,
        db: AsyncSession,
        use_ai_personalization: bool = True,
        use_sync_agent_bridge: bool = False,
    ):
        self.db = db
        self.flow_state_repo = FlowStateRepository(db)
        self.message_repo = MessageRepository(db)
        from app.services.unified_whatsapp_service import UnifiedWhatsAppService

        self.whatsapp_service = UnifiedWhatsAppService(db)
        self.use_ai_personalization = use_ai_personalization
        self.use_sync_agent_bridge = use_sync_agent_bridge
        self._enhanced_flow_engine: Optional["EnhancedFlowEngine"] = None

    async def handle_response_and_continue(
        self,
        patient_id: UUID,
        response_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Handle patient response and continue flow progression."""
        try:
            from app.services.flow._flow_functions import run_flow_response

            return await run_flow_response(
                patient_id=patient_id,
                response_context=response_context,
                handler=self,
            )
        except Exception as exc:
            logger.exception("Error handling response continuation via direct flow function")
            return {"status": "error", "message": str(exc)}

    def _build_flow_message_thread_id(
        self,
        *,
        patient_id: UUID,
        flow_kind: str,
        day_number: int,
    ) -> str:
        return f"flow_message:{patient_id}:{flow_kind}:{day_number}"

    def _build_flow_response_thread_id(self, patient_id: UUID) -> str:
        return f"flow_response:{patient_id}"


def get_sequential_message_handler(db: AsyncSession) -> SequentialMessageHandler:
    """Factory function to get handler instance."""
    return SequentialMessageHandler(db)


__all__ = ["SequentialMessageHandler", "get_sequential_message_handler"]
