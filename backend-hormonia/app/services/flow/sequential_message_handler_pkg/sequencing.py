import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models.flow import PatientFlowState
from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.models.patient import Patient
from app.services.flow.config_validation import DayConfigValidationError
from app.services.flow.management.advancement import advance_day_atomic
from app.services.flow.sequential_message_handler_pkg.delivery import (
    await_inter_message_delay,
    build_flow_idempotency_key,
    build_flow_send_context,
    build_day_config_validation_error_response,
    delay_enabled,
    enqueue_failed_flow_send_retry,
)
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)
class SequencingMixin:
    @staticmethod
    def _delay_enabled() -> bool:
        return delay_enabled()

    async def _await_inter_message_delay(self, seconds: float) -> None:
        await await_inter_message_delay(seconds)

    async def send_day_messages(
        self,
        patient_id: UUID,
        day_number: int,
        flow_kind: str = "onboarding",
    ) -> Dict[str, Any]:
        """Start or continue sending messages for a specific day."""
        try:
            from app.services.flow._flow_functions import run_flow_message

            return await run_flow_message(patient_id=patient_id, day_number=day_number, flow_kind=flow_kind, handler=self)
        except DayConfigValidationError as exc:
            return build_day_config_validation_error_response(patient_id=patient_id, flow_kind=flow_kind, day_number=day_number, exc=exc)
        except Exception as exc:
            logger.exception("Error sending day messages via direct flow function")
            return {"status": "error", "message": str(exc)}

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
        idempotency_key = build_flow_idempotency_key(
            patient_id=patient.id,
            flow_kind=flow_kind,
            day_number=day_number,
            message_index=message_index,
        )
        flow_context = build_flow_send_context(
            flow_kind=flow_kind,
            day_number=day_number,
            message_index=message_index,
            expects_response=expects_response,
        )

        existing = self.message_repo.get_by_idempotency_key(patient.id, idempotency_key)
        if existing:
            if existing.status in {MessageStatus.FAILED, MessageStatus.CANCELLED}:
                success = await self.whatsapp_service.send_message(
                    existing,
                    flow_context=flow_context,
                )
                if not success:
                    enqueue_failed_flow_send_retry(
                        message_id=existing.id,
                        patient_id=patient.id,
                        flow_kind=flow_kind,
                        day_number=day_number,
                        message_index=message_index,
                        flow_context=flow_context,
                        resend=True,
                    )
                return success
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

        success = await self.whatsapp_service.send_message(
            message,
            flow_context=flow_context,
        )
        if not success:
            enqueue_failed_flow_send_retry(
                message_id=message.id,
                patient_id=patient.id,
                flow_kind=flow_kind,
                day_number=day_number,
                message_index=message_index,
                flow_context=flow_context,
            )
        return success

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

        if messages[-1].get("expects_response", False):
            pending_index = max(len(messages) - 1, 0)
            pending_message_id = self._resolve_sent_message_id(
                patient_id=patient.id,
                flow_kind=flow_kind,
                day_number=day_number,
                message_index=pending_index,
            )
            await self._set_flow_progress(
                flow_state,
                message_index=pending_index,
                awaiting_response=True,
                mark_last_sent=True,
                flow_day=day_number,
                flow_kind=flow_kind,
                pending_message_id=pending_message_id,
            )
        else:
            await advance_day_atomic(
                db=self.db,
                flow_state=flow_state,
                patient_id=getattr(patient, "id", None),
                day_number=day_number,
                flow_kind=flow_kind,
                message_index=max(len(messages) - 1, 0),
                sent_count=sent_count,
                mark_last_message_sent=self._mark_last_message_sent,
            )

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
        """Send wait_each messages, auto-advancing across non-response steps."""
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

        await advance_day_atomic(
            db=self.db,
            flow_state=flow_state,
            patient_id=getattr(patient, "id", None),
            day_number=day_number,
            flow_kind=flow_kind,
            message_index=len(messages) - 1,
            sent_count=sent_count,
            mark_last_message_sent=self._mark_last_message_sent,
        )

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

        await advance_day_atomic(
            db=self.db,
            flow_state=flow_state,
            patient_id=getattr(patient, "id", None),
            day_number=day_number,
            flow_kind=flow_kind,
            message_index=len(messages) - 1,
            sent_count=len(remaining),
            mark_last_message_sent=self._mark_last_message_sent,
        )

        return {"status": "complete", "sent_count": len(remaining)}


__all__ = ["SequencingMixin"]
