import asyncio
import hashlib
import logging
import os
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models.flow import PatientFlowState
from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.models.patient import Patient
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class SequencingMixin:
    @staticmethod
    def _delay_enabled() -> bool:
        """Disable inter-message sleeps in tests and explicit no-delay mode."""
        if os.getenv("FLOW_DISABLE_DELAYS", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return False
        return not (os.getenv("TESTING") == "1" or os.getenv("PYTEST_CURRENT_TEST"))

    async def _await_inter_message_delay(self, seconds: float) -> None:
        if seconds <= 0 or not self._delay_enabled():
            return
        await asyncio.sleep(seconds)

    async def send_day_messages(
        self,
        patient_id: UUID,
        day_number: int,
        flow_kind: str = "onboarding",
    ) -> Dict[str, Any]:
        """Start or continue sending messages for a specific day."""
        try:
            from app.services.flow._flow_functions import run_flow_message

            return await run_flow_message(
                patient_id=patient_id,
                day_number=day_number,
                flow_kind=flow_kind,
                handler=self,
            )
        except Exception as exc:
            logger.exception("Error sending day messages via direct flow function")
            return {"status": "error", "message": str(exc)}

    def _build_idempotency_key(
        self,
        patient_id: UUID,
        flow_kind: str,
        day_number: int,
        message_index: int,
    ) -> str:
        """Create a deterministic idempotency key for flow messages."""
        base = f"flow:{patient_id}:{flow_kind}:{day_number}:{message_index}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]

    async def _send_flow_message(
        self,
        patient: Patient,
        content: str,
        day_number: int,
        flow_kind: str,
        message_index: int,
        expects_response: bool,
    ) -> bool:
        """Create a Message record and enqueue it via UnifiedWhatsAppService."""
        idempotency_key = self._build_idempotency_key(
            patient.id, flow_kind, day_number, message_index
        )
        flow_context = {
            "flow_type": flow_kind,
            "flow_day": day_number,
            "message_index": message_index,
            "expects_response": expects_response,
            "source": "flow_sequential",
        }

        existing = self.message_repo.get_by_idempotency_key(patient.id, idempotency_key)
        if existing:
            if existing.status in {MessageStatus.FAILED, MessageStatus.CANCELLED}:
                return await self.whatsapp_service.send_message(
                    existing,
                    flow_context=flow_context,
                )
            logger.info(
                "Skipping duplicate flow message",
                extra={"patient_id": patient.id, "idempotency_key": idempotency_key},
            )
            return True

        content = await self._inject_quiz_link_if_needed(content, patient)

        message = Message(
            patient_id=patient.id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content=content,
            status=MessageStatus.PENDING,
            scheduled_for=now_sao_paulo(),
            idempotency_key=idempotency_key,
            message_metadata={
                "source": "flow_sequential",
                "flow_kind": flow_kind,
                "flow_day": day_number,
                "message_index": message_index,
                "expects_response": expects_response,
            },
        )

        self.db.add(message)
        await self.db.commit()

        return await self.whatsapp_service.send_message(message, flow_context=flow_context)

    async def _send_all_sequential(
        self,
        patient: Patient,
        messages: List[Dict],
        flow_state: PatientFlowState,
        day_number: int,
        flow_kind: str,
        day_config: Optional[Dict] = None,
        delay_seconds: float = 3.0,
    ) -> Dict[str, Any]:
        """Send all messages with short delays between them."""
        sent_count = 0

        for i, msg in enumerate(messages):
            content = await self._personalize_message_ai(
                msg,
                patient,
                day_number,
                flow_kind,
                day_config,
                message_index=i,
            )

            success = await self._send_flow_message(
                patient,
                content,
                day_number,
                flow_kind,
                i,
                msg.get("expects_response", False),
            )
            if not success:
                return {"status": "error", "message": "Failed to send flow message"}

            sent_count += 1

            if i < len(messages) - 1:
                await self._await_inter_message_delay(delay_seconds)

        step_data = flow_state.step_data or {}
        step_data["day_complete"] = True
        step_data["messages_sent"] = sent_count
        step_data["current_day_message_index"] = max(len(messages) - 1, 0)
        self._mark_last_message_sent(step_data)
        step_data["awaiting_response"] = messages[-1].get("expects_response", False)
        if step_data["awaiting_response"]:
            pending_index = max(len(messages) - 1, 0)
            pending_message_id = self._resolve_sent_message_id(
                patient_id=patient.id,
                flow_kind=flow_kind,
                day_number=day_number,
                message_index=pending_index,
            )
            step_data["pending_response_context"] = {
                "flow_day": day_number,
                "flow_kind": flow_kind,
                "message_index": pending_index,
                "prompt_message_id": pending_message_id,
            }
        else:
            step_data.pop("pending_response_context", None)
        flow_state.step_data = step_data
        flow_state.last_interaction_at = now_sao_paulo()
        await self.db.commit()

        return {"status": "ok", "sent_count": sent_count, "mode": "sequential_auto"}

    async def _send_wait_each_with_auto_advance(
        self,
        patient: Patient,
        messages: List[Dict],
        start_index: int,
        flow_state: PatientFlowState,
        day_number: int,
        flow_kind: str,
        day_config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        FIX 3: Send messages in wait_each mode with auto-advance for non-response messages.

        This fixes the Day 15 issue where the intro message (expects_response=False)
        would cause the flow to get stuck, never advancing to the Q&A messages.

        Logic:
        1. Send message at current index
        2. If message expects_response=False, advance and send next immediately
        3. Repeat until we hit a message that expects_response=True or end of day
        """
        if start_index >= len(messages):
            return {"status": "complete", "message": "All messages sent"}

        current_index = start_index
        sent_count = 0

        while current_index < len(messages):
            msg = messages[current_index]
            content = await self._personalize_message_ai(
                msg,
                patient,
                day_number,
                flow_kind,
                day_config,
                message_index=current_index,
            )

            expects_response = msg.get("expects_response", True)

            if expects_response:
                await self._set_flow_progress(
                    flow_state,
                    message_index=current_index,
                    awaiting_response=True,
                    flow_day=day_number,
                    flow_kind=flow_kind,
                )

            success = await self._send_flow_message(
                patient,
                content,
                day_number,
                flow_kind,
                current_index,
                expects_response,
            )
            if not success:
                if expects_response:
                    await self._set_flow_progress(
                        flow_state,
                        message_index=current_index,
                        awaiting_response=False,
                        flow_day=day_number,
                        flow_kind=flow_kind,
                    )
                return {
                    "status": "error",
                    "message": f"Failed to send message {current_index}",
                }

            sent_count += 1

            if expects_response:
                pending_message_id = self._resolve_sent_message_id(
                    patient_id=patient.id,
                    flow_kind=flow_kind,
                    day_number=day_number,
                    message_index=current_index,
                )
                await self._set_flow_progress(
                    flow_state,
                    message_index=current_index,
                    awaiting_response=True,
                    mark_last_sent=True,
                    flow_day=day_number,
                    flow_kind=flow_kind,
                    pending_message_id=pending_message_id,
                )

                return {
                    "status": "waiting",
                    "message_index": current_index,
                    "awaiting_response": True,
                    "sent_count": sent_count,
                }

            current_index += 1
            await self._set_flow_progress(
                flow_state,
                message_index=current_index - 1,
                awaiting_response=False,
                mark_last_sent=True,
                flow_day=day_number,
                flow_kind=flow_kind,
            )

            if current_index < len(messages):
                await self._await_inter_message_delay(2.0)

        step_data = flow_state.step_data or {}
        step_data["day_complete"] = True
        step_data["awaiting_response"] = False
        step_data["current_day_message_index"] = len(messages) - 1
        self._mark_last_message_sent(step_data)
        step_data.pop("pending_response_context", None)
        flow_state.step_data = step_data
        flow_state.last_interaction_at = now_sao_paulo()
        await self.db.commit()

        return {"status": "complete", "sent_count": sent_count, "day": day_number}

    async def _send_message_and_wait(
        self,
        patient: Patient,
        messages: List[Dict],
        index: int,
        flow_state: PatientFlowState,
        day_number: int,
        flow_kind: str,
        day_config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send a single message and mark awaiting response."""
        if index >= len(messages):
            return {"status": "complete", "message": "All messages sent"}

        msg = messages[index]
        content = await self._personalize_message_ai(
            msg,
            patient,
            day_number,
            flow_kind,
            day_config,
            message_index=index,
        )
        expects_response = msg.get("expects_response", True)

        await self._set_flow_progress(
            flow_state,
            message_index=index,
            awaiting_response=expects_response,
            flow_day=day_number,
            flow_kind=flow_kind,
        )

        try:
            success = await self._send_flow_message(
                patient,
                content,
                day_number,
                flow_kind,
                index,
                expects_response,
            )
        except Exception:
            await self._set_flow_progress(
                flow_state,
                message_index=index,
                awaiting_response=False,
                flow_day=day_number,
                flow_kind=flow_kind,
            )
            raise
        if not success:
            await self._set_flow_progress(
                flow_state,
                message_index=index,
                awaiting_response=False,
                flow_day=day_number,
                flow_kind=flow_kind,
            )
            return {"status": "error", "message": "Failed to send flow message"}

        pending_message_id = self._resolve_sent_message_id(
            patient_id=patient.id,
            flow_kind=flow_kind,
            day_number=day_number,
            message_index=index,
        )
        await self._set_flow_progress(
            flow_state,
            message_index=index,
            awaiting_response=expects_response,
            mark_last_sent=True,
            flow_day=day_number,
            flow_kind=flow_kind,
            pending_message_id=pending_message_id,
        )

        return {
            "status": "waiting",
            "message_index": index,
            "awaiting_response": expects_response,
        }

    async def _send_remaining_after_response(
        self,
        patient: Patient,
        messages: List[Dict],
        start_index: int,
        flow_state: PatientFlowState,
        day_number: int,
        flow_kind: str,
        day_config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send remaining messages after a response (for wait_response mode)."""
        remaining = messages[start_index:]

        for i, msg in enumerate(remaining):
            message_index = start_index + i
            content = await self._personalize_message_ai(
                msg,
                patient,
                day_number,
                flow_kind,
                day_config,
                message_index=message_index,
            )

            expects_response = msg.get("expects_response", False)
            if expects_response:
                await self._set_flow_progress(
                    flow_state,
                    message_index=message_index,
                    awaiting_response=True,
                    flow_day=day_number,
                    flow_kind=flow_kind,
                )
            success = await self._send_flow_message(
                patient,
                content,
                day_number,
                flow_kind,
                message_index,
                expects_response,
            )
            if not success:
                if expects_response:
                    await self._set_flow_progress(
                        flow_state,
                        message_index=message_index,
                        awaiting_response=False,
                        flow_day=day_number,
                        flow_kind=flow_kind,
                    )
                return {"status": "error", "message": "Failed to send flow message"}

            if expects_response:
                pending_message_id = self._resolve_sent_message_id(
                    patient_id=patient.id,
                    flow_kind=flow_kind,
                    day_number=day_number,
                    message_index=message_index,
                )
                await self._set_flow_progress(
                    flow_state,
                    message_index=message_index,
                    awaiting_response=True,
                    mark_last_sent=True,
                    flow_day=day_number,
                    flow_kind=flow_kind,
                    pending_message_id=pending_message_id,
                )
                return {
                    "status": "waiting",
                    "message_index": message_index,
                    "awaiting_response": True,
                }

            await self._set_flow_progress(
                flow_state,
                message_index=message_index,
                awaiting_response=False,
                mark_last_sent=True,
                flow_day=day_number,
                flow_kind=flow_kind,
            )

            if i < len(remaining) - 1:
                await self._await_inter_message_delay(2.0)

        step_data = flow_state.step_data or {}
        step_data["day_complete"] = True
        step_data["current_day_message_index"] = len(messages) - 1
        step_data["awaiting_response"] = False
        self._mark_last_message_sent(step_data)
        step_data.pop("pending_response_context", None)
        flow_state.step_data = step_data
        flow_state.last_interaction_at = now_sao_paulo()
        await self.db.commit()

        return {"status": "complete", "sent_count": len(remaining)}


__all__ = ["SequencingMixin"]
