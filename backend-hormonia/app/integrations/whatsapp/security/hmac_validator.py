"""
HMAC signature validation for WhatsApp webhooks.
"""

import hashlib
import hmac
import logging
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class WebhookHMACValidator:
    """Validate webhook HMAC signatures for multiple algorithms."""

    _ALGORITHMS = {
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
    }

    @classmethod
    def _parse_signature(cls, signature: str) -> Tuple[str, str]:
        """Parse signature header value into algorithm and digest."""
        signature = signature.strip()
        if "=" in signature:
            algorithm, digest = signature.split("=", 1)
            return algorithm.strip().lower(), digest.strip()
        if len(signature) == 128:
            return "sha512", signature
        return "sha256", signature

    @classmethod
    def validate_timestamp(
        cls,
        timestamp: Optional[str],
        *,
        required: bool,
        max_age_seconds: int,
        now_seconds: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Validate an optional webhook timestamp for replay protection.

        Returns ``(True, reason)`` for accepted timestamps and ``(False, reason)``
        for fail-closed denial reasons. If timestamps are not required and the
        provider did not send one, validation is intentionally skipped.
        """
        if not timestamp:
            if required:
                logger.warning("Webhook timestamp missing")
                return False, "missing_timestamp"
            return True, "timestamp_not_required"

        try:
            timestamp_seconds = int(str(timestamp).strip())
        except (TypeError, ValueError):
            logger.warning("Webhook timestamp malformed")
            return False, "malformed_timestamp"

        if max_age_seconds < 0:
            logger.warning("Webhook timestamp max age misconfigured")
            return False, "timestamp_config_invalid"

        current_seconds = int(now_seconds if now_seconds is not None else time.time())
        if abs(current_seconds - timestamp_seconds) > max_age_seconds:
            logger.warning("Webhook timestamp stale")
            return False, "stale_timestamp"

        return True, "timestamp_valid"

    @classmethod
    def validate_signature(cls, payload: bytes, signature: str, secret: str) -> bool:
        """
        Validate HMAC signature for payload.

        Supports signature formats:
        - sha256=<hex>
        - sha512=<hex>
        - <hex> (defaults to sha256, or sha512 if length is 128)
        """
        if not secret:
            logger.warning("Webhook HMAC secret missing")
            return False

        if not signature:
            logger.warning("Webhook HMAC signature missing")
            return False

        try:
            algorithm, digest = cls._parse_signature(signature)
            if algorithm not in cls._ALGORITHMS:
                logger.warning(
                    "Unsupported webhook HMAC algorithm",
                    extra={"algorithm": algorithm},
                )
                return False

            computed = hmac.new(
                secret.encode("utf-8"), payload, cls._ALGORITHMS[algorithm]
            ).hexdigest()
            valid = hmac.compare_digest(computed, digest)
            if not valid:
                logger.warning(
                    "Webhook HMAC validation failed",
                    extra={
                        "algorithm": algorithm,
                        "signature_length": len(digest),
                    },
                )
            return valid
        except Exception as exc:
            logger.error(
                "Webhook HMAC validation error",
                exc_info=True,
                extra={"error": str(exc)},
            )
            return False
