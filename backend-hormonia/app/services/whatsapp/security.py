"""
Security module for WhatsApp webhook validation.
"""

import hmac
import hashlib
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.config import settings

logger = logging.getLogger(__name__)


class WhatsAppSecurity:
    """
    Handles security and validation for WhatsApp webhooks.
    """

    @staticmethod
    def validate_webhook_signature(
        webhook_data: Dict[str, Any],
        signature_header: Optional[str] = None,
        timestamp_header: Optional[str] = None,
        raw_payload: Optional[bytes] = None,
    ) -> bool:
        """
        Validate webhook signature for security using HMAC-SHA256.

        Args:
            webhook_data: Parsed webhook payload
            signature_header: X-Webhook-Signature or X-Hub-Signature-256 header
            timestamp_header: X-Webhook-Timestamp header
            raw_payload: Raw request body bytes

        Returns:
            True if signature is valid, False otherwise

        Security Features:
            - HMAC-SHA256 signature verification (prevents tampering)
            - Timestamp validation (prevents replay attacks - 5 min window)
            - Constant-time comparison (prevents timing attacks)
        """
        # If no secret configured, skip validation (development mode)
        webhook_secret = getattr(settings, "EVOLUTION_WEBHOOK_SECRET", None)
        if not webhook_secret:
            logger.warning(
                "SECURITY WARNING: EVOLUTION_WEBHOOK_SECRET not configured. "
                "Webhook signature validation is DISABLED. This is insecure for production!"
            )
            return True

        # Require signature header in production
        if not signature_header:
            logger.error("SECURITY: Missing webhook signature header")
            return False

        try:
            # Extract signature from header
            # Supports both formats: "sha256=<sig>" or just "<sig>"
            if "=" in signature_header:
                algorithm, signature = signature_header.split("=", 1)
                if algorithm not in ("sha256", "hmac-sha256"):
                    logger.error(f"SECURITY: Invalid signature algorithm: {algorithm}")
                    return False
            else:
                signature = signature_header

            # Validate timestamp if provided (replay attack prevention)
            if timestamp_header:
                try:
                    webhook_time = int(timestamp_header)
                    current_time = int(datetime.now(timezone.utc).timestamp())
                    time_diff = abs(current_time - webhook_time)

                    # Reject webhooks older than 5 minutes
                    if time_diff > 300:  # 5 minutes
                        logger.error(
                            f"SECURITY: Webhook timestamp expired. Age: {time_diff}s (max: 300s)"
                        )
                        return False

                    logger.debug(f"Webhook timestamp validated (age: {time_diff}s)")

                except (ValueError, TypeError):
                    logger.error(
                        f"SECURITY: Invalid webhook timestamp: {timestamp_header}"
                    )
                    return False

            # Prepare payload for signature computation
            if raw_payload:
                # Use raw bytes if provided
                payload_bytes = raw_payload
            else:
                # Fallback to JSON encoding of webhook_data
                import json

                payload_bytes = json.dumps(webhook_data, sort_keys=True).encode("utf-8")

            # Compute expected signature with timestamp if available
            if timestamp_header:
                signature_payload = (
                    f"{timestamp_header}.{payload_bytes.decode('utf-8')}"
                )
                signature_bytes = signature_payload.encode("utf-8")
            else:
                signature_bytes = payload_bytes

            expected_signature = hmac.new(
                webhook_secret.encode("utf-8"), signature_bytes, hashlib.sha256
            ).hexdigest()

            # Constant-time comparison (timing attack prevention)
            is_valid = hmac.compare_digest(signature, expected_signature)

            if not is_valid:
                logger.error(
                    "SECURITY: Webhook signature validation FAILED",
                    extra={
                        "expected_prefix": expected_signature[:16],
                        "received_prefix": signature[:16],
                        "timestamp": timestamp_header,
                        "payload_size": len(payload_bytes),
                    },
                )
            else:
                logger.debug("Webhook signature validated successfully")

            return is_valid

        except Exception as e:
            logger.error(
                f"SECURITY: Exception during webhook signature validation: {e}",
                exc_info=True,
            )
            # Fail secure: reject webhook on validation errors
            return False
