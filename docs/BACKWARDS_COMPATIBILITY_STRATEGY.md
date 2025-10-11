# Backwards Compatibility Strategy

## Overview
Comprehensive strategy for implementing strict patient-only WhatsApp access while maintaining full backwards compatibility with existing functionality and ensuring zero-downtime deployment.

## Current System Analysis

### Existing Functionality to Preserve:
1. **Rate Limiting** - Recent improvements to unauthorized attempt limiting (5 per hour)
2. **Unauthorized Responses** - Portuguese message to non-registered numbers
3. **Webhook Processing** - All existing webhook event handling
4. **Message Flow** - Complete patient message processing pipeline
5. **Database Schema** - All existing table structures and relationships
6. **API Endpoints** - All current webhook and API endpoints
7. **Configuration** - Existing environment variable structure

### Integration Points Identified:
- **WebhookProcessor** (recently enhanced with rate limiting)
- **Evolution API Client** (recently improved rate limiting logic)
- **Patient Service** (existing patient lookup and validation)
- **Message Service** (existing message creation and processing)

## Compatibility Strategy

### 1. Feature Flag Architecture

```python
# File: app/config/security_flags.py
"""
Feature flags for gradual security rollout.
"""
from typing import Dict, Any
from app.config import settings

class SecurityFeatureFlags:
    """Feature flags for security enhancements."""

    def __init__(self):
        self.flags = {
            # Core security features
            'PATIENT_AUTHORIZATION_MIDDLEWARE': getattr(settings, 'SECURITY_PATIENT_AUTH_MIDDLEWARE', False),
            'STRICT_PATIENT_MODE': getattr(settings, 'SECURITY_STRICT_PATIENT_MODE', False),
            'ENHANCED_WEBHOOK_PROCESSOR': getattr(settings, 'SECURITY_ENHANCED_WEBHOOK', False),

            # Security logging and monitoring
            'SECURITY_EVENT_LOGGING': getattr(settings, 'SECURITY_EVENT_LOGGING', True),
            'SECURITY_REAL_TIME_ALERTS': getattr(settings, 'SECURITY_REAL_TIME_ALERTS', False),
            'SECURITY_DASHBOARD': getattr(settings, 'SECURITY_DASHBOARD', False),

            # Onboarding features
            'PRE_AUTHORIZATION_SYSTEM': getattr(settings, 'SECURITY_PRE_AUTH_SYSTEM', False),
            'ONBOARDING_SESSIONS': getattr(settings, 'SECURITY_ONBOARDING_SESSIONS', False),

            # Compatibility modes
            'MAINTAIN_RATE_LIMITING': getattr(settings, 'SECURITY_MAINTAIN_RATE_LIMITING', True),
            'MAINTAIN_UNAUTHORIZED_RESPONSES': getattr(settings, 'SECURITY_MAINTAIN_UNAUTHORIZED_RESPONSES', True),
            'LEGACY_WEBHOOK_PROCESSING': getattr(settings, 'SECURITY_LEGACY_WEBHOOK_PROCESSING', True),
        }

    def is_enabled(self, flag: str) -> bool:
        """Check if a security feature flag is enabled."""
        return self.flags.get(flag, False)

    def get_security_mode(self) -> str:
        """Get current security mode."""
        if self.is_enabled('STRICT_PATIENT_MODE'):
            return 'strict'
        elif self.is_enabled('PATIENT_AUTHORIZATION_MIDDLEWARE'):
            return 'enforced'
        elif self.is_enabled('SECURITY_EVENT_LOGGING'):
            return 'monitoring'
        else:
            return 'legacy'

# Global instance
security_flags = SecurityFeatureFlags()
```

### 2. Backwards Compatible Webhook Processor

```python
# File: app/services/backwards_compatible_webhook_processor.py
"""
Backwards compatible webhook processor with gradual security enhancement.

Maintains 100% compatibility with existing functionality while adding
optional security layers based on feature flags.
"""
import logging
from typing import Any, Optional, Dict
from uuid import UUID

from app.services.webhook_processor import WebhookProcessor
from app.config.security_flags import security_flags
from app.services.patient_phone_security import PhoneNumberSecurityService
from app.services.whatsapp_security_audit import WhatsAppSecurityAuditService

logger = logging.getLogger(__name__)

class BackwardsCompatibleWebhookProcessor(WebhookProcessor):
    """
    Webhook processor that maintains backwards compatibility while
    gradually introducing security enhancements.

    Security is added as optional layers that can be enabled/disabled
    without affecting existing functionality.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize security services only if needed
        self.phone_security = None
        self.security_audit = None

        if security_flags.is_enabled('SECURITY_EVENT_LOGGING'):
            self.security_audit = WhatsAppSecurityAuditService(self.db)

        if security_flags.is_enabled('PATIENT_AUTHORIZATION_MIDDLEWARE'):
            self.phone_security = PhoneNumberSecurityService(self.db)

        # Log compatibility mode
        security_mode = security_flags.get_security_mode()
        logger.info(f"Webhook processor initialized in {security_mode} mode")

    async def process_message_webhook(self, event_data: dict[str, Any]) -> Optional[str]:
        """
        Process message webhook with optional security enhancements.

        Maintains exact compatibility with existing logic while optionally
        adding security layers based on feature flags.
        """
        # If legacy mode, use original logic
        if security_flags.is_enabled('LEGACY_WEBHOOK_PROCESSING'):
            return await self._process_legacy_webhook(event_data)

        # Enhanced processing with backwards compatibility
        return await self._process_enhanced_webhook(event_data)

    async def _process_legacy_webhook(self, event_data: dict[str, Any]) -> Optional[str]:
        """
        Process webhook using original logic (exact compatibility).

        This method preserves the exact original webhook processing logic
        including recent improvements (rate limiting, unauthorized responses).
        """
        # Call parent implementation with security logging overlay
        webhook_id = None
        result = None

        try:
            # Optional security logging (non-intrusive)
            if self.security_audit:
                webhook_id = await self._log_webhook_received(event_data)

            # Use original processing logic
            result = await super().process_message_webhook(event_data)

            # Optional security success logging
            if self.security_audit and result:
                await self._log_webhook_success(webhook_id, result, event_data)

            return result

        except Exception as e:
            # Optional security error logging
            if self.security_audit and webhook_id:
                await self._log_webhook_error(webhook_id, str(e), event_data)
            raise

    async def _process_enhanced_webhook(self, event_data: dict[str, Any]) -> Optional[str]:
        """
        Process webhook with enhanced security (gradual rollout).

        Adds security validation while maintaining compatibility with
        existing rate limiting and response logic.
        """
        webhook_id = None
        try:
            # Step 0: Security logging (always enabled if available)
            if self.security_audit:
                webhook_id = await self._log_webhook_received(event_data)

            # Step 1: Extract message data (original logic)
            message_data = self._extract_message_data(event_data)
            if not message_data:
                logger.warning("No valid message data found in webhook")
                if webhook_id:
                    await self._mark_webhook_processed(webhook_id, False, "No valid message data")
                return None

            whatsapp_id = message_data["whatsapp_id"]

            # Step 2: Enhanced or original patient lookup
            if security_flags.is_enabled('PATIENT_AUTHORIZATION_MIDDLEWARE'):
                # Enhanced security validation
                security_result = await self._enhanced_patient_lookup(message_data, webhook_id)

                if not security_result["authorized"]:
                    return await self._handle_unauthorized_with_compatibility(
                        security_result, message_data, webhook_id
                    )

                patient = security_result["patient"]
            else:
                # Original patient lookup (maintains existing logic)
                patient = self._find_patient_by_phone(message_data["phone"])

                if not patient:
                    # Use existing unauthorized handling
                    return await self._handle_original_unauthorized(message_data, webhook_id)

            # Step 3: Continue with original processing
            return await self._continue_original_processing(
                patient, message_data, whatsapp_id, webhook_id
            )

        except Exception as e:
            logger.error(f"Error in enhanced webhook processing: {e}", exc_info=True)
            if webhook_id:
                await self._mark_webhook_processed(webhook_id, False, str(e))
            return None

    async def _enhanced_patient_lookup(
        self,
        message_data: dict,
        webhook_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Enhanced patient lookup with security validation."""

        try:
            # Normalize phone securely
            normalized_phone = self.phone_security.normalize_phone_secure(message_data["phone"])

            # Get authorized patient
            patient = await self.phone_security.get_authorized_patient(normalized_phone)

            if patient:
                # Success - log if security logging enabled
                if self.security_audit:
                    await self.security_audit.log_authorization_event(
                        phone_number=normalized_phone,
                        patient_id=patient.id,
                        event_type="AUTHORIZED",
                        webhook_path="/webhooks/evolution/message",
                        metadata={
                            "patient_name": patient.name,
                            "webhook_id": str(webhook_id) if webhook_id else None,
                            "security_mode": security_flags.get_security_mode()
                        }
                    )

                return {
                    "authorized": True,
                    "patient": patient,
                    "normalized_phone": normalized_phone,
                    "security_enhanced": True
                }
            else:
                # Unauthorized - log if security logging enabled
                if self.security_audit:
                    await self.security_audit.log_authorization_event(
                        phone_number=normalized_phone,
                        patient_id=None,
                        event_type="UNAUTHORIZED_PHONE",
                        webhook_path="/webhooks/evolution/message",
                        metadata={
                            "webhook_id": str(webhook_id) if webhook_id else None,
                            "security_mode": security_flags.get_security_mode(),
                            "original_phone": message_data["phone"]
                        }
                    )

                return {
                    "authorized": False,
                    "patient": None,
                    "normalized_phone": normalized_phone,
                    "block_reason": f"Phone {normalized_phone} not registered",
                    "security_enhanced": True
                }

        except Exception as e:
            logger.error(f"Enhanced patient lookup error: {e}")
            # Fallback to original logic on error
            patient = self._find_patient_by_phone(message_data["phone"])
            return {
                "authorized": bool(patient),
                "patient": patient,
                "normalized_phone": message_data["phone"],
                "security_enhanced": False,
                "fallback_used": True
            }

    async def _handle_unauthorized_with_compatibility(
        self,
        security_result: Dict[str, Any],
        message_data: dict,
        webhook_id: Optional[UUID]
    ) -> None:
        """
        Handle unauthorized access with backwards compatibility.

        Maintains existing rate limiting and response behavior while
        adding optional enhanced security.
        """
        phone = security_result["normalized_phone"]

        # Use existing rate limiting logic (maintains compatibility)
        if security_flags.is_enabled('MAINTAIN_RATE_LIMITING'):
            redis_client = await get_async_redis()
            rate_limit_key = f"unauthorized:ratelimit:{phone}"
            attempt_count = await redis_client.incr(rate_limit_key)
            if attempt_count == 1:
                await redis_client.expire(rate_limit_key, 3600)  # 1 hour

            # Send response using existing logic if enabled
            if (security_flags.is_enabled('MAINTAIN_UNAUTHORIZED_RESPONSES') and
                attempt_count <= 3):
                await self._send_unauthorized_response(phone)

        # Enhanced security actions (optional)
        if security_flags.is_enabled('STRICT_PATIENT_MODE'):
            # In strict mode, additional blocking measures could be added here
            logger.warning(f"STRICT MODE: Blocking unauthorized phone {phone}")

        # Mark webhook as processed (existing logic)
        if webhook_id:
            await self._mark_webhook_processed(
                webhook_id, False,
                f"Unauthorized: {security_result.get('block_reason', 'No patient found')}"
            )

        return None

    async def _handle_original_unauthorized(
        self,
        message_data: dict,
        webhook_id: Optional[UUID]
    ) -> None:
        """
        Handle unauthorized using original logic (exact compatibility).

        This preserves the recent improvements to the original webhook processor
        including rate limiting and unauthorized responses.
        """
        phone = message_data["phone"]

        logger.warning(f"Patient not found for phone: {phone}")

        # Use existing rate limiting logic (recent improvement)
        redis_client = await get_async_redis()
        rate_limit_key = f"unauthorized:ratelimit:{phone}"
        attempt_count = await redis_client.incr(rate_limit_key)
        if attempt_count == 1:
            await redis_client.expire(rate_limit_key, 3600)  # 1 hour

        # Send response for first 3 attempts (existing logic)
        if attempt_count <= 3:
            await self._send_unauthorized_response(phone)

        # Mark webhook as processed with failure (existing logic)
        if webhook_id:
            await self._mark_webhook_processed(
                webhook_id, False,
                f"Unauthorized: patient not found (attempt {attempt_count})"
            )

        return None

    async def _continue_original_processing(
        self,
        patient,
        message_data: dict,
        whatsapp_id: str,
        webhook_id: Optional[UUID]
    ) -> str:
        """
        Continue with original message processing logic.

        This maintains 100% compatibility with existing message processing
        while allowing optional security enhancements.
        """
        # Use existing idempotency check
        redis_client = await get_async_redis()
        idempotency_key = f"webhook:message:{whatsapp_id}"

        is_duplicate = await redis_client.exists(idempotency_key)
        if is_duplicate:
            logger.info(f"Duplicate webhook message detected (Redis): {whatsapp_id}")
            existing_id = await redis_client.get(idempotency_key)
            return existing_id.decode() if existing_id else None

        # Check database for existing message
        existing_message = self.db.query(Message).filter(
            Message.whatsapp_id == whatsapp_id
        ).first()

        if existing_message:
            logger.info(f"Duplicate webhook message detected (DB): {whatsapp_id}")
            await redis_client.setex(idempotency_key, 3600, str(existing_message.id))
            return str(existing_message.id)

        # Continue with existing message processing
        active_flow = self.flow_state_repo.get_active_flow(patient.id)
        metadata = message_data.get("metadata", {})

        # Add security metadata if enhanced mode
        if security_flags.is_enabled('SECURITY_EVENT_LOGGING'):
            metadata.update({
                "security_validated": True,
                "security_mode": security_flags.get_security_mode()
            })

        # Rest of processing follows original logic exactly
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

        # Create message (original logic)
        message = self.message_service.process_inbound_message(
            patient_id=patient.id,
            content=message_data["content"],
            whatsapp_id=whatsapp_id,
            message_type=message_data["type"],
            message_metadata=metadata,
        )

        # Cache for idempotency (original logic)
        await redis_client.setex(idempotency_key, 3600, str(message.id))

        logger.info(
            f"Processed message {message.id} from patient {patient.id} "
            f"(context: {metadata['context']})"
        )

        # Publish WebSocket event (original logic)
        await self._publish_message_event(message, patient.id)

        # Route to handler (original logic)
        if active_flow:
            await self._handle_flow_message(patient, message, active_flow)
        else:
            await self._handle_general_chat(patient, message)

        # Mark webhook processed (original logic)
        if webhook_id:
            await self._mark_webhook_processed(webhook_id, True)

        return str(message.id)

    # Security logging methods (non-intrusive)
    async def _log_webhook_received(self, event_data: dict) -> Optional[UUID]:
        """Log webhook received (optional security logging)."""
        if not self.security_audit:
            return None

        try:
            # Extract phone for logging
            phone = None
            data = event_data.get("data", {})
            key = data.get("key", {})
            remote_jid = key.get("remoteJid", "")
            if "@" in remote_jid:
                phone = remote_jid.split("@")[0]

            # Log webhook received
            return await self.security_audit.log_authorization_event(
                phone_number=phone or "unknown",
                patient_id=None,
                event_type="WEBHOOK_RECEIVED",
                webhook_path="/webhooks/evolution/message",
                metadata={
                    "event_data_keys": list(event_data.keys()),
                    "security_mode": security_flags.get_security_mode()
                }
            )
        except Exception as e:
            logger.error(f"Error logging webhook received: {e}")
            return None

    async def _log_webhook_success(
        self,
        webhook_id: Optional[UUID],
        message_id: str,
        event_data: dict
    ) -> None:
        """Log successful webhook processing."""
        if not self.security_audit or not webhook_id:
            return

        try:
            await self.security_audit.log_authorization_event(
                phone_number="logged",  # Already logged in main event
                patient_id=None,
                event_type="WEBHOOK_SUCCESS",
                webhook_path="/webhooks/evolution/message",
                metadata={
                    "message_id": message_id,
                    "webhook_id": str(webhook_id)
                }
            )
        except Exception as e:
            logger.error(f"Error logging webhook success: {e}")

    async def _log_webhook_error(
        self,
        webhook_id: Optional[UUID],
        error: str,
        event_data: dict
    ) -> None:
        """Log webhook processing error."""
        if not self.security_audit or not webhook_id:
            return

        try:
            await self.security_audit.log_authorization_event(
                phone_number="error",
                patient_id=None,
                event_type="WEBHOOK_ERROR",
                webhook_path="/webhooks/evolution/message",
                metadata={
                    "error": error,
                    "webhook_id": str(webhook_id)
                }
            )
        except Exception as e:
            logger.error(f"Error logging webhook error: {e}")
```

### 3. Gradual Rollout Plan

```python
# File: app/config/rollout_phases.py
"""
Gradual rollout phases for security enhancements.
"""

ROLLOUT_PHASES = {
    "phase_0_baseline": {
        "description": "Current system (no changes)",
        "flags": {
            'LEGACY_WEBHOOK_PROCESSING': True,
            'MAINTAIN_RATE_LIMITING': True,
            'MAINTAIN_UNAUTHORIZED_RESPONSES': True,
        },
        "duration": "Already deployed"
    },

    "phase_1_monitoring": {
        "description": "Add security logging and monitoring",
        "flags": {
            'SECURITY_EVENT_LOGGING': True,
            'LEGACY_WEBHOOK_PROCESSING': True,
            'MAINTAIN_RATE_LIMITING': True,
            'MAINTAIN_UNAUTHORIZED_RESPONSES': True,
        },
        "duration": "1 week",
        "validation": [
            "Security events are logged correctly",
            "No performance impact",
            "All existing functionality works"
        ]
    },

    "phase_2_enhanced_validation": {
        "description": "Enhanced phone validation with fallback",
        "flags": {
            'SECURITY_EVENT_LOGGING': True,
            'PATIENT_AUTHORIZATION_MIDDLEWARE': True,
            'MAINTAIN_RATE_LIMITING': True,
            'MAINTAIN_UNAUTHORIZED_RESPONSES': True,
        },
        "duration": "1 week",
        "validation": [
            "Enhanced validation works correctly",
            "Fallback to original logic on errors",
            "No blocked legitimate patients"
        ]
    },

    "phase_3_strict_monitoring": {
        "description": "Strict mode monitoring (log only, don't block)",
        "flags": {
            'SECURITY_EVENT_LOGGING': True,
            'PATIENT_AUTHORIZATION_MIDDLEWARE': True,
            'ENHANCED_WEBHOOK_PROCESSOR': True,
            'MAINTAIN_RATE_LIMITING': True,
            'MAINTAIN_UNAUTHORIZED_RESPONSES': True,
        },
        "duration": "1 week",
        "validation": [
            "Enhanced processor works correctly",
            "Security monitoring is effective",
            "Ready for strict enforcement"
        ]
    },

    "phase_4_strict_enforcement": {
        "description": "Full strict patient-only mode",
        "flags": {
            'SECURITY_EVENT_LOGGING': True,
            'PATIENT_AUTHORIZATION_MIDDLEWARE': True,
            'ENHANCED_WEBHOOK_PROCESSOR': True,
            'STRICT_PATIENT_MODE': True,
            'SECURITY_REAL_TIME_ALERTS': True,
        },
        "duration": "Ongoing",
        "validation": [
            "Only registered patients can access WhatsApp",
            "Unauthorized access is blocked",
            "Security alerts work correctly"
        ]
    },

    "phase_5_advanced_features": {
        "description": "Advanced security features and onboarding",
        "flags": {
            'SECURITY_EVENT_LOGGING': True,
            'PATIENT_AUTHORIZATION_MIDDLEWARE': True,
            'ENHANCED_WEBHOOK_PROCESSOR': True,
            'STRICT_PATIENT_MODE': True,
            'SECURITY_REAL_TIME_ALERTS': True,
            'PRE_AUTHORIZATION_SYSTEM': True,
            'ONBOARDING_SESSIONS': True,
            'SECURITY_DASHBOARD': True,
        },
        "duration": "Future enhancement",
        "validation": [
            "Pre-authorization system works",
            "Onboarding flow is secure",
            "Security dashboard is functional"
        ]
    }
}
```

## Migration Strategy

### Database Migration Approach:
1. **Add Security Tables** - New tables for security events (non-breaking)
2. **Extend Existing Tables** - Add optional security columns
3. **Maintain Indexes** - Ensure query performance remains optimal
4. **Data Migration** - Migrate existing data to new security structure

### Configuration Migration:
```bash
# Environment variable mapping for backwards compatibility

# Phase 1: Monitoring
SECURITY_EVENT_LOGGING=true
LEGACY_WEBHOOK_PROCESSING=true

# Phase 2: Enhanced validation
SECURITY_PATIENT_AUTH_MIDDLEWARE=true

# Phase 3: Strict monitoring
SECURITY_ENHANCED_WEBHOOK=true

# Phase 4: Strict enforcement
SECURITY_STRICT_PATIENT_MODE=true
SECURITY_REAL_TIME_ALERTS=true

# Phase 5: Advanced features
SECURITY_PRE_AUTH_SYSTEM=true
SECURITY_ONBOARDING_SESSIONS=true
SECURITY_DASHBOARD=true
```

### Rollback Strategy:
1. **Immediate Rollback** - Disable feature flags to return to previous phase
2. **Database Rollback** - Security tables are additive, original tables unchanged
3. **Configuration Rollback** - Simple environment variable changes
4. **Code Rollback** - Original webhook processor remains available

## Testing Strategy for Compatibility

### 1. Regression Testing:
- All existing webhook endpoints work correctly
- Patient message processing unchanged
- Rate limiting behavior preserved
- Unauthorized response messages maintained

### 2. Performance Testing:
- No performance degradation in webhook processing
- Database query performance maintained
- Memory usage within acceptable limits

### 3. Security Testing:
- Security enhancements work as expected
- No security bypasses introduced
- Logging and monitoring function correctly

### 4. Integration Testing:
- Evolution API integration unchanged
- WebSocket events continue working
- Dashboard functionality preserved

## Risk Mitigation

### High-Risk Areas:
1. **Webhook Processing** - Critical path for all WhatsApp communication
2. **Patient Lookup** - Core business logic for patient identification
3. **Database Performance** - Additional security queries could impact performance

### Mitigation Strategies:
1. **Feature Flags** - Instant rollback capability
2. **Fallback Logic** - Original processing available on errors
3. **Gradual Rollout** - Phase-by-phase deployment with validation
4. **Monitoring** - Real-time performance and error monitoring
5. **Testing** - Comprehensive regression and integration testing