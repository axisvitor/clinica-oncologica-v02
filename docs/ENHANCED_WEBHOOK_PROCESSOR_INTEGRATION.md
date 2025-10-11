# Enhanced Webhook Processor Integration

## Overview
Integration plan for enhancing the existing webhook processor with strict patient authorization while maintaining the recent improvements (rate limiting, unauthorized responses).

## Current State Analysis

### Recent Improvements Detected:
1. **Rate Limiting**: Lines 142-147 add rate limiting for unauthorized attempts (5 per hour)
2. **Unauthorized Response**: Lines 148-150 send responses for first 3 attempts
3. **Enhanced Logging**: Lines 153-159 mark webhooks as processed with failure details

### Integration Strategy:
**Enhance existing logic** rather than replace it to maintain backwards compatibility and recent improvements.

## Enhanced Webhook Processor Implementation

```python
# File: app/services/enhanced_webhook_processor.py
"""
Enhanced Webhook Processor with Strict Patient Authorization

Builds upon existing webhook_processor.py with additional security layers
while maintaining compatibility with recent improvements.
"""
import logging
from typing import Any, Optional
from uuid import UUID

from app.services.webhook_processor import WebhookProcessor
from app.services.patient_phone_security import PhoneNumberSecurityService
from app.services.whatsapp_security_audit import WhatsAppSecurityAuditService
from app.config import settings

logger = logging.getLogger(__name__)

class EnhancedWebhookProcessor(WebhookProcessor):
    """
    Enhanced webhook processor with strict patient authorization.

    Extends the base WebhookProcessor with:
    - Strict patient authorization enforcement
    - Enhanced security logging
    - Real-time security monitoring
    - Improved phone number validation
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.phone_security = PhoneNumberSecurityService(self.db)
        self.security_audit = WhatsAppSecurityAuditService(self.db)

        # Security configuration
        self.strict_mode = getattr(settings, 'WHATSAPP_STRICT_PATIENT_MODE', True)
        self.security_logging = getattr(settings, 'WHATSAPP_SECURITY_LOGGING', True)

        logger.info(
            f"Enhanced webhook processor initialized: "
            f"strict_mode={self.strict_mode}, security_logging={self.security_logging}"
        )

    async def process_message_webhook(self, event_data: dict[str, Any]) -> Optional[str]:
        """
        Enhanced message processing with strict patient authorization.

        Maintains existing logic but adds comprehensive security validation.
        """
        webhook_id = None
        try:
            # Step 0: Persist webhook event (existing logic)
            webhook_id = await self._persist_webhook_event(
                event_type="message.received",
                source="evolution_api",
                payload=event_data
            )

            # Step 1: Extract message data (existing logic)
            message_data = self._extract_message_data(event_data)
            if not message_data:
                logger.warning("No valid message data found in webhook")
                if webhook_id:
                    await self._mark_webhook_processed(webhook_id, False, "No valid message data")
                return None

            whatsapp_id = message_data["whatsapp_id"]

            # Step 2: Enhanced security validation
            security_result = await self._validate_phone_security(
                message_data["phone"],
                webhook_id,
                event_data
            )

            if not security_result["authorized"]:
                # Security block - comprehensive logging and response
                return await self._handle_security_block(
                    security_result,
                    message_data,
                    webhook_id
                )

            # Get authorized patient from security validation
            patient = security_result["patient"]

            # Step 3: Idempotency check (existing logic - enhanced with security metadata)
            existing_message_id = await self._check_message_idempotency(
                whatsapp_id,
                patient.id
            )
            if existing_message_id:
                # Log successful authorization for existing message
                if self.security_logging:
                    await self.security_audit.log_authorization_event(
                        phone_number=security_result["normalized_phone"],
                        patient_id=patient.id,
                        event_type="AUTHORIZED_DUPLICATE",
                        webhook_path="/webhooks/evolution/message",
                        metadata={"existing_message_id": existing_message_id}
                    )
                return existing_message_id

            # Continue with existing flow processing...
            # [Rest of the existing logic remains the same]

            # Step 4: Process the message (existing logic)
            return await self._process_authorized_message(
                patient,
                message_data,
                whatsapp_id,
                webhook_id,
                security_result
            )

        except Exception as e:
            logger.error(f"Error in enhanced message processing: {e}", exc_info=True)
            if webhook_id:
                await self._mark_webhook_processed(webhook_id, False, str(e))
            return None

    async def _validate_phone_security(
        self,
        raw_phone: str,
        webhook_id: Optional[UUID],
        event_data: dict
    ) -> dict[str, Any]:
        """
        Comprehensive phone number security validation.

        Returns:
            {
                "authorized": bool,
                "patient": Optional[Patient],
                "normalized_phone": str,
                "security_events": list,
                "block_reason": Optional[str]
            }
        """
        try:
            # Step 1: Normalize phone number securely
            try:
                normalized_phone = self.phone_security.normalize_phone_secure(raw_phone)
            except Exception as e:
                logger.warning(f"Phone normalization failed: {raw_phone} - {e}")
                return {
                    "authorized": False,
                    "patient": None,
                    "normalized_phone": raw_phone,
                    "security_events": ["PHONE_NORMALIZATION_FAILED"],
                    "block_reason": f"Invalid phone format: {e}"
                }

            # Step 2: Get authorized patient
            patient = await self.phone_security.get_authorized_patient(normalized_phone)

            if patient:
                # AUTHORIZED
                if self.security_logging:
                    await self.security_audit.log_authorization_event(
                        phone_number=normalized_phone,
                        patient_id=patient.id,
                        event_type="AUTHORIZED",
                        webhook_path="/webhooks/evolution/message",
                        metadata={
                            "patient_name": patient.name,
                            "webhook_id": str(webhook_id) if webhook_id else None,
                            "raw_phone": raw_phone
                        }
                    )

                return {
                    "authorized": True,
                    "patient": patient,
                    "normalized_phone": normalized_phone,
                    "security_events": ["AUTHORIZED"],
                    "block_reason": None
                }
            else:
                # NOT AUTHORIZED
                if self.security_logging:
                    await self.security_audit.log_authorization_event(
                        phone_number=normalized_phone,
                        patient_id=None,
                        event_type="UNAUTHORIZED_PHONE",
                        webhook_path="/webhooks/evolution/message",
                        metadata={
                            "webhook_id": str(webhook_id) if webhook_id else None,
                            "raw_phone": raw_phone,
                            "event_data_keys": list(event_data.keys())
                        }
                    )

                return {
                    "authorized": False,
                    "patient": None,
                    "normalized_phone": normalized_phone,
                    "security_events": ["UNAUTHORIZED_PHONE"],
                    "block_reason": f"Phone number {normalized_phone} not registered as patient"
                }

        except Exception as e:
            logger.error(f"Security validation error for phone {raw_phone}: {e}")
            return {
                "authorized": False,
                "patient": None,
                "normalized_phone": raw_phone,
                "security_events": ["SECURITY_VALIDATION_ERROR"],
                "block_reason": f"Security validation failed: {e}"
            }

    async def _handle_security_block(
        self,
        security_result: dict,
        message_data: dict,
        webhook_id: Optional[UUID]
    ) -> None:
        """
        Handle security block with comprehensive logging and response.

        Maintains existing rate limiting logic while adding enhanced security.
        """
        phone = security_result["normalized_phone"]
        block_reason = security_result["block_reason"]

        logger.warning(f"SECURITY BLOCK: {block_reason} for phone {phone}")

        # Use existing rate limiting logic (enhanced)
        redis_client = await get_async_redis()
        rate_limit_key = f"unauthorized:ratelimit:{phone}"

        # Enhanced rate limiting with security metadata
        attempt_count = await redis_client.incr(rate_limit_key)
        if attempt_count == 1:
            await redis_client.expire(rate_limit_key, 3600)  # 1 hour

        # Store security metadata in Redis
        security_key = f"unauthorized:security:{phone}"
        security_metadata = {
            "last_attempt": datetime.utcnow().isoformat(),
            "block_reason": block_reason,
            "attempt_count": attempt_count,
            "security_events": security_result["security_events"]
        }
        await redis_client.setex(security_key, 3600, json.dumps(security_metadata))

        # Send response for first few attempts (existing logic)
        if attempt_count <= 3:
            await self._send_enhanced_unauthorized_response(
                phone,
                attempt_count,
                block_reason
            )

        # Enhanced webhook processing result
        if webhook_id:
            await self._mark_webhook_processed(
                webhook_id,
                False,
                f"SECURITY_BLOCK: {block_reason} (attempt {attempt_count})"
            )

        return None

    async def _send_enhanced_unauthorized_response(
        self,
        phone: str,
        attempt_count: int,
        block_reason: str
    ) -> None:
        """
        Send enhanced unauthorized response with security context.
        """
        try:
            if self.strict_mode:
                # Strict mode: No response to unauthorized numbers
                logger.info(f"Strict mode: No response sent to unauthorized phone {phone}")
                return

            # Permissive mode: Send informative response
            response_text = (
                f"⚠️ Este número não está autorizado para comunicação WhatsApp. "
                f"Entre em contato com a clínica para registrar seu número. "
                f"(Tentativa {attempt_count}/3)"
            )

            # Use existing message sending infrastructure
            await self._send_response(
                patient_id=None,  # No patient for unauthorized numbers
                content=response_text,
                metadata={
                    "context": "security_block",
                    "block_reason": block_reason,
                    "attempt_count": attempt_count,
                    "unauthorized_phone": phone
                }
            )

        except Exception as e:
            logger.error(f"Error sending unauthorized response to {phone}: {e}")

    async def _process_authorized_message(
        self,
        patient: Patient,
        message_data: dict,
        whatsapp_id: str,
        webhook_id: Optional[UUID],
        security_result: dict
    ) -> str:
        """
        Process message from authorized patient (existing logic enhanced).
        """
        # Continue with existing message processing logic
        # Enhanced with security metadata

        metadata = message_data.get("metadata", {})
        metadata.update({
            "security_validated": True,
            "patient_authorized": True,
            "normalized_phone": security_result["normalized_phone"],
            "security_events": security_result["security_events"]
        })

        # Check flow status and add context (existing logic)
        active_flow = self.flow_state_repo.get_active_flow(patient.id)

        if active_flow:
            flow_type = self._get_flow_type_from_state(active_flow)
            metadata.update({
                "context": "flow",
                "flow_type": flow_type,
                "flow_state_id": str(active_flow.id),
                "current_step": active_flow.current_step
            })
        else:
            metadata["context"] = "general_chat"

        # Create inbound message record (existing logic)
        message = self.message_service.process_inbound_message(
            patient_id=patient.id,
            content=message_data["content"],
            whatsapp_id=whatsapp_id,
            message_type=message_data["type"],
            message_metadata=metadata,
        )

        # Cache message_id for idempotency (existing logic)
        redis_client = await get_async_redis()
        idempotency_key = f"webhook:message:{whatsapp_id}"
        await redis_client.setex(idempotency_key, 3600, str(message.id))

        logger.info(
            f"Processed authorized message {message.id} from patient {patient.id} "
            f"(context: {metadata['context']}, security_validated: True)"
        )

        # Publish WebSocket event (existing logic)
        await self._publish_message_event(message, patient.id)

        # Route to handler (existing logic)
        if active_flow:
            await self._handle_flow_message(patient, message, active_flow)
        else:
            await self._handle_general_chat(patient, message)

        # Mark webhook as processed (existing logic)
        if webhook_id:
            await self._mark_webhook_processed(webhook_id, True)

        return str(message.id)
```

## Integration Steps

### Phase 1: Preparation (1-2 days)
1. **Database Migration**: Create security tables
2. **Service Creation**: Implement PhoneNumberSecurityService and WhatsAppSecurityAuditService
3. **Testing Setup**: Create test environment with security features

### Phase 2: Core Implementation (2-3 days)
1. **Enhanced Processor**: Implement EnhancedWebhookProcessor
2. **Middleware Integration**: Add PatientAuthorizationMiddleware
3. **Configuration**: Add security settings to config

### Phase 3: Integration & Testing (2-3 days)
1. **Replace Processor**: Switch to enhanced webhook processor
2. **End-to-End Testing**: Test all scenarios (authorized, unauthorized, edge cases)
3. **Monitoring Setup**: Configure security alerting

### Phase 4: Production Deployment (1 day)
1. **Feature Flags**: Deploy with feature flags for gradual rollout
2. **Monitoring**: Monitor security events and performance
3. **Documentation**: Update operational procedures

## Backwards Compatibility

### Maintained Features:
- All existing webhook processing logic
- Rate limiting for unauthorized attempts
- Unauthorized response messages (configurable)
- Webhook event persistence
- Message idempotency
- Flow processing logic

### Enhanced Features:
- Strict patient authorization (configurable)
- Comprehensive security logging
- Real-time security monitoring
- Enhanced phone number validation
- Security event tracking

### Configuration Options:
```python
# settings.py additions
WHATSAPP_STRICT_PATIENT_MODE = True  # False for permissive mode
WHATSAPP_SECURITY_LOGGING = True     # Enable security event logging
WHATSAPP_SECURITY_RATE_LIMIT = 5     # Attempts per hour for unauthorized numbers
WHATSAPP_UNAUTHORIZED_RESPONSE_LIMIT = 3  # Response limit for unauthorized attempts
```