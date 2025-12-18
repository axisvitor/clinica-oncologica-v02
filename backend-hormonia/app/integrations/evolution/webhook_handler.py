"""
Webhook validation and event parsing functionality.
"""

import hashlib
import hmac
from typing import Dict, Optional, Any

import structlog

from .models import WebhookEvent, EvolutionAPIError

logger = structlog.get_logger(__name__)


class WebhookHandler:
    """Handles webhook validation and event parsing."""

    def __init__(
        self,
        webhook_secret: Optional[str] = None,
        api_key: Optional[str] = None,
        instance_name: str = "hormonia",
        environment: str = "development",
    ):
        """
        Initialize webhook handler.

        Args:
            webhook_secret: Secret for webhook validation
            api_key: API key (fallback for validation)
            instance_name: Default instance name
            environment: Environment mode (production/development)
        """
        self.webhook_secret = webhook_secret
        self.api_key = api_key
        self.instance_name = instance_name
        self.environment = environment

    def validate_signature(
        self, payload: bytes, signature: str, secret: Optional[str] = None
    ) -> bool:
        """
        Validate webhook signature for security. ALWAYS required in production.

        Args:
            payload: Raw webhook payload
            signature: Signature from webhook headers (X-Signature or similar)
            secret: Webhook secret (defaults to webhook secret or API key)

        Returns:
            True if signature is valid

        Raises:
            ValueError: If webhook secret is not configured in production
        """
        validation_secret = secret or self.webhook_secret or self.api_key

        if not validation_secret:
            if self.environment == "production":
                logger.error(
                    "SECURITY CRITICAL: Webhook secret not configured in production!",
                    environment=self.environment,
                    has_api_key=bool(self.api_key),
                    has_webhook_secret=bool(self.webhook_secret),
                )
                return False
            else:
                logger.warning(
                    "SECURITY WARNING: Webhook validation disabled in development",
                    environment=self.environment,
                    has_api_key=bool(self.api_key),
                    has_webhook_secret=bool(self.webhook_secret),
                )
                return True  # Allow ONLY in development

        try:
            # Remove common prefixes
            clean_signature = signature
            for prefix in ["sha256=", "sha1=", "hmac-sha256="]:
                if signature.startswith(prefix):
                    clean_signature = signature[len(prefix) :]
                    break

            # Calculate expected signature (try multiple hash algorithms)
            expected_sha256 = hmac.new(
                validation_secret.encode("utf-8"), payload, hashlib.sha256
            ).hexdigest()

            expected_sha1 = hmac.new(
                validation_secret.encode("utf-8"), payload, hashlib.sha1
            ).hexdigest()

            # Secure comparison with multiple algorithms
            is_valid = hmac.compare_digest(
                clean_signature, expected_sha256
            ) or hmac.compare_digest(clean_signature, expected_sha1)

            logger.info(
                "Webhook signature validation",
                is_valid=is_valid,
                signature_length=len(clean_signature),
                payload_length=len(payload),
            )

            return is_valid

        except Exception as e:
            logger.error(
                "Webhook signature validation error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    def parse_event(self, payload: Dict[str, Any]) -> WebhookEvent:
        """
        Parse webhook event payload with comprehensive validation.

        Args:
            payload: Raw webhook payload from Evolution API

        Returns:
            Parsed webhook event
        """
        try:
            # Log incoming webhook for debugging
            logger.info(
                "Parsing webhook event",
                event_type=payload.get("event"),
                instance=payload.get("instance"),
                has_data=bool(payload.get("data")),
                payload_keys=list(payload.keys()),
            )

            # Handle Evolution API webhook format variations
            if "event" not in payload:
                # Try to infer event type from data structure
                if "message" in payload.get("data", {}):
                    payload["event"] = "message.received"
                elif "status" in payload.get("data", {}):
                    payload["event"] = "message.status"
                else:
                    payload["event"] = "unknown"

            if "instance" not in payload:
                payload["instance"] = self.instance_name

            return WebhookEvent(**payload)

        except Exception as e:
            logger.error(
                "Failed to parse webhook event",
                error=str(e),
                payload_preview=str(payload)[:200] if payload else None,
                error_type=type(e).__name__,
            )
            raise EvolutionAPIError(f"Invalid webhook payload: {e}")
