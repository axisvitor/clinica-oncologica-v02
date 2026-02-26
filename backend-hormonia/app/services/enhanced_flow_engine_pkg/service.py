from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.ai.client import GeminiClient, get_gemini_client
from app.models.flow import FlowKind, FlowTemplateVersion, PatientFlowState
from app.services.conversation_memory import ConversationMemory, get_conversation_memory
from app.services.flow_core import FlowCore
from app.services.platform_synchronization import PlatformSynchronizationService
from app.services.template_loader_pkg import EnhancedTemplateLoader
from app.infrastructure.cache import UnifiedCacheManager as UnifiedCacheService

from .conversation import FlowConversationMixin
from .orchestration import FlowOrchestrationMixin
from .response_processing import FlowResponseMixin

logger = logging.getLogger(__name__)


class EnhancedFlowEngine(
    FlowOrchestrationMixin,
    FlowResponseMixin,
    FlowConversationMixin,
    FlowCore,
):
    """
    AI-powered flow execution engine.
    Inherits all shared flow operations from FlowCore.
    Focuses on AI/ML operations: message generation, response processing, conversation memory.
    """

    def __init__(
        self,
        db: Any,
        gemini_client: GeminiClient | None = None,
        conversation_memory: ConversationMemory | None = None,
        platform_sync: PlatformSynchronizationService | None = None,
        template_loader: EnhancedTemplateLoader | None = None,
        template_cache: UnifiedCacheService | None = None,
    ):
        super().__init__(db, platform_sync, template_loader, template_cache)

        self.gemini_client = gemini_client or get_gemini_client()
        self.conversation_memory = conversation_memory or get_conversation_memory()
        self._reminder_handler = None

        logger.info("Enhanced FlowEngine initialized with AI integration")

    async def _get_flow_type_from_state(self, flow_state: PatientFlowState) -> str:
        """Helper method to get flow_type from a PatientFlowState using template_version_id."""
        result = await self.db.execute(
            select(FlowTemplateVersion).filter(
                FlowTemplateVersion.id == flow_state.flow_template_version_id
            )
        )
        template_version = result.scalar_one_or_none()

        if not template_version:
            logger.error(f"Template version not found for flow state {flow_state.id}")
            return "unknown"

        result = await self.db.execute(
            select(FlowKind).filter(FlowKind.id == template_version.flow_kind_id)
        )
        flow_kind = result.scalar_one_or_none()

        if not flow_kind:
            logger.error(f"Flow kind not found for template version {template_version.id}")
            return "unknown"

        return flow_kind.flow_type

    def _get_reminder_handler(self):
        if self._reminder_handler is None:
            from app.services.reminders import ReminderHandler

            self._reminder_handler = ReminderHandler(self.db, self.gemini_client)
        return self._reminder_handler


_enhanced_flow_engine: EnhancedFlowEngine | None = None


def get_enhanced_flow_engine(db: Any) -> EnhancedFlowEngine:
    """Get enhanced flow engine instance."""
    return EnhancedFlowEngine(db)


async def test_enhanced_flow_engine() -> bool:
    """Test enhanced flow engine functionality."""
    try:
        from app.database import get_scoped_session

        with get_scoped_session() as db:
            engine = get_enhanced_flow_engine(db)

            health_status = await engine.health_check()
            logger.info(f"Enhanced flow engine health check: {health_status}")

            if not health_status["overall_healthy"]:
                logger.warning("Some components are not healthy")
                return False

            logger.info("Enhanced flow engine test completed successfully")
            return True

    except Exception as e:
        logger.error(f"Enhanced flow engine test failed: {e}")
        return False


__all__ = [
    "EnhancedFlowEngine",
    "get_enhanced_flow_engine",
    "test_enhanced_flow_engine",
]
