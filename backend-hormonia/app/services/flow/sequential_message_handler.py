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
import difflib
import re
import os
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.ai.langgraph.graphs import get_flow_message_graph, get_flow_response_graph
from app.ai.langgraph.runtime import build_graph_config
from app.models.flow import PatientFlowState
from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.models.patient import Patient
from app.repositories.flow import FlowStateRepository
from app.repositories.message import MessageRepository
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.services.enhanced_flow_engine import EnhancedFlowEngine
from app.services.template_loader_pkg import MessageTemplate as FlowMessageTemplate
from app.utils.timezone import now_sao_paulo

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

    def _normalize_text(self, text: str) -> str:
        """Normalize text for similarity checks (lowercase, collapse spaces)."""
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        return normalized

    @staticmethod
    def _delay_enabled() -> bool:
        """Disable inter-message sleeps in tests and explicit no-delay mode."""
        if os.getenv("FLOW_DISABLE_DELAYS", "").strip().lower() in {"1", "true", "yes", "on"}:
            return False
        return not (
            os.getenv("TESTING") == "1" or os.getenv("PYTEST_CURRENT_TEST")
        )

    async def _await_inter_message_delay(self, seconds: float) -> None:
        if seconds <= 0 or not self._delay_enabled():
            return
        await asyncio.sleep(seconds)

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful tokens from base content to validate AI grounding."""
        # Remove placeholders to avoid false positives
        cleaned = re.sub(r"\[[^\]]+\]|\{[^}]+\}", " ", text or "")
        tokens = re.findall(r"[a-zA-ZÀ-ÿ]+", cleaned.lower())
        return [t for t in tokens if len(t) >= 4]

    def _personalization_is_grounded(self, base_content: str, personalized: str) -> bool:
        """Check if AI output stays anchored to the base template."""
        base_norm = self._normalize_text(base_content)
        personalized_norm = self._normalize_text(personalized)
        if not base_norm or not personalized_norm:
            return False

        similarity = difflib.SequenceMatcher(None, base_norm, personalized_norm).ratio()
        base_keywords = set(self._extract_keywords(base_content))
        if not base_keywords:
            return similarity >= 0.35

        personalized_tokens = set(self._extract_keywords(personalized))
        overlap_ratio = len(base_keywords & personalized_tokens) / max(len(base_keywords), 1)

        # Similarity can be noisy for similarly sized texts, so prefer lexical overlap
        # and only allow pure similarity when it is clearly high.
        return overlap_ratio >= 0.2 or similarity >= 0.6
    
    async def send_day_messages(
        self, 
        patient_id: UUID, 
        day_number: int,
        flow_kind: str = "onboarding"
    ) -> Dict[str, Any]:
        """
        Start or continue sending messages for a specific day.
        
        Args:
            patient_id: The patient UUID
            day_number: The day in the flow (1-15, 16-45, etc.)
            flow_kind: The flow kind key (onboarding, daily_follow_up, quiz_mensal)
        
        Returns:
            Dict with status and messages sent info
        """
        try:
            graph = get_flow_message_graph()
            state = await graph.ainvoke(
                {
                    "patient_id": patient_id,
                    "day_number": day_number,
                    "flow_kind": flow_kind,
                    "result": None,
                    "error": None,
                },
                config=build_graph_config(
                    thread_id=self._build_flow_message_thread_id(
                        patient_id=patient_id,
                        flow_kind=flow_kind,
                        day_number=day_number,
                    ),
                    handler=self,
                ),
            )
            result = state.get("result")
            if not isinstance(result, dict):
                raise ValueError("LangGraph did not return a result payload")
            return result
        
        except (RuntimeError, TypeError, ValueError) as e:
            logger.exception("Error sending day messages via LangGraph")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("Unexpected error sending day messages via LangGraph")
            return {"status": "error", "message": str(e)}
    
    async def handle_response_and_continue(
        self,
        patient_id: UUID,
        response_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Handle patient response and send next message if needed.
        
        Called by ResponseProcessor after processing inbound message.

        Args:
            patient_id: Patient identifier.
            response_context: Optional correlation payload with
                flow_day/flow_kind/message_index/prompt_message_id/response_message_id.
        
        Returns:
            Dict with status and next action info
        """
        try:
            graph = get_flow_response_graph()
            graph_state: Dict[str, Any] = {"patient_id": patient_id}
            # Clear persisted checkpoint terminal payloads from prior invocations.
            graph_state["result"] = None
            graph_state["error"] = None
            if response_context is not None:
                graph_state["response_context"] = response_context
            state = await graph.ainvoke(
                graph_state,
                config=build_graph_config(
                    thread_id=self._build_flow_response_thread_id(patient_id),
                    handler=self,
                ),
            )
            result = state.get("result")
            if not isinstance(result, dict):
                raise ValueError("LangGraph did not return a result payload")
            return result
        
        except (RuntimeError, TypeError, ValueError) as e:
            logger.exception("Error handling response continuation")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("Unexpected error handling response continuation")
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
        # TODO(async-migration): sync SQLAlchemy execute in async method blocks event loop.
        # Migrate handler DB access to AsyncSession and awaitable execute.
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
        # TODO(async-migration): repository currently uses sync SQLAlchemy in async flow.
        flow_state = self.flow_state_repo.get_active_flow(patient_id)
        
        if not flow_state:
            # Create new flow state
            # Get flow template version
            # TODO(async-migration): sync SQLAlchemy execute/add/commit in async method.
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

    def _build_flow_message_thread_id(
        self, *, patient_id: UUID, flow_kind: str, day_number: int
    ) -> str:
        return f"flow_message:{patient_id}:{flow_kind}:{day_number}"

    def _build_flow_response_thread_id(self, patient_id: UUID) -> str:
        return f"flow_response:{patient_id}"

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

        # TODO(async-migration): sync SQLAlchemy add/commit in async method.
        self.db.add(message)
        self.db.commit()

        return await self.whatsapp_service.send_message(
            message, flow_context=flow_context
        )

    async def _inject_quiz_link_if_needed(
        self, content: str, patient: Patient
    ) -> str:
        """Replace quiz link placeholder with a generated monthly quiz link."""
        placeholder = "[LINK DO QUIZ]"
        if placeholder not in content:
            return content

        from app.models.quiz import QuizTemplate, QuizSession
        from app.schemas.monthly_quiz import MonthlyQuizLinkCreate, DeliveryMethod
        from app.domain.quizzes.manager import QuizSessionManager
        from app.domain.quizzes.quiz_trigger_policy import QuizTriggerPolicy
        from app.core.monthly_quiz_config import get_monthly_quiz_config
        from app.utils.timezone import SAO_PAULO_TZ

        templates = (
            # TODO(async-migration): sync SQLAlchemy query in async method.
            self.db.query(QuizTemplate)
            .filter(QuizTemplate.is_active.is_(True))
            .all()
        )
        if not templates:
            raise ValueError("No active quiz template found for monthly quiz link")

        def _rank_template(template: QuizTemplate) -> int:
            name = (template.name or "").lower()
            category = (template.category or "").lower()
            if "mensal" in name or "monthly" in name:
                return 2
            if "mensal" in category or "monthly" in category:
                return 1
            return 0

        templates.sort(key=_rank_template, reverse=True)
        template = templates[0]

        config = get_monthly_quiz_config()
        enrollment_date = patient.enrollment_date or patient.created_at
        if isinstance(enrollment_date, datetime):
            if enrollment_date.tzinfo is None:
                enrollment_date = enrollment_date.replace(tzinfo=SAO_PAULO_TZ)
            enrollment_local_date = enrollment_date.astimezone(SAO_PAULO_TZ).date()
        else:
            enrollment_local_date = enrollment_date

        days_since_enrollment = (
            now_sao_paulo().date() - enrollment_local_date
        ).days
        monthly_cycle, _ = QuizTriggerPolicy.calculate_monthly_cycle(
            days_since_enrollment
        )

        manager = QuizSessionManager(self.db)
        existing_session = (
            # TODO(async-migration): sync SQLAlchemy query in async method.
            self.db.query(QuizSession)
            .filter(QuizSession.patient_id == patient.id)
            .filter(
                QuizSession.session_metadata["monthly_cycle"].astext
                == str(monthly_cycle)
            )
            .order_by(QuizSession.started_at.desc())
            .first()
        )

        if existing_session:
            link_response = await manager.regenerate_link(existing_session.id)
        else:
            link_data = MonthlyQuizLinkCreate(
                patient_id=patient.id,
                quiz_template_id=template.id,
                delivery_method=DeliveryMethod.WHATSAPP,
                expiry_hours=config.MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS,
                send_immediately=False,
            )
            link_response = await manager.create_quiz_link(link_data)

        if link_response.session_id:
            session = (
                # TODO(async-migration): sync SQLAlchemy query in async method.
                self.db.query(QuizSession)
                .filter(QuizSession.id == link_response.session_id)
                .first()
            )
            if session:
                metadata = session.session_metadata or {}
                metadata["monthly_cycle"] = monthly_cycle
                session.session_metadata = metadata
                # TODO(async-migration): sync SQLAlchemy commit in async method.
                self.db.commit()

        return content.replace(placeholder, link_response.link_url)
    
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
            
            # Short delay between messages (except last)
            if i < len(messages) - 1:
                await self._await_inter_message_delay(delay_seconds)
        
        # Update flow state
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
        # TODO(async-migration): sync SQLAlchemy commit in async method.
        self.db.commit()
        
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
            
            # NOTE: Default True for wait_each - assumes response expected unless explicitly False
            expects_response = msg.get("expects_response", True)

            if expects_response:
                # Persist awaiting_response before send to avoid missing fast replies
                self._set_flow_progress(
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
                    # Revert awaiting flag on failure
                    self._set_flow_progress(
                        flow_state,
                        message_index=current_index,
                        awaiting_response=False,
                        flow_day=day_number,
                        flow_kind=flow_kind,
                    )
                return {"status": "error", "message": f"Failed to send message {current_index}"}
            
            sent_count += 1
            
            # Update flow state
            if expects_response:
                # Stop here and wait for patient response
                pending_message_id = self._resolve_sent_message_id(
                    patient_id=patient.id,
                    flow_kind=flow_kind,
                    day_number=day_number,
                    message_index=current_index,
                )
                self._set_flow_progress(
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
                    "sent_count": sent_count
                }
            
            # Message doesn't expect response - auto-advance to next
            current_index += 1
            self._set_flow_progress(
                flow_state,
                message_index=current_index - 1,
                awaiting_response=False,
                mark_last_sent=True,
                flow_day=day_number,
                flow_kind=flow_kind,
            )
            
            # Small delay between auto-advanced messages
            if current_index < len(messages):
                await self._await_inter_message_delay(2.0)
        
        # All messages sent without waiting for response
        step_data = flow_state.step_data or {}
        step_data["day_complete"] = True
        step_data["awaiting_response"] = False
        step_data["current_day_message_index"] = len(messages) - 1
        self._mark_last_message_sent(step_data)
        step_data.pop("pending_response_context", None)
        flow_state.step_data = step_data
        flow_state.last_interaction_at = now_sao_paulo()
        # TODO(async-migration): sync SQLAlchemy commit in async method.
        self.db.commit()
        
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

        # Persist awaiting_response before send to avoid missing fast replies
        self._set_flow_progress(
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
            # Revert awaiting flag on failure
            self._set_flow_progress(
                flow_state,
                message_index=index,
                awaiting_response=False,
                flow_day=day_number,
                flow_kind=flow_kind,
            )
            raise
        if not success:
            self._set_flow_progress(
                flow_state,
                message_index=index,
                awaiting_response=False,
                flow_day=day_number,
                flow_kind=flow_kind,
            )
            return {"status": "error", "message": "Failed to send flow message"}
        
        # Update flow state after successful send
        pending_message_id = self._resolve_sent_message_id(
            patient_id=patient.id,
            flow_kind=flow_kind,
            day_number=day_number,
            message_index=index,
        )
        self._set_flow_progress(
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
            "awaiting_response": expects_response
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
        
        # Send remaining messages sequentially
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
                # Persist awaiting_response before send to avoid missing fast replies
                self._set_flow_progress(
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
                    self._set_flow_progress(
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
                self._set_flow_progress(
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

            self._set_flow_progress(
                flow_state,
                message_index=message_index,
                awaiting_response=False,
                mark_last_sent=True,
                flow_day=day_number,
                flow_kind=flow_kind,
            )
            
            # Short delay between
            if i < len(remaining) - 1:
                await self._await_inter_message_delay(2.0)
        
        # Mark day complete
        step_data = flow_state.step_data or {}
        step_data["day_complete"] = True
        step_data["current_day_message_index"] = len(messages) - 1
        step_data["awaiting_response"] = False
        self._mark_last_message_sent(step_data)
        step_data.pop("pending_response_context", None)
        flow_state.step_data = step_data
        flow_state.last_interaction_at = now_sao_paulo()
        # TODO(async-migration): sync SQLAlchemy commit in async method.
        self.db.commit()
        
        return {"status": "complete", "sent_count": len(remaining)}

    
    async def _personalize_message_ai(
        self,
        message: Dict[str, Any],
        patient: Patient,
        day_number: int,
        flow_kind: str,
        day_config: Optional[Dict] = None,
        message_index: Optional[int] = None,
    ) -> str:
        """
        Personalize message using AI (EnhancedFlowEngine).
        Falls back to simple/template personalization when AI fails.
        """
        content = message.get("content", "") if isinstance(message, dict) else ""
        expects_response = (
            message.get("expects_response") if isinstance(message, dict) else None
        )
        fallback_content = self._build_fallback_content(
            message=message,
            patient=patient,
            content=content,
            flow_kind=flow_kind,
            day_number=day_number,
            message_index=message_index,
            expects_response=expects_response,
        )
        if not self.use_ai_personalization:
            return fallback_content
        if expects_response is False:
            return fallback_content
        
        try:
            engine = self._get_ai_engine()
            intent = (
                (message or {}).get("intent")
                or (day_config or {}).get("intent")
                or f"day_{day_number}_message"
            )
            personalization_hints = (
                (message or {}).get("personalization_hints")
                or (day_config or {}).get("personalization_hints")
                or ["patient_name"]
            )
            ai_instructions = (message or {}).get("ai_instructions") or (
                day_config or {}
            ).get("ai_instructions")
            variations = (message or {}).get("variations") or []

            template = FlowMessageTemplate(
                day=day_number,
                intent=intent,
                base_content=content,
                personalization_hints=personalization_hints,
                ai_instructions=ai_instructions,
                variations=variations,
            )

            # Rely on GeminiClient's internal per-attempt timeouts and retries.
            # Outer wait_for can prematurely abort after the first retry, causing
            # false "AI personalization timed out" errors.
            personalized = await engine.generate_flow_message(
                patient_id=patient.id,
                day=day_number,
                message_template=template,
                strict=True,
            )
            if not personalized:
                logger.warning(
                    "AI personalization returned empty content, using fallback",
                    extra={
                        "patient_id": str(patient.id),
                        "day": day_number,
                        "flow_kind": flow_kind,
                    },
                )
                return fallback_content

            if not self._personalization_is_grounded(content, personalized):
                logger.warning(
                    "AI personalization not grounded to base template, using fallback",
                    extra={
                        "patient_id": str(patient.id),
                        "day": day_number,
                        "flow_kind": flow_kind,
                    },
                )
                return fallback_content

            logger.debug(f"AI personalized message for patient {patient.id}")
            return personalized
        except asyncio.TimeoutError:
            logger.exception(
                "AI personalization timed out, using fallback",
                extra={
                    "patient_id": str(patient.id),
                    "day": day_number,
                    "flow_kind": flow_kind,
                },
            )
            return fallback_content
        except (ValueError, RuntimeError):
            logger.exception(
                "AI personalization failed, using fallback",
                extra={
                    "patient_id": str(patient.id),
                    "day": day_number,
                    "flow_kind": flow_kind,
                },
            )
            return fallback_content
        except Exception:
            logger.exception(
                "Unexpected AI personalization failure, using fallback",
                extra={
                    "patient_id": str(patient.id),
                    "day": day_number,
                    "flow_kind": flow_kind,
                },
            )
            return fallback_content

    def _build_fallback_content(
        self,
        *,
        message: Dict[str, Any],
        patient: Patient,
        content: str,
        flow_kind: str,
        day_number: int,
        message_index: Optional[int],
        expects_response: Optional[bool],
    ) -> str:
        """
        Build deterministic fallback content with light anti-repetition.

        Priority:
        1) Template-provided variations (if present)
        2) Placeholder substitution
        3) Lightweight question reformulation for response-expected prompts
        """
        candidate = self._select_template_variation(
            message=message,
            content=content,
            patient=patient,
            flow_kind=flow_kind,
            day_number=day_number,
            message_index=message_index,
        )
        personalized = self._personalize_message_simple(candidate, patient)
        if expects_response is False:
            return personalized
        return self._lightly_rephrase_question(
            personalized,
            day_number=day_number,
            message_index=message_index,
        )

    def _select_template_variation(
        self,
        *,
        message: Dict[str, Any],
        content: str,
        patient: Patient,
        flow_kind: str,
        day_number: int,
        message_index: Optional[int],
    ) -> str:
        """Pick a deterministic variation when templates provide alternatives."""
        variations = message.get("variations") if isinstance(message, dict) else None
        if not isinstance(variations, list):
            return content

        normalized_base = self._normalize_text(content)
        candidates: List[str] = []
        for raw in variations:
            if not isinstance(raw, str):
                continue
            candidate = raw.strip()
            if not candidate:
                continue
            if self._normalize_text(candidate) == normalized_base:
                continue
            if candidate in candidates:
                continue
            candidates.append(candidate)

        if not candidates:
            return content

        seed = (
            f"{patient.id}:{flow_kind}:{day_number}:"
            f"{message_index if message_index is not None else 0}"
        )
        selected_index = (
            int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(candidates)
        )
        return candidates[selected_index]

    def _lightly_rephrase_question(
        self,
        content: str,
        *,
        day_number: int,
        message_index: Optional[int],
    ) -> str:
        """Apply a subtle wrapper to reduce repetitive question phrasing."""
        question = (content or "").strip()
        if not question or "?" not in question:
            return content

        normalized = self._normalize_text(question)
        existing_prefixes = (
            "queria te perguntar:",
            "só para confirmar com você:",
            "para acompanharmos melhor:",
        )
        if normalized.startswith(existing_prefixes):
            return content

        wrappers = (
            "Queria te perguntar:",
            "Só para confirmar com você:",
            "Para acompanharmos melhor:",
        )
        offset = day_number + (message_index if isinstance(message_index, int) else 0)
        prefix = wrappers[offset % len(wrappers)]
        return f"{prefix} {question}"
    
    def _personalize_message_simple(self, content: str, patient: Patient) -> str:
        """Simple placeholder replacement (fallback)."""
        name = patient.name or patient.preferred_name or "Paciente"
        
        content = content.replace("[NOME]", name)
        content = content.replace("[nome]", name)
        content = content.replace("{patient_name}", name)
        
        return content

    def _mark_last_message_sent(self, step_data: Dict[str, Any]) -> None:
        """Persist canonical last-message timestamps."""
        timestamp = now_sao_paulo().isoformat()
        step_data["last_message_sent_at"] = timestamp
        step_data["last_message_sent"] = timestamp

    def _resolve_sent_message_id(
        self,
        *,
        patient_id: UUID,
        flow_kind: str,
        day_number: int,
        message_index: int,
    ) -> Optional[str]:
        """Resolve persisted message id for deterministic response correlation."""
        idempotency_key = self._build_idempotency_key(
            patient_id, flow_kind, day_number, message_index
        )
        try:
            message = self.message_repo.get_by_idempotency_key(patient_id, idempotency_key)
        except Exception:
            logger.exception("Failed to resolve sent message id for flow correlation")
            return None

        message_id = getattr(message, "id", None)
        return str(message_id) if message_id else None

    def _set_flow_progress(
        self,
        flow_state: PatientFlowState,
        *,
        message_index: int,
        awaiting_response: bool,
        mark_last_sent: bool = False,
        last_response_at: bool = False,
        flow_day: Optional[int] = None,
        flow_kind: Optional[str] = None,
        pending_message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist flow progress updates in a single commit."""
        step_data = flow_state.step_data or {}
        step_data["current_day_message_index"] = message_index
        step_data["awaiting_response"] = awaiting_response
        if flow_day is not None:
            step_data["current_flow_day"] = flow_day
        if flow_kind is not None:
            step_data["flow_kind"] = flow_kind

        if awaiting_response:
            step_data["pending_response_context"] = {
                "flow_day": step_data.get("current_flow_day"),
                "flow_kind": step_data.get("flow_kind"),
                "message_index": message_index,
                "prompt_message_id": pending_message_id,
            }
        else:
            step_data.pop("pending_response_context", None)

        if mark_last_sent:
            self._mark_last_message_sent(step_data)
        if last_response_at:
            step_data["last_response_at"] = now_sao_paulo().isoformat()
        flow_state.step_data = step_data
        flow_state.last_interaction_at = now_sao_paulo()
        # TODO(async-migration): sync SQLAlchemy commit in async method.
        self.db.commit()
        return step_data


def get_sequential_message_handler(db: Session) -> SequentialMessageHandler:
    """Factory function to get handler instance."""
    return SequentialMessageHandler(db)
