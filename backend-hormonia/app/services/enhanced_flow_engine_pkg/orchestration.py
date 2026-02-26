from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

import sentry_sdk
from sqlalchemy import select

from app.config import settings
from app.core.exceptions import FeatureNotAvailableError
from app.exceptions import NotFoundError
from app.models.flow import FlowKind, FlowTemplateVersion, PatientFlowState
from app.models.patient import Patient
from app.services.flow.types import FlowType, normalize_flow_type
from app.services.template_loader_pkg import MessageTemplate
from app.utils.db_retry import with_db_retry

from .context import FlowContext

logger = logging.getLogger(__name__)


class FlowOrchestrationMixin:
    """AI message-generation behavior for EnhancedFlowEngine."""

    def _get_few_shot_examples(self, intent: str) -> list[dict[str, str]]:
        """Get few-shot examples based on intent."""
        examples = {
            "greeting": [
                {
                    "input": "Olá [nome]",
                    "output": "Oi [nome], que bom falar com você! Como está se sentindo?",
                },
                {
                    "input": "Bom dia [nome]",
                    "output": "Bom dia, [nome]! Espero que seu dia esteja sendo tranquilo.",
                },
            ],
            "check_in": [
                {
                    "input": "Como você está?",
                    "output": "Me conta, como você está se sentindo hoje? Alguma novidade?",
                },
                {
                    "input": "Sentiu algum efeito colateral?",
                    "output": "Você notou algo diferente no seu corpo ou humor desde nossa última conversa?",
                },
            ],
        }
        return examples.get(intent, [])

    @with_db_retry(max_retries=3)
    async def generate_flow_message(
        self,
        patient_id: UUID,
        day: int | None = None,
        message_template: MessageTemplate | None = None,
        strict: bool = False,
        use_sync_agents: bool = False,
    ) -> str:
        """
        Generate personalized flow message using AI and database templates.

        Args:
            patient_id: Patient UUID
            day: Specific day to generate message for (optional)
            message_template: Message template to personalize (optional, will load from DB if not provided)

        Returns:
            Personalized message text
        """
        try:
            gemini_client: Any = self.gemini_client
            result = await self.db.execute(select(Patient).filter(Patient.id == patient_id))
            patient = result.scalar_one_or_none()
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")

            result = await self.db.execute(
                select(PatientFlowState).filter(
                    PatientFlowState.patient_id == patient_id,
                    PatientFlowState.status == "active",
                )
            )
            flow_state = result.scalar_one_or_none()
            if not flow_state:
                raise NotFoundError(f"No active flow for patient {patient_id}")

            if day is None:
                day = await self.calculate_patient_day(patient_id)

            flow_type_str = await self._get_flow_type_from_state(flow_state)

            if message_template is None:
                flow_type = normalize_flow_type(flow_type_str)
                if flow_type == FlowType.CUSTOM:
                    flow_type = FlowType.ONBOARDING
                message_template = await self.get_message_template_for_day(flow_type, day)
                if not message_template:
                    raise NotFoundError(
                        f"Message template not found for flow {flow_type_str} day {day}"
                    )

            conversation_history = await self._get_conversation_history(patient_id)
            recent_interactions = await self._get_recent_interactions(patient_id)
            communication_preferences = (
                await self.conversation_memory.get_communication_preferences(patient_id)
            )

            flow_context = FlowContext(
                patient=patient,
                flow_state=flow_state,
                current_day=day,
                flow_type=flow_type_str,
                conversation_history=conversation_history,
                recent_interactions=recent_interactions,
                communication_preferences=communication_preferences,
                medical_context={
                    "treatment_type": getattr(patient, "treatment_type", "hormone_therapy")
                },
            )

            ai_humanization_enabled = bool(getattr(settings, "AI_ENABLE_HUMANIZATION", True))

            if not ai_humanization_enabled:
                personalized_message = message_template.base_content
            else:
                repetition_check = await self.conversation_memory.check_message_repetition(
                    patient_id, message_template.base_content
                )

                intent = getattr(message_template, "intent", "check_in")
                few_shot_examples = self._get_few_shot_examples(intent)

                if repetition_check["recommendation"] in ["regenerate", "modify"]:
                    if hasattr(message_template, "variations") and message_template.variations:
                        import random

                        base_content = random.choice(message_template.variations)
                    else:
                        base_content = message_template.base_content

                    if use_sync_agents:
                        sync_varied_question = getattr(
                            gemini_client, "generate_varied_question_sync", None
                        )
                        if not callable(sync_varied_question):
                            raise FeatureNotAvailableError(
                                "sync variation method unavailable",
                                "variation",
                                "generate_flow_message",
                            )
                        personalized_message = await asyncio.to_thread(
                            sync_varied_question,
                            base_content,
                            conversation_history[-5:],
                            flow_context.to_dict(),
                            few_shot_examples,
                            getattr(message_template, "ai_instructions", None),
                            strict,
                        )
                    else:
                        async_varied_question = getattr(
                            gemini_client, "generate_varied_question", None
                        )
                        if not callable(async_varied_question):
                            raise FeatureNotAvailableError(
                                "async variation method unavailable",
                                "variation",
                                "generate_flow_message",
                            )
                        varied_result: Any = async_varied_question(
                            base_content,
                            conversation_history[-5:],
                            flow_context.to_dict(),
                            few_shot_examples=few_shot_examples,
                            ai_instructions=getattr(message_template, "ai_instructions", None),
                            strict=strict,
                        )
                        if asyncio.iscoroutine(varied_result):
                            varied_result = await varied_result
                        personalized_message = varied_result
                else:
                    try:
                        if use_sync_agents:
                            sync_humanize = getattr(gemini_client, "humanize_flow_message_sync", None)
                            if not callable(sync_humanize):
                                raise FeatureNotAvailableError(
                                    "sync humanization method unavailable",
                                    "humanization",
                                    "generate_flow_message",
                                )
                            personalized_message = await asyncio.to_thread(
                                sync_humanize,
                                message_template.base_content,
                                patient.name,
                                flow_context.to_dict(),
                                conversation_history,
                                list(getattr(message_template, "personalization_hints", []) or []),
                                few_shot_examples,
                                getattr(message_template, "ai_instructions", None),
                                strict,
                            )
                        else:
                            async_humanize = getattr(gemini_client, "humanize_flow_message", None)
                            if not callable(async_humanize):
                                raise FeatureNotAvailableError(
                                    "async humanization method unavailable",
                                    "humanization",
                                    "generate_flow_message",
                                )
                            humanized_result: Any = async_humanize(
                                message_template.base_content,
                                patient.name,
                                flow_context.to_dict(),
                                conversation_history,
                                list(getattr(message_template, "personalization_hints", []) or []),
                                few_shot_examples=few_shot_examples,
                                ai_instructions=getattr(message_template, "ai_instructions", None),
                                strict=strict,
                            )
                            if asyncio.iscoroutine(humanized_result):
                                humanized_result = await humanized_result
                            personalized_message = humanized_result
                        if not isinstance(personalized_message, str):
                            raise FeatureNotAvailableError(
                                "humanization returned non-text output",
                                "humanization",
                                "generate_flow_message",
                            )
                        if not personalized_message:
                            raise FeatureNotAvailableError(
                                "humanization returned no output",
                                "humanization",
                                "generate_flow_message",
                            )
                    except FeatureNotAvailableError as exc:
                        sentry_sdk.capture_exception(exc)
                        logger.error(
                            "Humanization failed, using unhumanized template: %s",
                            exc,
                            extra={"feature": "humanization"},
                        )
                        personalized_message = message_template.base_content

            await self.conversation_memory.store_message_pattern(
                patient_id, str(personalized_message)
            )

            logger.info(f"Generated personalized message for patient {patient_id}, day {day}")
            return str(personalized_message)

        except Exception as e:
            logger.error(f"Failed to generate flow message: {e}")
            raise


async def resolve_flow_type_from_state(db: Any, flow_state: PatientFlowState) -> str:
    """Resolve flow type from flow state via template version and flow kind."""
    result = await db.execute(
        select(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == flow_state.flow_template_version_id
        )
    )
    template_version = result.scalar_one_or_none()

    if not template_version:
        logger.error(f"Template version not found for flow state {flow_state.id}")
        return "unknown"

    result = await db.execute(
        select(FlowKind).filter(FlowKind.id == template_version.flow_kind_id)
    )
    flow_kind = result.scalar_one_or_none()

    if not flow_kind:
        logger.error(f"Flow kind not found for template version {template_version.id}")
        return "unknown"

    return flow_kind.flow_type


__all__ = ["FlowOrchestrationMixin", "resolve_flow_type_from_state"]
