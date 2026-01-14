"""
Sequential Message Handler

Handles sending messages sequentially within a day based on send_mode:
- sequential_auto: Send all messages with short delay (no response wait)
- wait_response: Send first message, wait for response, then send remaining
- wait_each: Send each message, wait for response before next
- single: Just one message
"""

import logging
import asyncio
import hashlib
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.flow import PatientFlowState
from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.models.patient import Patient
from app.repositories.flow import FlowStateRepository
from app.repositories.message import MessageRepository
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.services.enhanced_flow_engine import EnhancedFlowEngine

logger = logging.getLogger(__name__)


class SequentialMessageHandler:
    """
    Orchestrates sequential message sending within a day.
    
    Tracks which message the patient is on via patient_flow_states.step_data:
    {
        "current_day_message_index": 0,  # Which message we're on for today
        "day_messages_completed": [0, 1, 2],  # Which messages have been sent
        "awaiting_response": true  # Whether we're waiting for patient response
    }
    """
    
    def __init__(self, db: Session, use_ai_personalization: bool = True):
        self.db = db
        self.flow_state_repo = FlowStateRepository(db)
        self.message_repo = MessageRepository(db)
        self.whatsapp_service = UnifiedWhatsAppService(db)
        self.use_ai_personalization = use_ai_personalization
        self._enhanced_flow_engine: Optional[EnhancedFlowEngine] = None
    
    def _get_ai_engine(self) -> EnhancedFlowEngine:
        """Lazy initialization of AI engine."""
        if self._enhanced_flow_engine is None:
            self._enhanced_flow_engine = EnhancedFlowEngine(self.db)
        return self._enhanced_flow_engine
    
    async def send_day_messages(
        self, 
        patient_id: UUID, 
        day_number: int,
        flow_kind: str = "initial_15_days"
    ) -> Dict[str, Any]:
        """
        Start or continue sending messages for a specific day.
        
        Args:
            patient_id: The patient UUID
            day_number: The day in the flow (1-15, 16-45, etc.)
            flow_kind: The flow kind key (initial_15_days, days_16_45, monthly_recurring)
        
        Returns:
            Dict with status and messages sent info
        """
        try:
            # Get patient
            patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                return {"status": "error", "message": "Patient not found"}
            
            # Get flow template
            day_config = await self._get_day_config(flow_kind, day_number)
            if not day_config:
                return {"status": "error", "message": f"No config for day {day_number} in {flow_kind}"}
            
            messages = day_config.get("messages", [])
            send_mode = day_config.get("send_mode", "single")
            
            # Get or create flow state
            flow_state = await self._get_or_create_flow_state(patient_id, flow_kind)
            
            # Get current state data
            step_data = flow_state.step_data or {}
            current_index = step_data.get("current_day_message_index", 0)
            
            # Store flow context in step_data for use by internal methods
            step_data["current_flow_day"] = day_number
            step_data["flow_kind"] = flow_kind
            flow_state.step_data = step_data
            
            if send_mode == "sequential_auto":
                # Send all messages with short delays
                return await self._send_all_sequential(patient, messages, flow_state, day_number, flow_kind)
            
            elif send_mode == "wait_response":
                # Send first message, mark awaiting response
                if current_index == 0:
                    return await self._send_message_and_wait(patient, messages, 0, flow_state, day_number, flow_kind)
                else:
                    # Continuation after response - send remaining
                    return await self._send_remaining_after_response(patient, messages, current_index, flow_state, day_number, flow_kind)
            
            elif send_mode == "wait_each":
                # Send one message at a time
                return await self._send_message_and_wait(patient, messages, current_index, flow_state, day_number, flow_kind)
            
            else:  # single
                # Just send the single message
                return await self._send_all_sequential(patient, messages, flow_state, day_number, flow_kind)
        
        except Exception as e:
            logger.error(f"Error sending day messages: {e}")
            return {"status": "error", "message": str(e)}
    
    async def handle_response_and_continue(
        self, 
        patient_id: UUID
    ) -> Dict[str, Any]:
        """
        Handle patient response and send next message if needed.
        
        Called by ResponseProcessor after processing inbound message.
        
        Returns:
            Dict with status and next action info
        """
        try:
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                return {"status": "no_active_flow"}
            
            step_data = flow_state.step_data or {}
            
            # Check if we're awaiting response
            if not step_data.get("awaiting_response"):
                return {"status": "not_awaiting", "message": "Not waiting for response"}
            
            # Get current day config
            current_day = step_data.get("current_flow_day", 1)
            flow_kind = step_data.get("flow_kind", "initial_15_days")
            
            day_config = await self._get_day_config(flow_kind, current_day)
            if not day_config:
                return {"status": "no_config"}
            
            messages = day_config.get("messages", [])
            send_mode = day_config.get("send_mode", "single")
            current_index = step_data.get("current_day_message_index", 0)
            
            # Mark response received
            step_data["awaiting_response"] = False
            step_data["last_response_at"] = datetime.now(timezone.utc).isoformat()
            
            # Advance to next message
            next_index = current_index + 1
            
            if next_index >= len(messages):
                # Day complete
                step_data["day_complete"] = True
                flow_state.step_data = step_data
                self.db.commit()
                return {"status": "day_complete", "day": current_day}
            
            # Get patient
            patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
            
            if send_mode == "wait_response":
                # Send remaining messages automatically
                return await self._send_remaining_after_response(patient, messages, next_index, flow_state, current_day, flow_kind)
            
            elif send_mode == "wait_each":
                # Send next message and wait again
                return await self._send_message_and_wait(patient, messages, next_index, flow_state, current_day, flow_kind)
            
            return {"status": "ok"}
        
        except Exception as e:
            logger.error(f"Error handling response continuation: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _get_day_config(self, flow_kind: str, day: int) -> Optional[Dict]:
        """
        Get the configuration for a specific day in a flow.
        
        Uses Redis cache to reduce database load with multiple patients.
        Cache TTL: 1 hour (templates rarely change)
        """
        import json
        from app.core.redis_manager import get_sync_redis_client
        
        cache_key = f"flow_template:{flow_kind}:steps"
        cache_ttl = 3600  # 1 hour
        
        try:
            # Try Redis cache first
            redis_client = get_sync_redis_client()
            if redis_client:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    logger.debug(f"Cache hit for {cache_key}")
                    steps = json.loads(cached_data)
                    for step in steps:
                        if step.get("day") == day:
                            return step
                    return None
        except Exception as e:
            logger.warning(f"Redis cache error (falling back to DB): {e}")
        
        # Cache miss or error - query database
        result = self.db.execute(text("""
            SELECT ftv.steps 
            FROM flow_template_versions ftv 
            JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id 
            WHERE fk.kind_key = :kind AND ftv.is_active = true
        """), {"kind": flow_kind}).fetchone()
        
        if not result or not result[0]:
            return None
        
        steps = result[0]
        
        # Store in Redis cache for future requests
        try:
            redis_client = get_sync_redis_client()
            if redis_client:
                redis_client.setex(cache_key, cache_ttl, json.dumps(steps, ensure_ascii=False))
                logger.debug(f"Cached {cache_key} with TTL {cache_ttl}s")
        except Exception as e:
            logger.warning(f"Failed to cache flow template: {e}")
        
        # Find and return the specific day
        for step in steps:
            if step.get("day") == day:
                return step
        
        return None
    
    async def _get_or_create_flow_state(
        self, 
        patient_id: UUID, 
        flow_kind: str
    ) -> PatientFlowState:
        """Get or create patient flow state."""
        flow_state = self.flow_state_repo.get_active_flow(patient_id)
        
        if not flow_state:
            # Create new flow state
            # Get flow template version
            result = self.db.execute(text("""
                SELECT ftv.id 
                FROM flow_template_versions ftv 
                JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id 
                WHERE fk.kind_key = :kind AND ftv.is_active = true
            """), {"kind": flow_kind}).fetchone()
            
            if result:
                flow_state = PatientFlowState(
                    patient_id=patient_id,
                    flow_template_version_id=result[0],
                    status="active",
                    step_data={"flow_kind": flow_kind}
                )
                self.db.add(flow_state)
                self.db.commit()
        
        return flow_state

    def _build_idempotency_key(
        self, patient_id: UUID, flow_kind: str, day_number: int, message_index: int
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

        existing = self.message_repo.get_by_idempotency_key(
            patient.id, idempotency_key
        )
        if existing:
            if existing.status in {MessageStatus.FAILED, MessageStatus.CANCELLED}:
                return await self.whatsapp_service.send_message(
                    existing, flow_context=flow_context
                )
            logger.info(
                "Skipping duplicate flow message",
                extra={"patient_id": patient.id, "idempotency_key": idempotency_key},
            )
            return True

        message = Message(
            patient_id=patient.id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content=content,
            status=MessageStatus.PENDING,
            scheduled_for=datetime.now(timezone.utc),
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
        self.db.commit()

        return await self.whatsapp_service.send_message(
            message, flow_context=flow_context
        )
    
    async def _send_all_sequential(
        self, 
        patient: Patient, 
        messages: List[Dict], 
        flow_state: PatientFlowState,
        day_number: int,
        flow_kind: str,
        delay_seconds: float = 3.0
    ) -> Dict[str, Any]:
        """Send all messages with short delays between them."""
        sent_count = 0
        
        for i, msg in enumerate(messages):
            content = await self._personalize_message_ai(msg.get("content", ""), patient, day_number, flow_kind)

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
            
            # Short delay between messages (except last)
            if i < len(messages) - 1:
                await asyncio.sleep(delay_seconds)
        
        # Update flow state
        step_data = flow_state.step_data or {}
        step_data["day_complete"] = True
        step_data["messages_sent"] = sent_count
        step_data["awaiting_response"] = messages[-1].get("expects_response", False)
        flow_state.step_data = step_data
        flow_state.last_interaction_at = datetime.now(timezone.utc)
        self.db.commit()
        
        return {"status": "ok", "sent_count": sent_count, "mode": "sequential_auto"}
    
    async def _send_message_and_wait(
        self, 
        patient: Patient, 
        messages: List[Dict], 
        index: int,
        flow_state: PatientFlowState,
        day_number: int,
        flow_kind: str
    ) -> Dict[str, Any]:
        """Send a single message and mark awaiting response."""
        if index >= len(messages):
            return {"status": "complete", "message": "All messages sent"}
        
        msg = messages[index]
        content = await self._personalize_message_ai(msg.get("content", ""), patient, day_number, flow_kind)

        success = await self._send_flow_message(
            patient,
            content,
            day_number,
            flow_kind,
            index,
            msg.get("expects_response", True),
        )
        if not success:
            return {"status": "error", "message": "Failed to send flow message"}
        
        # Update flow state
        step_data = flow_state.step_data or {}
        step_data["current_day_message_index"] = index
        step_data["awaiting_response"] = msg.get("expects_response", True)
        step_data["last_message_sent_at"] = datetime.now(timezone.utc).isoformat()
        flow_state.step_data = step_data
        flow_state.last_interaction_at = datetime.now(timezone.utc)
        self.db.commit()
        
        return {
            "status": "waiting", 
            "message_index": index,
            "awaiting_response": msg.get("expects_response", True)
        }
    
    async def _send_remaining_after_response(
        self, 
        patient: Patient, 
        messages: List[Dict], 
        start_index: int,
        flow_state: PatientFlowState,
        day_number: int,
        flow_kind: str
    ) -> Dict[str, Any]:
        """Send remaining messages after a response (for wait_response mode)."""
        remaining = messages[start_index:]
        
        # Send remaining messages sequentially
        for i, msg in enumerate(remaining):
            content = await self._personalize_message_ai(msg.get("content", ""), patient, day_number, flow_kind)

            message_index = start_index + i
            success = await self._send_flow_message(
                patient,
                content,
                day_number,
                flow_kind,
                message_index,
                msg.get("expects_response", False),
            )
            if not success:
                return {"status": "error", "message": "Failed to send flow message"}
            
            # Short delay between
            if i < len(remaining) - 1:
                await asyncio.sleep(2.0)
        
        # Mark day complete
        step_data = flow_state.step_data or {}
        step_data["day_complete"] = True
        step_data["current_day_message_index"] = len(messages) - 1
        step_data["awaiting_response"] = False
        flow_state.step_data = step_data
        self.db.commit()
        
        return {"status": "complete", "sent_count": len(remaining)}
    
    async def _personalize_message_ai(
        self, 
        content: str, 
        patient: Patient, 
        day_number: int,
        flow_kind: str
    ) -> str:
        """
        Personalize message using AI (EnhancedFlowEngine).
        Falls back to simple replacement if AI fails.
        """
        if not self.use_ai_personalization:
            return self._personalize_message_simple(content, patient)
        
        try:
            engine = self._get_ai_engine()
            # Build minimal context for AI personalization
            personalized = await engine.gemini_client.humanize_flow_message(
                template=content,
                patient_name=patient.name or patient.preferred_name or "Paciente",
                patient_context={
                    "patient_id": str(patient.id),
                    "patient_name": patient.name,
                    "current_day": day_number,
                    "flow_type": flow_kind,
                },
                conversation_history=[],
                personalization_hints=["patient_name", "treatment_context"],
            )
            if personalized:
                logger.debug(f"AI personalized message for patient {patient.id}")
                return personalized
        except Exception as e:
            logger.warning(f"AI personalization failed, using fallback: {e}")
        
        return self._personalize_message_simple(content, patient)
    
    def _personalize_message_simple(self, content: str, patient: Patient) -> str:
        """Simple placeholder replacement (fallback)."""
        name = patient.name or patient.preferred_name or "Paciente"
        
        content = content.replace("[NOME]", name)
        content = content.replace("[nome]", name)
        content = content.replace("{patient_name}", name)
        
        return content


def get_sequential_message_handler(db: Session) -> SequentialMessageHandler:
    """Factory function to get handler instance."""
    return SequentialMessageHandler(db)
