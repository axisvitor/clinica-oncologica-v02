"""
Message webhook handler for Evolution API integration.
Processes incoming WhatsApp messages through the flow engine.
"""

import asyncio
import logging
from typing import Any, Optional, Dict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.config.settings.cache import cache_settings
from app.models.message import Message, MessageType, MessageStatus, MessageDirection
from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.domain.messaging.core import MessageService
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository
from app.services.flow.context_parsing import (
    parse_optional_str,
)
from app.services.flow.sequential_response_gate import (
    evaluate_sequential_gate,
    should_record_processed_response,
)

# NOTE: EnhancedFlowEngine imported lazily to avoid circular import
import app.services.websocket_events as websocket_events_module
from app.schemas.websocket import WebSocketEventType
from app.schemas.message import MessageCreate
from app.integrations import get_langchain_orchestrator
from app.config import settings
from app.core.redis_manager import get_async_redis_client as get_async_redis
from app.utils.db_retry import with_db_retry
from app.services.webhook.utils.phone_normalizer import PhoneNormalizer
from app.services.webhook.utils.message_extractor import extract_message_data
from app.utils.timezone import now_sao_paulo
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LGPD Art. 18 — WhatsApp opt-out keyword detection
# ---------------------------------------------------------------------------
# Patients may revoke consent by sending any of these keywords.
# Both accented and unaccented Portuguese forms are included so the check
# is resilient to keyboard/IME differences.
OPT_OUT_KEYWORDS: frozenset[str] = frozenset(
    [
        # English
        "stop",
        # Portuguese unaccented
        "parar",
        "cancelar",
        "pare",
        "sair",
        "remover",
        "descadastrar",
        "nao quero",
        "cancela",
        "para",
        # Portuguese with accent (common mobile keyboard output)
        "não quero",
        "não",
    ]
)


def is_opt_out_message(text: str) -> bool:
    """
    Check whether an inbound message is an opt-out request.

    Case-insensitive, strips surrounding whitespace before comparing.
    Only exact matches are accepted to avoid false positives on phrases
    that happen to contain these words mid-sentence.

    Args:
        text: Raw message text received from the patient.

    Returns:
        True if the message is recognised as an opt-out keyword.
    """
    if not text:
        return False
    normalized = text.strip().lower()
    return normalized in OPT_OUT_KEYWORDS


# ---------------------------------------------------------------------------


async def handle_opt_out(patient: Patient, db: AsyncSession) -> None:
    """
    Standalone opt-out handler for any webhook endpoint (WuzAPI, Evolution, etc.).

    LGPD Art. 18 compliance flow:
    1. Stamp messaging_stopped_at immediately.
    2. Revoke active COMMUNICATION consents (best-effort).
    3. Commit the transaction.
    """
    from sqlalchemy import select as sa_select

    from app.models.consent import Consent, ConsentType, ConsentStatus
    from app.services.lgpd.consent_service import ConsentService

    now = now_sao_paulo()
    patient.messaging_stopped_at = now
    logger.info(
        "Patient %s opted out of WhatsApp messaging via STOP keyword",
        patient.id,
        extra={"patient_id": str(patient.id)},
    )

    try:
        stmt = sa_select(Consent).where(
            Consent.patient_id == patient.id,
            Consent.consent_type == ConsentType.COMMUNICATION,
            Consent.status == ConsentStatus.GRANTED,
        )
        result = await db.execute(stmt)
        active_consents = result.scalars().all()

        consent_service = ConsentService(db)
        for consent in active_consents:
            try:
                await consent_service.revoke_consent(
                    consent_id=consent.id,
                    reason="Patient opt-out via WhatsApp STOP message",
                )
                logger.info(
                    "Revoked COMMUNICATION consent %s for patient %s",
                    consent.id,
                    patient.id,
                )
            except Exception as revoke_err:
                logger.warning(
                    "Failed to revoke consent %s for patient %s (opt-out still applied): %s",
                    consent.id,
                    patient.id,
                    revoke_err,
                )
    except Exception as consent_err:
        logger.warning(
            "Failed to query consents for patient %s (opt-out still applied): %s",
            patient.id,
            consent_err,
        )

    await db.commit()


# ---------------------------------------------------------------------------


class MessageWebhookHandler:
    """
    Handler for incoming message webhooks from Evolution API.

    Responsibilities:
    1. Extract and validate message data
    2. Check idempotency (deduplicate by whatsapp_id)
    3. Find patient by phone number
    4. Create inbound message record
    5. Publish WebSocket events
    6. Route to flow or general chat handler
    """

    def __init__(self, db: Any):
        """
        Initialize message handler with required services.

        Args:
            db: Database session (AsyncSession when called from FastAPI webhook route)
        """
        self.db = db
        self.message_service = MessageService(db)
        self.patient_repo = PatientRepository(db)
        # Lazy import to avoid circular dependency
        from app.services.enhanced_flow_engine import EnhancedFlowEngine

        self.enhanced_flow_engine = EnhancedFlowEngine(db)
        self.flow_state_repo = FlowStateRepository(db)
        self.ai_client = get_langchain_orchestrator()
        self.phone_normalizer = PhoneNormalizer(self.patient_repo)

        logger.info("MessageWebhookHandler initialized")

    @with_db_retry(max_retries=3)
    async def process_message(
        self,
        event_data: Dict[str, Any],
        webhook_store: Optional[Any] = None,
        webhook_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Process incoming message webhook from Evolution API.

        Args:
            event_data: Webhook event data
            webhook_store: Optional webhook persistence store
            webhook_id: Optional webhook event ID header (for persistence)

        Returns:
            Message ID if processed successfully, None otherwise
        """
        stored_event_id = None
        try:
            # Step 0: Persist webhook event
            if webhook_store:
                if webhook_id:
                    _, stored_event_id = await webhook_store.persist_event_atomic(
                        event_id=webhook_id,
                        event_type="message.received",
                        source="evolution_api",
                        payload=event_data,
                    )
                else:
                    stored_event_id = await webhook_store.persist_event(
                        event_type="message.received",
                        source="evolution_api",
                        payload=event_data,
                    )

            # Step 1: Extract message data
            message_data = extract_message_data(event_data)
            if not message_data:
                logger.warning("No valid message data found in webhook")
                if stored_event_id and webhook_store:
                    await webhook_store.mark_processed(
                        stored_event_id, False, "No valid message data"
                    )
                return None

            whatsapp_id = message_data["whatsapp_id"]

            # FIX: Validate whatsapp_id to prevent key collision with "None"
            if not whatsapp_id:
                logger.warning("WhatsApp ID is None or empty, skipping message")
                if stored_event_id and webhook_store:
                    await webhook_store.mark_processed(
                        stored_event_id, False, "Missing WhatsApp ID"
                    )
                return None

            # Step 2: Idempotency check via atomic SET NX + DB fallback
            # FIX: Use atomic SET NX BEFORE any database operation to prevent race conditions
            # Fall back to DB-only idempotency if Redis is unavailable.
            redis_client = None
            try:
                redis_client = await get_async_redis()
            except Exception as redis_error:
                logger.error(
                    "Redis unavailable for webhook idempotency; falling back to DB-only check",
                    exc_info=True,
                    extra={
                        "instance": "message_webhook_handler",
                        "error_type": type(redis_error).__name__,
                    },
                )
            idempotency_key = f"webhook:message:{whatsapp_id}"

            if redis_client:
                # First, try to atomically acquire processing lock
                acquired = await redis_client.set(
                    idempotency_key,
                    "processing",
                    nx=True,  # Only set if doesn't exist
                    ex=cache_settings.CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS,
                )

                if not acquired:
                    # Key exists - check if it's completed or still processing
                    existing_value = await redis_client.get(idempotency_key)
                    if existing_value:
                        existing_str = (
                            existing_value.decode()
                            if isinstance(existing_value, bytes)
                            else str(existing_value)
                        )
                        if existing_str != "processing":
                            # Already completed, return the message ID
                            logger.info(
                                f"Duplicate webhook message detected (Redis): {whatsapp_id}"
                            )
                            return existing_str
                        else:
                            # Another worker is processing, wait briefly and check DB
                            logger.info(
                                f"Message {whatsapp_id} being processed by another worker, checking DB"
                            )
                            for _ in range(3):
                                await asyncio.sleep(0.2)
                                existing_message = (
                                    self.db.query(Message)
                                    .filter(Message.whatsapp_id == whatsapp_id)
                                    .first()
                                )
                                if existing_message:
                                    await redis_client.set(
                                        idempotency_key,
                                        str(existing_message.id),
                                        ex=cache_settings.CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS,
                                    )
                                    return str(existing_message.id)
                            # Another worker still owns processing. Exit early to
                            # avoid duplicate inbound creation; retry flow will
                            # pick it up if the owner fails before commit.
                            logger.info(
                                "Message %s still in processing lock; deferring duplicate worker",
                                whatsapp_id,
                            )
                            return None

            # DB fallback check (also catches race condition edge cases)
            existing_message = (
                self.db.query(Message)
                .filter(Message.whatsapp_id == whatsapp_id)
                .first()
            )

            if existing_message:
                logger.info(f"Duplicate webhook message detected (DB): {whatsapp_id}")
                # Update Redis with actual message ID (best-effort)
                if redis_client:
                    await redis_client.set(
                        idempotency_key,
                        str(existing_message.id),
                        ex=cache_settings.CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS,
                    )
                return str(existing_message.id)

            # Step 3: Find patient with security monitoring
            patient = await self._find_patient_with_security(
                message_data, stored_event_id, webhook_store
            )
            if not patient:
                return None

            # Step 3b: LGPD Art. 18 — opt-out interception
            # Must run BEFORE any flow advancement or message creation so that
            # no outbound response is triggered after the revocation is recorded.
            if is_opt_out_message(message_data.get("content", "")):
                await self._handle_opt_out(patient)
                if stored_event_id and webhook_store:
                    await webhook_store.mark_processed(stored_event_id, True)
                return None  # Do not advance flow or create any outbound message

            # Step 4: Check flow status and add context
            active_flow = self.flow_state_repo.get_active_flow(patient.id)
            metadata = message_data.get("metadata", {})

            if active_flow:
                step_data = active_flow.step_data or {}
                metadata["context"] = "flow"
                metadata["flow_state_id"] = str(active_flow.id)
                metadata["current_step"] = active_flow.current_step
                metadata["flow_kind"] = step_data.get("flow_kind") or active_flow.flow_type
                metadata["flow_day"] = step_data.get("current_flow_day")
                metadata["message_index"] = step_data.get("current_day_message_index")
                metadata["awaiting_response"] = step_data.get("awaiting_response")
            else:
                metadata["context"] = "general_chat"

            # Step 5: Create inbound message record
            message = self.message_service.process_inbound_message(
                patient_id=patient.id,
                content=message_data["content"],
                whatsapp_id=whatsapp_id,
                message_type=message_data["type"],
                message_metadata=metadata,
            )

            # FIX: Update Redis key with message ID (replacing "processing" value)
            # This marks the message as fully processed with its actual ID
            if redis_client:
                await redis_client.set(
                    idempotency_key,
                    str(message.id),
                    ex=cache_settings.CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS,
                )

            logger.info(
                f"Processed inbound message {message.id} from patient {patient.id}",
                extra={
                    "message_id": str(message.id),
                    "patient_id": str(patient.id),
                    "context": metadata["context"],
                },
            )

            # Step 6: Publish WebSocket event
            await self._publish_message_event(message, patient.id)

            # Step 7: Route to appropriate handler
            if active_flow:
                await self._handle_flow_message(patient, message, active_flow)
            else:
                await self._handle_general_chat(patient, message)

            # Step 8: Mark webhook as processed
            if stored_event_id and webhook_store:
                await webhook_store.mark_processed(stored_event_id, True)

            return str(message.id)

        except Exception as e:
            logger.error(f"Error processing message webhook: {e}", exc_info=True)
            if stored_event_id and webhook_store:
                await webhook_store.mark_processed(stored_event_id, False, str(e))
            return None

    async def _find_patient_with_security(
        self,
        message_data: Dict[str, Any],
        webhook_id: Optional[UUID],
        webhook_store: Optional[Any],
    ) -> Optional[Patient]:
        """
        Find patient by phone with security monitoring for unauthorized access.

        Args:
            message_data: Extracted message data
            webhook_id: Webhook event ID
            webhook_store: Webhook persistence store

        Returns:
            Patient or None if not found/blocked
        """
        metadata = message_data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        remote_jid = parse_optional_str(metadata.get("remote_jid")) or ""
        remote_jid_alt = parse_optional_str(metadata.get("remote_jid_alt")) or ""
        instance_name = parse_optional_str(metadata.get("instance_name"))
        phone = self.phone_normalizer.clean_phone_number(message_data["phone"])
        patient = self.phone_normalizer.find_patient_by_phone(phone)

        if patient:
            return patient

        # Evolution official payload can include remoteJidAlt for LID addressed chats.
        # Prefer this direct phone JID before network-based LID resolution.
        if remote_jid_alt:
            alt_phone = self.phone_normalizer.clean_phone_number(remote_jid_alt)
            if alt_phone and alt_phone != phone:
                patient = self.phone_normalizer.find_patient_by_phone(alt_phone)
                if patient:
                    message_data["phone"] = alt_phone
                    metadata["resolved_from_remote_jid_alt"] = True
                    metadata["resolved_phone"] = alt_phone
                    message_data["metadata"] = metadata
                    return patient

        # Evolution can deliver inbound as @lid while the patient is registered by phone.
        # Try to resolve the LID to a phone JID before classifying as unauthorized.
        if remote_jid.endswith("@lid"):
            resolved_phone = await self.phone_normalizer.resolve_phone_from_lid(
                remote_jid, instance_name=instance_name
            )
            if resolved_phone:
                phone = self.phone_normalizer.clean_phone_number(resolved_phone)
                patient = self.phone_normalizer.find_patient_by_phone(phone)
                if patient:
                    message_data["phone"] = phone
                    metadata["resolved_from_lid"] = True
                    metadata["resolved_phone"] = phone
                    message_data["metadata"] = metadata
                    return patient
            else:
                logger.warning(
                    "Skipping unauthorized handling for unresolved LID sender",
                    extra={"remote_jid": remote_jid, "instance_name": instance_name},
                )
                if webhook_id and webhook_store:
                    await webhook_store.mark_processed(
                        webhook_id,
                        False,
                        "Unable to resolve LID sender to patient phone",
                    )
                return None

        # Patient not found - handle unauthorized access
        from app.services.security_monitor import SecurityMonitor

        security_monitor = SecurityMonitor(self.db)

        # Log unauthorized access attempt
        await security_monitor.log_unauthorized_access(
            phone=message_data["phone"],
            message_content=message_data["content"][:100],
            source_metadata={
                "whatsapp_id": message_data["whatsapp_id"],
                "timestamp": message_data.get("metadata", {}).get("timestamp"),
                "push_name": message_data.get("metadata", {}).get("pushName"),
            },
        )

        # Check if phone should be blocked
        should_block = await security_monitor.should_block_phone(message_data["phone"])
        if should_block:
            logger.warning(
                "Phone blocked due to repeated unauthorized attempts",
                extra={"phone": message_data["phone"][:6] + "****"},
            )
            if webhook_id and webhook_store:
                await webhook_store.mark_processed(
                    webhook_id, False, "Phone blocked - too many unauthorized attempts"
                )
            return None

        # Get attempt count and send appropriate response
        attempt_count = await security_monitor.get_attempt_count(message_data["phone"])

        logger.warning(
            f"Unauthorized access attempt (#{attempt_count})",
            extra={
                "phone": message_data["phone"][:6] + "****",
                "content_preview": message_data["content"][:30] + "...",
            },
        )

        # Send response only for first 3 attempts
        if attempt_count <= 3:
            await self._send_unauthorized_response(message_data["phone"], attempt_count)

        if webhook_id and webhook_store:
            await webhook_store.mark_processed(
                webhook_id,
                False,
                f"Unauthorized: patient not found (attempt {attempt_count})",
            )

        return None

    async def _handle_opt_out(self, patient: Patient) -> None:
        """
        Handle a WhatsApp opt-out request from a patient.

        LGPD Art. 18 compliance flow:
        1. Stamp messaging_stopped_at immediately (primary, must succeed).
        2. Revoke any active COMMUNICATION consents via ConsentService
           (secondary — failure is logged but does NOT prevent the opt-out).
        3. Commit the transaction.

        The opt-out is resilient: if the patient has no formal consent
        record, or revocation of a specific record fails, the
        messaging_stopped_at timestamp is still persisted.

        Args:
            patient: Patient instance who sent the opt-out keyword.
        """
        now = now_sao_paulo()
        patient.messaging_stopped_at = now
        logger.info(
            "Patient %s opted out of WhatsApp messaging via STOP keyword",
            patient.id,
            extra={"patient_id": str(patient.id)},
        )

        # Attempt to revoke active COMMUNICATION consents (best-effort)
        try:
            from app.models.consent import Consent, ConsentType, ConsentStatus
            from app.services.lgpd.consent_service import ConsentService

            active_consents = (
                self.db.query(Consent)
                .filter(
                    Consent.patient_id == patient.id,
                    Consent.consent_type == ConsentType.COMMUNICATION,
                    Consent.status == ConsentStatus.GRANTED,
                )
                .all()
            )

            consent_service = ConsentService(self.db)
            for consent in active_consents:
                try:
                    await consent_service.revoke_consent(
                        consent_id=consent.id,
                        reason="Patient opt-out via WhatsApp STOP message",
                    )
                    logger.info(
                        "Revoked COMMUNICATION consent %s for patient %s",
                        consent.id,
                        patient.id,
                    )
                except Exception as revoke_err:
                    logger.warning(
                        "Failed to revoke consent %s for patient %s (opt-out still applied): %s",
                        consent.id,
                        patient.id,
                        revoke_err,
                    )

        except Exception as consent_err:
            logger.warning(
                "Could not query consents for patient %s during opt-out (opt-out still applied): %s",
                patient.id,
                consent_err,
            )

        # Persist the opt-out timestamp regardless of consent revocation outcome
        try:
            self.db.commit()
        except Exception as commit_err:
            logger.error(
                "Failed to commit opt-out for patient %s: %s",
                patient.id,
                commit_err,
                exc_info=True,
            )
            self.db.rollback()

    async def _handle_flow_message(
        self, patient: Patient, message: Message, flow_state: PatientFlowState
    ) -> None:
        """
        Handle message within active flow context.

        Args:
            patient: Patient record
            message: Inbound message
            flow_state: Active flow state
        """
        try:
            # Check for active quiz session
            from app.services.quiz import QuizSessionService

            quiz_session_service = QuizSessionService(self.db)
            active_quiz_session = quiz_session_service.get_active_session(patient.id)

            if active_quiz_session:
                logger.info(f"Routing message to quiz handler for patient {patient.id}")
                await self._handle_quiz_message(patient, message, active_quiz_session)
                return

            # Calculate current day
            current_day = await self.enhanced_flow_engine.calculate_patient_day(
                patient.id
            )

            # Process response through enhanced flow engine
            # Note: process_patient_response calculates current_day internally
            # Returns: status, sentiment_analysis, engagement_score, follow_up_message, requires_attention, medical_concerns
            step_data = flow_state.step_data or {}
            message_metadata = getattr(message, "message_metadata", None)
            if not isinstance(message_metadata, dict):
                message_metadata = getattr(message, "metadata", None)
            if not isinstance(message_metadata, dict):
                message_metadata = {}
            raw_flow_context = message_metadata.get("flow_context")
            flow_context = raw_flow_context if isinstance(raw_flow_context, dict) else {}
            pending_response_context = step_data.get("pending_response_context")
            if not isinstance(pending_response_context, dict):
                pending_response_context = {}
            prompt_message_id = parse_optional_str(
                flow_context.get("prompt_message_id")
                or message_metadata.get("prompt_message_id")
                or pending_response_context.get("prompt_message_id")
            )
            response_context = {
                "flow_day": step_data.get("current_flow_day"),
                "flow_kind": step_data.get("flow_kind"),
                "message_index": step_data.get("current_day_message_index"),
                "awaiting_response": step_data.get("awaiting_response"),
                "prompt_message_id": prompt_message_id,
                "response_message_id": str(message.id),
            }
            response_context = {
                key: value for key, value in response_context.items() if value is not None
            }
            # Continue sequential flow first so webhook latency doesn't block the next prompt.
            sequential_result = await self._trigger_sequential_continuation(
                patient.id,
                response_context=response_context,
            )
            status = (
                sequential_result.get("status")
                if isinstance(sequential_result, dict)
                else None
            )
            should_advance = bool(
                isinstance(sequential_result, dict)
                and sequential_result.get("advance_allowed")
            )

            # Advance flow only for valid day-completion progressions.
            if should_advance:
                advancement = await self.enhanced_flow_engine.advance_patient_flow(
                    patient_id=patient.id
                )
                logger.info(
                    f"Flow advanced for patient {patient.id}: {advancement}",
                    extra={
                        "patient_id": str(patient.id),
                        "status": status,
                    },
                )
            else:
                logger.info(
                    "Skipping flow advance due to progression gate",
                    extra={
                        "patient_id": str(patient.id),
                        "status": status,
                        "reason": sequential_result.get("reason")
                        if isinstance(sequential_result, dict)
                        else None,
                    },
                )

            # AI response analysis is optional and disabled inline by default to keep
            # webhook latency low. Sequential continuation remains the primary path.
            response: Dict[str, Any] = {}
            inline_analysis_enabled = bool(
                getattr(settings, "WHATSAPP_PROCESS_RESPONSE_ANALYSIS_INLINE", False)
            )
            if inline_analysis_enabled:
                analysis_timeout = int(
                    max(1, min(getattr(settings, "WHATSAPP_FLOW_RESPONSE_TIMEOUT_SECONDS", 8), 8))
                )
                try:
                    maybe_response = await asyncio.wait_for(
                        self.enhanced_flow_engine.process_patient_response(
                            patient_id=patient.id,
                            response_text=message.content,
                            response_context=response_context,
                        ),
                        timeout=analysis_timeout,
                    )
                    if isinstance(maybe_response, dict):
                        response = maybe_response
                except asyncio.TimeoutError:
                    logger.warning(
                        "Timed out processing patient response analysis; sequential flow already continued",
                        extra={
                            "patient_id": str(patient.id),
                            "timeout_seconds": analysis_timeout,
                        },
                    )
                except Exception as analysis_error:
                    logger.warning(
                        "Patient response analysis failed; sequential flow already continued",
                        extra={
                            "patient_id": str(patient.id),
                            "error_type": type(analysis_error).__name__,
                        },
                        exc_info=True,
                    )

            # Send follow-up response if generated by AI (typically for attention cases)
            if response.get("follow_up_message"):
                await self._send_response(
                    patient_id=patient.id,
                    content=response["follow_up_message"],
                    metadata={
                        "context": "flow",
                        "flow_state_id": str(flow_state.id),
                        "current_day": current_day,
                        "response_to": str(message.id),
                        "requires_attention": response.get("requires_attention", False),
                    },
                )

        except Exception as e:
            logger.error(
                f"Error handling flow message for patient {patient.id}: {e}",
                exc_info=True,
            )

    @staticmethod
    def _should_record_processed_response(
        *,
        status: Optional[str],
        reason: Optional[str],
    ) -> bool:
        """Return whether the inbound response should be marked as consumed."""
        return should_record_processed_response(status=status, reason=reason)

    def _evaluate_sequential_gate(
        self, step_data: dict[str, Any], response_context: Optional[dict[str, Any]]
    ) -> tuple[bool, str, dict[str, Any]]:
        """Validate that an inbound response matches the pending flow prompt."""
        return evaluate_sequential_gate(step_data, response_context)

    async def _trigger_sequential_continuation(
        self, patient_id: UUID, response_context: Optional[dict[str, Any]] = None
    ) -> Optional[dict]:
        """Send next flow message when we're waiting for a patient response."""
        try:
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                return {"status": "no_active_flow", "advance_allowed": False}

            step_data = flow_state.step_data or {}
            gate_allowed, gate_reason, normalized_context = self._evaluate_sequential_gate(
                step_data, response_context
            )
            if not gate_allowed:
                logger.info(
                    "Skipping sequential continuation due to progression gate",
                    extra={
                        "patient_id": str(patient_id),
                        "reason": gate_reason,
                        "response_context": normalized_context,
                    },
                )
                status = "not_awaiting" if gate_reason == "not_awaiting_response" else "context_mismatch"
                return {
                    "status": status,
                    "reason": gate_reason,
                    "advance_allowed": False,
                }

            from app.services.flow.sequential_message_handler import (
                SequentialMessageHandler,
            )

            handler = SequentialMessageHandler(self.db)
            result = await handler.handle_response_and_continue(
                patient_id, response_context=normalized_context
            )
            status = result.get("status") if isinstance(result, dict) else None

            if status in {"waiting", "day_complete", "complete"}:
                logger.info(
                    "Sequential flow progressed after response",
                    extra={"patient_id": str(patient_id), "status": status},
                )

            result_reason = result.get("reason") if isinstance(result, dict) else None
            response_message_id = normalized_context.get("response_message_id")
            if response_message_id and self._should_record_processed_response(
                status=status,
                reason=result_reason,
            ):
                latest_flow_state = self.flow_state_repo.get_active_flow(patient_id)
                if latest_flow_state:
                    latest_step_data = dict(latest_flow_state.step_data or {})
                    latest_step_data["last_processed_response_message_id"] = (
                        response_message_id
                    )
                    latest_flow_state.step_data = latest_step_data
                    flag_modified(latest_flow_state, "step_data")
                    self.db.commit()

            if status in {"day_complete", "complete"}:
                await self._send_deferred_followups(patient_id)
            if isinstance(result, dict):
                result.setdefault("advance_allowed", status in {"day_complete", "complete"})
            return result
        except Exception as e:
            logger.error(
                f"Failed to continue sequential flow for patient {patient_id}: {e}",
                exc_info=True,
            )
            return {"status": "error", "message": str(e), "advance_allowed": False}

    async def _send_deferred_followups(self, patient_id: UUID) -> None:
        """Send any deferred follow-up messages after the day is complete."""
        try:
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                return

            # Copy to plain dict to avoid MutableDict flagging on detached state
            step_data = dict(flow_state.step_data or {})
            deferred_raw = list(step_data.get("deferred_followups") or [])
            if not deferred_raw:
                return

            seen = set()
            deferred = []
            for item in deferred_raw:
                key = (
                    (item or {}).get("type"),
                    (item or {}).get("reminder_id"),
                    (item or {}).get("message"),
                )
                if key in seen:
                    continue
                seen.add(key)
                deferred.append(item)

            remaining = []
            for item in deferred:
                content = (item or {}).get("message")
                if not content:
                    continue

                metadata = {
                    "context": "deferred_followup",
                    "type": (item or {}).get("type"),
                    "reminder_id": (item or {}).get("reminder_id"),
                    "flow_state_id": str(flow_state.id),
                    "flow_day": step_data.get("current_flow_day"),
                    "flow_kind": step_data.get("flow_kind"),
                }
                sent_message = await self._send_response(
                    patient_id=patient_id,
                    content=content,
                    metadata=metadata,
                )
                if not sent_message:
                    remaining.append(item)

            if remaining:
                step_data["deferred_followups"] = remaining
            else:
                step_data.pop("deferred_followups", None)
            flow_state.step_data = step_data
            flag_modified(flow_state, "step_data")
            self.db.commit()
        except Exception as exc:
            logger.error(
                f"Failed to send deferred follow-ups for patient {patient_id}: {exc}",
                exc_info=True,
            )

    async def _handle_quiz_message(
        self, patient: Patient, message: Message, quiz_session: Any
    ) -> None:
        """
        Handle message within active quiz context with debouncing.

        HIGH-005 FIX: Implements debouncing to prevent duplicate responses.

        Args:
            patient: Patient record
            message: Inbound message
            quiz_session: Active quiz session
        """
        try:
            from app.domain.quizzes.integration.flow_integration.utils import (
                process_quiz_response_with_debounce,
            )

            current_question_id = (
                quiz_session.current_question
                if hasattr(quiz_session, "current_question")
                and quiz_session.current_question
                else str(quiz_session.current_question_index)
                if hasattr(quiz_session, "current_question_index")
                else "unknown"
            )

            result = await process_quiz_response_with_debounce(
                self.db,
                patient_id=patient.id,
                quiz_session_id=quiz_session.id,
                current_question_id=str(current_question_id),
                response_text=message.content,
                message_metadata={
                    "message_id": str(message.id),
                    "whatsapp_id": message.whatsapp_id,
                    "patient_id": str(patient.id),
                },
            )

            if result.get("action") == "debounced":
                logger.info(
                    f"Quiz response debounced for patient {patient.id}",
                    extra={
                        "patient_id": str(patient.id),
                        "session_id": str(quiz_session.id),
                        "reason": "duplicate_within_3s_window",
                    },
                )
                return

            logger.info(
                f"Quiz response processed for patient {patient.id}: action={result.get('action')}"
            )

        except Exception as e:
            logger.error(
                f"Error handling quiz message for patient {patient.id}: {e}",
                exc_info=True,
            )

    async def _handle_general_chat(self, patient: Patient, message: Message) -> None:
        """
        Handle general chat message (no active flow).

        Args:
            patient: Patient record
            message: Inbound message
        """
        try:
            # Get conversation history for context
            history = self.message_service.get_conversation_history(
                patient_id=patient.id, limit=10
            )
            conversation_history = [m.content for m in history if m.content]

            # Build patient context
            patient_context = {
                "patient_id": str(patient.id),
                "name": patient.name,
                "phone": patient.phone,
                "treatment_type": getattr(patient, "treatment_type", None),
                "diagnosis": getattr(patient, "diagnosis", None),
            }

            # Generate AI response
            ai_response = await self.ai_client.generate_contextual_response(
                patient_message=message.content,
                patient_context=patient_context,
                conversation_history=conversation_history,
            )

            # Send response
            await self._send_response(
                patient_id=patient.id,
                content=ai_response,
                metadata={"context": "general_chat", "response_to": str(message.id)},
            )

        except Exception as e:
            logger.error(
                f"Error handling general chat for patient {patient.id}: {e}",
                exc_info=True,
            )

    async def _send_response(
        self, patient_id: UUID, content: str, metadata: Dict[str, Any]
    ) -> Optional[Message]:
        """
        Create and send response message.

        FIX P0-2: Creates ONE message, then schedules it.

        Args:
            patient_id: Patient ID
            content: Response content
            metadata: Message metadata

        Returns:
            Created message or None
        """
        try:
            # Step 1: Create outbound message
            response_data = MessageCreate(
                patient_id=patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=content,
                message_metadata=metadata,
                status=MessageStatus.PENDING,
            )

            response_message = self.message_service.create_message(response_data)
            logger.info(
                f"Created message {response_message.id} for patient {patient_id}"
            )

            # Step 2: Publish WebSocket event
            await self._publish_message_event(response_message, patient_id)

            # Step 3: Schedule for delivery
            from app.domain.messaging.scheduling import MessageScheduler

            scheduler = MessageScheduler(self.db)

            send_time = now_sao_paulo() + timedelta(seconds=1)
            await scheduler.schedule_existing_message(
                message_id=response_message.id, send_time=send_time, priority="high"
            )

            logger.info(f"Scheduled message {response_message.id} for delivery")
            return response_message

        except Exception as e:
            logger.error(f"Error sending response: {e}", exc_info=True)
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(
                    f"Failed to rollback transaction after error: {rollback_error}",
                    exc_info=True,
                )
            return None

    async def _send_unauthorized_response(
        self, phone: str, attempt_count: int = 1
    ) -> None:
        """
        Send escalating unauthorized messages to non-registered numbers.

        Args:
            phone: Phone number
            attempt_count: Number of attempts (1-3)
        """
        try:
            from app.integrations.evolution import get_evolution_client

            client = await get_evolution_client()
            if not client:
                logger.warning("Evolution client unavailable")
                return

            # Escalating messages based on attempt count
            messages = {
                1: (
                    "Olá! Este número não está cadastrado no sistema de acompanhamento da clínica. "
                    "Para informações sobre cadastro, entre em contato com a recepção pelos telefones oficiais."
                ),
                2: (
                    "ATENÇÃO: Este número não tem autorização para acessar o sistema da clínica. "
                    "Se você é paciente, verifique se está usando o número correto cadastrado."
                ),
                3: (
                    "ALERTA DE SEGURANÇA: Múltiplas tentativas de acesso não autorizado detectadas. "
                    "Este número será temporariamente bloqueado."
                ),
            }

            message = messages.get(attempt_count, messages[3])
            delay = min(1000 * attempt_count, 5000)

            await client.send_text_message(phone, message, delay=delay)

            logger.info(
                f"Sent unauthorized response (attempt #{attempt_count})",
                extra={"phone": phone[:6] + "****", "attempt": attempt_count},
            )

        except Exception as e:
            logger.error(f"Failed to send unauthorized response: {e}")

    async def _publish_message_event(self, message: Message, patient_id: UUID) -> None:
        """
        Publish WebSocket event for message.

        Args:
            message: Message to publish
            patient_id: Patient ID
        """
        websocket_events = websocket_events_module.websocket_events
        if not websocket_events:
            logger.debug("WebSocket events service unavailable; skipping message event")
            return
        await websocket_events.broadcast_message_event(
            event_type=WebSocketEventType.NEW_MESSAGE,
            message_data={
                "message_id": message.id,
                "patient_id": patient_id,
                "direction": message.direction.value,
                "type": message.type.value,
                "content": message.content,
                "whatsapp_id": message.whatsapp_id,
                "metadata": message.message_metadata or {},
            },
        )
